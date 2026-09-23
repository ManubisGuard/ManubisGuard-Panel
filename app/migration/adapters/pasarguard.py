from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.migration.detector import BackupDetection
from app.migration.schema import is_supported_core_type, normalize_core_type


@dataclass(frozen=True)
class PasarGuardMigrationReport:
    source: str
    detection: BackupDetection
    source_revision: str | None
    target_revision: str
    transformations: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers


class PasarGuardAdapter:
    """Compatibility adapter for legacy PasarGuard backups.

    Planning is deliberately side-effect free. SQL import is performed only by
    the future isolated staging/restore layer.
    """

    name = "pasarguard"
    target_product = "manubisguard"
    target_revision = "awg2026091901"

    def plan(self, path: str | Path, detection: BackupDetection) -> PasarGuardMigrationReport:
        blockers: list[str] = []
        warnings: list[str] = []
        transformations = (
            "preserve legacy primary keys where possible",
            "map legacy schema to current SQLAlchemy metadata",
            "apply missing ManubisGuard migrations in staging",
            "normalize protocol/core type aliases",
            "preserve settings JSON and unknown keys unless explicitly unsafe",
            "validate foreign-key graph before production restore",
        )

        if not detection.is_pasarguard:
            blockers.append("Backup is not positively identified as PasarGuard.")

        if detection.format == "pg_dump_custom":
            blockers.append("Binary pg_dump requires isolated pg_restore inspection before import.")

        if not is_supported_core_type("amneziawg"):
            blockers.append("Target ManubisGuard build does not advertise AmneziaWG support.")

        warnings.append(
            "Historical telemetry may be excluded when absent from the source backup; "
            "configuration/account data is handled separately."
        )

        return PasarGuardMigrationReport(
            source=str(path),
            detection=detection,
            source_revision=detection.schema_revision,
            target_revision=self.target_revision,
            transformations=transformations,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    @staticmethod
    def normalize_core_type(value: str | None) -> str:
        return normalize_core_type(value)
