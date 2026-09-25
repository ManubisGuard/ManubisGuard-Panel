from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.certificate_store import CertificateArtifactStore
from app.core.managed_certificate_runtime import build_runtime_core
from app.db.models import CoreType
from app.models.settings import ManagedDomain


class FakeXRayCore(dict):
    type = CoreType.xray

    def copy(self):
        return FakeXRayCore(deepcopy(dict(self)))


def _make_pair(domain: str) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=90))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return (
        certificate.public_bytes(serialization.Encoding.PEM).decode(),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    )


def _core(*certificates: dict) -> FakeXRayCore:
    return FakeXRayCore(
        {
            "inbounds": [
                {
                    "tag": "tls-a",
                    "protocol": "vless",
                    "streamSettings": {
                        "security": "tls",
                        "tlsSettings": {"certificates": list(certificates)},
                    },
                },
                {
                    "tag": "plain",
                    "protocol": "vless",
                    "streamSettings": {"security": "none"},
                },
            ],
            "outbounds": [{"tag": "direct", "protocol": "freedom"}],
        }
    )
def test_build_runtime_core_injects_all_active_domains_on_tls_inbounds(tmp_path: Path):
    store = CertificateArtifactStore(tmp_path)
    cert_a, key_a = _make_pair("edge-a.example.com")
    cert_b, key_b = _make_pair("edge-b.example.com")
    store.save("edge-a.example.com", cert_a, key_a)
    store.save("edge-b.example.com", cert_b, key_b)

    domains = [
        ManagedDomain(id="a", domain="edge-a.example.com", node_id=7, status="active"),
        ManagedDomain(id="b", domain="edge-b.example.com", node_id=7, status="expiring"),
    ]
    original = _core()
    result = build_runtime_core(original, domains, store)

    assert result.eligible_domain_ids == ("a", "b")
    assert result.injected_domain_ids == ("a", "b")
    assert result.skipped_domain_ids == ()
    tls = result.core["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"]
    assert len(tls) == 2
    assert all("certificate" in item and "key" in item for item in tls)
    assert all("certificateFile" not in item and "keyFile" not in item for item in tls)
    assert original["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"] == []


def test_build_runtime_core_skips_missing_or_ineligible_certificates(tmp_path: Path):
    store = CertificateArtifactStore(tmp_path)
    cert, key = _make_pair("edge.example.com")
    store.save("edge.example.com", cert, key)

    domains = [
        ManagedDomain(id="active", domain="edge.example.com", status="active"),
        ManagedDomain(id="missing", domain="missing.example.com", status="active"),
        ManagedDomain(id="expired", domain="expired.example.com", status="expired"),
        ManagedDomain(id="failed", domain="failed.example.com", status="failed"),
    ]
    result = build_runtime_core(_core(), domains, store)

    assert result.eligible_domain_ids == ("active", "missing")
    assert result.injected_domain_ids == ("active",)
    assert result.skipped_domain_ids == ("missing",)
def test_build_runtime_core_does_not_duplicate_existing_managed_certificate(tmp_path: Path):
    store = CertificateArtifactStore(tmp_path)
    cert, key = _make_pair("edge.example.com")
    store.save("edge.example.com", cert, key)

    result = build_runtime_core(
        _core({"certificate": cert.splitlines(), "key": key.splitlines()}),
        [ManagedDomain(id="d1", domain="edge.example.com", status="active")],
        store,
    )

    tls = result.core["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"]
    assert len(tls) == 1
    assert result.injected_domain_ids == ("d1",)


def test_build_runtime_core_leaves_non_xray_core_untouched(tmp_path: Path):
    class FakeWireGuardCore(dict):
        type = CoreType.wg

    original = FakeWireGuardCore({"inbounds": [], "outbounds": []})
    result = build_runtime_core(
        original,
        [ManagedDomain(id="d1", domain="edge.example.com", status="active")],
        CertificateArtifactStore(tmp_path),
    )

    assert result.core is original
    assert result.eligible_domain_ids == ()
    assert result.injected_domain_ids == ()
    assert result.tls_inbound_count == 0


def test_build_runtime_core_respects_serve_tls_toggle(tmp_path: Path):
    store = CertificateArtifactStore(tmp_path)
    cert, key = _make_pair("edge-disabled.example.com")
    store.save("edge-disabled.example.com", cert, key)

    result = build_runtime_core(
        _core(),
        [ManagedDomain(id="disabled", domain="edge-disabled.example.com", status="active", serve_tls=False)],
        store,
    )

    assert result.eligible_domain_ids == ()
    assert result.injected_domain_ids == ()
    assert result.skipped_domain_ids == ()
    assert result.core["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"] == []
