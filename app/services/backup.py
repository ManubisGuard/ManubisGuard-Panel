from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime as dt
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup
from app.migration.runner import analyze_backup
from app.migration.timescale import filter_postgresql_compatibility_line
from app.models.backup import BackupCheckResponse
from config import database_settings

BACKUP_DIR = Path("/opt/manubisguard/backup/database")
MAX_BACKUP_SIZE = 10 * 1024 * 1024 * 1024


def _database_name() -> str:
    return (urlsplit(database_settings.url).path or "").lstrip("/")


def _pg_dump_url() -> str:
    parsed = urlsplit(database_settings.url)
    return urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _source_metadata(
    *,
    postgresql_version: str | None = None,
    timescaledb_version: str | None = None,
) -> dict[str, str | int]:
    return {
        "product": "manubisguard",
        "database": _database_name(),
        "created_at": dt.now(UTC).isoformat(),
        "postgresql": postgresql_version or os.getenv("POSTGRES_VERSION", "unknown"),
        # This must be read from pg_extension, not inferred from the Docker tag.
        # A backup restore needs the exact extension catalog version.
        "timescaledb": timescaledb_version or "unknown",
    }


def _pg_dump(*, target_pg_major: int | None) -> BinaryIO:
    """Write pg_dump output to a temporary file instead of buffering the database in RAM."""
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = tempfile.TemporaryFile(mode="w+b", dir=BACKUP_DIR)
    stderr = tempfile.TemporaryFile(mode="w+b", dir=BACKUP_DIR)
    try:
        result = subprocess.run(
            [
                "pg_dump",
                "--format=plain",
                "--no-owner",
                "--no-privileges",
                "--quote-all-identifiers",
                _pg_dump_url(),
            ],
            stdout=payload,
            stderr=stderr,
            timeout=900,
            check=False,
        )
        if result.returncode != 0:
            stderr.seek(0, os.SEEK_END)
            stderr_size = stderr.tell()
            stderr.seek(max(0, stderr_size - 2000))
            detail = stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"pg_dump failed: {detail}")
        payload.seek(0, os.SEEK_END)
        if payload.tell() == 0:
            raise RuntimeError("pg_dump returned an empty backup")
        payload.seek(0)
        return payload
    except Exception:
        payload.close()
        raise
    finally:
        stderr.close()


def _write_archive(
    payload: BinaryIO,
    filename: str,
    *,
    target_pg_major: int | None,
    source_metadata: dict[str, str | int] | None = None,
) -> tuple[Path, int, int]:
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive_path = BACKUP_DIR / filename
    with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, prefix=".backup-", suffix=".tmp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        database_size = 0
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            with archive.open("db.sql", "w") as db_entry:
                for raw_line in payload:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if filter_postgresql_compatibility_line(line, target_pg_major=target_pg_major):
                        continue
                    db_entry.write(raw_line)
                    database_size += len(raw_line)
            if database_size == 0:
                raise RuntimeError("pg_dump produced an empty compatible backup")
            manifest = dict(source_metadata or _source_metadata())
            manifest.update({"format": "zip", "database_size": database_size, "dump": "db.sql"})
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        size = tmp_path.stat().st_size
        if size > MAX_BACKUP_SIZE:
            raise RuntimeError("Backup exceeds the configured maximum size")
        if archive_path.exists():
            raise RuntimeError(f"Refusing to overwrite existing backup: {archive_path.name}")
        os.link(tmp_path, archive_path)
        tmp_path.unlink()
        archive_path.chmod(0o600)
        return archive_path, size, database_size
    finally:
        tmp_path.unlink(missing_ok=True)


