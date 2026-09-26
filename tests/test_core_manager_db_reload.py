from types import SimpleNamespace

import pytest

from app.core import manager as manager_module
from app.core.manager import CoreManager
from app.db.models import CoreType


@pytest.mark.asyncio
async def test_reload_from_cache_prefers_db_source_of_truth(monkeypatch):
    manager = CoreManager()
    manager._cores = {3: "STALE_KV_CORE"}
    calls = []

    class FakeDB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    async def fake_get_core_configs(db, query):
        return [SimpleNamespace(
            id=3,
            config={"fresh": True},
            exclude_inbound_tags=set(),
            fallbacks_inbound_tags=set(),
            type=CoreType.amneziawg,
        )], 1

    def fake_validate(config, exclude, fallbacks, core_type):
        calls.append((config, core_type))
        return SimpleNamespace(inbounds_by_tag={"WG_51820": {"protocol": "amneziawg"}}, to_json=dict)

    async def fake_update_inbounds():
        return None

    async def fake_persist_state():
        return None

    async def fail_cache():
        raise AssertionError("KV fallback must not be used when DB refresh succeeds")

    monkeypatch.setattr(manager_module, "GetDB", lambda: FakeDB())
    monkeypatch.setattr(manager_module, "get_core_configs", fake_get_core_configs)
    monkeypatch.setattr(manager, "validate_core", fake_validate)
    monkeypatch.setattr(manager, "update_inbounds", fake_update_inbounds)
    monkeypatch.setattr(manager, "_persist_state", fake_persist_state)
    monkeypatch.setattr(manager, "_load_state_from_cache", fail_cache)

    await manager._reload_from_cache()

    assert calls == [({"fresh": True}, CoreType.amneziawg)]
    assert manager._cores[3] != "STALE_KV_CORE"
