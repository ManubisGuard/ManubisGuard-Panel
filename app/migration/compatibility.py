from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TIMESCALE_FIRST_RELID = (2, 29, 0)
TIMESCALE_LAST_SCHEMA_NAME = "2.28.3"

_TS_VERSION_PATTERNS = (
    r"timescaledb[_ -]?version[:\s\"]+(\d+\.\d+(?:\.\d+)?)",
    r"backup version[:\s]+(\d+\.\d+(?:\.\d+)?)",
    r"timescale/timescaledb:(\d+\.\d+(?:\.\d+)?)",
    r"extension[:\s]+timescaledb[^\n]{0,100}?(\d+\.\d+\.\d+)",
)

_TS_MISSING_COLUMN = re.compile(
    r'column\s+"([^"]+)"\s+of relation\s+"([^"]+)"\s+does not exist',
    re.I,
)


@dataclass(frozen=True)
class TimescaleCompatibility:
    versions: tuple[str, ...] = ()
    source_version: str | None = None
    minimum_version: str | None = None
    catalog_era: str | None = None
    recommended_version: str | None = None
    warnings: tuple[str, ...] = ()


def version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", value.strip())
    if not match:
        return None
    return tuple(int(x or 0) for x in match.groups())


def version_lt(a: str | None, b: str | None) -> bool:
    ta, tb = version_tuple(a), version_tuple(b)
    return ta is not None and tb is not None and ta < tb


def max_version(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return b if version_lt(a, b) else a


def detect_catalog_era(sql_text: str) -> str | None:
    if not sql_text:
        return None
    for match in re.finditer(
        r"COPY\s+(?:_timescaledb_catalog\.)?chunk\s*\(([^)]+)\)",
        sql_text,
        re.I,
    ):
        columns = {x.strip().strip('"').lower() for x in match.group(1).split(",")}
        if {"schema_name", "table_name"} & columns:
            return "schema_name"
        if "relid" in columns:
            return "relid"
    low = sql_text.lower()
    if "_timescaledb_catalog.chunk" in low and "schema_name" in low:
        return "schema_name"
    if "_timescaledb_catalog.chunk" in low and "relid" in low:
        return "relid"
    return None


def detect_catalog_floor(sql_text: str) -> str | None:
    if not sql_text:
        return None
    floor: str | None = None
    if detect_catalog_era(sql_text) == "schema_name":
        floor = TIMESCALE_LAST_SCHEMA_NAME
    if re.search(
        r"COPY\s+(?:_timescaledb_catalog\.)?continuous_agg\s*\([^)]*\bschema_change_timestamp\b",
        sql_text,
        re.I,
    ):
        floor = max_version(floor, "2.28.0")
    return floor


def collect_versions(sql_text: str) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in _TS_VERSION_PATTERNS:
        found.extend(re.findall(pattern, sql_text or "", re.I))
    return tuple(dict.fromkeys(v.strip() for v in found if v.strip()))


def analyze_timescale_sql(
    sql_text: str,
    *,
    source_version: str | None = None,
) -> TimescaleCompatibility:
    versions = collect_versions(sql_text)
    explicit = source_version.strip() if source_version else None
    if explicit and explicit not in versions:
        versions = (explicit, *versions)
    if explicit is None and len(versions) == 1:
        explicit = versions[0]

    era = detect_catalog_era(sql_text)
    minimum = detect_catalog_floor(sql_text)
    # Explicit version strings describe the source environment; they are not
    # automatically a catalog floor. The catalog fingerprint is authoritative
    # for the known 2.29 chunk schema break.
    recommended = None
    warnings: list[str] = []
    if len(versions) > 1 and explicit is None:
        warnings.append(
            "Multiple TimescaleDB version strings were found; an exact source "
            "version could not be selected automatically."
        )
    if era == "schema_name":
        recommended = TIMESCALE_LAST_SCHEMA_NAME
        warnings.append(
            "Backup uses the pre-2.29 Timescale chunk catalog (schema_name/table_name). "
            "Restoring it directly into TimescaleDB 2.29+ is unsafe."
        )
    elif era == "relid":
        recommended = "2.29.0"
    elif minimum:
        recommended = minimum
    return TimescaleCompatibility(
        versions=versions,
        source_version=explicit,
        minimum_version=minimum,
        catalog_era=era,
        recommended_version=recommended,
        warnings=tuple(warnings),
    )


def classify_restore_error(output: str) -> str | None:
    low = (output or "").lower()
    if any(x in low for x in (
        "sasl authentication failed",
        "password authentication failed",
        "authentication failed",
    )):
        return "authentication"
    if (
        (
            "timescaledb" in low
            or "_timescaledb_catalog" in low
            or 'relation "chunk"' in low
        )
        and (
            "catalog version mismatch" in low
            or "does not exist" in low
            or "undefined_column" in low
        )
    ):
        return "timescaledb_catalog_mismatch"
    if "timescaledb.restoring" in low or "timescaledb_post_restore" in low:
        return "timescaledb_restore_mode"
    if "no space left on device" in low or "could not extend file" in low:
        return "disk_full"
    if "duplicate_object" in low or "already exists" in low:
        return "duplicate_object"
    if "alembic" in low and "revision" in low:
        return "alembic_revision"
    return None


def classify_restore_error_from_file(path: Path) -> str | None:
    try:
        return classify_restore_error(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
