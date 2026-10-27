from __future__ import annotations

import gzip
import json
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PASARGUARD_MARKERS = (
    "pasarguard",
    "pasar guard",
    "pasarguard_backup",
    "pasarguard-backup",
)

# Archive limits follow the conservative limits used by the PGClockMG reference
# while remaining compatible with large native PasarGuard database dumps. Keep
# preflight and extraction limits aligned so an accepted backup is not rejected
# later solely because the two layers disagree.
MAX_ARCHIVE_FILES = 20_000
MAX_ARCHIVE_ENTRY_BYTES = 8 * 1024 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 200

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
    source_postgres_major: int | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_pasarguard(self) -> bool:
        return self.source_product == "pasarguard"

    @property
    def is_manubisguard(self) -> bool:
        return self.source_product == "manubisguard"

    @property
    def is_mariadb(self) -> bool:
        return any("mariadb" in item.lower() or "mysql" in item.lower() for item in self.evidence)

    @property
    def is_supported_source(self) -> bool:
        return self.is_pasarguard or self.is_manubisguard


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

    if "mariadb dump" in sample or "mysql dump" in sample:
        evidence.append("detected MariaDB/MySQL logical dump")
    if "alembic_version" in sample:
        evidence.append("contains alembic_version")
    for table in sorted(KNOWN_TABLES):
        if re.search(rf"\b{re.escape(table)}\b", sample):
            evidence.append(f"contains table marker: {table}")

    marker_hits = [marker for marker in PASARGUARD_MARKERS if marker in sample]
    if marker_hits:
        evidence.extend(f"legacy marker: {marker}" for marker in marker_hits)

    revision = None
    pg_major = None
    pg_match = re.search(r"dumped from database version\s+(\d+)(?:\.\d+)?", sample, re.IGNORECASE)
    if pg_match:
        pg_major = int(pg_match.group(1))
        evidence.append(f"detected source PostgreSQL major: {pg_major}")
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
        source_postgres_major=pg_major,
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
        source_postgres_major=result.source_postgres_major,
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

    # pg_dump --globals-only emits roles/ACL SQL in a separate globals.sql file.
    # It is metadata for the cluster, not the application database dump, and must
    # never compete with the real PasarGuard database backup during candidate search.
    if name == "globals.sql":
        return BackupDetection(
            path=str(p),
            format="sql",
            source_product="unknown",
            confidence="low",
            evidence=("PostgreSQL cluster globals-only dump; not an application database backup",),
            warnings=("Cluster globals dump is ignored for database restore candidate selection.",),
        )

    if ".zip" in suffixes:
        with zipfile.ZipFile(p) as archive:
            names = "\n".join(archive.namelist()).lower()
            if "manifest.json" in names:
                try:
                    with archive.open("manifest.json") as fh:
                        payload = json.load(fh)
                except (OSError, json.JSONDecodeError, UnicodeDecodeError, zipfile.BadZipFile):
                    payload = {"files": archive.namelist()}

                manifest_product = str(payload.get("product", "")).strip().lower()
                if manifest_product == "manubisguard":
                    dump_name = str(payload.get("dump", "db.sql"))
                    try:
                        raw = archive.read(dump_name)[:5_000_000]
                        nested = _detect_text(p, raw.decode("utf-8", errors="replace"))
                        result = BackupDetection(
                            path=str(p),
                            format="zip",
                            source_product="manubisguard",
                            confidence="high",
                            evidence=("manifest product: manubisguard", *nested.evidence),
                            schema_revision=nested.schema_revision,
                            source_postgres_major=nested.source_postgres_major,
                            warnings=nested.warnings,
                        )
                    except (KeyError, OSError, RuntimeError, UnicodeDecodeError):
                        result = _detect_json(p, payload)
                else:
                    result = _detect_json(p, payload)
            else:
                result = _detect_text(p, names)
                for member in archive.infolist():
                    member_name = member.filename.lower()
                    if member_name.rsplit("/", 1)[-1] == "globals.sql":
                        continue
                    if not member_name.endswith((".sql", ".sql.gz", ".dump")):
                        continue
                    try:
                        with archive.open(member) as fh:
                            raw = fh.read(5_000_000)
                        candidate = _detect_text(p, raw.decode("utf-8", errors="replace"))
                    except (OSError, RuntimeError, zipfile.BadZipFile, UnicodeDecodeError):
                        continue
                    if candidate.source_product == "pasarguard" or candidate.evidence:
                        result = candidate
                        break
            return BackupDetection(
                path=result.path,
                format="zip",
                source_product=result.source_product,
                confidence=result.confidence,
                evidence=result.evidence,
                schema_revision=result.schema_revision,
                source_postgres_major=result.source_postgres_major,
                warnings=(*result.warnings, "Archive contents must be validated before restore."),
            )

    if ".tar" in suffixes or ".tgz" in suffixes or (name.endswith(".tar.gz") and ".gz" in suffixes):
        with tarfile.open(p, "r:*") as archive:
            names = "\n".join(member.name for member in archive.getmembers()).lower()
        return _with_format(_detect_text(p, names), "tar")

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