async def create_backup(db: AsyncSession, *, created_by: int | None, note: str | None = None) -> Backup:
    filename = f"manubisguard-db-{dt.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.zip"
    backup = Backup(
        filename=filename,
        size=0,
        source_version=os.getenv("MANUBISGUARD_VERSION"),
        source_db=_database_name(),
        status="validating",
        backup_path=str(BACKUP_DIR / filename),
        metadata_json={"note": note} if note else {},
        created_by=created_by,
    )
    db.add(backup)
    await db.flush()
    try:
        result = await db.execute(text("SHOW server_version_num"))
        server_version_num = int(result.scalar_one())
        target_pg_major = server_version_num // 10000
        version_result = await db.execute(text("SHOW server_version"))
        postgresql_version = str(version_result.scalar_one())
        extension_result = await db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        )
        extension_version = extension_result.scalar_one_or_none()
        source_metadata = _source_metadata(
            postgresql_version=postgresql_version,
            timescaledb_version=str(extension_version) if extension_version else None,
        )
        with _pg_dump(target_pg_major=target_pg_major) as payload:
            _path, size, database_size = _write_archive(
                payload,
                filename,
                target_pg_major=target_pg_major,
                source_metadata=source_metadata,
            )
        backup.size = size
        backup.status = "created"
        backup.metadata_json = {
            **(backup.metadata_json or {}),
            **source_metadata,
            "database_size": database_size,
        }
        await db.commit()
        await db.refresh(backup)
        return backup
    except Exception as exc:
        backup.status = "failed"
        backup.error_message = str(exc)[:4000]
        await db.commit()
        raise


def validate_backup(path: str | Path) -> BackupCheckResponse:
    analysis = analyze_backup(path)
    detection = analysis.detection
    preflight = analysis.preflight
    return BackupCheckResponse.model_validate(
        {
            "backup": {
                "id": 0,
                "created_at": dt.now(UTC),
                "filename": Path(path).name,
                "size": Path(path).stat().st_size,
                "source_version": None,
                "source_db": None,
                "status": "valid" if preflight.ok else "failed",
                "error_message": None if preflight.ok else "; ".join(preflight.blocking_errors),
                "backup_path": str(Path(path).resolve()),
                "metadata_json": {},
                "created_by": None,
                "schedule_id": None,
            },
            "valid": preflight.ok,
            "source_product": detection.source_product,
            "source_version": detection.schema_revision,
            "source_db": None,
            "database_size": None,
            "evidence": list(detection.evidence),
            "errors": list(preflight.blocking_errors),
            "warnings": list(preflight.warnings),
        }
    )


async def check_backup(db: AsyncSession, backup: Backup) -> BackupCheckResponse:
    result = validate_backup(backup.backup_path)
    backup.status = "valid" if result.valid else "failed"
    backup.error_message = None if result.valid else "; ".join(result.errors)
    backup.source_version = result.source_version
    backup.source_db = result.source_db
    backup.metadata_json = {**(backup.metadata_json or {}), "evidence": result.evidence, "warnings": result.warnings}
    await db.commit()
    await db.refresh(backup)
    result.backup = backup
    return result


async def list_backups(db: AsyncSession) -> tuple[list[Backup], int]:
    total = int((await db.execute(select(func.count(Backup.id)).where(Backup.status != "telegram_configured"))).scalar_one())
    items = list((await db.execute(select(Backup).where(Backup.status != "telegram_configured").order_by(Backup.created_at.desc()))).scalars())
    return items, total


async def delete_backup(db: AsyncSession, backup: Backup) -> None:
    path = Path(backup.backup_path)
    root = BACKUP_DIR.resolve()
    if path.is_symlink():
        raise ValueError("Refusing to delete a backup symlink")
    resolved = path.resolve()
    if root not in resolved.parents:
        raise ValueError("Refusing to delete a backup outside the configured backup directory")

    # Quarantine the archive before the DB transaction. If the DB delete/commit
    # fails, restore the original path so the row never points at a missing file.
    quarantine: Path | None = None
    if resolved.exists():
        quarantine = root / f".deleting-{uuid.uuid4().hex}.tmp"
        os.replace(resolved, quarantine)

    try:
        await db.execute(delete(Backup).where(Backup.id == backup.id))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        finally:
            if quarantine is not None and quarantine.exists() and not resolved.exists():
                os.replace(quarantine, resolved)
        raise

    if quarantine is not None:
        quarantine.unlink(missing_ok=True)


