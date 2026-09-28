from __future__ import annotations

import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class EncryptionConfigurationError(RuntimeError):
    """Raised when the backup encryption key is missing or invalid."""


KEY_PATH = Path("/var/lib/manubisguard/backup-telegram.key")


def _fernet() -> Fernet:
    key = os.getenv("BACKUP_TELEGRAM_KEY", "").strip()

    if not key:
        try:
            KEY_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if KEY_PATH.is_file():
                key = KEY_PATH.read_text(encoding="ascii").strip()
            else:
                key = Fernet.generate_key().decode("ascii")
                KEY_PATH.write_text(key + "\n", encoding="ascii")
                KEY_PATH.chmod(0o600)
        except OSError as exc:
            raise EncryptionConfigurationError(
                "BACKUP_TELEGRAM_KEY is not set and the persistent backup key could not be created"
            ) from exc

    try:
        return Fernet(key.encode("ascii") if isinstance(key, str) else key)
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise EncryptionConfigurationError("Backup Telegram encryption key is not a valid Fernet key") from exc


def encrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("Secret cannot be empty")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("Encrypted secret cannot be empty")
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise EncryptionConfigurationError("Unable to decrypt secret") from exc
