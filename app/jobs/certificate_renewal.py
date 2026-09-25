from app import scheduler
from app.core.managed_certificates import ManagedCertificateService
from app.db import GetDB
from app.utils.logger import get_logger
from config import runtime_settings

logger = get_logger("certificate-renewal")


async def scheduled_certificate_renewal() -> None:
    if not runtime_settings.role.runs_scheduler:
        return
    async with GetDB() as db:
        try:
            changed = await ManagedCertificateService().process_settings(db)
            if changed:
                logger.info("Managed certificate lifecycle updated %d domain(s)", changed)
        except Exception:
            logger.exception("Managed certificate renewal tick failed")


if runtime_settings.role.runs_scheduler:
    scheduler.add_job(
        scheduled_certificate_renewal,
        "interval",
        minutes=15,
        id="managed_certificate_renewal_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
