from pathlib import Path

from app.migration.detector import detect_backup
from app.migration.preflight import preflight_backup


def test_detects_pasarguard_sql(tmp_path: Path):
    backup = tmp_path / "backup.sql"
    backup.write_text(
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE core_configs (id integer);\n"
        "-- PasarGuard backup\n",
        encoding="utf-8",
    )

    result = detect_backup(backup)

    assert result.source_product == "pasarguard"
    assert result.format == "sql"
    assert result.confidence == "high"
    assert result.is_pasarguard


def test_unknown_backup_is_blocked(tmp_path: Path):
    backup = tmp_path / "backup.sql"
    backup.write_text("CREATE TABLE something_else (id integer);", encoding="utf-8")

    result = preflight_backup(backup)

    assert not result.ok
    assert result.blocking_errors


def test_pg_custom_dump_is_never_guessed(tmp_path: Path):
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"PGDMP" + b"\x00" * 20)

    result = preflight_backup(backup)

    assert not result.ok
    assert result.detection.format == "pg_dump_custom"
