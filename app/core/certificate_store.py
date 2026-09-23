from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.core.certificate_intelligence import ExistingCertificateValidator
from app.models.domain_intelligence import ExistingCertificateValidation
from app.models.settings import ManagedDomain


DEFAULT_CERTIFICATE_DIR = Path("/var/lib/PasarGuard/certs")


class CertificateArtifactStore:
    """Store managed TLS certificate artifacts outside the database.

    Each domain gets a private directory containing cert.pem and key.pem.
    Writes are atomic and the private key is created with mode 0600.
    """

    def __init__(self, base_dir: str | Path | None = None):
        configured = base_dir or os.getenv("PASARGUARD_CERTIFICATE_DIR")
        self.base_dir = Path(configured) if configured else DEFAULT_CERTIFICATE_DIR

    def validate_pair(
        self,
        domain: str,
        certificate_pem: str,
        private_key_pem: str,
    ) -> ExistingCertificateValidation:
        return ExistingCertificateValidator().validate(domain, certificate_pem, private_key_pem)

    def save(
        self,
        domain: str,
        certificate_pem: str,
        private_key_pem: str,
    ) -> ExistingCertificateValidation:
        result = self.validate_pair(domain, certificate_pem, private_key_pem)
        if not result.valid:
            return result

        normalized = ManagedDomain(id="certificate-artifact", domain=domain).domain
        target_dir = self._domain_dir(normalized)
        target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        self._atomic_write(target_dir / "cert.pem", certificate_pem, 0o644)
        self._atomic_write(target_dir / "key.pem", private_key_pem, 0o600)
        return result

    def load(self, domain: str) -> tuple[str, str]:
        normalized = ManagedDomain(id="certificate-artifact", domain=domain).domain
        target_dir = self._domain_dir(normalized)
        return (
            (target_dir / "cert.pem").read_text(),
            (target_dir / "key.pem").read_text(),
        )

    def exists(self, domain: str) -> bool:
        normalized = ManagedDomain(id="certificate-artifact", domain=domain).domain
        target_dir = self._domain_dir(normalized)
        return (target_dir / "cert.pem").is_file() and (target_dir / "key.pem").is_file()

    def delete(self, domain: str) -> None:
        normalized = ManagedDomain(id="certificate-artifact", domain=domain).domain
        target_dir = self._domain_dir(normalized)
        for filename in ("cert.pem", "key.pem"):
            path = target_dir / filename
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            target_dir.rmdir()
        except OSError:
            pass

    def _domain_dir(self, domain: str) -> Path:
        normalized = ManagedDomain(id="certificate-artifact", domain=domain).domain
        # The domain validator guarantees a DNS hostname, so the directory
        # name cannot escape base_dir through path separators or traversal.
        return self.base_dir / normalized

    @staticmethod
    def _atomic_write(path: Path, content: str, mode: int) -> None:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary)
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            os.chmod(path, mode)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
