from types import SimpleNamespace

import pytest

from app.core import manager as manager_module
from app.core.manager import CoreManager
from app.db.models import CoreType


@pytest.mark.asyncio
async def test_initialize_reloads_db_after_cached_state(monkeypatch):
    manager = CoreManager()
    cached_called = False
    validate_calls = []

    async def fake_load_cache():
        nonlocal cached_called
        cached_called = True
        return True

    async def fake_get_core_configs(db, query):
        return [
            SimpleNamespace(
                id=3,
                config={"interface_name": "WG_51820"},
                type=CoreType.amneziawg,
                exclude_inbound_tags=set(),
                fallbacks_inbound_tags=set(),
            )
        ], 1

    def fake_validate(config, exclude, fallbacks, core_type):
        validate_calls.append(core_type)
        return SimpleNamespace(
            inbounds_by_tag={
                "WG_51820": {
                    "protocol": "amneziawg",
                    "amneziawg": {"jc": 3},
                }
            },
            to_json=lambda: {"type": "amneziawg", "config": config},
        )

    monkeypatch.setattr(manager, "_load_state_from_cache", fake_load_cache)
    monkeypatch.setattr(manager_module, "get_core_configs", fake_get_core_configs)
    monkeypatch.setattr(manager, "validate_core", fake_validate)
    monkeypatch.setattr(manager_module.router, "register_handler", lambda *args, **kwargs: None)

    await manager.initialize(object())

    assert cached_called is True
    assert validate_calls == [CoreType.amneziawg]
    assert (await manager.get_inbound_by_tag("WG_51820"))["protocol"] == "amneziawg"
