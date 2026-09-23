from __future__ import annotations

import gzip
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.migration.adapters.pasarguard import PasarGuardAdapter
from app.migration.async_utils import run_async
from app.migration.compatibility import (
    TimescaleCompatibility,
    analyze_timescale_sql,
)
from app.migration.detector import BackupDetection
from app.migration.preflight import PreflightResult, preflight_backup
from app.migration.staging import (
    MigrationSafetyError,
    StagingDatabase,
    inspect_backup_source,
    restore_backup_into_staging,
    upgrade_staging_database,
)
from app.migration.timescale import choose_timescale_version
from app.migration.validator import ValidationResult, validate_migrated_database


DURABLE_COUNT_TABLES = (
    "admins",
    "users",
    "nodes",
    "hosts",
    "core_configs",
    "inbounds",
    "groups",
    "user_templates",
)


@dataclass(frozen=True)
class BackupAnalysis:
    detection: BackupDetection
    preflight: PreflightResult
    timescale: TimescaleCompatibility
    uses_timescaledb: bool


@dataclass(frozen=True)
class MigrationRunResult:
    analysis: BackupAnalysis
    pre_upgrade_counts: dict[str, int]
    post_upgrade_counts: dict[str, int]
    count_losses: dict[str, tuple[int, int]]
    transformations: tuple[str, ...]
    validation: ValidationResult

    @property
    def valid(self) -> bool:
        return self.validation.valid and not self.count_losses

    def as_jsonable(self) -> dict[str, Any]:
        return {
            "analysis": {
                "detection": asdict(self.analysis.detection),
                "preflight": {
                    "ok": self.analysis.preflight.ok,
                    "blocking_errors": list(self.analysis.preflight.blocking_errors),
                    "warnings": list(self.analysis.preflight.warnings),
                },
                "timescale": asdict(self.analysis.timescale),
                "uses_timescaledb": self.analysis.uses_timescaledb,
            },
            "pre_upgrade_counts": self.pre_upgrade_counts,
            "post_upgrade_counts": self.post_upgrade_counts,
            "count_losses": {
                key: list(value) for key, value in self.count_losses.items()
            },
            "transformations": list(self.transformations),
            "validation": {
                "valid": self.validation.valid,
                "blocking_errors": list(self.validation.blocking_errors),
                "warnings": list(self.validation.warnings),
                "missing_target_tables": list(self.validation.missing_target_tables),
                "orphan_checks": [asdict(x) for x in self.validation.orphan_checks],
                "snapshot": (
                    {
                        "tables": list(self.validation.snapshot.tables),
                        "row_counts": self.validation.snapshot.row_counts,
                        "alembic_versions": list(self.validation.snapshot.alembic_versions),
                        "core_type_counts": self.validation.snapshot.core_type_counts,
                    }
                    if self.validation.snapshot
                    else None
                ),
            },
            "valid": self.valid,
        }


def _read_timescale_sample(path: Path) -> str:
    if path.name.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            head = fh.read(1_200_000)
            try:
                fh.seek(max(0, fh.tell() - 1_200_000))
                tail = fh.read(1_200_000)
            except (OSError, ValueError):
                tail = ""
        return head + "\n" + tail
    with path.open("rt", encoding="utf-8", errors="replace") as fh:
        head = fh.read(1_200_000)
        try:
            fh.seek(max(0, path.stat().st_size - 1_200_000))
            tail = fh.read(1_200_000)
        except OSError:
            tail = ""
    return head + "\n" + tail


def _custom_uses_timescale(detection: BackupDetection) -> bool:
    return any(
        "timescaledb" in item.lower() or "_timescaledb_catalog" in item.lower()
        for item in detection.evidence
    )


