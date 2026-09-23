

_SOURCE_VERSION_RE = __import__("re").compile(
    r"^\s*(\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)?)\s*$"
)


def _read_small_text(path: Path, limit: int = 16_384) -> str:
    with path.open("rt", encoding="utf-8", errors="replace") as fh:
        return fh.read(limit)


def _source_timescale_metadata(root: Path, source: Path) -> tuple[str | None, tuple[str, ...]]:
    files: list[Path] = []
    direct_candidates = (
        source.with_name("db_backup.timescaledb-version"),
        source.with_name(source.name + ".timescaledb-version"),
        source.parent / "timescaledb.version",
    )
    for candidate in direct_candidates:
        if candidate.is_file():
            files.append(candidate)

    # Official PasarGuard archives use db_backup.timescaledb-version and/or
    # manifest.tsv. We also inspect archived compose files as a compatibility
    # fallback, but only inside the already extracted archive root.
    for pattern in ("db_backup.timescaledb-version", "manifest.tsv", "docker-compose.yml", "compose.yml"):
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
                if len(fields) >= 5 and fields[2].strip() == "1" and fields[4].strip():
                    value = fields[4].strip()
                    if _SOURCE_VERSION_RE.fullmatch(value):
                        versions.append(value)
            continue

        if name.endswith(".timescaledb-version") or name == "timescaledb.version":
            first = text.splitlines()[0].strip() if text.splitlines() else ""
            if first:
                match = _SOURCE_VERSION_RE.fullmatch(first)
                if match:
                    versions.append(first)
                else:
                    warnings.append(f"Unsafe TimescaleDB version metadata ignored: {path.name}")
            continue

        # Do not scrape arbitrary SQL/YAML values. Only accept the Timescale
        # Docker image syntax used by PasarGuard's compose snapshots.
        for match in __import__("re").finditer(
            r"timescale/timescaledb(?:-ha)?:(?:pg\d+-ts)?(\d+\.\d+\.\d+)(?:-pg\d+)?",
            text,
            flags=__import__("re").I,
        ):
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
    sql_versions = tuple(v for v in versions if version_tuple(v))
    exact = source_version
    if exact is None and len(sql_versions) == 1:
        exact = sql_versions[0]
    if source_version and sql_versions and any(v != source_version for v in sql_versions):
        # A SQL comment and a sidecar disagree: never choose one silently.
        conflicting = tuple(dict.fromkeys(v for v in sql_versions if v != source_version))
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
                compatibility = TimescaleCompatibility()
                uses_timescaledb = _custom_uses_timescale(detection)
                if uses_timescaledb and selected_version:
                    compatibility = TimescaleCompatibility(
                        versions=(selected_version,),
                        source_version=selected_version,
                        warnings=metadata_warnings,
                    )
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
