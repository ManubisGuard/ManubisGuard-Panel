import asyncio
import io
import zipfile
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from app.core.manager import core_manager
from app.db.models import CoreConfig
from app.subscription.config_cache import clear_sub_config_cache
from app.subscription.wireguard import WireGuardConfiguration
from app.utils.crypto import generate_wireguard_keypair
from tests.api import TestSession, client
from tests.api.helpers import (
    auth_headers,
    create_core,
    create_group,
    create_user,
    delete_core,
    delete_group,
    delete_user,
    unique_name,
)

AWG_FIELDS = ("jc", "jmin", "jmax", "s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4")


def _parse_conf(payload: bytes) -> tuple[dict[str, str], dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        assert len(names) == 1
        assert "/" not in names[0] and "\\" not in names[0]
        content = archive.read(names[0]).decode()
    sections: dict[str, dict[str, str]] = {"Interface": {}, "Peer": {}}
    section = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections.setdefault(section, {})
        elif section and "=" in line:
            key, value = line.split("=", 1)
            sections[section][key.strip()] = value.strip()
    return sections["Interface"], sections["Peer"]


def _query_from_links(response) -> dict[str, str]:
    assert response.status_code == 200, response.text
    links = [line for line in response.text.splitlines() if line.startswith("wireguard://")]
    assert len(links) == 1
    return {key: values[0] for key, values in parse_qs(urlsplit(links[0]).query).items()}


async def _persisted_core_config(core_id: int) -> dict:
    async with TestSession() as session:
        row = await session.execute(select(CoreConfig.config).where(CoreConfig.id == core_id))
        return dict(row.scalar_one())


def _make_awg(access_token: str, *, subnet: str = "172.31.60.1/24") -> tuple[dict, int, dict]:
    private_key, _ = generate_wireguard_keypair()
    interface_name = unique_name("awg_phase4")
    core = create_core(
        access_token,
        name=unique_name("awg_phase4_core"),
        type="amneziawg",
        fallbacks=[],
        config={
            "interface_name": interface_name,
            "private_key": private_key,
            "listen_port": 51820,
            "address": [subnet],
            # Deliberately partial: validation must persist the remaining AWG fields.
            "jc": 7,
            "s1": 19,
            "h1": "10101",
            "h2": "20202",
            "h3": "30303",
            "h4": "40404",
        },
    )
    host_response = client.post(
        "/api/host",
        headers=auth_headers(access_token),
        json={
            "remark": "Phase4 AWG {USERNAME}",
            "address": ["198.51.100.60"],
            "port": 51820,
            "inbound_tag": interface_name,
            "priority": 1,
            "wireguard_overrides": {"dns": ["1.1.1.1", "8.8.8.8"], "mtu": 1320},
        },
    )
    assert host_response.status_code == 201, host_response.text
    group = create_group(access_token, name=unique_name("awg_phase4_group"), inbound_tags=[interface_name])
    return core, host_response.json()["id"], group


def _cleanup_awg(access_token: str, core: dict, host_id: int, group: dict, users: list[dict]) -> None:
    for user in users:
        delete_user(access_token, user["username"])
    delete_group(access_token, group["id"])
    client.delete(f"/api/host/{host_id}", headers=auth_headers(access_token))
    delete_core(access_token, core["id"])
    clear_sub_config_cache()


def test_awg_subscription_matches_persisted_core_config(access_token):
    core, host_id, group = _make_awg(access_token)
    users = []
    try:
        user = create_user(access_token, username=unique_name("phase4_match"), group_ids=[group["id"]])
        users.append(user)
        persisted = asyncio.run(_persisted_core_config(core["id"]))
        query = _query_from_links(client.get(f"{user['subscription_url']}/links"))
        interface, peer = _parse_conf(client.get(f"{user['subscription_url']}/wireguard").content)

        for field in AWG_FIELDS:
            assert query[field] == str(persisted[field])
            assert interface[field.capitalize()] == str(persisted[field])
        assert peer["AllowedIPs"] == "0.0.0.0/0, ::/0"
        assert peer["PresharedKey"] == user["proxy_settings"]["wireguard"]["pre_shared_key"]
        assert interface["Address"] == user["proxy_settings"]["wireguard"]["peer_ips"][0]
    finally:
        _cleanup_awg(access_token, core, host_id, group, users)


def test_awg_subscription_is_stable_after_reload(access_token):
    core, host_id, group = _make_awg(access_token, subnet="172.31.61.1/24")
    users = []
    try:
        user = create_user(access_token, username=unique_name("phase4_reload"), group_ids=[group["id"]])
        users.append(user)
        clear_sub_config_cache()
        before = _query_from_links(client.get(f"{user['subscription_url']}/links"))

        async def reload_core_manager():
            async with TestSession() as session:
                await core_manager.initialize(session)

        asyncio.run(reload_core_manager())
        clear_sub_config_cache()
        after = _query_from_links(client.get(f"{user['subscription_url']}/links"))
        assert {field: before[field] for field in AWG_FIELDS} == {field: after[field] for field in AWG_FIELDS}
    finally:
        _cleanup_awg(access_token, core, host_id, group, users)


def test_awg_subscription_multiple_users(access_token):
    core, host_id, group = _make_awg(access_token, subnet="172.31.62.1/24")
    users = []
    try:
        for index in range(3):
            users.append(create_user(access_token, username=unique_name(f"phase4_user{index}"), group_ids=[group["id"]]))
        allocated = []
        for user in users:
            query = _query_from_links(client.get(f"{user['subscription_url']}/links"))
            allocated.append(query["address"])
            assert query["address"] == user["proxy_settings"]["wireguard"]["peer_ips"][0]
        assert len(set(allocated)) == 3
    finally:
        _cleanup_awg(access_token, core, host_id, group, users)


def test_awg_subscription_regeneration_is_deterministic(access_token):
    core, host_id, group = _make_awg(access_token, subnet="172.31.63.1/24")
    users = []
    try:
        user = create_user(access_token, username=unique_name("phase4_regen"), group_ids=[group["id"]])
        users.append(user)
        values = []
        for _ in range(3):
            clear_sub_config_cache()
            values.append(_query_from_links(client.get(f"{user['subscription_url']}/links")))
        assert [{field: value[field] for field in AWG_FIELDS} for value in values] == [
            {field: values[0][field] for field in AWG_FIELDS}
        ] * 3
    finally:
        _cleanup_awg(access_token, core, host_id, group, users)


def test_awg_uri_roundtrip_preserves_parameters(access_token):
    core, host_id, group = _make_awg(access_token, subnet="172.31.64.1/24")
    users = []
    try:
        user = create_user(access_token, username=unique_name("phase4_uri"), group_ids=[group["id"]])
        users.append(user)
        query = _query_from_links(client.get(f"{user['subscription_url']}/links"))
        persisted = asyncio.run(_persisted_core_config(core["id"]))
        assert {field: query[field] for field in AWG_FIELDS} == {field: str(persisted[field]) for field in AWG_FIELDS}
        assert query["presharedkey"] == user["proxy_settings"]["wireguard"]["pre_shared_key"]
    finally:
        _cleanup_awg(access_token, core, host_id, group, users)


def test_awg_zip_filename_is_safe():
    configuration = WireGuardConfiguration()
    configuration.configs = [("../evil.conf\\../../foo/bar", "[Interface]\nPrivateKey = key")]
    with zipfile.ZipFile(io.BytesIO(configuration.render())) as archive:
        names = archive.namelist()
    assert len(names) == 1
    assert names[0] == "evil.conf_____foo_bar.conf"
    assert not names[0].startswith(("/", ".."))


def test_awg_subscription_mixed_wireguard(access_token):
    wg_key, _ = generate_wireguard_keypair()
    wg_psk, _ = generate_wireguard_keypair()
    awg_key, _ = generate_wireguard_keypair()
    wg_name = unique_name("phase4_wg")
    awg_name = unique_name("phase4_awg")
    wg = create_core(
        access_token,
        type="wg",
        name=unique_name("phase4_wg_core"),
        fallbacks=[],
        config={
            "interface_name": wg_name,
            "private_key": wg_key,
            "pre_shared_key": wg_psk,
            "listen_port": 51821,
            "address": ["172.31.65.1/24"],
        },
    )
    awg = create_core(
        access_token,
        type="amneziawg",
        name=unique_name("phase4_awg_core"),
        fallbacks=[],
        config={"interface_name": awg_name, "private_key": awg_key, "listen_port": 51822, "address": ["172.31.66.1/24"]},
    )
    group_wg = create_group(access_token, name=unique_name("phase4_wg_group"), inbound_tags=[wg_name])
    group_awg = create_group(access_token, name=unique_name("phase4_awg_group"), inbound_tags=[awg_name])
    host_ids = []
    users = []
    try:
        for tag, port, remark, group in ((wg_name, 51821, "Phase4 WG", group_wg), (awg_name, 51822, "Phase4 AWG", group_awg)):
            response = client.post(
                "/api/host/",
                headers=auth_headers(access_token),
                json={"remark": remark, "address": ["198.51.100.65"], "port": port, "inbound_tag": tag, "priority": 1},
            )
            assert response.status_code == 201, response.text
            host_ids.append(response.json()["id"])
            users.append(create_user(access_token, username=unique_name(remark.lower().replace(" ", "_")), group_ids=[group["id"]]))

        wg_query = _query_from_links(client.get(f"{users[0]['subscription_url']}/links"))
        awg_query = _query_from_links(client.get(f"{users[1]['subscription_url']}/links"))
        assert "jc" not in wg_query and "h1" not in wg_query
        assert all(field in awg_query for field in AWG_FIELDS)
        assert wg_query["address"] != awg_query["address"]
        _, wg_peer = _parse_conf(client.get(f"{users[0]['subscription_url']}/wireguard").content)
        _, awg_peer = _parse_conf(client.get(f"{users[1]['subscription_url']}/wireguard").content)
        assert "PresharedKey" in wg_peer
        assert awg_peer["PresharedKey"] == users[1]["proxy_settings"]["wireguard"]["pre_shared_key"]
    finally:
        for user in users:
            delete_user(access_token, user["username"])
        delete_group(access_token, group_awg["id"])
        delete_group(access_token, group_wg["id"])
        for host_id in host_ids:
            client.delete(f"/api/host/{host_id}", headers=auth_headers(access_token))
        delete_core(access_token, awg["id"])
        delete_core(access_token, wg["id"])
        clear_sub_config_cache()
