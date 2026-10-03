from datetime import UTC, datetime as dt

from app import scheduler
from app.db import GetDB
from app.db.models import BackupSchedule
from app.services.backup import apply_backup_retention, create_backup, get_backup_schedule, send_backup_to_telegram
from app.utils.logger import get_logger
from config import runtime_settings

logger = get_logger("backup-scheduler")


def _period_key(now: dt, schedule: BackupSchedule) -> str:
    if schedule.frequency == "weekly":
        return f"{now.isocalendar().year}-W{now.isocalendar().week}"
    if schedule.frequency == "monthly":
        return f"{now.year}-{now.month:02d}"
    return now.date().isoformat()


def _is_due(now: dt, schedule: BackupSchedule) -> bool:
    if not schedule.enabled:
        return False
    if schedule.frequency == "interval":
        if not schedule.interval_minutes:
            return False
        if schedule.last_run_at is None:
            return True
        elapsed = (now - schedule.last_run_at.astimezone(UTC)).total_seconds()
        return elapsed >= schedule.interval_minutes * 60
    if now.hour != schedule.hour or now.minute != schedule.minute:
        return False
    if schedule.frequency == "weekly" and now.weekday() != schedule.weekday:
        return False
    if schedule.frequency == "monthly" and now.day != schedule.day_of_month:
        return False
    if schedule.last_run_at is None:
        return True
    return _period_key(now, schedule) != _period_key(schedule.last_run_at.astimezone(UTC), schedule)


async def scheduled_backup() -> None:
    if not runtime_settings.role.runs_scheduler:
        return
    async with GetDB() as db:
        schedule = await get_backup_schedule(db)
        now = dt.now(UTC)
        if not _is_due(now, schedule):
            return
        try:
            backup = await create_backup(db, created_by=None, note=f"scheduled:{schedule.frequency}")
            try:
                await send_backup_to_telegram(db, backup)
                backup.metadata_json = {**(backup.metadata_json or {}), "telegram_delivery": "sent"}
                await db.commit()
                logger.info("Scheduled backup sent to Telegram: %s", backup.filename)
            except Exception as telegram_exc:
                backup.metadata_json = {
                    **(backup.metadata_json or {}),
                    "telegram_delivery": "failed",
                    "telegram_error": str(telegram_exc)[:1000],
                }
                await db.commit()
                logger.exception("Scheduled backup Telegram delivery failed: %s", backup.filename)
            schedule.last_run_at = now
            await db.commit()
            deleted = await apply_backup_retention(db, schedule.retention_count)
            logger.info("Scheduled backup created: %s; retention deleted=%s", backup.filename, deleted)
        except Exception:
            logger.exception("Scheduled backup failed")


# Persisted schedule is intentionally opt-in. The scheduler wakes once per minute and
# evaluates the single persisted schedule, so disabled/default installs perform no backup.
if runtime_settings.role.runs_scheduler:
    scheduler.add_job(scheduled_backup, "cron", minute="*", id="backup_schedule_tick", replace_existing=True)
