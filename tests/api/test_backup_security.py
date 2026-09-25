import asyncio

import pytest
from sqlalchemy import select

from app.db.models import Backup
from app.security.encryption import decrypt_secret, encrypt_secret
from tests.api import TestSession, client


def test_backup_telegram_encryption_round_trip(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("BACKUP_TELEGRAM_KEY", Fernet.generate_key().decode())
    token = "test-bot-token-12345"
    encrypted = encrypt_secret(token)
    assert encrypted != token
    assert decrypt_secret(encrypted) == token
    assert token not in encrypted


def test_configure_telegram_hides_token_and_stores_ciphertext(access_token, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("BACKUP_TELEGRAM_KEY", Fernet.generate_key().decode())
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
