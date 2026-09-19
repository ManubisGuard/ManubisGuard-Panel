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


def test_amneziawg_rejects_padding_and_header_collisions():
    config = _base_config()
    config.update({"s1": 0, "s2": 56, "s3": 0, "s4": 8})
    with pytest.raises(ValueError, match="colliding packet sizes"):
        AmneziaWGConfig(config)

    config = _base_config()
    config.update({"h1": "100-200", "h2": "200-300", "h3": "400", "h4": "500"})
    with pytest.raises(ValueError, match="ranges must not overlap"):
        AmneziaWGConfig(config)
