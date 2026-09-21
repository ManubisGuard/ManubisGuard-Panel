from __future__ import annotations

from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = REPOSITORY_ROOT / "app/db/migrations/versions/awg2026091901_add_amneziawg_core_type.py"
AWG_REVISION = "awg2026091901"
PREVIOUS_REVISION = "48a6bcb8bba1"


def _migration_module():
    spec = spec_from_file_location("phase5_awg_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _alembic_config(database: Path) -> Config:
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _sync_engine(database: Path):
    return create_engine(f"sqlite:///{database}")


def _version(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _insert_core(engine, name: str, core_type: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO core_configs "
                "(created_at, name, config, exclude_inbound_tags, fallbacks_inbound_tags, type) "
                "VALUES (:created_at, :name, :config, :exclude, :fallbacks, :type)"
            ),
            {
                "created_at": datetime.now(UTC),
                "name": name,
                "config": "{}",
                "exclude": None,
                "fallbacks": None,
                "type": core_type,
            },
        )


def test_migration_metadata_and_chain_contract():
    migration = _migration_module()
    assert migration.revision == AWG_REVISION
    assert migration.down_revision == PREVIOUS_REVISION
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_fresh_sqlite_runs_full_chain_and_exposes_awg_type(tmp_path):
    database = tmp_path / "fresh.sqlite"
    config = _alembic_config(database)
    upgrade(config, "head")
    engine = _sync_engine(database)
    inspector = inspect(engine)

    assert _version(engine) == AWG_REVISION
    assert "core_configs" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("core_configs")} >= {
        "id",
        "created_at",
        "name",
        "config",
        "type",
    }
    assert inspector.get_columns("core_configs")[6]["name"] == "type"
    assert inspector.get_foreign_keys("core_configs") == []

    _insert_core(engine, "fresh-awg", "amneziawg")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT type FROM core_configs WHERE name = 'fresh-awg'")
        ).scalar_one() == "amneziawg"


def test_existing_sqlite_upgrade_preserves_legacy_core_rows(tmp_path):
    database = tmp_path / "existing.sqlite"
    config = _alembic_config(database)
    upgrade(config, PREVIOUS_REVISION)
    engine = _sync_engine(database)
    _insert_core(engine, "existing-xray", "xray")
    _insert_core(engine, "existing-wg", "wg")

    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT name, type, config FROM core_configs ORDER BY name")
        ).all()

    upgrade(config, "head")

    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT name, type, config FROM core_configs ORDER BY name")
        ).all()
    assert _version(engine) == AWG_REVISION
    assert after == before


def test_sqlite_downgrade_is_schema_safe_and_reupgrade_is_repeatable(tmp_path):
    database = tmp_path / "roundtrip.sqlite"
    config = _alembic_config(database)
    upgrade(config, "head")
    engine = _sync_engine(database)
    _insert_core(engine, "roundtrip-awg", "amneziawg")

    downgrade(config, PREVIOUS_REVISION)
    assert _version(engine) == PREVIOUS_REVISION
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT type FROM core_configs WHERE name = 'roundtrip-awg'")
        ).scalar_one() == "amneziawg"

    upgrade(config, "head")
    assert _version(engine) == AWG_REVISION
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT type FROM core_configs WHERE name = 'roundtrip-awg'")
        ).scalar_one() == "amneziawg"


def test_postgresql_downgrade_policy_refuses_data_loss():
    migration = _migration_module()
    source = MIGRATION_PATH.read_text()
    assert "Cannot downgrade awg2026091901 while core_configs contains" in source
    assert "ALTER TYPE coretype ADD VALUE IF NOT EXISTS" in source
    assert "CREATE TYPE coretype_downgrade AS ENUM" in source
    assert "DROP TYPE coretype" in source
    assert "migrate those rows explicitly first" in source
    assert migration._LEGACY_CORE_TYPES == ("xray", "wg", "mtproto", "singbox")


def test_postgresql_is_explicitly_reported_unavailable_when_no_server():
    pytest.importorskip("psycopg")
    pytest.skip("No PostgreSQL server/container is configured in this environment")
