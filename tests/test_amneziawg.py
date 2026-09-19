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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jc", 11),
        ("jmin", 63),
        ("jmax", 1025),
        ("s4", 33),
    ],
)
def test_amneziawg_config_rejects_invalid_values(field: str, value: int):
    config = _base_config()
    config[field] = value

    with pytest.raises(ValueError):
        AmneziaWGConfig(config)


def test_amneziawg_allows_values_not_restricted_by_awgctrl_validation():
    config = _base_config()
    config.update({"s1": 0, "s2": 56, "s3": 0, "s4": 8})
    awg = AmneziaWGConfig(config)
    assert awg["s1"] == 0
    assert awg["s3"] == 0

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


def test_amneziawg_subscription_emits_all_canonical_keys_and_ignores_unknown():
    from app.models.subscription import SubscriptionInboundData
    from app.subscription.wireguard import WireGuardConfiguration

    inbound = SubscriptionInboundData(
        remark="AWG",
        inbound_tag="awg0",
        protocol="amneziawg",
        address=["1.2.3.4"],
        port=[51820],
        network="udp",
        tls_config=None,
        transport_config=None,
        wireguard_public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        wireguard_pre_shared_key=None,
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
