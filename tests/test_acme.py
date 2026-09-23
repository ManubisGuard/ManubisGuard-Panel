import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.core.acme import (
    AcmeCertificateClient,
    AcmeError,
    AcmeHttp01ChallengeStore,
    ManagedCertificateEngine,
    _AcmeAccountStore,
)
from app.core.certificate_store import CertificateArtifactStore
from app.models.settings import ManagedDomain
from app.routers.acme import acme_http01_challenge


@pytest.mark.asyncio
async def test_http01_challenge_store_persists_and_cleans_up(tmp_path: Path):
    store = AcmeHttp01ChallengeStore(tmp_path)
    token = "a" * 43

    await store.present("edge.example.com", token, "token-thumbprint")
    assert store.get(token) == "token-thumbprint"
    assert (tmp_path / "_acme" / "http-01" / token).stat().st_mode & 0o777 == 0o600

    await store.cleanup("edge.example.com", token)
    assert store.get(token) is None




@pytest.mark.asyncio
async def test_acme_http01_route_serves_persisted_challenge(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PASARGUARD_CERTIFICATE_DIR", str(tmp_path))
    store = AcmeHttp01ChallengeStore()
    token = "c" * 43
    await store.present(token, "route-value")

    response = await acme_http01_challenge(token)

    assert response.status_code == 200
    assert response.body == b"route-value"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_http01_challenge_store_rejects_unsafe_token(tmp_path: Path):
    store = AcmeHttp01ChallengeStore(tmp_path)

    with pytest.raises(ValueError):
        await store.present("edge.example.com", "../escape", "value")

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
        certificate_store=CertificateArtifactStore(tmp_path),
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


@pytest.mark.asyncio
async def test_acme_http01_issue_flow_is_atomic_and_cleans_challenge(tmp_path: Path, monkeypatch):
    certificate_store = CertificateArtifactStore(tmp_path)
    challenge_store = AcmeHttp01ChallengeStore(tmp_path)
    client = AcmeCertificateClient(
        certificate_store=certificate_store,
        challenge_provider=challenge_store,
        directory_url="https://acme.test/directory",
        poll_interval=0,
        session_factory=lambda **kwargs: FakeAcmeSession(),
        sleep=lambda _: asyncio.sleep(0),
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "edge.example.com")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=90))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("edge.example.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    monkeypatch.setattr(client, "_build_csr", lambda domain: (key, b"csr"))
    FakeAcmeSession.certificate_pem = certificate_pem

    result = await client.issue(
        ManagedDomain(
            id="domain-1",
            domain="edge.example.com",
            certificate_method="letsencrypt",
            email="admin@example.com",
        )
    )

    assert result.provider == "letsencrypt"
    assert result.certificate.valid is True
    assert certificate_store.exists("edge.example.com") is True
    assert challenge_store.get(FakeAcmeSession.challenge_token) is None
    assert FakeAcmeSession.challenge_presented is True


class FakeAcmeResponse:
    def __init__(self, status: int, body=b"", headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def read(self):
        return self._body

    async def json(self, content_type=None):
        return json.loads(self._body)


class FakeAcmeSession:
    challenge_token = "b" * 43
    challenge_presented = False
    certificate_pem = ""

    def __init__(self):
        self.authz_polls = 0
        self.order_polls = 0
        type(self).challenge_presented = False

    async def close(self):
        return None

    def get(self, url):
        if url == "https://acme.test/directory":
            return FakeAcmeResponse(
                200,
                json.dumps(
                    {
                        "newNonce": "https://acme.test/new-nonce",
                        "newAccount": "https://acme.test/new-account",
                        "newOrder": "https://acme.test/new-order",
                    }
                ).encode(),
            )
        if url == "https://acme.test/account/authz":
            return FakeAcmeResponse(404)
        raise AssertionError(f"unexpected GET {url}")

    def head(self, url, **kwargs):
        assert url == "https://acme.test/new-nonce"
        return FakeAcmeResponse(200, headers={"Replay-Nonce": "nonce-1"})

    def post(self, url, data, headers):
        assert headers["Content-Type"] == "application/jose+json"
        if url == "https://acme.test/new-account":
            return FakeAcmeResponse(
                201,
                b"{}",
                {"Location": "https://acme.test/account/1", "Replay-Nonce": "nonce-2"},
            )
        if url == "https://acme.test/new-order":
            return FakeAcmeResponse(
                201,
                json.dumps(
                    {
                        "status": "pending",
                        "authorizations": ["https://acme.test/authz/1"],
                        "finalize": "https://acme.test/finalize/1",
                    }
                ).encode(),
                {"Location": "https://acme.test/order/1", "Replay-Nonce": "nonce-3"},
            )
        if url == "https://acme.test/authz/1":
            self.authz_polls += 1
            if self.authz_polls == 1:
                body = {
                    "status": "pending",
                    "challenges": [
                        {
                            "type": "http-01",
                            "token": self.challenge_token,
                            "url": "https://acme.test/challenge/1",
                        }
                    ],
                }
            else:
                body = {"status": "valid"}
            return FakeAcmeResponse(200, json.dumps(body).encode(), {"Replay-Nonce": "nonce-auth"})
        if url == "https://acme.test/challenge/1":
            FakeAcmeSession.challenge_presented = True
            return FakeAcmeResponse(
                200,
                b'{"status":"processing"}',
                {"Replay-Nonce": "nonce-challenge"},
            )
        if url == "https://acme.test/finalize/1":
            return FakeAcmeResponse(
                200,
                json.dumps({"status": "processing"}).encode(),
                {"Replay-Nonce": "nonce-finalize"},
            )
        if url == "https://acme.test/order/1":
            self.order_polls += 1
            body = {"status": "valid", "certificate": "https://acme.test/cert/1"}
            return FakeAcmeResponse(200, json.dumps(body).encode(), {"Replay-Nonce": "nonce-order"})
        if url == "https://acme.test/cert/1":
            return FakeAcmeResponse(
                200,
                self.certificate_pem.encode(),
                {"Replay-Nonce": "nonce-cert"},
            )
        raise AssertionError(f"unexpected POST {url}")

