from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import ssl
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, utils

from app.core.certificate_store import CertificateArtifactStore
from app.models.domain_intelligence import ExistingCertificateValidation
from app.models.settings import ManagedDomain


LETSENCRYPT_PRODUCTION_DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"
_ACME_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


class AcmeError(RuntimeError):
    """Raised when an ACME operation cannot be completed."""


class AcmeChallengeProvider(Protocol):
    challenge_type: str

    async def present(self, token: str, key_authorization: str) -> None:
        ...

    async def cleanup(self, token: str) -> None:
        ...


class AcmeHttp01ChallengeStore:
    """Persist HTTP-01 challenge responses in a shared filesystem."""

    def __init__(self, base_dir: str | Path | None = None):
        configured = base_dir if base_dir is not None else os.getenv("PASARGUARD_CERTIFICATE_DIR")
        self.base_dir = Path(configured) if configured else Path("/var/lib/PasarGuard/certs")
        self.challenge_dir = self.base_dir / "_acme" / "http-01"

    async def present(self, token: str, key_authorization: str) -> None:
        self._validate_token(token)
        if not key_authorization or len(key_authorization) > 1024:
            raise ValueError("Invalid ACME HTTP-01 key authorization.")

        self.challenge_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.challenge_dir, 0o700)

        target = self.challenge_dir / token
        fd, temporary = tempfile.mkstemp(prefix=f".{token}.", dir=self.challenge_dir)
        temporary_path = Path(temporary)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(key_authorization)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, target)
            os.chmod(target, 0o600)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    async def cleanup(self, token: str) -> None:
        self._validate_token(token)
        try:
            (self.challenge_dir / token).unlink()
        except FileNotFoundError:
            pass

    def get(self, token: str) -> str | None:
        self._validate_token(token)
        try:
            return (self.challenge_dir / token).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    @staticmethod
    def _validate_token(token: str) -> None:
        if not _ACME_TOKEN_RE.fullmatch(token):
            raise ValueError("Invalid ACME HTTP-01 challenge token.")


class _AcmeAccountStore:
    def __init__(self, base_dir: str | Path, directory_url: str):
        self.directory = Path(base_dir) / "_acme" / hashlib.sha256(directory_url.encode()).hexdigest()[:16]
        self.key_path = self.directory / "account.key"

    def load_or_create(self) -> ec.EllipticCurvePrivateKey:
        if self.key_path.is_file():
            key = serialization.load_pem_private_key(
                self.key_path.read_bytes(),
                password=None,
            )
            if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
                raise AcmeError("Stored ACME account key is not an ES256 P-256 private key.")
            return key

        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)

        key = ec.generate_private_key(ec.SECP256R1())
        encoded = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

        fd, temporary = tempfile.mkstemp(prefix=".account.", dir=self.directory)
        temporary_path = Path(temporary)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.key_path)
            os.chmod(self.key_path, 0o600)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return key


@dataclass(frozen=True)
class AcmeIssueResult:
    domain: str
    provider: str
    order_url: str
    certificate: ExistingCertificateValidation


