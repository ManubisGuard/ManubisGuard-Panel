import asyncio

from sqlalchemy import text

from app.db import base
from app.utils.crypto import generate_wireguard_keypair
from tests.api import TestSession, app, client, get_test_db
from tests.api.helpers import (
    create_core,
    create_group,
    create_user,
    delete_core,
    delete_group,
    delete_user,
    unique_name,
)


def test_api_dependency_uses_test_database():
    assert app.dependency_overrides[base.get_db] is get_test_db

    async def inspect_test_database():
        async with TestSession() as session:
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
            assert (await session.execute(text("SELECT COUNT(*) FROM jwt"))).scalar_one() >= 1

    asyncio.run(inspect_test_database())


def test_jwt_endpoint_uses_test_database():
    response = client.post(
        "/api/admin/token",
        data={"username": "testadmin", "password": "testadmin", "grant_type": "password"},
    )
    assert response.status_code != 503, response.text
    assert response.status_code == 200, response.text
    assert response.json().get("access_token")


def test_amneziawg_users_receive_unique_peer_ips(access_token):
    private_key, _ = generate_wireguard_keypair()
    core = create_core(
        access_token,
        name=unique_name("awg_pool_core"),
        type="amneziawg",
        config={
            "interface_name": unique_name("awg"),
            "private_key": private_key,
            "listen_port": 51820,
            "address": ["172.31.88.1/24"],
            "jc": 3,
            "jmin": 64,
            "jmax": 128,
            "s1": 15,
            "s2": 64,
            "s3": 25,
            "s4": 8,
            "h1": "1851500115",
            "h2": "163827579",
            "h3": "775454101",
            "h4": "1260834266",
        },
        fallbacks=[],
    )
    group = create_group(
        access_token,
        name=unique_name("awg_pool_group"),
        inbound_tags=[core["config"]["interface_name"]],
    )

    users = []
    try:
        user1 = create_user(access_token, username=unique_name("awg_pool_user1"), group_ids=[group["id"]])
        user2 = create_user(access_token, username=unique_name("awg_pool_user2"), group_ids=[group["id"]])
        users.extend([user1, user2])

        peer1 = user1["proxy_settings"]["wireguard"]["peer_ips"]
        peer2 = user2["proxy_settings"]["wireguard"]["peer_ips"]

        assert peer1 == ["172.31.88.2/32"]
        assert peer2 == ["172.31.88.3/32"]
        assert set(peer1).isdisjoint(peer2)

        delete_user(access_token, user1["username"])
        users.remove(user1)

        user3 = create_user(access_token, username=unique_name("awg_pool_user3"), group_ids=[group["id"]])
        users.append(user3)

        assert user3["proxy_settings"]["wireguard"]["peer_ips"] == ["172.31.88.2/32"]
    finally:
        for user in users:
            delete_user(access_token, user["username"])
        delete_group(access_token, group["id"])
        delete_core(access_token, core["id"])


def test_wireguard_and_amneziawg_share_subnet_pool_without_collisions(access_token):
    wg_key, _ = generate_wireguard_keypair()
    awg_key, _ = generate_wireguard_keypair()
    subnet = "172.31.90.1/29"
    wg = create_core(
        access_token,
        name=unique_name("wg_mixed_core"),
        type="wg",
        config={
            "interface_name": unique_name("wg_mixed"),
            "private_key": wg_key,
            "listen_port": 51821,
            "address": [subnet],
        },
        fallbacks=[],
    )
    awg = create_core(
        access_token,
        name=unique_name("awg_mixed_core"),
        type="amneziawg",
        config={
            "interface_name": unique_name("awg_mixed"),
            "private_key": awg_key,
            "listen_port": 51822,
            "address": [subnet],
            "jc": 3,
            "jmin": 64,
            "jmax": 128,
            "s1": 15,
            "s2": 64,
            "s3": 25,
            "s4": 8,
            "h1": "1851500115",
            "h2": "163827579",
            "h3": "775454101",
            "h4": "1260834266",
        },
        fallbacks=[],
    )
    group = create_group(
        access_token,
        name=unique_name("mixed_pool_group"),
        inbound_tags=[wg["config"]["interface_name"], awg["config"]["interface_name"]],
    )
    users = []
    try:
        users.append(create_user(access_token, username=unique_name("mixed_wg_user"), group_ids=[group["id"]]))
        users.append(create_user(access_token, username=unique_name("mixed_awg_user"), group_ids=[group["id"]]))
        peer_ips = [user["proxy_settings"]["wireguard"]["peer_ips"] for user in users]
        assert peer_ips == [["172.31.90.2/32"], ["172.31.90.3/32"]]
        assert peer_ips[0][0] != peer_ips[1][0]
    finally:
        for user in users:
            delete_user(access_token, user["username"])
        delete_group(access_token, group["id"])
        delete_core(access_token, awg["id"])
        delete_core(access_token, wg["id"])
