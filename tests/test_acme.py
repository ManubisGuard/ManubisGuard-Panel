import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.acme import (
    AcmeCertificateClient,
    AcmeError,
    AcmeHttp01ChallengeStore,
    ManagedCertificateEngine,
    _AcmeAccountStore,
)
from app.core.certificate_store import CertificateArtifactStore
from app.models.settings import ManagedDomain


@pytest.mark.asyncio
async def test_http01_challenge_store_persists_and_cleans_up(tmp_path: Path):
    store = AcmeHttp01ChallengeStore(tmp_path)
    token = "a" * 43

    await store.present(token, "token-thumbprint")
    assert store.get(token) == "token-thumbprint"
    assert (tmp_path / "_acme" / "http-01" / token).stat().st_mode & 0o777 == 0o600

    await store.cleanup(token)
    assert store.get(token) is None


@pytest.mark.asyncio
async def test_http01_challenge_store_rejects_unsafe_token(tmp_path: Path):
    store = AcmeHttp01ChallengeStore(tmp_path)

    with pytest.raises(ValueError):
        await store.present("../escape", "value")

    with pytest.raises(ValueError):
        store.get("../escape")


def test_acme_account_store_reuses_persistent_es256_key(tmp_path: Path):
    store = _AcmeAccountStore(tmp_path, "https://acme.test/directory")
    first = store.load_or_create()
    second = store.load_or_create()

    assert isinstance(first, ec.EllipticCurvePrivateKey)
    assert first.private_numbers() == second.private_numbers()
    assert store.directory.stat().st_mode & 0o777 == 0o700
    assert store.key_path.stat().st_mode & 0o777 == 0o600


def test_acme_jws_uses_jwk_before_account_creation(tmp_path: Path):
    store = _AcmeAccountStore(tmp_path, "https://acme.test/directory")
    client = AcmeCertificateClient(
        certificate_store=CertificateArtifactStore(tmp_path),
        challenge_provider=AcmeHttp01ChallengeStore(tmp_path),
        directory_url="https://acme.test/directory",
    )
    client._account_key = store.load_or_create()
    client._nonce = "nonce"

    first = client._signed_payload("https://acme.test/new-account", {"termsOfServiceAgreed": True}, use_jwk=True)
    protected = json.loads(base64.urlsafe_b64decode(first["protected"] + "=="))

    assert "jwk" in protected
    assert "kid" not in protected
    assert protected["nonce"] == "nonce"


def test_acme_jws_uses_kid_after_account_creation(tmp_path: Path):
    store = _AcmeAccountStore(tmp_path, "https://acme.test/directory")
    client = AcmeCertificateClient(
        certificate_store=__import__("app.core.certificate_store", fromlist=["CertificateArtifactStore"]).CertificateArtifactStore(tmp_path),
        challenge_provider=AcmeHttp01ChallengeStore(tmp_path),
        directory_url="https://acme.test/directory",
    )
    client._account_key = store.load_or_create()
    client._account_url = "https://acme.test/acct/123"
    client._nonce = "nonce"

    body = client._signed_payload("https://acme.test/new-order", {"identifiers": []})
    protected = json.loads(base64.urlsafe_b64decode(body["protected"] + "=="))

    assert protected["kid"] == "https://acme.test/acct/123"
    assert "jwk" not in protected


def test_acme_csr_contains_requested_domain():
    client = object.__new__(AcmeCertificateClient)
    key, csr_der = client._build_csr("edge.example.com")

    from cryptography import x509

    csr = x509.load_der_x509_csr(csr_der)
    san = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value

    assert csr.subject.rfc4514_string() == "CN=edge.example.com"
    assert san.get_values_for_type(x509.DNSName) == ["edge.example.com"]
    assert key.key_size == 2048


@pytest.mark.asyncio
async def test_managed_certificate_engine_rejects_cloudflare_until_dns01_is_available(tmp_path: Path):
    engine = ManagedCertificateEngine(
        CertificateArtifactStore(tmp_path)
    )
    domain = ManagedDomain(
        id="domain-1",
        domain="edge.example.com",
        certificate_method="cloudflare",
    )

    with pytest.raises(AcmeError, match="Cloudflare DNS-01 is not implemented"):
        await engine.issue(domain)
