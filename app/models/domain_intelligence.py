from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class DomainDNSResult(BaseModel):
    a: list[str] = Field(default_factory=list)
    aaaa: list[str] = Field(default_factory=list)
    cname: str | None = None
    nameservers: list[str] = Field(default_factory=list)


class DomainHTTPProbe(BaseModel):
    url: str
    reachable: bool = False
    status_code: int | None = None
    final_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    error: str | None = None


class DomainIntelligenceResult(BaseModel):
    domain: str
    checked_at: datetime
    dns: DomainDNSResult
    http: DomainHTTPProbe
    https: DomainHTTPProbe
    tls_valid: bool | None = None
    service_hints: list[str] = Field(default_factory=list)
    status: Literal["unreachable", "dns_only", "http_only", "https", "redirected", "healthy"] = "unreachable"

    @classmethod
    def now(cls, domain: str, dns: DomainDNSResult, http: DomainHTTPProbe, https: DomainHTTPProbe):
        service_hints: list[str] = []
        if http.reachable:
            service_hints.append("http:80")
        if https.reachable:
            service_hints.append("https:443")

        tls_valid = https.reachable if https.url.startswith("https://") else None
        redirected = any(http.redirect_chain) or any(https.redirect_chain)

        if https.reachable:
            status = "redirected" if redirected else "healthy"
        elif http.reachable:
            status = "http_only"
        elif dns.a or dns.aaaa or dns.cname:
            status = "dns_only"
        else:
            status = "unreachable"

        return cls(
            domain=domain,
            checked_at=datetime.now(timezone.utc),
            dns=dns,
            http=http,
            https=https,
            tls_valid=tls_valid,
            service_hints=service_hints,
            status=status,
        )


class DomainIntelligenceRequest(BaseModel):
    domain: str


class DomainCertificateResult(BaseModel):
    domain: str
    checked_at: datetime
    reachable: bool = False
    valid: bool | None = None
    expires_at: datetime | None = None
    days_remaining: int | None = None
    subject: str | None = None
    issuer: str | None = None
    serial_number: str | None = None
    tls_version: str | None = None
    san: list[str] = Field(default_factory=list)
    error: str | None = None
    status: Literal["valid", "expiring", "expired", "invalid", "unreachable"] = "unreachable"
