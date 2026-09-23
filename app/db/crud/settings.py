from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Settings
from app.models.settings import SettingsSchema


async def get_settings(db: AsyncSession) -> Settings:
    """
    Retrieves the Settings.

    Args:
        db (AsyncSession): Settings information.

    Returns:
        Settings: Settings information.
    """
    return (await db.execute(select(Settings))).scalar_one_or_none()


async def modify_settings(db: AsyncSession, db_setting: Settings, modify: SettingsSchema) -> Settings:
    # Settings sections are modeled with defaults, so a normal model_dump() would
    # turn a partial update into a full replacement with default values. Preserve
    # only fields explicitly supplied by the caller.
    settings_data = modify.model_dump(exclude_unset=True, exclude_none=True)

    for key, value in settings_data.items():
        setattr(db_setting, key, value)

    await db.commit()
    await db.refresh(db_setting)
    return db_setting
