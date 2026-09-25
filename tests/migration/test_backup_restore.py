import asyncio
from types import SimpleNamespace

from app.routers.admin_backup import restore_backup_to_staging


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDB:
    async def execute(self, _statement):
        return _ScalarResult(SimpleNamespace(id=7, status="valid", backup_path="/tmp/backup.zip"))


def test_staging_restore_endpoint_never_uses_production_as_restore_target(monkeypatch):
    import app.migration.staging as staging_module
    import app.routers.admin_backup as router_module
    from app.migration import runner

    calls = {}
    fake_staging = SimpleNamespace(
        database_name="manubisguard_migration_deadbeef1234",
        url="postgresql+asyncpg://u:p@127.0.0.1:5432/manubisguard_migration_deadbeef1234",
    )

    monkeypatch.setattr(router_module.database_settings, "url", "postgresql+asyncpg://u:p@127.0.0.1:5432/manubisguard")

    def fake_create(production_url):
        calls["create_production_url"] = production_url
        return fake_staging

    def fake_migrate(backup_path, staging, *, production_url, timeout):
        calls.update(
            {
                "backup_path": backup_path,
                "staging_url": staging.url,
                "production_url": production_url,
                "timeout": timeout,
            }
        )
        assert staging.url != production_url
        return SimpleNamespace(
            valid=True,
            analysis=SimpleNamespace(
                detection=SimpleNamespace(format="sql", source_product="pasarguard", schema_revision="1")
            ),
            pre_upgrade_counts={"users": 1},
            post_upgrade_counts={"users": 1},
            transformations=("none",),
            validation=SimpleNamespace(blocking_errors=(), warnings=()),
        )

    def fake_drop(staging):
        calls["dropped"] = staging.database_name

    monkeypatch.setattr(staging_module, "create_staging_database", fake_create)
    monkeypatch.setattr(staging_module, "drop_staging_database", fake_drop)
    monkeypatch.setattr(runner, "migrate_manubisguard_staging", fake_migrate)

    result = asyncio.run(restore_backup_to_staging(7, db=_FakeDB()))

    assert result.valid is True
    assert calls["create_production_url"].endswith("/manubisguard")
    assert calls["production_url"].endswith("/manubisguard")
    assert calls["staging_url"] != calls["production_url"]
    assert calls["dropped"] == fake_staging.database_name
