from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class EncryptionConfigurationError(RuntimeError):
    """Raised when the backup encryption key is missing or invalid."""


def _fernet() -> Fernet:
    key = os.getenv("BACKUP_TELEGRAM_KEY")
    if not key:
        raise EncryptionConfigurationError("BACKUP_TELEGRAM_KEY is required")
    try:
        return Fernet(key)
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise EncryptionConfigurationError("BACKUP_TELEGRAM_KEY is not a valid Fernet key") from exc


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
