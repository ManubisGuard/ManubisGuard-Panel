from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import zipfile
from collections import deque
from datetime import UTC, datetime as dt
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup
from app.migration.runner import analyze_backup
from app.migration.timescale import filter_postgresql_compatibility_line
from app.models.backup import BackupCheckResponse
from config import database_settings

BACKUP_DIR = Path("/opt/pasarguard/backup/database")
MAX_BACKUP_SIZE = 10 * 1024 * 1024 * 1024
PG_DUMP_COMPLETE_MARKER = b"-- PostgreSQL database dump complete"


def _has_complete_dump_trailer(payload: bytes) -> bool:
    lines = payload.rstrip().splitlines()
    if not lines:
        return False
    last = lines[-1].strip()
    if last.startswith(b"\\unrestrict "):
        key = last.removeprefix(b"\\unrestrict ")
        if not re.fullmatch(rb"[A-Za-z0-9]+", key):
            return False
        if b"\\restrict " + key not in lines:
            return False
        lines.pop()
    elif any(line.startswith(b"\\restrict ") for line in lines):
        return False
    while lines and lines[-1].strip() in (b"", b"--"):
        lines.pop()
    return bool(lines and lines[-1] == PG_DUMP_COMPLETE_MARKER)


def _database_name() -> str:
    return (urlsplit(database_settings.url).path or "").lstrip("/")


def _pg_dump_connection() -> tuple[str, dict[str, str]]:
    """Keep the database password out of the pg_dump process argument list."""
    from urllib.parse import unquote

    parsed = urlsplit(database_settings.url)
    if parsed.password is None:
        raise RuntimeError("Database URL must contain a password for backup")
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    username = unquote(parsed.username or "")
    clean_host = f"[{host}]" if ":" in host else host
    safe_url = urlunsplit(("postgresql", f"{clean_host}:{port}", parsed.path, parsed.query, ""))
    return safe_url, {"PGPASSWORD": unquote(parsed.password), "PGUSER": username}


def _source_metadata(
    *,
    postgresql_version: str | None = None,
    timescaledb_version: str | None = None,
) -> dict[str, str | int]:
    return {
        "product": "pasarguard",
        "database": _database_name(),
        "created_at": dt.now(UTC).isoformat(),
        "postgresql": postgresql_version or os.getenv("POSTGRES_VERSION", "unknown"),
        # This must be read from pg_extension, not inferred from the Docker tag.
        # A backup restore needs the exact extension catalog version.
        "timescaledb": timescaledb_version or "unknown",
    }


def _pg_dump(*, target_pg_major: int | None) -> bytes:
    dump_url, pg_env = _pg_dump_connection()
    result = subprocess.run(
        [
            "pg_dump",
            "--format=plain",
            "--no-owner",
            "--no-privileges",
            "--quote-all-identifiers",
            dump_url,
        ],
        env={**os.environ, **pg_env},
        capture_output=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"pg_dump failed: {detail}")
    if not result.stdout:
        raise RuntimeError("pg_dump returned an empty backup")

    # The runtime image currently carries a newer pg_dump than the PG16 server.
    # Keep the compatibility filter deliberately narrow: only statements known
    # to be unsupported by the detected destination major are removed.
    filtered = bytearray()
    for raw_line in result.stdout.splitlines(keepends=True):
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if filter_postgresql_compatibility_line(line, target_pg_major=target_pg_major):
            continue
        filtered.extend(raw_line)
    if not filtered:
        raise RuntimeError("pg_dump produced an empty compatible backup")
    payload = bytes(filtered)
    # pg_dump writes this trailer only after the logical dump has completed.
    # Do not package a truncated dump as a successful backup even if the process
    # returned zero (e.g. interrupted output or an unexpected wrapper behavior).
    if not _has_complete_dump_trailer(payload):
        raise RuntimeError("pg_dump output is incomplete: PostgreSQL dump completion marker is missing")
    return payload


