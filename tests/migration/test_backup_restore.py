import asyncio

import pytest
from fastapi import HTTPException

from app.routers.admin_backup import restore_backup_to_staging


class _FakeDB:
    async def execute(self, _statement):
        pytest.fail("disabled staging restore must not query or create a production-cluster database")


def test_staging_restore_endpoint_fails_closed_until_external_staging_db_is_configured(monkeypatch):
    import app.migration.staging as staging_module
    import app.routers.admin_backup as router_module

    monkeypatch.setattr(
        staging_module,
        "create_staging_database",
        lambda *_args, **_kwargs: pytest.fail("must not create a staging DB on the production cluster"),
    )
    assert router_module.APPLICATION_STAGING_RESTORE_ENABLED is False

    with pytest.raises(HTTPException) as error:
        asyncio.run(restore_backup_to_staging(7, db=_FakeDB()))

    assert error.value.status_code == 503
    assert "production PostgreSQL cluster" in str(error.value.detail)
