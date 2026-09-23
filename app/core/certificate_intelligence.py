from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.models.domain_intelligence import DomainCertificateResult, ExistingCertificateValidation
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
        try:
            with socket.create_connection((domain, 443), timeout=self.timeout) as raw_socket:
                try:
                    context = ssl.create_default_context()
                    with context.wrap_socket(raw_socket, server_hostname=domain) as tls_socket:
                        certificate = tls_socket.getpeercert()
                        return self._result_from_certificate(
                            domain, checked_at, certificate, tls_socket.version()
                        )
                except ssl.SSLError as verification_error:
                    # A certificate can be reachable but fail trust/hostname/expiry
                    # validation. Reconnect once without verification so the panel
                    # can report the actual certificate instead of "unreachable".
                    with socket.create_connection((domain, 443), timeout=self.timeout) as retry_socket:
                        context = ssl._create_unverified_context()
                        with context.wrap_socket(retry_socket, server_hostname=domain) as tls_socket:
                            certificate = tls_socket.getpeercert()
                            if not certificate:
                                raise
                            result = self._result_from_certificate(
                                domain, checked_at, certificate, tls_socket.version()
                            )
                            result.valid = False
                            result.status = "invalid"
                            result.error = type(verification_error).__name__
                            return result
        except (OSError, ssl.SSLError, ValueError) as exc:
            return DomainCertificateResult(
                domain=domain,
                checked_at=checked_at,
                reachable=False,
                error=type(exc).__name__,
                status="unreachable",
            )

    def _result_from_certificate(
        self,
        domain: str,
        checked_at: datetime,
        certificate: dict,
        tls_version: str | None,
    ) -> DomainCertificateResult:
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
        san = [value for kind, value in certificate.get("subjectAltName", ()) if kind == "DNS"]
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
            tls_version=tls_version,
            san=san,
            status=status,
        )

    @staticmethod
    def _name_value(name: tuple[tuple[tuple[str, str], ...], ...] | tuple) -> str | None:
        for relative_name in name:
            for key, value in relative_name:
                if key == "commonName":
                    return value
        return None


class ExistingCertificateValidator:
    """Validate an existing PEM certificate/private-key pair without storing secrets."""

    def validate(self, domain: str, certificate_pem: str, private_key_pem: str) -> ExistingCertificateValidation:
        normalized = ManagedDomain(id="certificate-validation", domain=domain).domain
        checked_at = datetime.now(UTC)
        errors: list[str] = []
        certificate = None
        private_key = None

        try:
            certificate = x509.load_pem_x509_certificate(certificate_pem.encode())
        except (ValueError, TypeError):
            errors.append("invalid_certificate_pem")

        try:
            private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        except (ValueError, TypeError):
            errors.append("invalid_private_key_pem")

        result = ExistingCertificateValidation(
            domain=normalized,
            checked_at=checked_at,
            certificate_present=certificate is not None,
            private_key_present=private_key is not None,
            errors=errors,
        )

        if certificate is None or private_key is None:
            return result

        now = datetime.now(UTC)
        expires_at = certificate.not_valid_after_utc
        not_before = certificate.not_valid_before_utc
        result.expires_at = expires_at
        result.days_remaining = (expires_at - now).days
        result.currently_valid = not_before <= now <= expires_at
        result.subject = self._x509_name_value(certificate.subject)
        result.issuer = self._x509_name_value(certificate.issuer)
        result.serial_number = format(certificate.serial_number, "x")
        result.san = self._dns_names(certificate)

        try:
            cert_public = certificate.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            key_public = private_key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            result.key_matches = cert_public == key_public
        except (TypeError, ValueError):
            result.key_matches = False

        result.domain_matches = self._domain_matches(normalized, result.san, result.subject)
        if not result.key_matches:
            errors.append("private_key_mismatch")
        if not result.domain_matches:
            errors.append("domain_mismatch")
        if not result.currently_valid:
            errors.append("certificate_expired_or_not_yet_valid")

        result.valid = not errors
        return result

    @staticmethod
    def _x509_name_value(name: x509.Name) -> str | None:
        attribute = name.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        return attribute[0].value if attribute else None

    @staticmethod
    def _dns_names(certificate: x509.Certificate) -> list[str]:
        try:
            extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        except x509.ExtensionNotFound:
            return []
        return sorted(set(extension.value.get_values_for_type(x509.DNSName)))

    @staticmethod
    def _domain_matches(domain: str, san: list[str], subject: str | None) -> bool:
        names = san or ([subject] if subject else [])
        for name in names:
            candidate = name.lower().rstrip(".")
            if candidate == domain:
                return True
            if (
                candidate.startswith("*.")
                and domain.endswith(candidate[1:])
                and domain.count(".") == candidate.count(".")
            ):
                return True
        return False
