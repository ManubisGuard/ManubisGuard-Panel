from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.core import CoreType
from app.models.node import NodeStatus
from app.node import node_manager
from app.operation.node import NodeOperation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("version", "expected_status"),
    [("0.5.4", NodeStatus.error), ("0.6.0", NodeStatus.connected)],
)
async def test_amneziawg_requires_compatible_node_runtime(monkeypatch, version, expected_status):
    fake_node = SimpleNamespace(
        info=AsyncMock(return_value=SimpleNamespace(node_version=version)),
        node_version=AsyncMock(return_value=version),
        stop=AsyncMock(),
    )
    start_result = SimpleNamespace(node_version=version, core_version="test")

    monkeypatch.setattr(node_manager, "get_node", AsyncMock(return_value=fake_node))
    monkeypatch.setattr(
        NodeOperation,
        "_start_or_attach_node",
        staticmethod(AsyncMock(return_value=start_result)),
    )

    result = await NodeOperation.connect_node(
        SimpleNamespace(id=999, name="awg-test", status=NodeStatus.connected),
        SimpleNamespace(type=CoreType.amneziawg),
        [],
        force_start=True,
    )

    assert result["status"] == expected_status
    if version == "0.5.4":
        assert "requires node runtime v0.6.0 or newer" in result["message"]
