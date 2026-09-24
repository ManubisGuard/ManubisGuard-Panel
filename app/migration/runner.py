from __future__ import annotations

import gzip
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.migration.adapters.pasarguard import PasarGuardAdapter
from app.migration.compatibility import TimescaleCompatibility, analyze_timescale_sql, version_tuple
from app.migration.detector import BackupDetection
from app.migration.preflight import PreflightResult, preflight_backup
from app.migration.staging import (
    MigrationSafetyError,
    StagingDatabase,
    inspect_backup_source,
    restore_backup_into_staging,
    read_timescaledb_version,
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

_SOURCE_VERSION_RE = re.compile(
    r"^\s*(\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)?)\s*$"
)
_COMPOSE_TS_RE = re.compile(
    r"timescale/timescaledb(?:-ha)?:(?:pg\d+-ts)?"
    r"(\d+\.\d+\.\d+)(?:-pg\d+)?",
    re.IGNORECASE,
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


def _read_small_text(path: Path, limit: int = 16_384) -> str:
    with path.open("rt", encoding="utf-8", errors="replace") as fh:
        return fh.read(limit)


def _source_timescale_metadata(
    root: Path,
    source: Path,
) -> tuple[str | None, tuple[str, ...]]:
    files: list[Path] = []

    direct_candidates = (
        source.with_name("db_backup.timescaledb-version"),
        source.with_name(source.name + ".timescaledb-version"),
        source.parent / "timescaledb.version",
    )
    for candidate in direct_candidates:
        if candidate.is_file():
            files.append(candidate)

    # PasarGuard backups can carry the exact version in a sidecar or
    # manifest.tsv. Deployment files such as docker-compose.yml are deliberately
    # excluded: they are not database migration artifacts and must never influence
    # the ManubisGuard deployment or migration target.
    for pattern in (
        "db_backup.timescaledb-version",
        "manifest.tsv",
    ):
        try:
            files.extend(sorted(root.rglob(pattern)))
        except OSError:
            continue

    versions: list[str] = []
    warnings: list[str] = []

    for path in dict.fromkeys(files):
        try:
            text = _read_small_text(path)
        except OSError:
            continue

        name = path.name.lower()

        if name == "manifest.tsv":
            for line in text.splitlines():
                fields = line.split("\t")
                if len(fields) >= 5 and fields[2].strip() == "1":
                    value = fields[4].strip()
                    if not value:
                        continue
                    if _SOURCE_VERSION_RE.fullmatch(value):
                        versions.append(value)
                    else:
                        warnings.append(
                            f"Unsafe TimescaleDB manifest version ignored: {value!r}"
                        )
            continue

        if name.endswith(".timescaledb-version") or name == "timescaledb.version":
            first = next((line.strip() for line in text.splitlines() if line.strip()), "")
            if not first:
                continue
            if _SOURCE_VERSION_RE.fullmatch(first):
                versions.append(first)
            else:
                warnings.append(
                    f"Unsafe TimescaleDB sidecar version ignored: {path.name}"
                )
            continue

        for match in _COMPOSE_TS_RE.finditer(text):
            versions.append(match.group(1))

    unique = tuple(dict.fromkeys(versions))
    if len(unique) > 1:
        raise MigrationSafetyError(
            "Multiple conflicting TimescaleDB source versions were found in the backup: "
            + ", ".join(unique)
        )
    return (unique[0] if unique else None, tuple(dict.fromkeys(warnings)))


def _merge_timescale_source_version(
    compatibility: TimescaleCompatibility,
    source_version: str | None,
    warnings: tuple[str, ...],
) -> TimescaleCompatibility:
    versions = compatibility.versions
    if source_version and source_version not in versions:
        versions = (source_version, *versions)

    parsed_versions = tuple(v for v in versions if version_tuple(v))
    exact = source_version
    if exact is None and len(parsed_versions) == 1:
        exact = parsed_versions[0]

    if source_version and any(v != source_version for v in parsed_versions):
        conflicting = tuple(dict.fromkeys(v for v in parsed_versions if v != source_version))
        raise MigrationSafetyError(
            "TimescaleDB source version metadata conflicts with the SQL dump: "
            f"metadata={source_version}, sql={', '.join(conflicting)}"
        )

    return TimescaleCompatibility(
        versions=versions,
        source_version=exact,
        minimum_version=compatibility.minimum_version,
        catalog_era=compatibility.catalog_era,
        recommended_version=compatibility.recommended_version,
        warnings=tuple(dict.fromkeys((*compatibility.warnings, *warnings))),
    )


def _custom_uses_timescale(detection: BackupDetection) -> bool:
    return any(
        "timescaledb" in item.lower() or "_timescaledb_catalog" in item.lower()
        for item in detection.evidence
    )


def analyze_backup(
    path: str | Path,
    *,
    source_timescale_version: str | None = None,
) -> BackupAnalysis:
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
            root = Path(tmp.name) if tmp is not None else source.parent
            metadata_version, metadata_warnings = _source_timescale_metadata(root, source)

            explicit_version = source_timescale_version.strip() if source_timescale_version else None
            if explicit_version and _SOURCE_VERSION_RE.fullmatch(explicit_version) is None:
                raise MigrationSafetyError(
                    f"Invalid --source-timescale value: {source_timescale_version!r}"
                )
            if explicit_version and metadata_version and explicit_version != metadata_version:
                raise MigrationSafetyError(
                    "Explicit source TimescaleDB version conflicts with backup metadata: "
                    f"override={explicit_version}, detected={metadata_version}"
                )
            selected_version = explicit_version or metadata_version

            if detection.format in {"sql", "sql.gz"}:
                sample = _read_timescale_sample(source)
                compatibility = analyze_timescale_sql(
                    sample,
                    source_version=selected_version,
                )
                compatibility = _merge_timescale_source_version(
                    compatibility,
                    selected_version,
                    metadata_warnings,
                )
                uses_timescaledb = (
                    "timescaledb" in sample.lower()
                    or compatibility.catalog_era is not None
                )
            else:
                uses_timescaledb = _custom_uses_timescale(detection)
                compatibility = TimescaleCompatibility(
                    versions=(selected_version,) if selected_version else (),
                    source_version=selected_version,
                    warnings=metadata_warnings,
                )
        finally:
            if tmp is not None:
                tmp.cleanup()
    except MigrationSafetyError:
        raise
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
    source_timescale_version: str | None = None,
) -> MigrationRunResult:
    analysis = analyze_backup(
        backup_path,
        source_timescale_version=source_timescale_version,
    )
    if not analysis.preflight.ok:
        raise MigrationSafetyError(
            "Migration preflight blocked the backup: "
            + "; ".join(analysis.preflight.blocking_errors)
        )

    if analysis.uses_timescaledb:
        live_timescale = read_timescaledb_version(production_url)
        if not live_timescale:
            raise MigrationSafetyError(
                "TimescaleDB backup detected, but the destination TimescaleDB extension "
                "version could not be read safely."
            )
        required_timescale = resolve_staging_timescale_version(
            analysis,
            live_version=live_timescale,
        )
        if version_tuple(required_timescale) != version_tuple(live_timescale):
            # A version mismatch is handled by the host migration orchestrator:
            # it starts an isolated source-compatible TimescaleDB runtime, restores
            # there, upgrades the extension in isolation, and only then exports the
            # validated staging database for cross-major PostgreSQL cutover.
            # Never attempt to replay a Timescale catalog directly into the live
            # destination extension.
            analysis = BackupAnalysis(
                detection=analysis.detection,
                preflight=analysis.preflight,
                timescale=TimescaleCompatibility(
                    versions=analysis.timescale.versions,
                    source_version=analysis.timescale.source_version,
                    minimum_version=analysis.timescale.minimum_version,
                    catalog_era=analysis.timescale.catalog_era,
                    recommended_version=required_timescale,
                    warnings=(*analysis.timescale.warnings,
                              f"Adaptive restore selected source-compatible TimescaleDB {required_timescale} "
                              f"for destination {live_timescale}."),
                ),
                uses_timescaledb=analysis.uses_timescaledb,
            )

    restore_backup_into_staging(
        backup_path,
        staging,
        timeout=timeout,
        allow_external_staging=allow_external_staging,
    )

    from app.migration.inspector import inspect_database

    pre_upgrade = inspect_database(staging.staging_url)

    adapter = PasarGuardAdapter()
    pre_transformations = adapter.prepare(staging.staging_url)

    upgrade_staging_database(
        staging,
        production_url=production_url,
        revision="head",
        allow_external_staging=allow_external_staging,
    )

    post_transformations = adapter.apply(staging.staging_url)
    transformations = (*pre_transformations, *post_transformations)
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
                + ", ".join(f"{table} {before}→{after}" for table, (before, after) in losses.items()),
            ),
            warnings=validation.warnings,
            snapshot=validation.snapshot,
            missing_target_tables=validation.missing_target_tables,
            orphan_checks=validation.orphan_checks,
        )

    return MigrationRunResult(
        analysis=analysis,
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
        "orphan_checks": [asdict(item) for item in result.orphan_checks],
        "snapshot": (
            {
                "tables": list(snapshot.tables),
                "columns": {key: list(value) for key, value in snapshot.columns.items()},
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
