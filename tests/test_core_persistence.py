import pytest

from app.core.amneziawg import AmneziaWGConfig
from app.db.crud.core import create_core_config, modify_core_config
from app.db.models import CoreConfig, CoreType
from app.models.core import CoreCreate


class FakeDB:
    def __init__(self):
        self.added = None

    def add(self, value):
        self.added = value

    async def commit(self):
        return None

    async def refresh(self, value):
        return None


def _core_input(config: dict) -> CoreCreate:
    return CoreCreate(
        name="awg",
        type=CoreType.amneziawg,
        config=config,
        exclude_inbound_tags=set(),
        fallbacks_inbound_tags=set(),
    )


def _configs() -> tuple[dict, dict]:
    raw_config = {
        "interface_name": "awg0",
        "private_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "listen_port": 51820,
        "address": ["10.0.0.1/24"],
    }
    validated_config = dict(AmneziaWGConfig(raw_config))
    return raw_config, validated_config


@pytest.mark.asyncio
async def test_create_core_persists_validated_config():
    raw_config, validated_config = _configs()
    db = FakeDB()

    await create_core_config(db, _core_input(raw_config), validated_config=validated_config)

    assert db.added.config == validated_config
    assert db.added.config != raw_config
    assert all(key in db.added.config for key in ("jc", "jmin", "jmax", "s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4"))


@pytest.mark.asyncio
async def test_modify_core_persists_validated_config():
    _, validated_config = _configs()
    old = CoreConfig(
        name="old",
        type=CoreType.amneziawg,
        config={"old": True},
        exclude_inbound_tags=set(),
        fallbacks_inbound_tags=set(),
    )

    await modify_core_config(
        FakeDB(),
        old,
        _core_input(validated_config),
        validated_config=validated_config,
    )

    assert old.config == validated_config
    assert all(key in old.config for key in ("jc", "jmin", "jmax", "s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4"))


def test_awg_reload_is_deterministic_from_persisted_config():
    _, persisted_config = _configs()
    before = dict(AmneziaWGConfig(persisted_config))
    after = dict(AmneziaWGConfig(dict(persisted_config)))

    assert after == before
    assert all(after[key] == before[key] for key in ("jc", "jmin", "jmax", "s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4"))