def _safe_archive_member(name: str) -> str | None:
    name = name.replace("\\", "/")
    if name.startswith("/") or ":" in name.split("/")[0]:
        return None
    normalized = posixpath.normpath(name)
    if normalized in {".", ""} or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def validate_archive_integrity(path: str | Path) -> tuple[str, ...]:
    """Validate archive paths, file types, size limits, and CRCs before restore.

    Metadata limits are checked before reading member payloads. This prevents a
    compressed archive bomb from forcing a full decompression pass just to learn
    that the archive was already unsafe.
    """
    archive_path = Path(path).expanduser().resolve()
    errors: list[str] = []

    if archive_path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(archive_path) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ARCHIVE_FILES:
                    return (f"Archive contains too many entries: {len(infos)} > {MAX_ARCHIVE_FILES}.",)
                seen: dict[str, str] = {}
                total_uncompressed = 0
                total_compressed = 0
                file_count = 0
                for info in infos:
                    name = _safe_archive_member(info.filename)
                    if name is None:
                        errors.append(f"Archive contains unsafe path: {info.filename!r}")
                        continue
                    if name in seen:
                        errors.append(
                            f"Archive contains duplicate path after normalization: {name!r} "
                            f"({seen[name]!r}, {info.filename!r})"
                        )
                        continue
                    seen[name] = info.filename
                    mode = stat.S_IFMT((info.external_attr >> 16) & 0o170000)
                    if info.is_dir() or mode == stat.S_IFDIR:
                        continue
                    if mode not in {0, stat.S_IFREG}:
                        errors.append(f"Archive contains a link/special file: {info.filename!r}")
                        continue
                    file_count += 1
                    if file_count > MAX_ARCHIVE_FILES:
                        errors.append(f"Archive contains too many files: > {MAX_ARCHIVE_FILES}.")
                        break
                    if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
                        errors.append(
                            f"Archive entry exceeds the safe uncompressed size limit: {info.filename!r}"
                        )
                    total_uncompressed += info.file_size
                    total_compressed += info.compress_size
                    if total_uncompressed > MAX_ARCHIVE_TOTAL_BYTES:
                        errors.append("Archive expands beyond the safe total uncompressed size limit.")
                        break

                if total_uncompressed and total_uncompressed > max(total_compressed, 1) * MAX_ARCHIVE_COMPRESSION_RATIO:
                    errors.append(
                        f"Archive compression ratio exceeds the safe limit ({MAX_ARCHIVE_COMPRESSION_RATIO}:1)."
                    )

                # Do not decompress any payload if metadata already proves the
                # archive unsafe. Otherwise CRC validation streams every member.
                if not errors:
                    bad_name = archive.testzip()
                    if bad_name is not None:
                        errors.append(f"Archive CRC validation failed for: {bad_name!r}")
        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
            errors.append(f"Invalid ZIP archive or CRC stream: {exc}")
        return tuple(dict.fromkeys(errors))

    if archive_path.suffix.lower() in {".tar", ".tgz"} or archive_path.name.lower().endswith(".tar.gz"):
        try:
            with tarfile.open(archive_path, "r:*") as archive:
                members = archive.getmembers()
                if len(members) > MAX_ARCHIVE_FILES:
                    return (f"Archive contains too many entries: {len(members)} > {MAX_ARCHIVE_FILES}.",)
                seen: dict[str, str] = {}
                total_uncompressed = 0
                for info in members:
                    name = _safe_archive_member(info.name)
                    if name is None:
                        errors.append(f"Archive contains unsafe path: {info.name!r}")
                        continue
                    if name in seen:
                        errors.append(
                            f"Archive contains duplicate normalized path: {name!r} ({seen[name]!r}, {info.name!r})"
                        )
                        continue
                    seen[name] = info.name
                    if not (info.isfile() or info.isdir()):
                        errors.append(f"Archive contains a link or special file: {info.name!r}")
                        continue
                    if not info.isfile():
                        continue
                    if info.size > MAX_ARCHIVE_ENTRY_BYTES:
                        errors.append(
                            f"Archive entry exceeds the safe uncompressed size limit: {info.name!r}"
                        )
                    total_uncompressed += info.size
                    if total_uncompressed > MAX_ARCHIVE_TOTAL_BYTES:
                        errors.append("Archive expands beyond the safe total uncompressed size limit.")
                        break

                compressed_size = max(archive_path.stat().st_size, 1)
                if total_uncompressed and total_uncompressed > compressed_size * MAX_ARCHIVE_COMPRESSION_RATIO:
                    errors.append(
                        f"Archive compression ratio exceeds the safe limit ({MAX_ARCHIVE_COMPRESSION_RATIO}:1)."
                    )

                if not errors:
                    for info in members:
                        if not info.isfile():
                            continue
                        try:
                            extracted = archive.extractfile(info)
                            if extracted is not None:
                                read_bytes = 0
                                while True:
                                    chunk = extracted.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    read_bytes += len(chunk)
                                    if read_bytes > MAX_ARCHIVE_ENTRY_BYTES:
                                        errors.append(
                                            f"Archive entry expanded beyond its safe limit: {info.name!r}"
                                        )
                                        break
                        except (OSError, EOFError, RuntimeError, tarfile.TarError) as exc:
                            errors.append(f"Archive integrity validation failed for {info.name!r}: {exc}")
        except (OSError, EOFError, RuntimeError, tarfile.TarError) as exc:
            errors.append(f"Invalid TAR archive: {exc}")
        return tuple(dict.fromkeys(errors))

    return ("Unsupported archive format.",)


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
            evidence=("PostgreSQL custom dump signature PGDMP", "pg_restore --list failed"),
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
    pg_major = None
    pg_match = re.search(r"dumped from database version\s+(\d+)(?:\.\d+)?", sample, re.IGNORECASE)
    if pg_match:
        pg_major = int(pg_match.group(1))
        evidence.append(f"detected source PostgreSQL major: {pg_major}")
    match = re.search(r"alembic_version.*?([0-9a-z]{8,32})", sample, flags=re.DOTALL)
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
        source_postgres_major=pg_major,
        warnings=("Custom PostgreSQL dump was positively identified from a read-only TOC inspection.",),
    )
