from types import SimpleNamespace

import pytest

from app.db.models import CoreType
from app.models.core import CoreResponse
from app.operation import OperatorType, core as core_operation_module
from app.operation.core import CoreOperation


@pytest.mark.asyncio
async def test_amneziawg_config_change_restarts_nodes(monkeypatch):
    operation = CoreOperation(OperatorType.API)
    old = SimpleNamespace(
        id=7,
        name="AWG",
        type=CoreType.amneziawg,
        config={"listen_port": 51820, "pre_shared_key": "OLD"},
        exclude_inbound_tags=set(),
        fallbacks_inbound_tags=set(),
    )
    modified = SimpleNamespace(
        name="AWG",
        type=CoreType.amneziawg,
        config={"listen_port": 51820, "pre_shared_key": "NEW"},
        exclude_inbound_tags=set(),
        fallbacks_inbound_tags=set(),
    )
    admin = SimpleNamespace(username="tester")
    restarted = []

    async def fake_modify_core_config(db, db_core, modified_core, validated_config=None):
        db_core.config = dict(modified_core.config)
        return db_core

    async def fake_restart(self, db, admin, core_id=None):
        restarted.append((admin.username, core_id))

    async def noop(*args, **kwargs):
        return None

    async def fake_get_validated_core_config(db, core_id):
        return old

    monkeypatch.setattr(operation, "get_validated_core_config", fake_get_validated_core_config)
    monkeypatch.setattr(core_operation_module, "modify_core_config", fake_modify_core_config)
    monkeypatch.setattr(core_operation_module.core_manager, "validate_core", lambda *args: dict(modified.config))
    monkeypatch.setattr(core_operation_module.core_manager, "update_core", noop)
    monkeypatch.setattr(operation, "_validate_wireguard_subnet", noop)
    monkeypatch.setattr(operation, "_reconcile_wireguard", noop)
    monkeypatch.setattr(operation, "_refresh_hosts_from_db", noop)
    monkeypatch.setattr(core_operation_module.notification, "modify_core", noop)
    monkeypatch.setattr(CoreResponse, "model_validate", lambda value: value)

    from app.operation.node import NodeOperation

    monkeypatch.setattr(NodeOperation, "restart_all_node", fake_restart)

    result = await operation.modify_core(None, 7, modified, admin)

    assert result is old
    assert restarted == [("tester", 7)]
