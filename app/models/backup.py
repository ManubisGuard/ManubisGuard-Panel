from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BackupStatus = Literal["created", "uploaded", "validating", "valid", "failed", "deleted"]


class BackupTelegramConfigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_bot_token: str = Field(min_length=1, max_length=256)
    telegram_chat_id: str = Field(min_length=1, max_length=128)


class BackupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class BackupRestore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_id: int


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    filename: str
    size: int
    source_version: str | None
    source_db: str | None
    status: BackupStatus | str
    error_message: str | None
    backup_path: str
    metadata_json: dict[str, Any] | None
    created_by: int | None
    schedule_id: int | None
    telegram_enabled: bool = False


class BackupCheckResponse(BaseModel):
    backup: BackupResponse
    valid: bool
    source_product: str | None = None
    source_version: str | None = None
    source_db: str | None = None
    database_size: int | None = None
    evidence: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BackupListResponse(BaseModel):
    items: list[BackupResponse]
    total: int
