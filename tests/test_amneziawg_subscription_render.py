from app.models.subscription import SubscriptionInboundData, TCPTransportConfig, TLSConfig
from app.subscription.wireguard import WireGuardConfiguration


def test_amneziawg_native_config_contains_awg_parameters():
    inbound = SubscriptionInboundData(
        remark="WG",
        inbound_tag="WG_51820",
        protocol="amneziawg",
        address=["10.0.0.2/32"],
        port=[51820],
        network="udp",
        tls_config=TLSConfig(),
        transport_config=TCPTransportConfig(path="", host=[]),
        wireguard_public_key="SERVER_PUBLIC_KEY",
        wireguard_pre_shared_key="PSK",
        wireguard_allowed_ips=["0.0.0.0/0", "::/0"],
        wireguard_keepalive=25,
        wireguard_mtu=1320,
        wireguard_dns=["1.1.1.1", "1.0.0.1"],
        amneziawg=True,
        amneziawg_params={
            "jc": 3,
            "jmin": 20,
            "jmax": 50,
            "s1": 15,
            "s2": 64,
            "s3": 25,
            "s4": 8,
            "h1": "100",
            "h2": "200",
            "h3": "300",
            "h4": "400",
        },
    )

    config = WireGuardConfiguration()
    config.add("WG", "example.test", inbound, {"private_key": "CLIENT_PRIVATE_KEY", "peer_ips": ["10.0.0.2/32"]})
    rendered = config.configs[0][1]

    for field, value in (("Jc", 3), ("Jmin", 20), ("Jmax", 50), ("S1", 15), ("S2", 64), ("S3", 25), ("S4", 8)):
        assert f"{field} = {value}" in rendered
    for field, value in (("H1", "100"), ("H2", "200"), ("H3", "300"), ("H4", "400")):
        assert f"{field} = {value}" in rendered
