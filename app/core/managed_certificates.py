from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.acme import AcmeError, ManagedCertificateEngine
from app.core.certificate_store import CertificateArtifactStore
from app.db import AsyncSession
from app.db.models import Settings
from app.models.settings import ManagedDomain

RENEWAL_WINDOW_DAYS = 30
_RENEW_LOCK = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _domain_index(general: dict, domain_id: str) -> int:
    for index, item in enumerate(general.get("domains") or []):
        if item.get("id") == domain_id:
            return index
    primary = general.get("primary_domain") or {}
    if primary.get("id") == domain_id:
        return -1
    raise KeyError(domain_id)


def _get_domain(general: dict, domain_id: str) -> ManagedDomain:
    index = _domain_index(general, domain_id)
    data = general.get("primary_domain") if index == -1 else (general.get("domains") or [])[index]
    return ManagedDomain.model_validate(data)


def _put_domain(general: dict, domain: ManagedDomain) -> None:
    index = _domain_index(general, domain.id)
    payload = domain.model_dump(mode="json")
    if index == -1:
        general["primary_domain"] = payload
    else:
        general.setdefault("domains", [])[index] = payload


class ManagedCertificateService:
    """Durable certificate lifecycle over the existing Settings domain registry."""

    def __init__(self, store: CertificateArtifactStore | None = None):
        self.store = store or CertificateArtifactStore()
        self.engine = ManagedCertificateEngine(self.store)

    async def issue(self, domain: ManagedDomain) -> ManagedDomain:
        result = await self.engine.issue(domain)
        validation = result.certificate
        expires_at = validation.expires_at
        now = _now()
        return domain.model_copy(
            update={
                "status": "expiring"
                if expires_at and expires_at <= now + timedelta(days=RENEWAL_WINDOW_DAYS)
                else "active",
                "certificate_expires_at": _iso(expires_at),
                "certificate_issued_at": domain.certificate_issued_at or _iso(now),
                "certificate_renewed_at": _iso(now) if domain.certificate_issued_at else domain.certificate_renewed_at,
                "certificate_error": None,
                "renewal_attempts": 0,
                "next_renewal_at": _iso(expires_at - timedelta(days=RENEWAL_WINDOW_DAYS)) if expires_at else None,
                "deployment_status": "not_deployed",
                "certificate_deployed_at": None,
                "deployment_error": None,
            }
        )

    def install_existing(self, domain: ManagedDomain, certificate_pem: str, private_key_pem: str) -> ManagedDomain:
        validation = self.engine.install_existing(domain, certificate_pem, private_key_pem)
        if not validation.valid:
            raise AcmeError("Existing certificate failed validation: " + ", ".join(validation.errors))
        now = _now()
        expires_at = validation.expires_at
        return domain.model_copy(
            update={
                "status": "expiring"
                if expires_at and expires_at <= now + timedelta(days=RENEWAL_WINDOW_DAYS)
                else "active",
                "certificate_expires_at": _iso(expires_at),
                "certificate_issued_at": domain.certificate_issued_at or _iso(now),
                "certificate_error": None,
                "renewal_attempts": 0,
                "next_renewal_at": _iso(expires_at - timedelta(days=RENEWAL_WINDOW_DAYS)) if expires_at else None,
                "deployment_status": "not_deployed",
                "certificate_deployed_at": None,
                "deployment_error": None,
            }
        )

    async def list_domains(self, db: AsyncSession) -> list[ManagedDomain]:
        settings = (await db.execute(select(Settings))).scalar_one_or_none()
        if settings is None:
            return []
        general = settings.general or {}
        domains = [ManagedDomain.model_validate(item) for item in (general.get("domains") or [])]
        primary = general.get("primary_domain")
        if primary:
            domains.append(ManagedDomain.model_validate(primary))
        return domains

    async def list_node_domains(self, db: AsyncSession, node_id: int) -> list[ManagedDomain]:
        return [domain for domain in await self.list_domains(db) if domain.node_id == node_id]

    async def mark_deployment(
        self,
        db: AsyncSession,
        domain_ids: tuple[str, ...] | list[str],
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        settings = (await db.execute(select(Settings))).scalar_one_or_none()
        if settings is None:
            return
        general = dict(settings.general or {})
        domains = [ManagedDomain.model_validate(item) for item in (general.get("domains") or [])]
        primary = general.get("primary_domain")
        if primary:
            domains.append(ManagedDomain.model_validate(primary))
        now = _iso(_now()) if status == "deployed" else None
        for domain in domains:
            if domain.id in domain_ids:
                _put_domain(
                    general,
                    domain.model_copy(
                        update={
                            "deployment_status": status,
                            "certificate_deployed_at": now if status == "deployed" else domain.certificate_deployed_at,
                            "deployment_error": None if status == "deployed" else error,
                        }
                    ),
                )
        settings.general = general

    async def renew_if_due(self, domain: ManagedDomain, *, force: bool = False) -> ManagedDomain:
        expires_at = _parse(domain.certificate_expires_at)
        if domain.certificate_method == "existing":
            if expires_at and expires_at <= _now():
                return domain.model_copy(update={"status": "expired"})
            return domain.model_copy(
                update={
                    "status": "expiring"
                    if expires_at and expires_at <= _now() + timedelta(days=RENEWAL_WINDOW_DAYS)
                    else domain.status
                }
            )
        due = force or (expires_at is not None and expires_at <= _now() + timedelta(days=RENEWAL_WINDOW_DAYS))
        if not domain.auto_renew and not force:
            return domain
        if not due:
            return domain
        try:
            return await self.issue(domain)
        except Exception as exc:
            attempts = domain.renewal_attempts + 1
            return domain.model_copy(
                update={
                    "status": "failed",
                    "certificate_error": type(exc).__name__,
                    "renewal_attempts": attempts,
                    "next_renewal_at": _iso(_now() + timedelta(hours=min(24, 2 ** min(attempts, 5)))),
                }
            )

    async def process_settings(self, db: AsyncSession, *, force_domain_id: str | None = None) -> int:
        async with _RENEW_LOCK:
            settings = (await db.execute(select(Settings))).scalar_one_or_none()
            if settings is None:
                return 0
            general = dict(settings.general or {})
            domains = [ManagedDomain.model_validate(item) for item in (general.get("domains") or [])]
            primary = general.get("primary_domain")
            if primary:
                domains.append(ManagedDomain.model_validate(primary))
            changed = 0
            for domain in domains:
                if force_domain_id and domain.id != force_domain_id:
                    continue
                updated = await self.renew_if_due(domain, force=bool(force_domain_id))
                if updated != domain:
                    _put_domain(general, updated)
                    changed += 1
            if changed:
                settings.general = general
                await db.commit()
            return changed