class AcmeCertificateClient:
    """Small ACME v2 client using only aiohttp + cryptography."""

    def __init__(
        self,
        *,
        certificate_store: CertificateArtifactStore,
        challenge_provider: AcmeChallengeProvider,
        directory_url: str = LETSENCRYPT_PRODUCTION_DIRECTORY,
        timeout: float = 15.0,
        poll_interval: float = 2.0,
        max_polls: int = 30,
        session_factory=None,
        sleep=asyncio.sleep,
    ):
        self.certificate_store = certificate_store
        self.challenge_provider = challenge_provider
        self.directory_url = directory_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self._session_factory = session_factory
        self._sleep = sleep
        self._nonce: str | None = None
        self._account_url: str | None = None
        self._account_key: ec.EllipticCurvePrivateKey | None = None

    async def issue(self, managed_domain: ManagedDomain) -> AcmeIssueResult:
        domain = managed_domain.domain
        if domain.startswith("*."):
            raise AcmeError("HTTP-01 cannot issue wildcard certificates.")
        if self.challenge_provider.challenge_type != "http-01":
            raise AcmeError("Unsupported ACME challenge provider.")

        account_store = _AcmeAccountStore(self.certificate_store.base_dir, self.directory_url)
        self._account_key = account_store.load_or_create()
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        if self._session_factory:
            session = await self._session_factory(timeout=timeout)
        else:
            session = aiohttp.ClientSession(timeout=timeout)

        try:
            directory = await self._get_json(session, self.directory_url)
            await self._ensure_account(session, directory["newAccount"], managed_domain.email)
            order_url, order = await self._post_jws_json(
                session,
                directory["newOrder"],
                {"identifiers": [{"type": "dns", "value": domain}]},
            )

            tokens: list[str] = []
            try:
                await self._complete_authorizations(session, order, tokens)
                csr_key, csr = self._build_csr(domain)
                finalized = await self._post_jws_json(
                    session,
                    order["finalize"],
                    {"csr": self._b64(csr)},
                )
                finalized = await self._poll(
                    session,
                    order_url,
                    lambda payload: payload.get("status") in {"valid", "invalid"},
                    initial=finalized,
                )
                if finalized.get("status") != "valid":
                    raise AcmeError(self._problem_detail(finalized, "ACME order did not become valid."))

                certificate_url = finalized.get("certificate")
                if not certificate_url:
                    raise AcmeError("ACME order is valid but returned no certificate URL.")

                certificate_pem = await self._post_jws_text(session, certificate_url, "")
                key_pem = csr_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode()

                validation = self.certificate_store.save(domain, certificate_pem, key_pem)
                if not validation.valid:
                    raise AcmeError(f"Issued certificate failed local validation: {validation.errors}")

                return AcmeIssueResult(
                    domain=domain,
                    provider="letsencrypt",
                    order_url=order_url,
                    certificate=validation,
                )
            finally:
                for token in tokens:
                    await self.challenge_provider.cleanup(token)
        finally:
            await session.close()

    async def _complete_authorizations(self, session, order: dict, tokens: list[str]) -> None:
        for authorization_url in order.get("authorizations", []):
            authorization = await self._post_jws_json(session, authorization_url, "")
            status = authorization.get("status")
            if status == "valid":
                continue
            if status != "pending":
                raise AcmeError(self._problem_detail(authorization, "ACME authorization is not pending."))

            challenge = next(
                (item for item in authorization.get("challenges", []) if item.get("type") == "http-01"),
                None,
            )
            if not challenge:
                raise AcmeError("ACME server did not provide an HTTP-01 challenge.")

            token = str(challenge.get("token", ""))
            key_authorization = f"{token}.{self._account_thumbprint()}"
            await self.challenge_provider.present(token, key_authorization)
            tokens.append(token)

            await self._post_jws_json(session, challenge["url"], "")
            await self._poll(
                session,
                authorization_url,
                lambda payload: payload.get("status") in {"valid", "invalid", "expired", "revoked"},
                initial=await self._post_jws_json(session, authorization_url, ""),
            )
            final_authorization = await self._post_jws_json(session, authorization_url, "")
            if final_authorization.get("status") != "valid":
                raise AcmeError(self._problem_detail(final_authorization, "ACME HTTP-01 validation failed."))

    async def _ensure_account(self, session, account_url: str, email: str | None) -> str:
        if self._account_url:
            return self._account_url

        payload = {"termsOfServiceAgreed": True}
        if email:
            payload["contact"] = [f"mailto:{email}"]

        response = await self._post_jws_response(session, account_url, payload, use_jwk=True)
        location = response.headers.get("Location")
        if not location:
            raise AcmeError("ACME account creation did not return an account URL.")
        self._account_url = location
        return location

    async def _post_jws_json(self, session, url: str, payload):
        response = await self._post_jws_response(session, url, payload)
        try:
            return await response.json(content_type=None)
        except (TypeError, ValueError) as exc:
            raise AcmeError("ACME server returned invalid JSON.") from exc

    async def _post_jws_text(self, session, url: str, payload: str) -> str:
        response = await self._post_jws_response(session, url, payload)
        return await response.text()

    async def _post_jws_response(self, session, url: str, payload, *, use_jwk: bool = False):
        if not self._account_key:
            raise AcmeError("ACME account key is not initialized.")
        if not use_jwk and not self._account_url:
            raise AcmeError("ACME account URL is not initialized.")

        if not self._nonce:
            await self._refresh_nonce(session, url)

        body = self._signed_payload(url, payload, use_jwk=use_jwk)
        encoded_body = json.dumps(body, separators=(",", ":")).encode()
        for attempt in range(2):
            async with session.post(
                url,
                data=encoded_body,
                headers={"Content-Type": "application/jose+json", "Accept": "application/json"},
            ) as response:
                body_bytes = await response.read()
                self._nonce = response.headers.get("Replay-Nonce", self._nonce)
                if response.status < 400:
                    return _BufferedResponse(response.status, response.headers, body_bytes)
                if attempt == 0 and self._is_bad_nonce(body_bytes):
                    if self._nonce:
                        encoded_body = json.dumps(
                            self._signed_payload(url, payload, use_jwk=use_jwk),
                            separators=(",", ":"),
                        ).encode()
                        continue
                detail = body_bytes.decode(errors="replace")
                raise AcmeError(f"ACME request failed ({response.status}): {detail[:1000]}")
        raise AcmeError("ACME request failed after nonce retry.")

    async def _refresh_nonce(self, session, resource_url: str) -> None:
        directory = await self._get_json(session, self.directory_url)
        async with session.head(directory["newNonce"], timeout=self.timeout) as response:
            if response.status >= 400:
                raise AcmeError(f"ACME nonce request failed ({response.status}).")
            nonce = response.headers.get("Replay-Nonce")
        if not nonce:
            raise AcmeError("ACME server did not return a replay nonce.")
        self._nonce = nonce

    async def _get_json(self, session, url: str) -> dict:
        async with session.get(url) as response:
            if response.status >= 400:
                raise AcmeError(f"ACME directory request failed ({response.status}).")
            return await response.json(content_type=None)

    def _signed_payload(self, url: str, payload, *, use_jwk: bool = False) -> dict:
        assert self._account_key is not None
        protected = {
            "alg": "ES256",
            "nonce": self._nonce,
            "url": url,
        }
        if use_jwk:
            protected["jwk"] = self._account_jwk()
        else:
            protected["kid"] = self._account_url
        protected_b64 = self._b64(json.dumps(protected, separators=(",", ":")).encode())
        payload_bytes = (
            payload.encode() if isinstance(payload, str) else json.dumps(payload, separators=(",", ":")).encode()
        )
        payload_b64 = self._b64(payload_bytes)
        signing_input = f"{protected_b64}.{payload_b64}".encode()
        der_signature = self._account_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der_signature)
        signature = self._b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return {"protected": protected_b64, "payload": payload_b64, "signature": signature}

    def _account_jwk(self) -> dict:
        assert self._account_key is not None
        public = self._account_key.public_key().public_numbers()
        return {
            "crv": "P-256",
            "kty": "EC",
            "x": self._b64(self._int_bytes(public.x)),
            "y": self._b64(self._int_bytes(public.y)),
        }

    def _account_thumbprint(self) -> str:
        jwk = self._account_jwk()
        digest = hashlib.sha256(json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()).digest()
        return self._b64(digest)

    def _build_csr(self, domain: str):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, domain)])
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(name)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False)
            .sign(key, hashes.SHA256())
            .public_bytes(serialization.Encoding.DER)
        )
        return key, csr

    async def _poll(self, session, url: str, done, *, initial: dict):
        payload = initial
        for _ in range(self.max_polls):
            if done(payload):
                return payload
            await self._sleep(self.poll_interval)
            payload = await self._post_jws_json(session, url, "")
        raise AcmeError("ACME resource polling timed out.")

    @staticmethod
    @staticmethod
    def _is_bad_nonce(body: bytes) -> bool:
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            return False
        return isinstance(payload, dict) and payload.get("type", "").endswith(":badNonce")

    @staticmethod
    def _problem_detail(payload: dict, fallback: str) -> str:
        error = payload.get("error")
        if isinstance(error, dict) and error.get("detail"):
            return str(error["detail"])
        return fallback

    @staticmethod
    def _int_bytes(value: int) -> bytes:
        return value.to_bytes(32, "big")

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