def _pg_dump_to_file(*, target_pg_major: int | None) -> tuple[Path, int]:
    """Produce a validated SQL dump on disk instead of buffering the DB in RAM.

    Call on a worker thread. Neither the raw dump nor the filtered dump is
    published as a backup until the complete trailer has been verified.
    """
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    dump_url, pg_env = _pg_dump_connection()
    with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, prefix=".raw-pg-dump-", delete=False) as raw:
        raw_path = Path(raw.name)
        try:
            result = subprocess.run(
                ["pg_dump", "--format=plain", "--no-owner", "--no-privileges",
                 "--quote-all-identifiers", dump_url],
                env={**os.environ, **pg_env}, stdout=raw, stderr=subprocess.PIPE,
                timeout=900, check=False,
            )
        except BaseException:
            raw_path.unlink(missing_ok=True)
            raise
    try:
        if result.returncode != 0:
            detail = (result.stderr or b"").decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"pg_dump failed: {detail}")
        with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, prefix=".filtered-pg-dump-", delete=False) as output:
            filtered_path = Path(output.name)
            try:
                tail: deque[bytes] = deque(maxlen=5)
                restrict_tokens: set[bytes] = set()
                seen_unrestrict = False
                written = 0
                with raw_path.open("rb") as source:
                    for raw_line in source:
                        if filter_postgresql_compatibility_line(
                            raw_line.decode("utf-8", errors="replace").rstrip("\r\n"),
                            target_pg_major=target_pg_major,
                        ):
                            continue
                        output.write(raw_line)
                        written += len(raw_line)
                        if written > MAX_BACKUP_SIZE:
                            raise RuntimeError("Uncompressed database dump exceeds backup size limit")
                        stripped = raw_line.strip()
                        tail.append(stripped)
                        if stripped.startswith(b"\\restrict "):
                            restrict_tokens.add(stripped.removeprefix(b"\\restrict "))
                lines = list(tail)
                while lines and lines[-1] in (b"", b"--"):
                    lines.pop()
                if lines and lines[-1].startswith(b"\\unrestrict "):
                    token = lines.pop().removeprefix(b"\\unrestrict ")
                    seen_unrestrict = bool(
                        re.fullmatch(rb"[A-Za-z0-9]+", token) and token in restrict_tokens
                    )
                    while lines and lines[-1] in (b"", b"--"):
                        lines.pop()
                if not lines or lines[-1] != PG_DUMP_COMPLETE_MARKER or (restrict_tokens and not seen_unrestrict):
                    raise RuntimeError("pg_dump output is incomplete: PostgreSQL dump completion marker is missing")
            except BaseException:
                filtered_path.unlink(missing_ok=True)
                raise
        return filtered_path, written
    finally:
        raw_path.unlink(missing_ok=True)


def _write_archive(
    payload: bytes | Path,
    filename: str,
    *,
    source_metadata: dict[str, str | int] | None = None,
) -> tuple[Path, int]:
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive_path = BACKUP_DIR / filename
    manifest = dict(source_metadata or _source_metadata())
    manifest.update({"format": "zip", "database_size": payload.stat().st_size if isinstance(payload, Path) else len(payload), "dump": "db.sql"})
    with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, prefix=".backup-", suffix=".tmp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            if isinstance(payload, Path):
                archive.write(payload, arcname="db.sql")
            else:
                archive.writestr("db.sql", payload)
        size = tmp_path.stat().st_size
        if size > MAX_BACKUP_SIZE:
            raise RuntimeError("Backup exceeds the configured maximum size")
        if archive_path.exists():
            raise RuntimeError(f"Refusing to overwrite existing backup: {archive_path.name}")
        os.link(tmp_path, archive_path)
        tmp_path.unlink()
        archive_path.chmod(0o600)
        return archive_path, size
    finally:
        tmp_path.unlink(missing_ok=True)


async def create_backup(db: AsyncSession, *, created_by: int | None, note: str | None = None) -> Backup:
    filename = f"pasarguard-db-{dt.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.zip"
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
        dump_path, dump_size = await asyncio.to_thread(_pg_dump_to_file, target_pg_major=target_pg_major)
        try:
            _path, size = await asyncio.to_thread(_write_archive, dump_path, filename, source_metadata=source_metadata)
        finally:
            dump_path.unlink(missing_ok=True)
        backup.size = size
        backup.status = "created"
        backup.metadata_json = {
            **(backup.metadata_json or {}),
            **source_metadata,
            "database_size": dump_size,
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
    result = await asyncio.to_thread(validate_backup, backup.backup_path)
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
    """Delete the DB record before removing the archive; never unlink on rollback.

    If the filesystem deletion fails, preserve the DB record when possible.
    Backup paths are restricted to the application backup root.
    """
    original_path = Path(backup.backup_path)
    path = original_path.resolve()
    root = BACKUP_DIR.resolve()
    if original_path.is_symlink():
        raise ValueError("Refusing to delete backup through a symlink")
    if backup.status == "telegram_configured":
        raise ValueError("Telegram settings cannot be deleted as a backup")
    if root not in path.parents:
        raise ValueError("Backup path escapes configured backup directory")
    # File must remain intact until the DB commit has succeeded.
    await db.execute(delete(Backup).where(Backup.id == backup.id))
    await db.commit()
    if original_path.is_file():
        original_path.unlink()


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
                .where(Backup.status.in_(("created", "valid")))
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
    if retention_count < 1:
        return 0
    backups = list((await db.execute(select(Backup).where(Backup.status != "telegram_configured").order_by(Backup.created_at.desc()))).scalars())
    backups = [
        backup for backup in backups
        if backup.status in ("created", "valid")
        and backup.created_by is None
        and str((backup.metadata_json or {}).get("note", "")).startswith("scheduled:")
    ]
    deleted = 0
    for backup in backups[retention_count:]:
        if backup.status == "telegram_configured":
            continue
        if (backup.metadata_json or {}).get("telegram_delivery") == "failed":
            continue
        await delete_backup(db, backup)
        deleted += 1
    return deleted
