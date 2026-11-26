"""Isolated P01 safety regression tests; no production DB or network needed."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile


def run(coro):
    return asyncio.run(coro)


class FakeDB:
    def __init__(self, *, fail_commit=False):
        self.fail_commit = fail_commit
        self.deleted = False
        self.committed = False
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, statement):
        self.deleted = True

    async def commit(self):
        if self.fail_commit:
            raise RuntimeError("DB commit failed")
        self.committed = True

    async def refresh(self, obj):
        return None


@pytest.mark.parametrize("fail_commit", [True, False])
def test_backup_delete_never_unlinks_before_db_commit(monkeypatch, tmp_path, fail_commit):
    from app.services import backup as svc

    root = tmp_path / "database"
    root.mkdir()
    archive = root / "original.zip"
    archive.write_bytes(b"valid-archive")
    monkeypatch.setattr(svc, "BACKUP_DIR", root)
    db = FakeDB(fail_commit=fail_commit)
    row = SimpleNamespace(backup_path=str(archive), id=14, status="created")
    if fail_commit:
        with pytest.raises(RuntimeError, match="DB commit failed"):
            run(svc.delete_backup(db, row))
        assert archive.read_bytes() == b"valid-archive"
    else:
        run(svc.delete_backup(db, row))
        assert not archive.exists()
        assert db.committed


def test_backup_delete_rejects_external_path(monkeypatch, tmp_path):
    from app.services import backup as svc

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    outsider = tmp_path / "outsider.zip"
    outsider.write_bytes(b"must-not-delete")
    monkeypatch.setattr(svc, "BACKUP_DIR", backup_root)
    db = FakeDB()
    row = SimpleNamespace(backup_path=str(outsider), id=22, status="created")
    with pytest.raises(ValueError, match="escapes"):
        run(svc.delete_backup(db, row))
    assert outsider.read_bytes() == b"must-not-delete"
    assert not db.deleted


def test_pg_dump_password_not_in_argv(monkeypatch):
    from app.services import backup as svc

    monkeypatch.setattr(svc.database_settings, "url", "postgresql+asyncpg://writer:secret123@localhost:5432/pasarguard")
    url, env = svc._pg_dump_connection()
    assert "secret123" not in url
    assert "writer" not in url
    assert env == {"PGPASSWORD": "secret123", "PGUSER": "writer"}


def test_repeated_uploads_never_replace_previous_archive(monkeypatch, tmp_path):
    from app.routers import admin_backup as router

    monkeypatch.setattr(router, "UPLOAD_DIR", tmp_path)
    admin = SimpleNamespace(id=42)
    db = FakeDB()
    first = UploadFile(filename="backup.zip", file=__import__("io").BytesIO(b"one"))
    second = UploadFile(filename="backup.zip", file=__import__("io").BytesIO(b"two"))
    first_row = run(router.upload_backup(first, db, admin))
    second_row = run(router.upload_backup(second, db, admin))
    assert first_row.backup_path != second_row.backup_path
    assert Path(first_row.backup_path).read_bytes() == b"one"
    assert Path(second_row.backup_path).read_bytes() == b"two"


def test_upload_size_limit_removes_only_new_temporary_file(monkeypatch, tmp_path):
    from app.routers import admin_backup as router

    monkeypatch.setattr(router, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(router, "MAX_UPLOAD_SIZE", 2)
    existing = tmp_path / "upload-existing.zip"
    existing.write_bytes(b"unchanged")
    upload = UploadFile(filename="backup.zip", file=__import__("io").BytesIO(b"too-large"))
    with pytest.raises(HTTPException) as exc:
        run(router.upload_backup(upload, FakeDB(), SimpleNamespace(id=42)))
    assert exc.value.status_code == 413
    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_bytes() == b"unchanged"


def test_telegram_retry_throttled_and_does_not_block_local_backup(monkeypatch):
    from app.jobs import backup_scheduler as job

    now = datetime.now(UTC)
    schedule = SimpleNamespace(enabled=True, frequency="interval", interval_minutes=60, last_run_at=now-timedelta(hours=2), retention_count=3)
    pending = SimpleNamespace(filename="previous.zip", metadata_json={"telegram_delivery": "failed", "telegram_retry_at": now.isoformat()})
    class Session(FakeDB):
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
    session = Session()
    called = {"created": 0, "telegram": 0}

    async def make_backup(*_args, **_kwargs):
        called["created"] += 1
        return SimpleNamespace(filename="new.zip", metadata_json={})
    async def send_backup(*_args):
        called["telegram"] += 1
        return False
    async def retention(*_args):
        return 0
    async def get_schedule(*_args):
        return schedule
    async def get_pending(*_args):
        return pending
    monkeypatch.setattr(job, "GetDB", lambda: session)
    monkeypatch.setattr(job, "get_backup_schedule", get_schedule)
    monkeypatch.setattr(job, "get_pending_telegram_backup", get_pending)
    monkeypatch.setattr(job, "create_backup", make_backup)
    monkeypatch.setattr(job, "send_backup_to_telegram", send_backup)
    monkeypatch.setattr(job, "apply_backup_retention", retention)
    monkeypatch.setattr(job, "runtime_settings", SimpleNamespace(role=SimpleNamespace(runs_scheduler=True)))
    run(job.scheduled_backup())
    assert called == {"created": 1, "telegram": 1}
    assert schedule.last_run_at > now - timedelta(minutes=5)


def test_telegram_retry_one_hour_backoff_when_backup_not_due(monkeypatch):
    from app.jobs import backup_scheduler as job

    now = datetime.now(UTC)
    schedule = SimpleNamespace(enabled=True, frequency="interval", interval_minutes=120, last_run_at=now, retention_count=3)
    pending = SimpleNamespace(filename="pending.zip", metadata_json={"telegram_delivery": "failed", "telegram_retry_at": now.isoformat()})

    class Session(FakeDB):
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    called = {"send": 0}

    async def get_schedule(*_args):
        return schedule
    async def get_pending(*_args):
        return pending
    async def send(*_args):
        called["send"] += 1
        return True
    monkeypatch.setattr(job, "GetDB", Session)
    monkeypatch.setattr(job, "get_backup_schedule", get_schedule)
    monkeypatch.setattr(job, "get_pending_telegram_backup", get_pending)
    monkeypatch.setattr(job, "send_backup_to_telegram", send)
    monkeypatch.setattr(job, "runtime_settings", SimpleNamespace(role=SimpleNamespace(runs_scheduler=True)))
    run(job.scheduled_backup())
    assert called["send"] == 0
    pending.metadata_json["telegram_retry_at"] = (now - timedelta(hours=2)).isoformat()
    run(job.scheduled_backup())
    assert called["send"] == 1


def test_retention_excludes_manual_and_uploaded_backups(monkeypatch):
    from app.services import backup as svc

    rows = [
        SimpleNamespace(id=1, status="created", created_by=None, metadata_json={"note": "scheduled:daily"}),
        SimpleNamespace(id=2, status="created", created_by=None, metadata_json={"note": "scheduled:daily"}),
        SimpleNamespace(id=3, status="uploaded", created_by=7, metadata_json={"upload": True}),
        SimpleNamespace(id=4, status="created", created_by=7, metadata_json={"note": "manual"}),
    ]

    class Result:
        def scalars(self):
            return self
        def __iter__(self):
            return iter(rows)

    class Session:
        async def execute(self, *_args):
            return Result()

    removed = []
    async def delete(_db, row):
        removed.append(row.id)
    monkeypatch.setattr(svc, "delete_backup", delete)
    assert run(svc.apply_backup_retention(Session(), 1)) == 1
    assert removed == [2]


def test_retention_can_expire_scheduled_validated_archive(monkeypatch):
    from app.services import backup as svc

    rows = [
        SimpleNamespace(id=1, status="created", created_by=None, metadata_json={"note": "scheduled:daily"}),
        SimpleNamespace(id=2, status="valid", created_by=None, metadata_json={"note": "scheduled:daily"}),
    ]

    class Result:
        def scalars(self):
            return self
        def __iter__(self):
            return iter(rows)
    class Session:
        async def execute(self, *_args):
            return Result()

    removed = []
    async def delete(_db, row):
        removed.append(row.id)
    monkeypatch.setattr(svc, "delete_backup", delete)
    assert run(svc.apply_backup_retention(Session(), 1)) == 1
    assert removed == [2]
