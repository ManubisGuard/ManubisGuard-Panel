from __future__ import annotations

import json
import os
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime as dt
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup
from app.migration.runner import analyze_backup
from app.models.backup import BackupCheckResponse
from config import database_settings

BACKUP_DIR = Path("/var/lib/manubisguard/backups")
MAX_BACKUP_SIZE = 10 * 1024 * 1024 * 1024


def _database_name() -> str:
    return (urlsplit(database_settings.url).path or "").lstrip("/")


def _pg_dump_url() -> str:
    parsed = urlsplit(database_settings.url)
    return urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _source_metadata() -> dict[str, str | int]:
    return {
        "product": "manubisguard",
        "database": _database_name(),
        "created_at": dt.now(UTC).isoformat(),
        "postgresql": os.getenv("POSTGRES_VERSION", "unknown"),
    }


def _pg_dump() -> bytes:
    result = subprocess.run(
        ["pg_dump", "--format=plain", "--no-owner", "--no-privileges", _pg_dump_url()],
        capture_output=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"pg_dump failed: {detail}")
    if not result.stdout:
        raise RuntimeError("pg_dump returned an empty backup")
    return result.stdout


def _write_archive(payload: bytes, filename: str) -> tuple[Path, int]:
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive_path = BACKUP_DIR / filename
    manifest = _source_metadata()
    manifest.update({"format": "zip", "database_size": len(payload), "dump": "db.sql"})
    with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, prefix=".backup-", suffix=".tmp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            archive.writestr("db.sql", payload)
        size = tmp_path.stat().st_size
        if size > MAX_BACKUP_SIZE:
            raise RuntimeError("Backup exceeds the configured maximum size")
        os.replace(tmp_path, archive_path)
        archive_path.chmod(0o600)
        return archive_path, size
    finally:
        tmp_path.unlink(missing_ok=True)


async def create_backup(db: AsyncSession, *, created_by: int | None, note: str | None = None) -> Backup:
    filename = f"manubisguard-{dt.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.zip"
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
        payload = _pg_dump()
        _path, size = _write_archive(payload, filename)
        backup.size = size
        backup.status = "created"
        backup.metadata_json = {**(backup.metadata_json or {}), **_source_metadata(), "database_size": len(payload)}
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
    total = int((await db.execute(select(func.count(Backup.id)))).scalar_one())
    items = list((await db.execute(select(Backup).order_by(Backup.created_at.desc()))).scalars())
    return items, total


async def delete_backup(db: AsyncSession, backup: Backup) -> None:
    path = Path(backup.backup_path)
    if path.exists():
        path.unlink()
    await db.execute(delete(Backup).where(Backup.id == backup.id))
    await db.commit()


async def configure_telegram(db: AsyncSession, *, created_by: int, token: str, chat_id: str) -> Backup:
    from app.security.encryption import encrypt_secret

    encrypted = encrypt_secret(token)
    backup = Backup(
        filename="telegram-config",
        size=0,
        status="telegram_configured",
        backup_path="",
        metadata_json={"telegram_enabled": True},
        created_by=created_by,
        telegram_bot_token=encrypted,
        telegram_chat_id=chat_id,
    )
    db.add(backup)
    await db.commit()
    await db.refresh(backup)
    return backup


def decrypt_telegram_token(backup: Backup) -> str | None:
    if not backup.telegram_bot_token:
        return None
    from app.security.encryption import decrypt_secret

    return decrypt_secret(backup.telegram_bot_token)


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
    for key, value in values.items():
        setattr(schedule, key, value)
    schedule.updated_at = dt.now(UTC)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def apply_backup_retention(db: AsyncSession, retention_count: int) -> int:
    if retention_count < 1:
        return 0
    backups = list((await db.execute(select(Backup).order_by(Backup.created_at.desc()))).scalars())
    deleted = 0
    for backup in backups[retention_count:]:
        if backup.status == "telegram_configured":
            continue
        await delete_backup(db, backup)
        deleted += 1
    return deleted
