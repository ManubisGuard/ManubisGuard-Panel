from pydantic import BaseModel, Field

from app.models.settings import ManagedDomain


class CertificateIssueRequest(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    force: bool = False


class ExistingCertificateInstallRequest(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    certificate_pem: str = Field(min_length=1)
    private_key_pem: str = Field(min_length=1)


class CertificateLifecycleResponse(BaseModel):
    domain: ManagedDomain
