from app.utils.crypto import generate_wireguard_keypair
from tests.api import client
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
            "address": ["10.88.0.1/24"],
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

        assert peer1 == ["10.88.0.2/32"]
        assert peer2 == ["10.88.0.3/32"]
        assert set(peer1).isdisjoint(peer2)

        delete_user(access_token, user1["username"])
        users.remove(user1)

        user3 = create_user(access_token, username=unique_name("awg_pool_user3"), group_ids=[group["id"]])
        users.append(user3)

        assert user3["proxy_settings"]["wireguard"]["peer_ips"] == ["10.88.0.2/32"]
    finally:
        for user in users:
            delete_user(access_token, user["username"])
        delete_group(access_token, group["id"])
        delete_core(access_token, core["id"])
