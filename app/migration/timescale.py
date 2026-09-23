from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.migration.compatibility import (
    TIMESCALE_FIRST_RELID,
    TIMESCALE_LAST_SCHEMA_NAME,
    TimescaleCompatibility,
    version_tuple,
)


TIMESCALEDB_CATALOG_SEED_CLEAR_SQL = """\
DO $manubisguard_ts_seed$
DECLARE
    r regclass;
BEGIN
    FOR r IN
        SELECT (quote_ident(n.nspname) || '.' || quote_ident(c.relname))::regclass
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname LIKE '\\_timescaledb%' ESCAPE '\\'
          AND c.relname IN ('bgw_job_stat_history', 'bgw_job_stat', 'bgw_job', 'metadata')
        ORDER BY CASE c.relname
            WHEN 'bgw_job_stat_history' THEN 1
            WHEN 'bgw_job_stat' THEN 2
            WHEN 'bgw_job' THEN 3
            WHEN 'metadata' THEN 4
            ELSE 5
        END
    LOOP
        EXECUTE format('DELETE FROM %s', r);
    END LOOP;
END
$manubisguard_ts_seed$;
"""


@dataclass(frozen=True)
class TimescaleRestoreSpec:
    target_version: str
    source_version: str | None
    catalog_era: str | None
    image_tag: str
    conversion_required: bool
    warnings: tuple[str, ...] = ()


def parse_pg_major(version: str | None) -> int | None:
    if not version:
        return None
    match = re.match(r"^(\d+)", version.strip())
    return int(match.group(1)) if match else None


def choose_timescale_version(
    compatibility: TimescaleCompatibility,
    *,
    live_version: str,
) -> str:
    """Pick the source-compatible Timescale release for an isolated staging DB.

    The known 2.29 catalog boundary is authoritative when backup metadata is incomplete.
    A source version newer than the live destination is rejected because automatic
    downgrade of the production extension is outside this migration engine's safety model.
    """
    live = version_tuple(live_version)
    if live is None:
        raise ValueError(f"Invalid destination TimescaleDB version: {live_version!r}")

    source = compatibility.source_version
    if source is None and len(compatibility.versions) == 1:
        source = compatibility.versions[0]

    # A TimescaleDB dump is tied to its extension catalog layout. Era detection
    # is only a boundary check; it is not precise enough to manufacture a source
    # version. Exact source-version metadata is therefore mandatory.
    if source is None:
        raise ValueError(
            "Exact TimescaleDB source version is unknown. Provide backup sidecar/"
            "manifest metadata or --source-timescale explicitly."
        )

    source_tuple = version_tuple(source)
    if source_tuple is None:
        raise ValueError(f"Invalid TimescaleDB source version: {source!r}")

    if compatibility.catalog_era == "schema_name" and source_tuple >= TIMESCALE_FIRST_RELID:
        raise ValueError(
            f"TimescaleDB source version {source} conflicts with the pre-2.29 catalog fingerprint."
        )
    if compatibility.catalog_era == "relid" and source_tuple < TIMESCALE_FIRST_RELID:
        raise ValueError(
            f"Backup reports TimescaleDB {source} but contains the 2.29+ relid catalog."
        )

    if source_tuple > live:
        raise ValueError(
            f"Backup TimescaleDB {source} is newer than destination {live_version}. "
            "Production TimescaleDB must be upgraded before this migration."
        )

    return source or live_version


def build_restore_spec(
    compatibility: TimescaleCompatibility,
    *,
    live_version: str,
    pg_major: int,
) -> TimescaleRestoreSpec:
    target = choose_timescale_version(compatibility, live_version=live_version)
    image_tag = f"{target}-pg{pg_major}"
    conversion_required = version_tuple(target) != version_tuple(live_version)
    warnings = list(compatibility.warnings)

    if compatibility.catalog_era == "schema_name" and version_tuple(target) >= TIMESCALE_FIRST_RELID:
        raise ValueError(
            "Internal safety error: pre-2.29 catalog was paired with a 2.29+ staging image."
        )

    if conversion_required:
        warnings.append(
            f"Staging will restore with TimescaleDB {target} and later upgrade the "
            f"extension to destination version {live_version} before cutover."
        )

    return TimescaleRestoreSpec(
        target_version=target,
        source_version=compatibility.source_version or target,
        catalog_era=compatibility.catalog_era,
        image_tag=image_tag,
        conversion_required=conversion_required,
        warnings=tuple(warnings),
    )


def filter_timescaledb_ddl_line(line: str) -> bool:
    """Return True for extension DDL that must not replay into a pre-created extension."""
    return bool(
        re.search(
            r"^\s*(DROP|CREATE)\s+EXTENSION\s+"
            r"(IF\s+(EXISTS|NOT\s+EXISTS)\s+)?timescaledb(_toolkit)?\b",
            line,
            re.I,
        )
        or re.search(r"^\s*COMMENT\s+ON\s+EXTENSION\s+timescaledb\b", line, re.I)
    )


def prepare_timescale_sql_file(src: Path, dest: Path) -> Path:
    """Stream a SQL dump, remove extension DDL and prepend safe catalog seed cleanup."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8", errors="replace") as inp, dest.open("w", encoding="utf-8") as out:
        out.write(TIMESCALEDB_CATALOG_SEED_CLEAR_SQL.rstrip())
        out.write("\n")
        for raw in inp:
            line = raw.rstrip("\r\n")
            if filter_timescaledb_ddl_line(line):
                continue
            out.write(line)
            out.write("\n")
    return dest


def prepare_timescale_sql_gzip(src: Path, dest: Path) -> Path:
    import gzip

    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as inp, dest.open("w", encoding="utf-8") as out:
        out.write(TIMESCALEDB_CATALOG_SEED_CLEAR_SQL.rstrip())
        out.write("\n")
        for raw in inp:
            line = raw.rstrip("\r\n")
            if filter_timescaledb_ddl_line(line):
                continue
            out.write(line)
            out.write("\n")
    return dest


