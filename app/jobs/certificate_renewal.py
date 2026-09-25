from sqlalchemy import select

from app import scheduler
from app.core.managed_certificates import ManagedCertificateService
from app.db import GetDB
from app.db.models import Node, NodeStatus
from app.operation import OperatorType
from app.operation.node import NodeOperation
from app.utils.logger import get_logger
from config import runtime_settings

logger = get_logger("certificate-renewal")


async def scheduled_certificate_renewal() -> None:
    if not runtime_settings.role.runs_scheduler:
        return
    async with GetDB() as db:
        try:
            service = ManagedCertificateService()
            changed = await service.process_settings(db)
            if changed:
                logger.info("Managed certificate lifecycle updated %d domain(s)", changed)

            domains = await service.list_domains(db)
            pending_node_ids = {
                domain.node_id
                for domain in domains
                if domain.node_id is not None
                and domain.status in ("active", "expiring")
                and domain.deployment_status == "not_deployed"
                and service.store.exists(domain.domain)
            }
            if pending_node_ids:
                result = await db.execute(
                    select(Node.id).where(Node.id.in_(pending_node_ids), Node.status == NodeStatus.connected)
                )
                connected_node_ids = [row[0] for row in result.all()]
                node_operator = NodeOperation(operator_type=OperatorType.SYSTEM)
                for node_id in connected_node_ids:
                    try:
                        await node_operator.connect_single_node(db, node_id, force_start=True)
                    except Exception:
                        logger.exception("Managed certificate deployment failed for node %s", node_id)
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
