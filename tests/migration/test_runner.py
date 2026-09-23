import pytest
import zipfile

from pathlib import Path

from app.migration.compatibility import TimescaleCompatibility
from app.migration.runner import analyze_backup, migrate_pasarguard_staging
from app.migration.staging import MigrationSafetyError


def test_runner_analyzes_old_timescale_sql_without_database_access(tmp_path: Path):
    backup = tmp_path / "backup.sql"
    backup.write_text(
        "-- PasarGuard backup\n"
        "-- timescaledb version: 2.28.3\n"
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE nodes (id bigint);\n"
        "CREATE TABLE core_configs (id bigint);\n"
        "COPY _timescaledb_catalog.chunk (id, schema_name, table_name) FROM stdin;\n"
        "\\.\n"
        "-- PostgreSQL database dump complete\n",
        encoding="utf-8",
    )
    result = analyze_backup(backup)
    assert result.preflight.ok
    assert result.uses_timescaledb
    assert result.timescale.catalog_era == "schema_name"
    assert result.timescale.recommended_version == "2.28.3"


def test_runner_reads_timescaledb_sidecar_version(tmp_path: Path):
    backup = tmp_path / "backup.sql"
    backup.write_text(
        "-- PasarGuard backup\n"
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE nodes (id bigint);\n"
        "CREATE TABLE core_configs (id bigint);\n"
        "COPY _timescaledb_catalog.chunk (id, schema_name, table_name) FROM stdin;\n"
        "\\.\n"
        "-- PostgreSQL database dump complete\n",
        encoding="utf-8",
    )
    (tmp_path / "db_backup.timescaledb-version").write_text("2.28.2\n", encoding="utf-8")

    result = analyze_backup(backup)
    assert result.timescale.source_version == "2.28.2"


def test_runner_ignores_archived_compose_for_timescale_version(tmp_path: Path):
    backup = tmp_path / "backup.zip"
    sql = (
        "-- PasarGuard backup\n"
        "-- timescaledb version: 2.28.2\n"
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE nodes (id bigint);\n"
        "CREATE TABLE core_configs (id bigint);\n"
        "COPY _timescaledb_catalog.chunk (id, schema_name, table_name) FROM stdin;\n"
        "\\.\n"
        "-- PostgreSQL database dump complete\n"
    )
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr("pg_dump/manifest.tsv", "pasarguard\\tpasarguard\\t1\\tdb-001.sql\\t2.28.2\\n")
        zf.writestr("pg_dump/db-001.sql", sql)
        zf.writestr(
            "docker-compose.yml",
            "image: timescale/timescaledb:9.99.9-pg17\\n",
        )

    result = analyze_backup(backup)
    assert result.preflight.ok
    assert result.timescale.source_version == "2.28.2"


def test_resolved_timescale_version_must_match_live_version():
    from app.migration.runner import resolve_staging_timescale_version

    analysis = type("A", (), {
        "uses_timescaledb": True,
        "timescale": TimescaleCompatibility(
            versions=("2.28.2",),
            source_version="2.28.2",
            catalog_era="schema_name",
        ),
    })()
    assert resolve_staging_timescale_version(analysis, live_version="2.28.2") == "2.28.2"


def test_migration_blocks_timescale_mismatch_before_restore(monkeypatch, tmp_path: Path):
    import app.migration.runner as runner

    analysis = type("A", (), {
        "preflight": type("P", (), {"ok": True, "blocking_errors": ()})(),
        "uses_timescaledb": True,
        "timescale": TimescaleCompatibility(
            versions=("2.28.2",),
            source_version="2.28.2",
            catalog_era="schema_name",
        ),
        "detection": None,
    })()

    monkeypatch.setattr(runner, "analyze_backup", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(runner, "read_timescaledb_version", lambda url: "2.29.0")
    monkeypatch.setattr(
        runner,
        "restore_backup_into_staging",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("restore must not start")),
    )

    staging = runner.StagingDatabase(
        "manubisguard_migration_0123456789ab",
        "postgresql://user:pass@localhost:5433/manubisguard_migration_0123456789ab",
        "postgresql://user:pass@localhost:5432/pasarguard",
    )

    with pytest.raises(MigrationSafetyError, match="source version does not match"):
        migrate_pasarguard_staging(tmp_path / "backup.sql", staging, production_url=staging._production_url)