def analyze_backup(path: str | Path) -> BackupAnalysis:
    source_path = Path(path).expanduser().resolve()
    preflight = preflight_backup(source_path)
    if not preflight.ok:
        return BackupAnalysis(
            detection=preflight.detection,
            preflight=preflight,
            timescale=TimescaleCompatibility(),
            uses_timescaledb=False,
        )

    try:
        source, detection, tmp = inspect_backup_source(source_path)
        try:
            if detection.format in {"sql", "sql.gz"}:
                sample = _read_timescale_sample(source)
                compatibility = analyze_timescale_sql(sample)
                uses_timescaledb = (
                    "timescaledb" in sample.lower()
                    or compatibility.catalog_era is not None
                )
            else:
                compatibility = TimescaleCompatibility()
                uses_timescaledb = _custom_uses_timescale(detection)
        finally:
            if tmp is not None:
                tmp.cleanup()
    except Exception as exc:
        raise MigrationSafetyError(f"Backup analysis failed: {exc}") from exc

    return BackupAnalysis(
        detection=detection,
        preflight=preflight,
        timescale=compatibility,
        uses_timescaledb=uses_timescaledb,
    )


def resolve_staging_timescale_version(
    analysis: BackupAnalysis,
    *,
    live_version: str,
) -> str:
    if not analysis.uses_timescaledb:
        return live_version
    return choose_timescale_version(analysis.timescale, live_version=live_version)


def _durable_counts(snapshot) -> dict[str, int]:
    return {
        table: int(snapshot.row_counts.get(table, 0))
        for table in DURABLE_COUNT_TABLES
        if table in snapshot.tables
    }


def migrate_pasarguard_staging(
    backup_path: str | Path,
    staging: StagingDatabase,
    *,
    production_url: str,
    timeout: int = 900,
    allow_external_staging: bool = False,
) -> MigrationRunResult:
    analysis = analyze_backup(backup_path)
    if not analysis.preflight.ok:
        raise MigrationSafetyError(
            "Migration preflight blocked the backup: "
            + "; ".join(analysis.preflight.blocking_errors)
        )

    detection = restore_backup_into_staging(
        backup_path,
        staging,
        timeout=timeout,
        allow_external_staging=allow_external_staging,
    )

    from app.migration.inspector import inspect_database

    pre_upgrade = inspect_database(staging.staging_url)
    upgrade_staging_database(
        staging,
        production_url=production_url,
        revision="head",
        allow_external_staging=allow_external_staging,
    )

    transformations = PasarGuardAdapter().apply(staging.staging_url)
    validation = validate_migrated_database(staging.staging_url)
    post_upgrade = validation.snapshot

    if post_upgrade is None:
        raise MigrationSafetyError("Validation produced no schema snapshot.")

    pre_counts = _durable_counts(pre_upgrade)
    post_counts = _durable_counts(post_upgrade)
    losses = {
        table: (before, post_counts.get(table, 0))
        for table, before in pre_counts.items()
        if post_counts.get(table, 0) < before
    }

    if losses:
        validation = ValidationResult(
            valid=False,
            blocking_errors=(
                *validation.blocking_errors,
                "Durable row-count loss after Alembic/normalization: "
                + ", ".join(f"{t} {a}→{b}" for t, (a, b) in losses.items()),
            ),
            warnings=validation.warnings,
            snapshot=validation.snapshot,
            missing_target_tables=validation.missing_target_tables,
            orphan_checks=validation.orphan_checks,
        )

    return MigrationRunResult(
        analysis=BackupAnalysis(
            detection=detection,
            preflight=analysis.preflight,
            timescale=analysis.timescale,
            uses_timescaledb=analysis.uses_timescaledb,
        ),
        pre_upgrade_counts=pre_counts,
        post_upgrade_counts=post_counts,
        count_losses=losses,
        transformations=transformations,
        validation=validation,
    )


def validation_jsonable(result: ValidationResult) -> dict[str, Any]:
    snapshot = result.snapshot
    return {
        "valid": result.valid,
        "blocking_errors": list(result.blocking_errors),
        "warnings": list(result.warnings),
        "missing_target_tables": list(result.missing_target_tables),
        "orphan_checks": [asdict(x) for x in result.orphan_checks],
        "snapshot": (
            {
                "tables": list(snapshot.tables),
                "columns": {k: list(v) for k, v in snapshot.columns.items()},
                "row_counts": snapshot.row_counts,
                "alembic_versions": list(snapshot.alembic_versions),
                "core_type_counts": snapshot.core_type_counts,
                "settings_invalid_rows": snapshot.settings_invalid_rows,
            }
            if snapshot
            else None
        ),
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
