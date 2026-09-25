from app import scheduler
from app.db import GetDB
from app.services.backup import create_backup
from app.utils.logger import get_logger
from config import runtime_settings

logger = get_logger("backup-scheduler")


async def scheduled_backup() -> None:
    if not runtime_settings.role.runs_scheduler:
        return
    async with GetDB() as db:
        try:
            backup = await create_backup(db, created_by=None, note="scheduled")
            logger.info("Scheduled backup created: %s", backup.filename)
        except Exception:
            logger.exception("Scheduled backup failed")


# The scheduler is deliberately opt-in until the Settings UI exposes a persisted
# schedule. Set MANUBISGUARD_BACKUP_SCHEDULE=daily|weekly|monthly to activate it.
schedule = __import__("os").getenv("MANUBISGUARD_BACKUP_SCHEDULE", "inactive").lower()
if runtime_settings.role.runs_scheduler and schedule != "inactive":
    if schedule == "daily":
        scheduler.add_job(scheduled_backup, "cron", hour=2, minute=0, id="backup_daily", replace_existing=True)
    elif schedule == "weekly":
        scheduler.add_job(
            scheduled_backup, "cron", day_of_week="mon", hour=2, minute=0, id="backup_weekly", replace_existing=True
        )
    elif schedule == "monthly":
        scheduler.add_job(scheduled_backup, "cron", day=1, hour=2, minute=0, id="backup_monthly", replace_existing=True)
