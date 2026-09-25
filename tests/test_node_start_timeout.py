from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PasarGuardNodeBridge import Health, NodeAPIError
from PasarGuardNodeBridge.storage import LifecycleStatus
from pydantic import ValidationError

from app.db.models import NodeStatus
from app.jobs import node_checker
from app.models.node import NodeModify
from app.operation import node as node_operation_module
from app.operation.node import NodeOperation


def test_default_timeout_allows_slow_node_startup():
    assert NodeModify(default_timeout=300).default_timeout == 300

    with pytest.raises(ValidationError):
        NodeModify(default_timeout=2)


@pytest.mark.asyncio
async def test_attach_requires_remote_core_to_be_started():
    state = SimpleNamespace(
        observed=LifecycleStatus.BROKEN,
        desired=LifecycleStatus.HEALTHY,
        epoch=1,
    )
    pg_node = SimpleNamespace(
        get_lifecycle_state=AsyncMock(return_value=state),
        info=AsyncMock(
            return_value=SimpleNamespace(
                started=False,
                node_version="0.5.4",
                core_version="1.0.20260223",
            )
        ),
        connect=AsyncMock(),
    )

    assert await NodeOperation._attach_if_running(pg_node, "slow-node") is None
    pg_node.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_or_attach_probes_broken_desired_healthy_lifecycle(monkeypatch: pytest.MonkeyPatch):
    state = SimpleNamespace(observed=LifecycleStatus.BROKEN, desired=LifecycleStatus.HEALTHY)
    pg_node = SimpleNamespace(get_lifecycle_state=AsyncMock(return_value=state), start=AsyncMock())
    attached = object()
    attach = AsyncMock(return_value=attached)
    monkeypatch.setattr(NodeOperation, "_attach_if_running", attach)

    result = await NodeOperation._start_or_attach_node(
        pg_node,
        SimpleNamespace(name="slow-node"),
        object(),
        [],
        object(),
    )

    assert result is attached
    attach.assert_awaited_once_with(pg_node, "slow-node")
    pg_node.start.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_start_skips_attach_and_starts_core(monkeypatch: pytest.MonkeyPatch):
    started = SimpleNamespace(node_version="0.5.4", core_version="26.3.27")
    pg_node = SimpleNamespace(
        get_lifecycle_state=AsyncMock(),
        start=AsyncMock(return_value=started),
        stop=AsyncMock(),
    )
    attach = AsyncMock(return_value=object())
    monkeypatch.setattr(NodeOperation, "_attach_if_running", attach)
    db_node = SimpleNamespace(name="england", keep_alive=60)
    core = SimpleNamespace(type=None, to_str=lambda: "{}", exclude_inbound_tags=[])

    result = await NodeOperation._start_or_attach_node(
        pg_node,
        db_node,
        core,
        [],
        object(),
        force_start=True,
    )

    assert result is started
    attach.assert_not_awaited()
    pg_node.stop.assert_awaited_once()
    pg_node.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_node_attaches_when_remote_start_finishes_after_timeout(monkeypatch: pytest.MonkeyPatch):
    pg_node = object()
    db_node = SimpleNamespace(id=19, name="slow-node", status=NodeStatus.connecting)
    core = SimpleNamespace(type=object())
    attached = SimpleNamespace(node_version="0.5.4", core_version="1.0.20260223")

    monkeypatch.setattr(node_operation_module.node_manager, "get_node", AsyncMock(return_value=pg_node))
    monkeypatch.setattr(
        NodeOperation,
        "_start_or_attach_node",
        AsyncMock(side_effect=NodeAPIError(-1, "Request timed out")),
    )
    attach = AsyncMock(return_value=attached)
    monkeypatch.setattr(NodeOperation, "_attach_if_running", attach)

    result = await NodeOperation.connect_node(db_node, core, [])

    assert result == {
        "node_id": 19,
        "status": NodeStatus.connected,
        "message": "",
        "xray_version": "1.0.20260223",
        "node_version": "0.5.4",
        "old_status": NodeStatus.connecting,
    }
    attach.assert_awaited_once_with(pg_node, "slow-node")


