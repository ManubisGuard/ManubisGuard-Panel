from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from app.core.certificate_intelligence import ExistingCertificateValidator
from app.models.domain_intelligence import ExistingCertificateValidation
from app.models.settings import ManagedDomain


DEFAULT_CERTIFICATE_DIR = Path("/var/lib/PasarGuard/certs")


class CertificateArtifactStore:
    """Store managed TLS certificate artifacts outside the database."""

    def __init__(self, base_dir: str | Path | None = None):
        configured = base_dir if base_dir is not None else os.getenv("PASARGUARD_CERTIFICATE_DIR")
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

        normalized = self._normalize(domain)
        self.base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.base_dir, 0o700)

        target_dir = self._domain_dir(normalized)
        staging_dir = self.base_dir / f".{normalized}.staging-{uuid4().hex}"
        backup_dir = self.base_dir / f".{normalized}.backup-{uuid4().hex}"

        staging_dir.mkdir(mode=0o700)
        os.chmod(staging_dir, 0o700)
        try:
            self._atomic_write(staging_dir / "cert.pem", certificate_pem, 0o644)
            self._atomic_write(staging_dir / "key.pem", private_key_pem, 0o600)

            had_previous = target_dir.exists()
            if had_previous:
                os.replace(target_dir, backup_dir)

            try:
                os.replace(staging_dir, target_dir)
            except Exception:
                if had_previous and not target_dir.exists() and backup_dir.exists():
                    os.replace(backup_dir, target_dir)
                raise

            if had_previous and backup_dir.exists():
                shutil.rmtree(backup_dir)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

        return result

    def load(self, domain: str) -> tuple[str, str]:
        target_dir = self._domain_dir(self._normalize(domain))
        return (
            (target_dir / "cert.pem").read_text(encoding="utf-8"),
            (target_dir / "key.pem").read_text(encoding="utf-8"),
        )

    def exists(self, domain: str) -> bool:
        target_dir = self._domain_dir(self._normalize(domain))
        return (target_dir / "cert.pem").is_file() and (target_dir / "key.pem").is_file()

    def delete(self, domain: str) -> None:
        target_dir = self._domain_dir(self._normalize(domain))
        if not target_dir.exists():
            return
        shutil.rmtree(target_dir)

    @staticmethod
    def _normalize(domain: str) -> str:
        return ManagedDomain(id="certificate-artifact", domain=domain).domain

    def _domain_dir(self, domain: str) -> Path:
        return self.base_dir / domain

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
