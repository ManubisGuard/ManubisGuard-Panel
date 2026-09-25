import asyncio

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
