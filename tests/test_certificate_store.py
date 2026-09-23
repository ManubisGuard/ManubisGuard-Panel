from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.certificate_store import CertificateArtifactStore


def test_certificate_artifact_store_rejects_invalid_pair(tmp_path: Path):
    store = CertificateArtifactStore(tmp_path)

    result = store.save(
        "edge.example.com",
        "not-a-certificate",
        "not-a-private-key",
    )

    assert result.valid is False
    assert store.exists("edge.example.com") is False


def test_certificate_artifact_store_writes_and_loads_valid_pair(tmp_path: Path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "edge.example.com")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=90))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("edge.example.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    private_key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    store = CertificateArtifactStore(tmp_path)
    result = store.save("EDGE.EXAMPLE.COM", certificate_pem, private_key_pem)

    assert result.valid is True
    assert store.exists("edge.example.com") is True

    loaded_certificate, loaded_key = store.load("edge.example.com")
    assert loaded_certificate == certificate_pem
    assert loaded_key == private_key_pem

    assert (tmp_path / "edge.example.com" / "key.pem").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "edge.example.com" / "cert.pem").stat().st_mode & 0o777 == 0o644


def test_certificate_artifact_store_uses_configured_directory(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PASARGUARD_CERTIFICATE_DIR", str(tmp_path))
    store = CertificateArtifactStore()
    assert store.base_dir == tmp_path