@pytest.mark.asyncio
async def test_health_check_attaches_ambiguous_timed_out_start_before_reconnect(monkeypatch: pytest.MonkeyPatch):
    state = SimpleNamespace(observed=LifecycleStatus.BROKEN, desired=LifecycleStatus.HEALTHY)
    node = MagicMock()
    node.requires_hard_reset.return_value = False
    node.get_lifecycle_state = AsyncMock(return_value=state)
    db_node = SimpleNamespace(id=19, name="slow-node", status=NodeStatus.error)

    monkeypatch.setattr(
        node_checker,
        "verify_node_backend_health",
        AsyncMock(return_value=(Health.NOT_CONNECTED, None, None)),
    )
    attach = AsyncMock(return_value=object())
    monkeypatch.setattr(NodeOperation, "_attach_if_running", attach)
    reconnect = AsyncMock()
    monkeypatch.setattr(node_checker.node_operator, "connect_single_node", reconnect)

    await node_checker.process_node_health_check(db_node, node)

    attach.assert_awaited_once_with(node, "slow-node")
    reconnect.assert_not_awaited()


class _FakeDB:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


def _patch_health_check_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(node_checker, "GetDB", lambda: _FakeDB())
    monkeypatch.setattr(NodeOperation, "_update_single_node_status", AsyncMock())
    monkeypatch.setattr(node_checker, "get_bridge_memory", lambda: (None, None, None))


@pytest.mark.asyncio
async def test_health_check_reapplies_config_when_keep_alive_stopped_core(monkeypatch: pytest.MonkeyPatch):
    """pg-node keep-alive stops Xray but leaves HTTP up. Panel must POST /start again."""
    node = MagicMock()
    node.requires_hard_reset.return_value = False
    node.get_lifecycle_state = AsyncMock(return_value=None)
    node.update_observed_lifecycle = AsyncMock()
    db_node = SimpleNamespace(id=19, name="dead-core", status=NodeStatus.connected)

    _patch_health_check_db(monkeypatch)
    monkeypatch.setattr(
        node_checker,
        "verify_node_backend_health",
        AsyncMock(return_value=(Health.BROKEN, 500, "backend not initialized")),
    )
    reconnect = AsyncMock()
    monkeypatch.setattr(node_checker.node_operator, "connect_single_node", reconnect)

    await node_checker.process_node_health_check(db_node, node)

    reconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check_waits_when_core_not_started_during_in_flight_start(monkeypatch: pytest.MonkeyPatch):
    node = MagicMock()
    node.requires_hard_reset.return_value = False
    node.get_lifecycle_state = AsyncMock(return_value=None)
    node.update_observed_lifecycle = AsyncMock()
    db_node = SimpleNamespace(id=19, name="starting-node", status=NodeStatus.connected)

    _patch_health_check_db(monkeypatch)
    NodeOperation._in_flight_connects.add(19)
    monkeypatch.setattr(
        node_checker,
        "verify_node_backend_health",
        AsyncMock(return_value=(Health.BROKEN, 500, "backend not initialized")),
    )
    reconnect = AsyncMock()
    monkeypatch.setattr(node_checker.node_operator, "connect_single_node", reconnect)

    try:
        await node_checker.process_node_health_check(db_node, node)
    finally:
        NodeOperation._in_flight_connects.discard(19)

    reconnect.assert_not_awaited()


def test_should_reconnect_skips_core_not_started_500():
    assert node_checker.should_reconnect_after_health_error(500, "core is not started yet") is False
    assert node_checker.is_core_not_started_error(500, "core is not started yet") is True
    assert node_checker.is_core_starting_error(503, "core is not started yet") is True
    assert node_checker.is_core_dead_error(500, "backend not initialized") is True
    assert node_checker.should_reconnect_after_health_error(500, "backend not initialized") is False
    assert node_checker.should_reconnect_after_health_error(400, "bad request") is True


