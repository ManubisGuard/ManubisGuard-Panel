import pytest

from app.core.amneziawg import AmneziaWGConfig


def _base_config() -> dict:
    return {
        "interface_name": "awg0",
        "private_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "listen_port": 51820,
        "address": ["10.0.0.1/24"],
    }


def test_amneziawg_config_sets_type_and_preserves_params():
    config = _base_config()
    config.update({"jc": 3, "jmin": 64, "jmax": 128, "s4": 8, "h1": "123-456", "i1": "<r 16>"})

    awg = AmneziaWGConfig(config)

    assert awg.type == "amneziawg"
    assert awg["amneziawg"] is True
    assert awg.inbounds_by_tag["awg0"]["protocol"] == "amneziawg"
    assert awg.inbounds_by_tag["awg0"]["amneziawg"]["jc"] == 3
    assert awg.inbounds_by_tag["awg0"]["amneziawg"]["i1"] == "<r 16>"


def test_amneziawg_config_accepts_values_beyond_legacy_panel_ranges():
    config = _base_config()
    config.update({
        "jc": 25,
        "jmin": 32,
        "jmax": 4096,
        "s1": 1024,
        "s2": 2048,
        "s3": 512,
        "s4": 256,
    })

    awg = AmneziaWGConfig(config)

    assert awg["jc"] == 25
    assert awg["jmin"] == 32
    assert awg["jmax"] == 4096
    assert awg["s1"] == 1024
    assert awg["s2"] == 2048
    assert awg["s3"] == 512
    assert awg["s4"] == 256


def test_amneziawg_rejects_jmin_greater_than_jmax():
    config = _base_config()
    config.update({"jmin": 128, "jmax": 64})

    with pytest.raises(ValueError):
        AmneziaWGConfig(config)


def test_amneziawg_allows_values_not_restricted_by_awgctrl_validation():
    config = _base_config()
    config.update({"s1": 0, "s2": 56, "s3": 1, "s4": 8})
    awg = AmneziaWGConfig(config)
    assert awg["s1"] == 0
    assert awg["s3"] == 1

    config = _base_config()
    config.update({"h1": "100-200", "h2": "200-300", "i1": "<r 16>"})
    awg = AmneziaWGConfig(config)
    assert awg["h1"] == "100-200"
    assert awg["h2"] == "200-300"
    assert awg["i1"] == "<r 16>"


def test_amneziawg_subscription_uses_canonical_key_names():
    from app.subscription.wireguard import WireGuardConfiguration

    renderer = WireGuardConfiguration()
    output = renderer._render_config(
        {
            "Interface": {
                "Jc": "3",
                "Jmin": "64",
                "Jmax": "128",
                "S1": "16",
                "H1": "123456-123999",
                "I1": "<r 16>",
            }
        }
    )

    assert "Jc = 3" in output
    assert "Jmin = 64" in output
    assert "Jmax = 128" in output
    assert "S1 = 16" in output
    assert "H1 = 123456-123999" in output
    assert "I1 = <r 16>" in output
    assert "JC =" not in output


def test_amneziawg_subscription_renders_interface_defaults_and_omits_psk():
    from app.models.subscription import SubscriptionInboundData, TCPTransportConfig, TLSConfig
    from app.subscription.wireguard import WireGuardConfiguration

    inbound = SubscriptionInboundData(
        remark="AWG",
        inbound_tag="awg0",
        protocol="amneziawg",
        address=["test.example.com"],
        port=[51820],
        network="udp",
        tls_config=TLSConfig(),
        transport_config=TCPTransportConfig(),
        wireguard_public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        wireguard_pre_shared_key="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
        wireguard_local_address=["10.13.13.1/24"],
        wireguard_allowed_ips=["0.0.0.0/0", "::/0"],
        wireguard_keepalive=25,
        wireguard_mtu=1320,
        wireguard_reserved=None,
        wireguard_dns=["1.1.1.1", "1.0.0.1"],
        amneziawg=True,
        amneziawg_params={
            "jc": 4,
            "jmin": 40,
            "jmax": 70,
            "s1": 86,
            "s2": 574,
            "s3": 45,
            "s4": 12,
            "h1": "104477831",
            "h2": "630113070",
            "h3": "1726947978",
            "h4": "1830566748",
        },
    )

    renderer = WireGuardConfiguration()
    renderer.add(
        "AWG",
        "test.example.com",
        inbound,
        {
            "private_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "peer_ips": ["10.13.13.2/32"],
        },
    )
    output = renderer.configs[0][1]

    assert output.index("MTU = 1320") < output.index("[Peer]")
    assert output.index("DNS = 1.1.1.1, 1.0.0.1") < output.index("[Peer]")
    assert output.index("Jc = 4") < output.index("[Peer]")
    assert output.index("H4 = 1830566748") < output.index("[Peer]")
    assert "PresharedKey =" not in output
    assert "PersistentKeepalive = 25" in output
    assert "Address = 10.13.13.2/32" in output


