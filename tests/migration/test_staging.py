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