@pytest.mark.asyncio
async def test_health_check_waits_when_core_is_still_starting(monkeypatch: pytest.MonkeyPatch):
    """pg-node still has a backend object; another Start would kill that process."""
    node = MagicMock()
    node.requires_hard_reset.return_value = False
    node.get_lifecycle_state = AsyncMock(return_value=None)
    node.update_observed_lifecycle = AsyncMock()
    db_node = SimpleNamespace(id=19, name="starting-core", status=NodeStatus.connected)

    _patch_health_check_db(monkeypatch)
    monkeypatch.setattr(
        node_checker,
        "verify_node_backend_health",
        AsyncMock(return_value=(Health.BROKEN, 503, "core is not started yet")),
    )
    reconnect = AsyncMock()
    monkeypatch.setattr(node_checker.node_operator, "connect_single_node", reconnect)

    await node_checker.process_node_health_check(db_node, node)

    reconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_node_skips_when_already_healthy(monkeypatch: pytest.MonkeyPatch):
    pg_node = SimpleNamespace(
        get_health=AsyncMock(return_value=Health.HEALTHY),
        get_versions=AsyncMock(return_value=("0.5.4", "26.3.27")),
        start=AsyncMock(),
    )
    db_node = SimpleNamespace(id=3, name="Hetz Tunnel", status=NodeStatus.connected)
    monkeypatch.setattr(node_operation_module.node_manager, "get_node", AsyncMock(return_value=pg_node))
    start_or_attach = AsyncMock()
    monkeypatch.setattr(NodeOperation, "_start_or_attach_node", start_or_attach)

    result = await NodeOperation.connect_node(db_node, object(), [])

    assert result is None
    start_or_attach.assert_not_awaited()
    pg_node.start.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_managed_certificate_deployment_rolls_back_after_start_failure(monkeypatch: pytest.MonkeyPatch):
    domain = SimpleNamespace(id="managed-1", node_id=7, status="active", domain="edge.example.com")
    original_core = SimpleNamespace(name="original")
    runtime_core = SimpleNamespace(name="managed")
    runtime = SimpleNamespace(
        core=runtime_core,
        injected_domain_ids=("managed-1",),
        skipped_domain_ids=(),
    )
    service = SimpleNamespace(
        list_domains=AsyncMock(return_value=[domain]),
        mark_deployment=AsyncMock(),
    )
    node = SimpleNamespace(id=7, core_config_id=1, status=NodeStatus.connected, name="node-7")

    monkeypatch.setattr(node_operation_module, "ManagedCertificateService", lambda: service)
    monkeypatch.setattr(
        node_operation_module.NodeOperation,
        "_get_core_users_map",
        AsyncMock(return_value=({1: original_core}, {1: []})),
    )
    monkeypatch.setattr(node_operation_module, "build_runtime_core", lambda core, domains: runtime)
    monkeypatch.setattr(node_operation_module.node_manager, "update_node", AsyncMock())
    monkeypatch.setattr(node_operation_module, "bulk_update_node_status", AsyncMock())

    failed = {
        "node_id": 7,
        "status": NodeStatus.error,
        "message": "new managed config rejected",
        "xray_version": "",
        "node_version": "",
        "old_status": NodeStatus.connected,
    }
    rolled_back = {
        "node_id": 7,
        "status": NodeStatus.connected,
        "message": "",
        "xray_version": "26.0.0",
        "node_version": "0.9.1",
        "old_status": NodeStatus.error,
    }
    start = AsyncMock(side_effect=[failed, rolled_back])
    monkeypatch.setattr(node_operation_module.NodeOperation, "connect_node", start)

    db = SimpleNamespace(commit=AsyncMock())
    operation = NodeOperation.__new__(NodeOperation)
    await operation._connect_nodes_bulk_local(db, [node], force_start=True)

    assert start.await_count == 2
    first_core = start.await_args_list[0].args[1]
    second_core = start.await_args_list[1].args[1]
    assert first_core is runtime_core
    assert second_core is original_core
    assert start.await_args_list[1].kwargs["force_start"] is True
    service.mark_deployment.assert_awaited_once_with(
        db,
        ("managed-1",),
        status="failed",
        error="new managed config rejected",
    )
