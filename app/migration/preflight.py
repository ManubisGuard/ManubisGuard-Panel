from __future__ import annotations

from dataclasses import asdict, dataclass, field
import gzip
import tarfile
import zipfile
import zlib
from pathlib import Path

from app.migration.detector import (
    BackupDetection,
    detect_backup,
    inspect_pg_dump_custom,
)
from app.migration.pasarguard_backup import (
    PasarGuardManifest,
    read_manifest_from_archive,
)


@dataclass(frozen=True)
class PreflightResult:
    detection: BackupDetection
    safe_to_attempt: bool
    blocking_errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    pasarguard_manifest: PasarGuardManifest | None = None

    @property
    def ok(self) -> bool:
        return self.safe_to_attempt and not self.blocking_errors

    def as_jsonable(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "safe_to_attempt": self.safe_to_attempt,
            "blocking_errors": list(self.blocking_errors),
            "warnings": list(self.warnings),
            "pasarguard_manifest": (
                {
                    "databases": [
                        asdict(entry) for entry in self.pasarguard_manifest.databases
                    ]
                }
                if self.pasarguard_manifest
                else None
            ),
        }


def _sql_dump_completion_error(path: Path, *, compressed: bool) -> str | None:
    """Return an error when a plain PostgreSQL dump lacks pg_dump's trailer."""
    marker = "-- PostgreSQL database dump complete"
    tail_limit = 1_200_000
    try:
        if compressed:
            tail = ""
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as stream:
                for chunk in iter(lambda: stream.read(tail_limit), ""):
                    tail = (tail + chunk)[-tail_limit:]
        else:
            size = path.stat().st_size
            if size <= 0:
                return "SQL backup is empty."
            with path.open("rt", encoding="utf-8", errors="replace") as stream:
                stream.seek(max(0, size - tail_limit))
                tail = stream.read(tail_limit)
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error) as exc:
        return f"SQL backup could not be read completely: {exc}"
    if marker not in tail:
        return (
            "SQL backup does not contain the PostgreSQL completion marker; "
            "it may be truncated or incomplete."
        )
    return None


def preflight_backup(path: str | Path) -> PreflightResult:
    """Perform product/format checks without restoring any database."""
    source_path = Path(path).expanduser()
    try:
        detection = detect_backup(source_path)
    except (OSError, ValueError, EOFError, gzip.BadGzipFile, zipfile.BadZipFile, tarfile.TarError, zlib.error) as exc:
        # Malformed archives must be a normal, fail-closed preflight result rather
        # than bubbling a parser exception into the API and bypassing diagnostics.
        detection = BackupDetection(
            path=str(source_path),
            format="unknown",
            source_product="unknown",
            confidence="low",
            evidence=(),
            warnings=("Backup format could not be safely inspected.",),
        )
        return PreflightResult(
            detection=detection,
            safe_to_attempt=False,
            blocking_errors=(f"Backup is corrupt or unreadable: {exc}",),
            warnings=detection.warnings,
        )
    warnings = list(detection.warnings)
    manifest: PasarGuardManifest | None = None

    # A PostgreSQL logical dump can contain recognizable schema markers while
    # still being truncated. Reject it during preflight, before any staging DB is
    # allocated. MariaDB dumps use a different trailer and are handled by their
    # own bridge path.
    if (
        detection.format in {"sql", "sql.gz"}
        and detection.is_supported_source
        and not detection.is_mariadb
    ):
        completion_error = _sql_dump_completion_error(
            Path(path).expanduser(), compressed=detection.format == "sql.gz"
        )
        if completion_error:
            return PreflightResult(
                detection=detection,
                safe_to_attempt=False,
                blocking_errors=(completion_error,),
                warnings=tuple(dict.fromkeys(warnings)),
            )

    # The backup container itself is untrusted input. Validate its structure and
    # CRC before any restore/staging operation is allowed to start.
    if detection.format in {"zip", "tar"}:
        from app.migration.detector import validate_archive_integrity

        try:
            archive_errors = validate_archive_integrity(path)
        except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
            archive_errors = (f"Archive integrity validation failed: {exc}",)
        if archive_errors:
            return PreflightResult(
                detection=detection,
                safe_to_attempt=False,
                blocking_errors=tuple(archive_errors),
                warnings=tuple(dict.fromkeys(warnings)),
            )

    # Binary custom dumps are intentionally unknown until a read-only TOC
    # inspection has identified their schema/product. Do this before evaluating
    # the generic product gate so a valid PasarGuard PGDMP is not rejected for
    # having started as "unknown".
    if detection.format == "pg_dump_custom" and detection.source_product == "unknown":
        inspected = inspect_pg_dump_custom(path)
        detection = inspected
        warnings = list(inspected.warnings)

    # PasarGuard's archive manifest is compatibility metadata, not restore data.
    # Parse it before any staging work and verify every declared dump exists in
    # the archive. A malformed manifest is a hard failure; an absent manifest is
    # retained as a warning so older/hand-built backups can still be inspected
    # from their SQL evidence rather than being silently guessed as compatible.
    if detection.is_pasarguard and detection.format in {"zip", "tar"}:
        try:
            manifest, manifest_errors = read_manifest_from_archive(path)
        except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
            manifest = None
            manifest_errors = (f"PasarGuard manifest inspection failed: {exc}",)
        if manifest_errors:
            return PreflightResult(
                detection=detection,
                safe_to_attempt=False,
                blocking_errors=tuple(manifest_errors),
                warnings=tuple(dict.fromkeys(warnings)),
                pasarguard_manifest=manifest,
            )
        if manifest is None:
            warnings.append(
                "PasarGuard manifest.tsv was not found; compatibility will rely on detected SQL/TOC evidence."
            )

    errors: list[str] = []
    if not detection.is_supported_source:
        errors.append(
            "Backup source could not be positively identified as a supported ManubisGuard/PasarGuard backup. "
            "No restore operation is permitted."
        )

    if detection.confidence == "low":
        errors.append("Detection confidence is too low for an automatic migration.")

    if not detection.evidence:
        errors.append("No schema/product evidence was found in the backup.")

    return PreflightResult(
        detection=detection,
        safe_to_attempt=not errors,
        blocking_errors=tuple(errors),
        warnings=tuple(dict.fromkeys(warnings)),
        pasarguard_manifest=manifest,
    )
