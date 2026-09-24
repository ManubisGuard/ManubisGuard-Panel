import io
import tarfile
import zipfile

import pytest

from app.migration.pasarguard_backup import (
    parse_manifest_tsv,
    read_manifest_from_archive,
    validate_manifest_members,
)


def test_parse_pasarguard_manifest():
    manifest = parse_manifest_tsv(
        "appdb\tappuser\t1\tdb-001.sql\t2.27.2\n"
        "otherdb\totheruser\t0\tdb-002.sql\n"
    )

    assert len(manifest.databases) == 2
    assert manifest.databases[0].name == "appdb"
    assert manifest.databases[0].timescale
    assert manifest.databases[0].timescale_version == "2.27.2"
    assert manifest.databases[1].timescale is False
    assert manifest.databases[1].timescale_version is None


@pytest.mark.parametrize(
    "manifest",
    [
        "appdb\tappuser\t2\tdb-001.sql",
        "appdb\tappuser\t1\tdb-001.sql",
        "appdb\tappuser\t0\tdb-001.sql\t2.27.2",
        "appdb\tappuser\tdb-001.sql",
        "",
    ],
)
def test_manifest_rejects_malformed_rows(manifest: str):
    with pytest.raises(ValueError):
        parse_manifest_tsv(manifest)


def test_manifest_ignores_blank_and_comment_lines():
    manifest = parse_manifest_tsv(
        "# PasarGuard backup\n\n"
        "appdb\tappuser\t1\tdb-001.sql\t2.28.2\n"
    )

    assert [entry.name for entry in manifest.databases] == ["appdb"]


def test_manifest_rejects_duplicate_database_names():
    with pytest.raises(ValueError, match="duplicate database name"):
        parse_manifest_tsv(
            "appdb\tappuser\t0\tdb-001.sql\n"
            "appdb\tappuser2\t0\tdb-002.sql\n"
        )


def test_validate_manifest_members_reports_missing_and_duplicate_dump():
    manifest = parse_manifest_tsv(
        "appdb\tappuser\t0\tdb-001.sql\n"
        "otherdb\totheruser\t0\tdb-001.sql\n"
        "missing\tmissinguser\t0\tdb-003.sql\n"
    )

    errors = validate_manifest_members(manifest, {"manifest.tsv", "db-001.sql"})
    assert "Manifest references the same dump more than once: 'db-001.sql'" in errors
    assert "Manifest dump file is missing from archive: 'db-003.sql'" in errors


def test_read_manifest_from_zip(tmp_path):
    archive_path = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "manifest.tsv",
            "appdb\tappuser\t1\tpg_dump/db-001.sql\t2.28.2\n",
        )
        archive.writestr("pg_dump/db-001.sql", "-- PostgreSQL dump\n")

    manifest, errors = read_manifest_from_archive(archive_path)
    assert errors == ()
    assert manifest is not None
    assert manifest.databases[0].dump_file == "pg_dump/db-001.sql"
    assert manifest.databases[0].timescale_version == "2.28.2"


def test_read_nested_manifest_from_zip(tmp_path):
    archive_path = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "pg_dump/manifest.tsv",
            "appdb\tappuser\t1\tdb-001.sql\t2.30.0\n",
        )
        archive.writestr("pg_dump/db-001.sql", "-- PostgreSQL dump\n")

    manifest, errors = read_manifest_from_archive(archive_path)
    assert errors == ()
    assert manifest is not None
    assert manifest.databases[0].name == "appdb"
    assert manifest.databases[0].dump_file == "db-001.sql"


def test_read_manifest_from_tar(tmp_path):
    archive_path = tmp_path / "pasarguard.tar"
    with tarfile.open(archive_path, "w") as archive:
        manifest = tarfile.TarInfo("manifest.tsv")
        payload = b"appdb\tappuser\t0\tdb-001.sql\n"
        manifest.size = len(payload)
        archive.addfile(manifest, io.BytesIO(payload))

        dump = tarfile.TarInfo("db-001.sql")
        dump_payload = b"-- PostgreSQL dump\n"
        dump.size = len(dump_payload)
        archive.addfile(dump, io.BytesIO(dump_payload))

    parsed, errors = read_manifest_from_archive(archive_path)
    assert errors == ()
    assert parsed is not None
    assert parsed.databases[0].name == "appdb"


def test_read_manifest_rejects_multiple_nested_manifests(tmp_path):
    archive_path = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("one/manifest.tsv", "appdb\tappuser\t0\tdb-001.sql\n")
        archive.writestr("two/manifest.tsv", "other\totheruser\t0\tdb-002.sql\n")

    manifest, errors = read_manifest_from_archive(archive_path)
    assert manifest is None
    assert errors == ("Archive contains multiple manifest.tsv files.",)


def test_read_manifest_rejects_unsafe_dump_path(tmp_path):
    archive_path = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.tsv", "appdb\tappuser\t0\t../db.sql\n")
        archive.writestr("db.sql", "-- PostgreSQL dump\n")

    manifest, errors = read_manifest_from_archive(archive_path)
    assert manifest is not None
    assert errors == ("Unsafe archive member path: '../db.sql'",)
