from types import SimpleNamespace

import pytest

from app.core import hosts as hosts_module
from app.core.hosts import HostManager


@pytest.mark.asyncio
async def test_reload_from_cache_prefers_db_source_of_truth(monkeypatch):
    manager = HostManager()
    manager._hosts = {7: SimpleNamespace(protocol="wireguard")}
    calls = []

    class FakeDB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    db_hosts = [SimpleNamespace(id=7, inbound_tag="WG_51820")]

    async def fake_get_hosts(db):
        return db_hosts

    async def fake_add_hosts_local(db, hosts):
        calls.append(hosts)
        manager._hosts = {7: SimpleNamespace(protocol="amneziawg", amneziawg=True)}

    async def fail_cache():
        raise AssertionError("KV fallback must not be used when DB refresh succeeds")

    monkeypatch.setattr(hosts_module, "GetDB", lambda: FakeDB())
    monkeypatch.setattr(hosts_module, "get_hosts", fake_get_hosts)
    monkeypatch.setattr(manager, "_add_hosts_local", fake_add_hosts_local)
    monkeypatch.setattr(manager, "_load_state_from_cache", fail_cache)

    await manager._reload_from_cache()

    assert calls == [db_hosts]
    assert manager._hosts[7].protocol == "amneziawg"
    assert manager._hosts[7].amneziawg is True