class _BufferedResponse:
    """Small response snapshot safe to consume after aiohttp closes the response."""

    def __init__(self, status: int, headers, body: bytes):
        self.status = status
        self.headers = headers
        self._body = body

    async def json(self, content_type=None):
        return json.loads(self._body)

    async def text(self) -> str:
        return self._body.decode(errors="replace")


class ManagedCertificateEngine:
    """Dispatch certificate provisioning according to ManagedDomain.certificate_method."""

    def __init__(self, store: CertificateArtifactStore | None = None):
        self.store = store or CertificateArtifactStore()

    async def issue(self, managed_domain: ManagedDomain) -> AcmeIssueResult:
        method = managed_domain.certificate_method
        if method == "letsencrypt":
            client = AcmeCertificateClient(
                certificate_store=self.store,
                challenge_provider=AcmeHttp01ChallengeStore(self.store.base_dir),
            )
            return await client.issue(managed_domain)
        if method == "cloudflare":
            raise AcmeError("Cloudflare DNS-01 is not implemented in this phase.")
        raise AcmeError("Existing certificates must be installed with certificate artifacts." )

    def install_existing(
        self,
        managed_domain: ManagedDomain,
        certificate_pem: str,
        private_key_pem: str,
    ) -> ExistingCertificateValidation:
        if managed_domain.certificate_method != "existing":
            raise AcmeError("Managed domain is not configured for existing certificate mode.")
        return self.store.save(managed_domain.domain, certificate_pem, private_key_pem)
