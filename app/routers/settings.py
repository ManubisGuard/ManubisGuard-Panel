from fastapi import APIRouter, Depends

from app.core.certificate_intelligence import DomainCertificateInspector
from app.core.domain_intelligence import DomainIntelligence
from app.core.managed_certificates import ManagedCertificateService
from app.db import AsyncSession, get_db
from app.models.domain_intelligence import (
    DomainCertificateResult,
    DomainIntelligenceRequest,
    DomainIntelligenceResult,
)
from app.models.managed_certificates import (
    CertificateIssueRequest,
    CertificateLifecycleResponse,
    ExistingCertificateInstallRequest,
)
from app.models.settings import General, ManagedDomain, SettingsSchema
from app.operation import OperatorType
from app.operation.settings import SettingsOperation
from app.utils import responses

from .authentication import require_permission

settings_operator = SettingsOperation(operator_type=OperatorType.API)
router = APIRouter(tags=["Settings"], prefix="/api/settings", responses={401: responses._401, 403: responses._403})


@router.get("", response_model=SettingsSchema)
async def get_settings(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings", "read"))):
    return await settings_operator.get_settings(db)


@router.get("/general", response_model=General)
async def get_general_settings(
    db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings", "read_general"))
):
    return await settings_operator.get_general_settings(db)


@router.post("/domains/intelligence", response_model=DomainIntelligenceResult)
async def inspect_domain(
    request: DomainIntelligenceRequest,
    _=Depends(require_permission("settings", "read_general")),
):
    return await DomainIntelligence().inspect(request.domain)


@router.post("/domains/certificate", response_model=DomainCertificateResult)
async def inspect_domain_certificate(
    request: DomainIntelligenceRequest,
    _=Depends(require_permission("settings", "read_general")),
):
    return await DomainCertificateInspector().inspect(request.domain)


@router.post("/domains/certificate/issue", response_model=CertificateLifecycleResponse)
async def issue_managed_certificate(
    request: CertificateIssueRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("settings", "update")),
):
    settings = await settings_operator.get_settings(db)
    general = dict(settings.general or {})
    domains = list(general.get("domains") or [])
    primary = general.get("primary_domain")
    target = next((item for item in domains if item.get("id") == request.domain_id), None)
    if target is None and primary and primary.get("id") == request.domain_id:
        target = primary
    if target is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Managed domain not found")
    service = ManagedCertificateService()
    domain = await service.renew_if_due(ManagedDomain.model_validate(target), force=True)
    if primary and primary.get("id") == request.domain_id:
        general["primary_domain"] = domain.model_dump(mode="json")
    else:
        general["domains"] = [
            domain.model_dump(mode="json") if item.get("id") == request.domain_id else item for item in domains
        ]
    settings.general = general
    await db.commit()
    return {"domain": domain}


@router.post("/domains/certificate/install", response_model=CertificateLifecycleResponse)
async def install_existing_certificate(
    request: ExistingCertificateInstallRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("settings", "update")),
):
    settings = await settings_operator.get_settings(db)
    general = dict(settings.general or {})
    domains = list(general.get("domains") or [])
    primary = general.get("primary_domain")
    target = next((item for item in domains if item.get("id") == request.domain_id), None)
    is_primary = False
    if target is None and primary and primary.get("id") == request.domain_id:
        target = primary
        is_primary = True
    if target is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Managed domain not found")
    service = ManagedCertificateService()
    domain = service.install_existing(
        ManagedDomain.model_validate(target),
        request.certificate_pem,
        request.private_key_pem,
    )
    if is_primary:
        general["primary_domain"] = domain.model_dump(mode="json")
    else:
        general["domains"] = [
            domain.model_dump(mode="json") if item.get("id") == request.domain_id else item for item in domains
        ]
    settings.general = general
    await db.commit()
    return {"domain": domain}


@router.put("", response_model=SettingsSchema)
async def modify_settings(
    modify: SettingsSchema, db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings", "update"))
):
    return await settings_operator.modify_settings(db, modify)
