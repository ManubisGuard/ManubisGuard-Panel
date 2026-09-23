from pathlib import Path

from app.migration.runner import analyze_backup


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
