from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from app.migration.inspector import _async_url
from app.migration.staging import (
    MigrationSafetyError,
    _safe_extract_zip,
    assert_staging_target,
)


def test_staging_target_rejects_production_database():
    with pytest.raises(MigrationSafetyError):
        assert_staging_target(
            "postgresql+asyncpg://u:p@127.0.0.1:5432/pasarguard",
            "postgresql+asyncpg://u:p@127.0.0.1:5432/pasarguard",
        )


def test_staging_target_requires_generated_database_name():
    with pytest.raises(MigrationSafetyError):
        assert_staging_target(
            "postgresql+asyncpg://u:p@127.0.0.1:5432/pasarguard",
            "postgresql+asyncpg://u:p@127.0.0.1:5432/temporary",
        )


def test_postgres_cli_connection_password_never_belongs_in_args():
    from app.migration.staging import _cli_args

    args = _cli_args("postgresql+asyncpg://user:supersecret@127.0.0.1:5432/pasarguard")
    assert "supersecret" not in " ".join(args)


def test_asyncpg_inspection_url_removes_libpq_sslmode():
    url, connect_args = _async_url(
        "postgresql+asyncpg://user:p@127.0.0.1:5432/pasarguard?sslmode=require"
    )
    assert "sslmode" not in url
    assert connect_args["ssl"] is True


def test_zip_path_traversal_is_blocked(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("../escape.sql", "CREATE TABLE nope (id integer);")

    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(MigrationSafetyError):
        _safe_extract_zip(archive, destination)


def test_zip_symlink_is_blocked(tmp_path: Path):
    archive = tmp_path / "link.zip"
    info = ZipInfo("link")
    info.external_attr = 0o120777 << 16
    with ZipFile(archive, "w") as zf:
        zf.writestr(info, "/etc/passwd")

    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(MigrationSafetyError):
        _safe_extract_zip(archive, destination)


def test_sql_gzip_detection_keeps_compressed_format(tmp_path: Path):
    import gzip

    from app.migration.detector import detect_backup

    backup = tmp_path / "backup.sql.gz"
    with gzip.open(backup, "wt", encoding="utf-8") as fh:
        fh.write(
            "-- PasarGuard backup\n"
            "CREATE TABLE alembic_version (version_num varchar(32));\n"
            "CREATE TABLE nodes (id integer);\n"
            "CREATE TABLE core_configs (id integer);\n"
        )

    result = detect_backup(backup)

    assert result.format == "sql.gz"
    assert result.is_pasarguard


def test_old_timescale_dump_fingerprint_is_detected(tmp_path: Path):
    from app.migration.compatibility import analyze_timescale_sql
    dump = tmp_path / "old.sql"
    dump.write_text(
        "COPY _timescaledb_catalog.chunk (id, schema_name, table_name) FROM stdin;\n"
    )
    result = analyze_timescale_sql(dump.read_text())
    assert result.catalog_era == "schema_name"
    assert result.recommended_version == "2.28.3"


def test_archive_deployment_files_are_ignored_when_finding_database(tmp_path: Path):
    from app.migration.staging import _find_candidate

    archive_root = tmp_path / "backup"
    archive_root.mkdir()
    (archive_root / "docker-compose.yml").write_text(
        "services:\n  pasarguard:\n    image: legacy/pasarguard:old\n",
        encoding="utf-8",
    )
    (archive_root / ".env").write_text(
        "POSTGRES_PASSWORD=must-never-be-applied\n",
        encoding="utf-8",
    )
    sql = archive_root / "database.sql"
    sql.write_text(
        "-- PasarGuard backup\n"
        "CREATE TABLE alembic_version (version_num varchar(32));\n"
        "CREATE TABLE users (id integer);\n"
        "CREATE TABLE nodes (id integer);\n"
        "CREATE TABLE core_configs (id integer);\n"
        "-- PostgreSQL database dump complete\n",
        encoding="utf-8",
    )

    candidate, detection = _find_candidate(archive_root)

    assert candidate == sql
    assert detection.is_pasarguard is True
    assert not (tmp_path / ".env").exists()
