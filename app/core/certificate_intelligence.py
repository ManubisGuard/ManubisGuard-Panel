from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import UTC, datetime

from app.models.domain_intelligence import DomainCertificateResult
from app.models.settings import ManagedDomain


class DomainCertificateInspector:
    """Inspect the public TLS certificate presented on TCP/443.

    This performs one TLS connection to the requested hostname only. It does
    not scan arbitrary ports or enumerate network services.
    """

    def __init__(self, *, timeout: float = 8.0, expiring_days: int = 30):
        self.timeout = timeout
        self.expiring_days = expiring_days

    async def inspect(self, domain: str) -> DomainCertificateResult:
        normalized = ManagedDomain(id="certificate-inspection", domain=domain).domain
        return await asyncio.get_running_loop().run_in_executor(None, self._inspect_sync, normalized)

    def _inspect_sync(self, domain: str) -> DomainCertificateResult:
        checked_at = datetime.now(UTC)
        context = ssl.create_default_context()

        try:
            with socket.create_connection((domain, 443), timeout=self.timeout) as raw_socket:
                with context.wrap_socket(raw_socket, server_hostname=domain) as tls_socket:
                    certificate = tls_socket.getpeercert()
                    if not certificate:
                        return DomainCertificateResult(
                            domain=domain,
                            checked_at=checked_at,
                            reachable=True,
                            error="CertificateUnavailable",
                            status="invalid",
                        )

                    expires_at = datetime.strptime(
                        certificate["notAfter"], "%b %d %H:%M:%S %Y %Z"
                    ).replace(tzinfo=UTC)
                    now = datetime.now(UTC)
                    days_remaining = (expires_at - now).days
                    san = [
                        value
                        for kind, value in certificate.get("subjectAltName", ())
                        if kind == "DNS"
                    ]
                    subject = self._name_value(certificate.get("subject", ()))
                    issuer = self._name_value(certificate.get("issuer", ()))
                    valid = expires_at > now
                    status = (
                        "expired"
                        if not valid
                        else "expiring"
                        if days_remaining <= self.expiring_days
                        else "valid"
                    )

                    return DomainCertificateResult(
                        domain=domain,
                        checked_at=checked_at,
                        reachable=True,
                        valid=valid,
                        expires_at=expires_at,
                        days_remaining=days_remaining,
                        subject=subject,
                        issuer=issuer,
                        serial_number=certificate.get("serialNumber"),
                        tls_version=tls_socket.version(),
                        san=san,
                        status=status,
                    )
        except (OSError, ssl.SSLError, ValueError) as exc:
            return DomainCertificateResult(
                domain=domain,
                checked_at=checked_at,
                reachable=False,
                error=type(exc).__name__,
                status="unreachable",
            )

    @staticmethod
    def _name_value(name: tuple[tuple[tuple[str, str], ...], ...] | tuple) -> str | None:
        for relative_name in name:
            for key, value in relative_name:
                if key == "commonName":
                    return value
        return None
