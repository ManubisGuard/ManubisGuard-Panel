from __future__ import annotations

import pytest


def test_pg_dump_rejects_success_exit_without_completion_marker(monkeypatch):
    from app.services import backup

    class Result:
        returncode = 0
        stdout = (
            b"-- PostgreSQL database dump\n"
            b"CREATE TABLE users (id integer);\n"
        )
        stderr = b""

    monkeypatch.setattr(backup, "_pg_dump_connection", lambda: ("postgresql://fixture/db", {"PGPASSWORD": "redacted"}))
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError, match="completion marker is missing"):
        backup._pg_dump(target_pg_major=16)


def test_pg_dump_accepts_complete_dump_after_compatibility_filter(monkeypatch):
    from app.services import backup

    class Result:
        returncode = 0
        stdout = (
            b"-- PostgreSQL database dump\n"
            b"SET transaction_timeout = 0;\n"
            b"CREATE TABLE users (id integer);\n"
            b"-- PostgreSQL database dump complete\n"
        )
        stderr = b""

    monkeypatch.setattr(backup, "_pg_dump_connection", lambda: ("postgresql://fixture/db", {"PGPASSWORD": "redacted"}))
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: Result())

    payload = backup._pg_dump(target_pg_major=16)

    assert payload.rstrip().endswith(backup.PG_DUMP_COMPLETE_MARKER)
    assert b"transaction_timeout" not in payload


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"-- PostgreSQL database dump complete\n--\n", True),
        (b"\\restrict abc123\n-- PostgreSQL database dump complete\n--\n\n\\unrestrict abc123\n", True),
        (b"\\restrict abc123\n-- PostgreSQL database dump complete\n", False),
        (b"\\restrict abc123\n-- PostgreSQL database dump complete\n\\unrestrict wrong\n", False),
        (b"-- PostgreSQL database dump complete\nSELECT 1;\n", False),
        (b"\\restrict abc123\n\\unrestrict abc123\n", False),
        (b"", False),
    ],
)
def test_complete_dump_trailer(payload, expected):
    from app.services.backup import _has_complete_dump_trailer

    assert _has_complete_dump_trailer(payload) is expected


def test_pg_dump_streams_and_packages_disk_file(monkeypatch, tmp_path):
    import zipfile
    from types import SimpleNamespace

    from app.services import backup

    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(backup, "_pg_dump_connection", lambda: ("postgresql://testdb/db", {"PGPASSWORD": "test-secret"}))
    payload = (b"-- PostgreSQL database dump\n"
               b"\\restrict token123\n"
               b"SET transaction_timeout = 0;\n"
               b"CREATE TABLE test_items (id integer);\n"
               b"-- PostgreSQL database dump complete\n"
               b"--\n"
               b"\\unrestrict token123\n")
    def fake_run(argv, **kwargs):
        assert "test-secret" not in " ".join(argv)
        assert kwargs["env"]["PGPASSWORD"] == "test-secret"
        kwargs["stdout"].write(payload)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    path, size = backup._pg_dump_to_file(target_pg_major=16)
    assert size == path.stat().st_size
    assert b"transaction_timeout" not in path.read_bytes()
    archive_path, _ = backup._write_archive(path, "archive.zip", source_metadata={"postgresql": "17"})
    with zipfile.ZipFile(archive_path) as zipped:
        assert zipped.read("db.sql") == path.read_bytes()
        assert zipped.getinfo("db.sql").file_size == size
    path.unlink()
    assert not list(tmp_path.glob(".raw-pg-dump-*"))


def test_pg_dump_stream_rejects_truncation_and_cleans_temp(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.services import backup

    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(backup, "_pg_dump_connection", lambda: ("postgresql://testdb/db", {"PGPASSWORD": "dummy"}))

    def fake_run(_argv, **kwargs):
        kwargs["stdout"].write(b"CREATE TABLE broken (id integer);\n")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="incomplete"):
        backup._pg_dump_to_file(target_pg_major=17)
    assert not list(tmp_path.iterdir())
