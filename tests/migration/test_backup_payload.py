from __future__ import annotations

import pytest


def test_pg_dump_rejects_success_exit_without_completion_marker(monkeypatch):
    import app.services.backup as backup

    class Result:
        returncode = 0
        stdout = (
            b"-- PostgreSQL database dump\n"
            b"CREATE TABLE users (id integer);\n"
        )
        stderr = b""

    monkeypatch.setattr(backup, "_pg_dump_url", lambda: "postgresql://fixture/db")
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError, match="completion marker is missing"):
        backup._pg_dump(target_pg_major=16)


def test_pg_dump_accepts_complete_dump_after_compatibility_filter(monkeypatch):
    import app.services.backup as backup

    class Result:
        returncode = 0
        stdout = (
            b"-- PostgreSQL database dump\n"
            b"SET transaction_timeout = 0;\n"
            b"CREATE TABLE users (id integer);\n"
            b"-- PostgreSQL database dump complete\n"
        )
        stderr = b""

    monkeypatch.setattr(backup, "_pg_dump_url", lambda: "postgresql://fixture/db")
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: Result())

    payload = backup._pg_dump(target_pg_major=16)

    assert payload.rstrip().endswith(backup.PG_DUMP_COMPLETE_MARKER)
    assert b"transaction_timeout" not in payload
