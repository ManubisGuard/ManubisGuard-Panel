from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.db import AsyncSession, get_db
from app.db.models import Backup
from app.models.admin import AdminDetails
from app.models.backup import (
    BackupCheckResponse,
    BackupCreate,
    BackupListResponse,
    BackupResponse,
    BackupTelegramConfigure,
)
from app.routers.authentication import require_permission
from app.services.backup import check_backup, configure_telegram, create_backup, delete_backup, list_backups

router = APIRouter(prefix="/api/admin/backup", tags=["Admin Backup"])
UPLOAD_DIR = Path("/var/lib/manubisguard/backups")
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
    target = UPLOAD_DIR / f"upload-{admin.id}-{filename}"
    size = 0
    try:
        with target.open("wb") as handle:
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
        await db.refresh(backup)
        return backup
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception as exc:
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


@router.get("/list", response_model=BackupListResponse)
async def get_backup_history(
    db: AsyncSession = Depends(get_db),
    _: AdminDetails = Depends(require_permission("settings", "read")),
):
    items, total = await list_backups(db)
    return BackupListResponse(items=items, total=total)


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
