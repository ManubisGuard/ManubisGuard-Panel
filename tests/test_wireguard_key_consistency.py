from types import SimpleNamespace

from app.db.crud.wireguard import _ensure_wireguard_keys
from app.utils.crypto import generate_wireguard_keypair, get_wireguard_public_key


def test_stale_wireguard_public_key_is_repaired_from_private_key():
    private_key, derived_public_key = generate_wireguard_keypair()
    _, stale_public_key = generate_wireguard_keypair()
    user = SimpleNamespace(
        proxy_settings={
            "wireguard": {
                "private_key": private_key,
                "public_key": stale_public_key,
                "peer_ips": ["10.0.0.2/32"],
            }
        }
    )

    changed = _ensure_wireguard_keys(user)

    assert changed is True
    assert user.proxy_settings["wireguard"]["public_key"] == derived_public_key
    assert user.proxy_settings["wireguard"]["public_key"] == get_wireguard_public_key(private_key)


def test_matching_wireguard_public_key_is_left_unchanged():
    private_key, public_key = generate_wireguard_keypair()
    user = SimpleNamespace(
        proxy_settings={"wireguard": {"private_key": private_key, "public_key": public_key}}
    )

    changed = _ensure_wireguard_keys(user)

    assert changed is False
    assert user.proxy_settings["wireguard"]["public_key"] == public_key
