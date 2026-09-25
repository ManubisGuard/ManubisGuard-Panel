from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.core.certificate_store import CertificateArtifactStore
from app.db.models import CoreType
from app.models.settings import ManagedDomain


@dataclass(frozen=True)
class ManagedCertificateRuntime:
    core: Any
    eligible_domain_ids: tuple[str, ...]
    injected_domain_ids: tuple[str, ...]
    skipped_domain_ids: tuple[str, ...]
    tls_inbound_count: int


def _pem_lines(value: str) -> list[str]:
    return value.strip().splitlines()


def _certificate_fingerprint(value: str) -> str:
    return sha256(value.strip().encode()).hexdigest()


def _certificate_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _is_tls_inbound(inbound: dict[str, Any]) -> bool:
    stream = inbound.get("streamSettings")
    return isinstance(stream, dict) and stream.get("security") == "tls"


def _ensure_certificate_list(tls_settings: dict[str, Any]) -> list[dict[str, Any]]:
    certificates = tls_settings.get("certificates")
    if certificates is None:
        certificates = []
        tls_settings["certificates"] = certificates
    if isinstance(certificates, dict):
        certificates = [certificates]
        tls_settings["certificates"] = certificates
    if not isinstance(certificates, list):
        raise ValueError("Xray TLS certificates must be a list or object")
    result = [item for item in certificates if isinstance(item, dict)]
    if len(result) != len(certificates):
        tls_settings["certificates"] = result
    return result


def build_runtime_core(
    core: Any,
    domains: list[ManagedDomain],
    store: CertificateArtifactStore | None = None,
) -> ManagedCertificateRuntime:
    if core is None or getattr(core, "type", None) != CoreType.xray:
        return ManagedCertificateRuntime(core=core, eligible_domain_ids=(), injected_domain_ids=(), skipped_domain_ids=(), tls_inbound_count=0)

    store = store or CertificateArtifactStore()
    runtime_core = core.copy()
    tls_inbound_count = 0
    tls_settings_seen: list[dict[str, Any]] = []

    for inbound in runtime_core.get("inbounds", []):
        if not isinstance(inbound, dict) or not _is_tls_inbound(inbound):
            continue
        stream = inbound["streamSettings"]
        tls_settings = stream.get("tlsSettings")
        if not isinstance(tls_settings, dict):
            continue
        _ensure_certificate_list(tls_settings)
        tls_settings_seen.append(tls_settings)
        tls_inbound_count += 1

    eligible: list[str] = []
    injected: list[str] = []
    skipped: list[str] = []
    if not tls_settings_seen:
        return ManagedCertificateRuntime(runtime_core, (), (), (), 0)

    seen_fingerprints: set[str] = set()
    for tls_settings in tls_settings_seen:
        for certificate in tls_settings["certificates"]:
            fingerprint = _certificate_fingerprint(_certificate_text(certificate.get("certificate")))
            if fingerprint:
                seen_fingerprints.add(fingerprint)

    for domain in domains:
        if domain.status not in ("active", "expiring"):
            continue
        eligible.append(domain.id)
        if not store.exists(domain.domain):
            skipped.append(domain.id)
            continue

        certificate_pem, private_key_pem = store.load(domain.domain)
        cert_fp = _certificate_fingerprint(certificate_pem)
        entry = {"certificate": _pem_lines(certificate_pem), "key": _pem_lines(private_key_pem)}
        if cert_fp in seen_fingerprints:
            injected.append(domain.id)
            continue

        for tls_settings in tls_settings_seen:
            tls_settings["certificates"].insert(0, dict(entry))
        seen_fingerprints.add(cert_fp)
        injected.append(domain.id)

    return ManagedCertificateRuntime(
        runtime_core,
        tuple(eligible),
        tuple(injected),
        tuple(skipped),
        tls_inbound_count,
    )