def test_amneziawg_host_subscription_defaults():
    from app.core.hosts import _resolve_wireguard_subscription_overrides

    allowed, keepalive, reserved, dns, mtu = _resolve_wireguard_subscription_overrides("amneziawg", None)

    assert allowed == ["0.0.0.0/0", "::/0"]
    assert keepalive == 25
    assert reserved is None
    assert dns == ["1.1.1.1", "1.0.0.1"]
    assert mtu == 1320

    allowed, keepalive, reserved, dns, mtu = _resolve_wireguard_subscription_overrides(
        "amneziawg",
        type("Overrides", (), {
            "allowed_ips": ["10.0.0.0/8"],
            "keepalive_seconds": 0,
            "reserved": "1,2,3",
            "dns": ["9.9.9.9"],
            "mtu": 1400,
        })(),
    )

    assert allowed == ["10.0.0.0/8"]
    assert keepalive is None
    assert reserved == "1,2,3"
    assert dns == ["9.9.9.9"]
    assert mtu == 1400


def test_amneziawg_subscription_emits_all_canonical_keys_and_ignores_unknown():
    from app.models.subscription import SubscriptionInboundData, TCPTransportConfig, TLSConfig
    from app.subscription.wireguard import WireGuardConfiguration

    inbound = SubscriptionInboundData(
        remark="AWG",
        inbound_tag="awg0",
        protocol="amneziawg",
        address=["1.2.3.4"],
        port=[51820],
        network="udp",
        tls_config=TLSConfig(),
        transport_config=TCPTransportConfig(),
        wireguard_public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        wireguard_pre_shared_key="",
        wireguard_local_address=["10.0.0.1/24"],
        wireguard_allowed_ips=["0.0.0.0/0"],
        wireguard_keepalive=None,
        wireguard_mtu=None,
        wireguard_reserved=None,
        wireguard_dns=None,
        amneziawg=True,
        amneziawg_params={
            "jc": 3, "jmin": 64, "jmax": 128,
            "s1": 1, "s2": 2, "s3": 3, "s4": 4,
            "h1": "100", "h2": "200", "h3": "300", "h4": "400",
            "i1": "<r 16>", "i2": "<r 10>", "i3": "<r 10>", "i4": "<r 10>", "i5": "<r 10>",
            "unknown": "must-not-be-rendered",
        },
    )
    renderer = WireGuardConfiguration()
    renderer.add("AWG", "1.2.3.4", inbound, {
        "private_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "peer_ips": ["10.0.0.2/32"],
    })
    output = renderer.configs[0][1]
    for key in ("Jc","Jmin","Jmax","S1","S2","S3","S4","H1","H2","H3","H4","I1","I2","I3","I4","I5"):
        assert f"{key} =" in output
    assert "must-not-be-rendered" not in output


def test_amneziawg_allows_partial_init_chain():
    config = _base_config()
    config["i1"] = "<r 16>"
    awg = AmneziaWGConfig(config)
    assert awg["i1"] == "<r 16>"


def test_amneziawg_generates_nova_style_defaults_when_missing():
    awg = AmneziaWGConfig(_base_config())

    assert awg["jc"] == 3
    assert awg["jmin"] == 20
    assert awg["jmax"] == 50
    assert awg["s1"] == 15
    assert awg["s2"] == 64
    assert awg["s3"] == 25
    assert awg["s4"] == 8

    headers = [int(awg[f"h{i}"]) for i in range(1, 5)]
    assert len(set(headers)) == 4
    assert all(5 <= value <= 2_147_483_647 for value in headers)