async def configure_telegram(db: AsyncSession, *, created_by: int | None, token: str, chat_id: str) -> Backup:
    from app.security.encryption import encrypt_secret

    encrypted = encrypt_secret(token)
    result = await db.execute(
        select(Backup).where(Backup.status == "telegram_configured").order_by(Backup.id.desc())
    )
    backup = result.scalars().first()
    if backup is None:
        backup = Backup(
            filename="telegram-config",
            size=0,
            status="telegram_configured",
            backup_path="",
            metadata_json={"telegram_enabled": True},
            created_by=created_by,
        )
        db.add(backup)

    backup.telegram_bot_token = encrypted
    backup.telegram_chat_id = chat_id
    backup.metadata_json = {"telegram_enabled": True}
    backup.created_by = created_by
    await db.commit()
    await db.refresh(backup)
    return backup


async def get_telegram_config(db: AsyncSession) -> tuple[str, str] | None:
    result = await db.execute(
        select(Backup).where(Backup.status == "telegram_configured").order_by(Backup.id.desc())
    )
    backup = result.scalars().first()
    if backup is None or not backup.telegram_bot_token or not backup.telegram_chat_id:
        return None
    token = decrypt_telegram_token(backup)
    if not token:
        return None
    return token, backup.telegram_chat_id


async def send_backup_to_telegram(db: AsyncSession, backup: Backup) -> bool:
    config = await get_telegram_config(db)
    if config is None:
        return False

    token, chat_id = config
    path = Path(backup.backup_path)
    if not path.is_file():
        raise FileNotFoundError(f"Backup file not found: {path}")

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    from app.settings import telegram_settings
    telegram = await telegram_settings()
    timeout = aiohttp.ClientTimeout(total=120)
    form = aiohttp.FormData()
    form.add_field("chat_id", chat_id)
    handle = await asyncio.to_thread(path.open, "rb")
    try:
        form.add_field("document", handle, filename=path.name, content_type="application/zip")
        async with aiohttp.ClientSession(timeout=timeout) as session, session.post(
            url, data=form, proxy=telegram.proxy_url
        ) as response:
            payload = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Telegram send failed ({response.status}): {payload[-1000:]}")
    finally:
        await asyncio.to_thread(handle.close)
    return True


def decrypt_telegram_token(backup: Backup) -> str | None:
    if not backup.telegram_bot_token:
        return None
    from app.security.encryption import decrypt_secret

    return decrypt_secret(backup.telegram_bot_token)


async def get_pending_telegram_backup(db: AsyncSession) -> Backup | None:
    backups = list(
        (
            await db.execute(
                select(Backup)
                .where(Backup.status == "created")
                .order_by(Backup.created_at.desc())
                .limit(20)
            )
        ).scalars()
    )
    for backup in backups:
        if (backup.metadata_json or {}).get("telegram_delivery") == "failed":
            return backup
    return None


async def get_backup_schedule(db: AsyncSession):
    from app.db.models import BackupSchedule

    schedule = (await db.execute(select(BackupSchedule).order_by(BackupSchedule.id))).scalars().first()
    if schedule is None:
        schedule = BackupSchedule()
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
    return schedule


async def configure_backup_schedule(db: AsyncSession, **values):
    schedule = await get_backup_schedule(db)
    interval_minutes = values.pop("interval_minutes", None)
    for key, value in values.items():
        setattr(schedule, key, value)
    if schedule.frequency == "interval":
        schedule.interval_minutes = interval_minutes
    schedule.updated_at = dt.now(UTC)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def apply_backup_retention(db: AsyncSession, retention_count: int) -> int:
    """Apply retention only to scheduler-owned backups, never manual or uploaded archives."""
    if retention_count < 1:
        return 0

    backups = list(
        (
            await db.execute(
                select(Backup)
                .where(Backup.status != "telegram_configured")
                .order_by(Backup.created_at.desc())
            )
        ).scalars()
    )
    scheduled_backups = [
        backup
        for backup in backups
        if str((backup.metadata_json or {}).get("note", "")).startswith("scheduled:")
        and (backup.metadata_json or {}).get("telegram_delivery") != "failed"
    ]

    deleted = 0
    for backup in scheduled_backups[retention_count:]:
        await delete_backup(db, backup)
        deleted += 1
    return deleted
