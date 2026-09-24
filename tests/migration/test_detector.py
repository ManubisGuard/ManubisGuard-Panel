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


def test_zip_crc_failure_is_blocked(tmp_path: Path):
    import zipfile

    backup = tmp_path / "backup.zip"
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("manifest.json", '{"pasarguard": true}')
    raw = bytearray(backup.read_bytes())
    marker = b'{"pasarguard": true}'
    idx = raw.find(marker)
    assert idx >= 0
    raw[idx] ^= 0x01
    backup.write_bytes(raw)

    result = preflight_backup(backup)

    assert not result.ok
    assert any("CRC" in error for error in result.blocking_errors)


def test_zip_duplicate_normalized_path_is_blocked(tmp_path: Path):
    import zipfile

    backup = tmp_path / "backup.zip"
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr("db_backup.sql", "CREATE TABLE users (id integer);\n")
        zf.writestr("./db_backup.sql", "CREATE TABLE users (id integer);\n")

    result = preflight_backup(backup)

    assert not result.ok
    assert any("duplicate path" in error.lower() for error in result.blocking_errors)


def test_zip_symlink_is_blocked(tmp_path: Path):
    import zipfile

    backup = tmp_path / "backup.zip"
    info = zipfile.ZipInfo("pasarguard_data/certs/key.pem")
    info.create_system = 3
    info.external_attr = (0o120777 << 16)
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr(info, "not-a-real-key")

    result = preflight_backup(backup)

    assert not result.ok
    assert any("link/special" in error.lower() for error in result.blocking_errors)


def test_zip_directory_entries_are_allowed(tmp_path: Path):
    import zipfile

    backup = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr("pasarguard_data/", "")
        zf.writestr("pg_dump/", "")
        zf.writestr(
            "pg_dump/manifest.tsv",
            "pasarguard\tpasarguard\t0\tdb-001.sql\n",
        )
        zf.writestr(
            "pg_dump/db-001.sql",
            "-- PasarGuard backup\n"
            "CREATE TABLE alembic_version (version_num varchar(32));\n"
            "CREATE TABLE core_configs (id integer);\n"
            "CREATE TABLE nodes (id integer);\n",
        )

    result = preflight_backup(backup)

    assert result.ok
    assert result.pasarguard_manifest is not None
    assert not result.blocking_errors


def test_detects_source_postgres_major_from_dump_header(tmp_path: Path):
    backup = tmp_path / "backup.sql"
    backup.write_text(
        "-- PostgreSQL database dump\n"
        "-- Dumped from database version 17.10\n"
        "-- Dumped by pg_dump version 17.10\n"
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE core_configs (id integer);\n"
        "CREATE TABLE nodes (id integer);\n"
        "-- PasarGuard backup\n",
        encoding="utf-8",
    )

    result = detect_backup(backup)

    assert result.source_postgres_major == 17


def test_globals_only_dump_is_not_a_database_candidate(tmp_path: Path):
    backup = tmp_path / "globals.sql"
    backup.write_text(
        "-- PostgreSQL database cluster dump\n"
        "CREATE ROLE pasarguard;\n"
        "GRANT CONNECT ON DATABASE pasarguard TO pasarguard;\n",
        encoding="utf-8",
    )

    result = detect_backup(backup)

    assert result.source_product == "unknown"
    assert result.confidence == "low"
    assert "globals-only" in result.evidence[0]
