from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.db import AsyncSession, get_db
from app.db.models import Backup
from app.models.admin import AdminDetails
from app.models.backup import (
    BackupCheckResponse,
    BackupCreate,
    BackupListResponse,
    BackupProductionRestoreRequest,
    BackupProductionRestoreResponse,
    BackupResponse,
    BackupScheduleConfigure,
    BackupScheduleResponse,
    BackupStagingRestoreResponse,
    BackupTelegramConfigure,
)
from app.routers.authentication import require_permission
from app.services.backup import (
    check_backup,
    configure_backup_schedule,
    configure_telegram,
    create_backup,
    delete_backup,
    get_backup_schedule,
    list_backups,
)
from config import database_settings

router = APIRouter(prefix="/api/admin/backup", tags=["Admin Backup"])
UPLOAD_DIR = Path("/opt/pasarguard/backup/database")
# Both application restore routes remain disabled until their executor uses an
# external disposable database and has a verified production rollback boundary.
APPLICATION_STAGING_RESTORE_ENABLED = False
MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024


@router.post("/create", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_backup(
    payload: BackupCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("settings", "update")),
):
    try:
        return await create_backup(db, created_by=admin.id, note=payload.note)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {exc}") from exc


@router.post("/configure-telegram", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def configure_backup_telegram(
    payload: BackupTelegramConfigure,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("settings", "update")),
):
    token = payload.telegram_bot_token
    chat_id = payload.telegram_chat_id
    if not token.strip() or not chat_id.strip():
        raise HTTPException(status_code=422, detail="Telegram bot token and chat ID are required")
    try:
        return await configure_telegram(db, created_by=admin.id, token=token.strip(), chat_id=chat_id.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Telegram configuration failed") from exc


@router.get("/schedule", response_model=BackupScheduleResponse)
async def get_schedule(
    db: AsyncSession = Depends(get_db), _: AdminDetails = Depends(require_permission("settings", "read"))
):
    return await get_backup_schedule(db)


@router.put("/schedule", response_model=BackupScheduleResponse)
async def update_schedule(
    payload: BackupScheduleConfigure,
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "update")),
):
    if payload.frequency == "interval":
        if payload.interval_minutes is None:
            raise HTTPException(status_code=422, detail="interval_minutes is required for interval schedules")
    elif payload.frequency == "weekly" and payload.weekday is None:
        raise HTTPException(status_code=422, detail="weekday is required for weekly schedules")
    elif payload.frequency == "monthly" and payload.day_of_month is None:
        raise HTTPException(status_code=422, detail="day_of_month is required for monthly schedules")
    return await configure_backup_schedule(db, **payload.model_dump())


@router.post("/upload", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def upload_backup(
    file: Annotated[UploadFile, File(...)],
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("settings", "update")),
):
    filename = Path(file.filename or "backup.zip").name
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP backup files are accepted")
    UPLOAD_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    UPLOAD_DIR.chmod(0o700)
    target = None
    committed = False
    size = 0
    try:
        with NamedTemporaryFile(dir=UPLOAD_DIR, prefix=f"upload-{admin.id}-", suffix=".zip", delete=False) as handle:
            target = Path(handle.name)
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="Backup file is too large")
                handle.write(chunk)
        backup = Backup(
            filename=filename,
            size=size,
            status="uploaded",
            backup_path=str(target),
            metadata_json={"upload": True},
            created_by=admin.id,
        )
        db.add(backup)
        await db.commit()
        committed = True
        await db.refresh(backup)
        return backup
    except HTTPException:
        if target is not None and not committed:
            target.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if target is not None and not committed:
            target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Backup upload failed: {exc}") from exc


@router.post("/check/{backup_id}", response_model=BackupCheckResponse)
async def check_uploaded_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "update")),
):
    backup = (await db.execute(select(Backup).where(Backup.id == backup_id))).scalar_one_or_none()
    if backup is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    try:
        return await check_backup(db, backup)
    except Exception as exc:
        backup.status = "failed"
        backup.error_message = str(exc)[:4000]
        await db.commit()
        raise HTTPException(status_code=422, detail=f"Backup validation failed: {exc}") from exc


@router.post("/restore/staging/{backup_id}", response_model=BackupStagingRestoreResponse)
async def restore_backup_to_staging(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "update")),
):
    """Restore only into a disposable DB; currently disabled fail-closed.

    The current staging helper creates its database on the configured production
    PostgreSQL cluster. Use the host-side --stage-test flow, which starts a
    network-isolated temporary container, until an external staging DB is wired.
    """
    if not APPLICATION_STAGING_RESTORE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Application staging restore is disabled because it would create a staging database on the production PostgreSQL cluster. Use `manubis restore <full-archive> --check` for non-destructive archive validation. Full restore testing must use the documented disposable round-trip harness, never the production API.",
        )
    backup = (await db.execute(select(Backup).where(Backup.id == backup_id))).scalar_one_or_none()
    if backup is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    if backup.status not in {"valid", "created", "uploaded"}:
        raise HTTPException(status_code=409, detail=f"Backup status does not permit staging restore: {backup.status}")
    from app.migration.runner import migrate_manubisguard_staging
    from app.migration.staging import MigrationSafetyError, create_staging_database, drop_staging_database

    staging = create_staging_database(database_settings.url)
    try:
        result = migrate_manubisguard_staging(
            backup.backup_path, staging, production_url=database_settings.url, timeout=900
        )
        return BackupStagingRestoreResponse(
            backup_id=backup.id,
            valid=result.valid,
            staging_database=staging.database_name,
            source_format=result.analysis.detection.format,
            source_product=result.analysis.detection.source_product,
            source_version=result.analysis.detection.schema_revision,
            pre_upgrade_counts=result.pre_upgrade_counts,
            post_upgrade_counts=result.post_upgrade_counts,
            transformations=list(result.transformations),
            errors=list(result.validation.blocking_errors),
            warnings=list(result.validation.warnings),
        )
    except (MigrationSafetyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        drop_staging_database(staging)


@router.post("/restore/production/{backup_id}", response_model=BackupProductionRestoreResponse)
async def restore_backup_to_production(
    backup_id: int,
    payload: BackupProductionRestoreRequest,
    _: AdminDetails = Depends(require_permission("settings", "update")),
):
    """Keep API production restore disabled until a verified rollback executor exists."""
    raise HTTPException(
        status_code=503,
        detail="Native production restore is disabled until destination preservation, a verified safety backup, and rollback are implemented and tested. No restore was attempted.",
    )


@router.get("/list", response_model=BackupListResponse)
async def get_backup_history(
    db: AsyncSession = Depends(get_db), _: AdminDetails = Depends(require_permission("settings", "read"))
):
    items, total = await list_backups(db)
    return BackupListResponse(items=items, total=total)


@router.get("/download/{backup_id}")
async def download_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "read")),
):
    backup = (await db.execute(select(Backup).where(Backup.id == backup_id))).scalar_one_or_none()
    if backup is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    path = Path(backup.backup_path).resolve()
    root = UPLOAD_DIR.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(path, media_type="application/zip", filename=backup.filename)


@router.delete("/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "update")),
):
    backup = (await db.execute(select(Backup).where(Backup.id == backup_id))).scalar_one_or_none()
    if backup is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    await delete_backup(db, backup)
