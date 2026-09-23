from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.migration.detector import (
    BackupDetection,
    detect_backup,
    inspect_pg_dump_custom,
)


@dataclass(frozen=True)
class PreflightResult:
    detection: BackupDetection
    safe_to_attempt: bool
    blocking_errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.safe_to_attempt and not self.blocking_errors


def preflight_backup(path: str | Path) -> PreflightResult:
    detection = detect_backup(path)
    errors: list[str] = []
    warnings = list(detection.warnings)

    if not detection.is_pasarguard:
        errors.append(
            "Backup source could not be positively identified as PasarGuard. "
            "No restore operation is permitted."
        )

    if detection.format == "pg_dump_custom" and detection.source_product == "unknown":
        inspected = inspect_pg_dump_custom(path)
        detection = inspected
        warnings = list(inspected.warnings)
        if not inspected.is_pasarguard:
            errors.append(
                "PostgreSQL custom dump could not be positively identified as PasarGuard "
                "from a read-only pg_restore TOC inspection."
            )

    if detection.confidence == "low":
        errors.append("Detection confidence is too low for an automatic migration.")

    if not detection.evidence:
        errors.append("No schema/product evidence was found in the backup.")

    return PreflightResult(
        detection=detection,
        safe_to_attempt=not errors,
        blocking_errors=tuple(errors),
        warnings=tuple(warnings),
    )
