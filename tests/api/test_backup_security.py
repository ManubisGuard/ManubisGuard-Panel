import asyncio

import pytest
from sqlalchemy import select

from app.db.models import Backup
from app.security.encryption import decrypt_secret, encrypt_secret
from tests.api import TestSession, client


def test_backup_telegram_encryption_round_trip(monkeypatch, tmp_path):
    from app.security import encryption

    monkeypatch.delenv("BACKUP_TELEGRAM_KEY", raising=False)
    monkeypatch.setattr(encryption, "KEY_PATH", tmp_path / "backup-telegram.key")
    token = "test-bot-token-12345"
    encrypted = encrypt_secret(token)
    assert encrypted != token
    assert decrypt_secret(encrypted) == token
    assert token not in encrypted


def test_configure_telegram_hides_token_and_stores_ciphertext(access_token, monkeypatch, tmp_path):
    from app.security import encryption

    monkeypatch.delenv("BACKUP_TELEGRAM_KEY", raising=False)
    monkeypatch.setattr(encryption, "KEY_PATH", tmp_path / "backup-telegram.key")
    token = "test-bot-token-12345"
    response = client.post(
        "/api/admin/backup/configure-telegram",
        json={"telegram_bot_token": token, "telegram_chat_id": "123456"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "telegram_bot_token" not in body
    assert body["telegram_enabled"] is True

    async def verify_db():
        async with TestSession() as session:
            row = (await session.execute(select(Backup).where(Backup.id == body["id"]))).scalar_one()
            assert row.telegram_bot_token != token
            assert decrypt_secret(row.telegram_bot_token) == token
            await session.delete(row)
            await session.commit()

    asyncio.run(verify_db())


def test_backup_list_does_not_expose_token(access_token, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("BACKUP_TELEGRAM_KEY", Fernet.generate_key().decode())
    response = client.get("/api/admin/backup/list", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert all("telegram_bot_token" not in item for item in response.json()["items"])


@pytest.mark.asyncio
async def test_telegram_notification_mock_does_not_require_real_token(monkeypatch):
    from app.notification import client as notification_client

    calls = []

    class FakeResponse:
        status = 200

    async def fake_post(url, data):
        calls.append((url, data))
        return FakeResponse()

    class FakeClient:
        post = staticmethod(fake_post)

    monkeypatch.setattr(notification_client, "client", FakeClient())
    result = await notification_client._send_telegram_message_direct(
        message="MANUBISGUARD BACKUP TEST",
        chat_id=123456,
        topic_id=None,
        max_retries=1,
        telegram_api_token="DISPOSABLE_TEST_TOKEN",
    )

    assert result is True
    assert calls == [
        (
            "https://api.telegram.org/botDISPOSABLE_TEST_TOKEN/sendMessage",
            {"parse_mode": "HTML", "text": "MANUBISGUARD BACKUP TEST", "chat_id": 123456},
        )
    ]


@pytest.mark.parametrize(
    ("frequency", "weekday", "day_of_month", "expected"),
    [
        ("daily", None, None, True),
        ("weekly", 4, None, True),
        ("weekly", 1, None, False),
        ("monthly", None, 25, True),
        ("monthly", None, 24, False),
    ],
)
def test_backup_schedule_due_rules(frequency, weekday, day_of_month, expected):
    from datetime import UTC, datetime as dt
    from types import SimpleNamespace

    from app.jobs.backup_scheduler import _is_due

    now = dt(2026, 9, 25, 2, 0, tzinfo=UTC)
    schedule = SimpleNamespace(
        enabled=True,
        frequency=frequency,
        hour=2,
        minute=0,
        weekday=weekday,
        day_of_month=day_of_month,
        last_run_at=None,
    )
    assert _is_due(now, schedule) is expected


@pytest.mark.parametrize(("last_run_minutes", "interval_minutes", "expected"), [(None, 30, True), (10, 30, False), (30, 30, True), (45, 30, True)])
def test_backup_interval_due_rules(last_run_minutes, interval_minutes, expected):
    from datetime import UTC, datetime as dt, timedelta
    from types import SimpleNamespace
    from app.jobs.backup_scheduler import _is_due
    now = dt(2026, 10, 3, 12, 0, tzinfo=UTC)
    last_run_at = None if last_run_minutes is None else now - timedelta(minutes=last_run_minutes)
    schedule = SimpleNamespace(enabled=True, frequency="interval", interval_minutes=interval_minutes, hour=2, minute=0, weekday=None, day_of_month=None, last_run_at=last_run_at)
    assert _is_due(now, schedule) is expected


@pytest.mark.asyncio
async def test_upload_storage_uses_unique_paths_and_never_overwrites(monkeypatch, tmp_path):
    from app.routers import admin_backup

    monkeypatch.setattr(admin_backup, "UPLOAD_DIR", tmp_path)

    class FakeUpload:
        filename = "same-name.zip"

        def __init__(self, payload):
            self.payload = payload

        async def read(self, _size):
            payload, self.payload = self.payload, b""
            return payload

    first, second = await asyncio.gather(
        admin_backup._store_uploaded_archive(FakeUpload(b"first"), 7),
        admin_backup._store_uploaded_archive(FakeUpload(b"second"), 7),
    )

    assert first[1] != second[1]
    assert first[1].suffix == ".zip" and second[1].suffix == ".zip"
    assert "same-name" not in first[1].name and "same-name" not in second[1].name
    assert first[1].read_bytes() == b"first"
    assert second[1].read_bytes() == b"second"
    assert first[1].stat().st_mode & 0o777 == 0o600
    assert second[1].stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".upload-*.tmp"))


@pytest.mark.asyncio
async def test_upload_storage_removes_only_temporary_file_on_size_limit(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from app.routers import admin_backup

    monkeypatch.setattr(admin_backup, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(admin_backup, "MAX_UPLOAD_SIZE", 3)

    class FakeUpload:
        filename = "oversize.zip"

        def __init__(self):
            self.chunks = [b"1234", b""]

        async def read(self, _size):
            return self.chunks.pop(0)

    with pytest.raises(HTTPException) as exc:
        await admin_backup._store_uploaded_archive(FakeUpload(), 7)

    assert exc.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_backup_retention_deletes_only_old_scheduled_backups(monkeypatch):
    from types import SimpleNamespace

    from app.services import backup as backup_service

    backups = [
        SimpleNamespace(id=1, status="created", metadata_json={"note": "scheduled:daily"}),
        SimpleNamespace(id=2, status="uploaded", metadata_json={"upload": True}),
        SimpleNamespace(id=3, status="created", metadata_json={"note": "manual request"}),
        SimpleNamespace(id=4, status="created", metadata_json={"note": "scheduled:daily"}),
        SimpleNamespace(id=5, status="created", metadata_json={"note": "scheduled:daily", "telegram_delivery": "failed"}),
    ]

    class FakeScalars:
        def __init__(self, rows):
            self.rows = rows

        def __iter__(self):
            return iter(self.rows)

    class FakeResult:
        def scalars(self):
            return FakeScalars(backups)

    class FakeDB:
        async def execute(self, _statement):
            return FakeResult()

    deleted = []

    async def fake_delete(_db, backup):
        deleted.append(backup.id)

    monkeypatch.setattr(backup_service, "delete_backup", fake_delete)

    count = await backup_service.apply_backup_retention(FakeDB(), 1)

    assert count == 1
    assert deleted == [4]


@pytest.mark.asyncio
async def test_delete_backup_refuses_paths_outside_backup_root(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.services import backup as backup_service

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    outside = tmp_path / "important.txt"
    outside.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_root)

    class FakeDB:
        async def execute(self, _statement):
            raise AssertionError("database row must not be deleted for an unsafe path")

    with pytest.raises(ValueError, match="outside the configured backup directory"):
        await backup_service.delete_backup(FakeDB(), SimpleNamespace(id=1, backup_path=str(outside)))

    assert outside.read_text(encoding="utf-8") == "preserve"


@pytest.mark.asyncio
async def test_delete_backup_refuses_symlinked_paths(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.services import backup as backup_service

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    target = backup_root / "real.zip"
    target.write_bytes(b"keep")
    link = backup_root / "linked.zip"
    link.symlink_to(target)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_root)

    class FakeDB:
        async def execute(self, _statement):
            raise AssertionError("database row must not be deleted for a symlinked path")

    with pytest.raises(ValueError, match="symlink"):
        await backup_service.delete_backup(FakeDB(), SimpleNamespace(id=1, backup_path=str(link)))

    assert target.read_bytes() == b"keep"
    assert link.is_symlink()
