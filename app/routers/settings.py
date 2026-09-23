from fastapi import APIRouter, Depends

from app.core.certificate_intelligence import DomainCertificateInspector
from app.core.domain_intelligence import DomainIntelligence
from app.db import AsyncSession, get_db
from app.models.domain_intelligence import (
    DomainCertificateResult,
    DomainIntelligenceRequest,
    DomainIntelligenceResult,
)
from app.models.settings import General, SettingsSchema
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


@router.put("", response_model=SettingsSchema)
async def modify_settings(
    modify: SettingsSchema, db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings", "update"))
):
    return await settings_operator.modify_settings(db, modify)
