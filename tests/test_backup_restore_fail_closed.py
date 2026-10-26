import asyncio

import pytest
from fastapi import HTTPException

from app.models.backup import BackupProductionRestoreRequest
from app.routers.admin_backup import restore_backup_to_production, restore_backup_to_staging


def test_production_restore_api_stays_fail_closed():
    request = BackupProductionRestoreRequest(confirmation="RESTORE_PRODUCTION")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(restore_backup_to_production(backup_id=1, payload=request))

    assert exc_info.value.status_code == 503
    assert "No restore was attempted." in exc_info.value.detail


def test_staging_restore_api_stays_fail_closed_before_database_access():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(restore_backup_to_staging(backup_id=1))

    assert exc_info.value.status_code == 503
    assert "Full restore testing must use the documented disposable round-trip harness" in exc_info.value.detail
