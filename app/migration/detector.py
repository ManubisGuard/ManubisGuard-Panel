from __future__ import annotations

import gzip
import json
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PASARGUARD_MARKERS = (
    "pasarguard",
    "pasar guard",
    "pasarguard_backup",
    "pasarguard-backup",
)

KNOWN_TABLES = {
    "admins",
    "users",
    "nodes",
    "hosts",
    "core_configs",
    "protocols",
    "settings",
    "alembic_version",
}


@dataclass(frozen=True)
class BackupDetection:
    path: str
    format: str
    source_product: str
    confidence: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    schema_revision: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_pasarguard(self) -> bool:
        return self.source_product == "pasarguard"


def _detect_text(path: Path, text: str) -> BackupDetection:
    sample = text[:5_000_000].lower()
    evidence: list[str] = []
    warnings: list[str] = []

    if "create table" in sample or "insert into" in sample:
        fmt = "sql"
    elif sample.lstrip().startswith("{") or sample.lstrip().startswith("["):
        fmt = "json"
    else:
        fmt = "text"

    if "alembic_version" in sample:
        evidence.append("contains alembic_version")
    for table in sorted(KNOWN_TABLES):
        if re.search(rf"\b{re.escape(table)}\b", sample):
            evidence.append(f"contains table marker: {table}")

    marker_hits = [marker for marker in PASARGUARD_MARKERS if marker in sample]
    if marker_hits:
        evidence.extend(f"legacy marker: {marker}" for marker in marker_hits)

    revision = None
    match = re.search(r"(?:alembic_version[^\n]{0,120})\b([0-9a-z]{8,32})\b", sample)
    if match:
        revision = match.group(1)
        evidence.append(f"detected alembic revision: {revision}")

    if marker_hits:
        product = "pasarguard"
        confidence = "high"
    elif "core_configs" in sample and "nodes" in sample and "alembic_version" in sample:
        product = "pasarguard"
        confidence = "medium"
        warnings.append("Product name marker was not present; detection is schema-based.")
    else:
        product = "unknown"
        confidence = "low"

    return BackupDetection(
        path=str(path),
        format=fmt,
        source_product=product,
        confidence=confidence,
        evidence=tuple(dict.fromkeys(evidence)),
        schema_revision=revision,
        warnings=tuple(warnings),
    )


def _detect_json(path: Path, payload: Any) -> BackupDetection:
    raw = json.dumps(payload, ensure_ascii=False)[:5_000_000]
    return _detect_text(path, raw)


def _with_format(result: BackupDetection, fmt: str) -> BackupDetection:
    return BackupDetection(
        path=result.path,
        format=fmt,
        source_product=result.source_product,
        confidence=result.confidence,
        evidence=result.evidence,
        schema_revision=result.schema_revision,
        warnings=result.warnings,
    )


def detect_backup(path: str | Path) -> BackupDetection:
    """Detect a backup without touching any production database.

    Unknown formats are never treated as safe PasarGuard backups.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(p)
    if not p.is_file():
        raise ValueError(f"Backup path is not a file: {p}")

    suffixes = {s.lower() for s in p.suffixes}
    name = p.name.lower()

    if ".zip" in suffixes:
        with zipfile.ZipFile(p) as archive:
            names = "\n".join(archive.namelist()).lower()
            if "manifest.json" in names:
                try:
                    with archive.open("manifest.json") as fh:
                        payload = json.load(fh)
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    payload = {"files": archive.namelist()}
                result = _detect_json(p, payload)
            else:
                result = _detect_text(p, names)
            return BackupDetection(
                path=result.path,
                format="zip",
                source_product=result.source_product,
                confidence=result.confidence,
                evidence=result.evidence,
                schema_revision=result.schema_revision,
                warnings=(*result.warnings, "Archive contents must be validated before restore."),
            )

    if ".tar" in suffixes or ".tgz" in suffixes or (name.endswith(".tar.gz") and ".gz" in suffixes):
        with tarfile.open(p, "r:*") as archive:
            names = "\n".join(member.name for member in archive.getmembers()).lower()
        return _detect_text(p, names)

    if name.endswith(".json.gz"):
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            payload = json.load(fh)
        return _with_format(_detect_json(p, payload), "json.gz")

    if name.endswith(".json"):
        with p.open("rt", encoding="utf-8", errors="replace") as fh:
            payload = json.load(fh)
        return _with_format(_detect_json(p, payload), "json")

    if name.endswith(".sql.gz"):
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            sql = fh.read(5_000_000)
        return _with_format(_detect_text(p, sql), "sql.gz")

    if name.endswith(".sql"):
        with p.open("rt", encoding="utf-8", errors="replace") as fh:
            sql = fh.read(5_000_000)
        return _with_format(_detect_text(p, sql), "sql")

    # PostgreSQL custom/tar formats are binary. Do not guess their origin.
    with p.open("rb") as fh:
        header = fh.read(16)
    if header.startswith(b"PGDMP"):
        return BackupDetection(
            path=str(p),
            format="pg_dump_custom",
            source_product="unknown",
            confidence="low",
            evidence=("PostgreSQL custom dump signature PGDMP",),
            warnings=("The dump must be inspected with pg_restore before product detection.",),
        )

    with p.open("rb") as fh:
        raw = fh.read(5_000_000)
    return _detect_text(p, raw.decode("utf-8", errors="replace"))


def inspect_pg_dump_custom(path: str | Path, timeout: int = 120) -> BackupDetection:
    """Inspect a PostgreSQL custom dump with pg_restore --list, without restoring it."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(p)

    binary = shutil.which("pg_restore")
    if not binary:
        return BackupDetection(
            path=str(p),
            format="pg_dump_custom",
            source_product="unknown",
            confidence="low",
            evidence=("PostgreSQL custom dump signature PGDMP",),
            warnings=("pg_restore is required to positively identify this custom dump.",),
        )

    result = subprocess.run(
        [binary, "--list", str(p)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "pg_restore --list failed")[-2000:]
        return BackupDetection(
            path=str(p),
            format="pg_dump_custom",
            source_product="unknown",
            confidence="low",
            evidence=(
                "PostgreSQL custom dump signature PGDMP",
                "pg_restore --list failed",
            ),
            warnings=(f"Read-only custom dump inspection failed: {detail}",),
        )

    sample = (result.stdout or "").lower()
    evidence = ["PostgreSQL custom dump signature PGDMP", "pg_restore TOC inspection completed"]
    marker_hits = [marker for marker in PASARGUARD_MARKERS if marker in sample]
    if marker_hits:
        product = "pasarguard"
        confidence = "high"
        evidence.extend(f"legacy marker in dump TOC: {marker}" for marker in marker_hits)
    elif all(table in sample for table in ("core_configs", "nodes", "alembic_version")):
        product = "pasarguard"
        confidence = "medium"
        evidence.append("schema markers found in pg_restore TOC")
    else:
        product = "unknown"
        confidence = "low"

    if "timescaledb" in sample or "_timescaledb_catalog" in sample:
        evidence.append("TimescaleDB objects found in pg_restore TOC")

    revision = None
    match = re.search(
        r"alembic_version.*?([0-9a-z]{8,32})",
        sample,
        flags=re.DOTALL,
    )
    if match:
        revision = match.group(1)
        evidence.append(f"detected alembic revision: {revision}")

    return BackupDetection(
        path=str(p),
        format="pg_dump_custom",
        source_product=product,
        confidence=confidence,
        evidence=tuple(dict.fromkeys(evidence)),
        schema_revision=revision,
        warnings=(
            "Custom PostgreSQL dump was positively identified from a read-only TOC inspection.",
        ),
    )
