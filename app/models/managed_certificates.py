from pydantic import BaseModel, Field

from app.models.settings import ManagedDomain


class CertificateIssueRequest(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    force: bool = False
    domain: ManagedDomain | None = None
    primary: bool = False


class CloudflareCredentialRequest(BaseModel):
    api_token: str = Field(min_length=1, max_length=512)


class CloudflareCredentialResponse(BaseModel):
    configured: bool


class ExistingCertificateInstallRequest(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    certificate_pem: str = Field(min_length=1)
    private_key_pem: str = Field(min_length=1)
    domain: ManagedDomain | None = None
    primary: bool = False


class CertificateDeploymentRequest(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)


class CertificateLifecycleResponse(BaseModel):
    domain: ManagedDomain


class CertificateDeploymentResponse(BaseModel):
    domain: ManagedDomain
    deployed_domains: list[str] = Field(default_factory=list)
    skipped_domains: list[str] = Field(default_factory=list)
