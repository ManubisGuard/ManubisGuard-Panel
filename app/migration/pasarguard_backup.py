from __future__ import annotations

from dataclasses import dataclass
import posixpath
from pathlib import Path
import tarfile
import zipfile


@dataclass(frozen=True)
class PasarGuardDatabaseEntry:
    name: str
    owner: str
    timescale: bool
    dump_file: str
    timescale_version: str | None = None


@dataclass(frozen=True)
class PasarGuardManifest:
    databases: tuple[PasarGuardDatabaseEntry, ...]


def parse_manifest_tsv(source: str | Path) -> PasarGuardManifest:
    """Parse the PasarGuard PostgreSQL/TimescaleDB manifest.tsv format.

    Expected columns are tab-separated:
    database_name, owner, timescale_present, dump_file, [timescale_version].
    Empty lines and comment lines are ignored. Malformed rows are rejected
    rather than guessed because this metadata controls restore compatibility.
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    else:
        text = source

    entries: list[PasarGuardDatabaseEntry] = []
    seen_names: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        columns = raw_line.split("\t")
        if len(columns) not in (4, 5):
            raise ValueError(
                f"Invalid manifest.tsv row {line_number}: expected 4 or 5 columns"
            )

        name, owner, timescale_raw, dump_file = (
            column.strip() for column in columns[:4]
        )
        if not name or not owner or not dump_file:
            raise ValueError(f"Invalid manifest.tsv row {line_number}: empty required field")
        if name in seen_names:
            raise ValueError(f"Invalid manifest.tsv row {line_number}: duplicate database name {name!r}")
        seen_names.add(name)

        normalized_timescale = timescale_raw.lower()
        if normalized_timescale not in {"0", "1"}:
            raise ValueError(
                f"Invalid manifest.tsv row {line_number}: Timescale flag must be 0 or 1"
            )

        timescale_version = columns[4].strip() if len(columns) == 5 else None
        if normalized_timescale == "1" and not timescale_version:
            raise ValueError(
                f"Invalid manifest.tsv row {line_number}: Timescale version is required"
            )
        if normalized_timescale == "0" and timescale_version:
            raise ValueError(
                f"Invalid manifest.tsv row {line_number}: non-Timescale database cannot declare a Timescale version"
            )

        entries.append(
            PasarGuardDatabaseEntry(
                name=name,
                owner=owner,
                timescale=normalized_timescale == "1",
                dump_file=dump_file,
                timescale_version=timescale_version or None,
            )
        )

    if not entries:
        raise ValueError("manifest.tsv contains no database entries")

    return PasarGuardManifest(databases=tuple(entries))


def _normalize_member_name(name: str) -> str:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    if name.startswith(("/", "\\")) or normalized in {".", ".."} or normalized.startswith("../"):
        raise ValueError(f"Unsafe archive member path: {name!r}")
    return normalized


def validate_manifest_members(
    manifest: PasarGuardManifest,
    members: set[str],
    *,
    manifest_path: str = "manifest.tsv",
) -> tuple[str, ...]:
    """Validate manifest dump paths against archive members without extracting files."""
    normalized_members = {_normalize_member_name(member) for member in members}
    normalized_manifest_path = _normalize_member_name(manifest_path)
    manifest_dir = posixpath.dirname(normalized_manifest_path)
    errors: list[str] = []
    seen_paths: set[str] = set()
    for entry in manifest.databases:
        try:
            dump_path = _normalize_member_name(entry.dump_file)
            if manifest_dir and "/" not in entry.dump_file.replace("\\", "/").lstrip("/"):
                dump_path = _normalize_member_name(posixpath.join(manifest_dir, dump_path))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if dump_path in seen_paths:
            errors.append(f"Manifest references the same dump more than once: {dump_path!r}")
        seen_paths.add(dump_path)
        if dump_path not in normalized_members:
            errors.append(f"Manifest dump file is missing from archive: {entry.dump_file!r}")
    return tuple(dict.fromkeys(errors))


def read_manifest_from_archive(path: str | Path) -> tuple[PasarGuardManifest | None, tuple[str, ...]]:
    """Read and validate manifest.tsv from a ZIP/TAR without extracting the archive."""
    archive_path = Path(path).expanduser()
    manifest_names: list[str] = []
    manifest_text: str | None = None
    members: set[str] = set()

    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                normalized = _normalize_member_name(info.filename)
                members.add(normalized)
                if posixpath.basename(normalized).lower() == "manifest.tsv":
                    manifest_names.append(normalized)
                    if len(manifest_names) > 1:
                        return None, ("Archive contains multiple manifest.tsv files.",)
                    manifest_text = archive.read(info).decode("utf-8-sig")
    elif archive_path.suffix.lower() in {".tar", ".tgz"} or archive_path.name.lower().endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:*") as archive:
            for info in archive.getmembers():
                normalized = _normalize_member_name(info.name)
                members.add(normalized)
                if posixpath.basename(normalized).lower() == "manifest.tsv":
                    manifest_names.append(normalized)
                    if len(manifest_names) > 1:
                        return None, ("Archive contains multiple manifest.tsv files.",)
                    extracted = archive.extractfile(info)
                    if extracted is None:
                        return None, ("manifest.tsv is not a regular file.",)
                    manifest_text = extracted.read().decode("utf-8-sig")
    else:
        return None, ("PasarGuard manifest inspection requires a ZIP or TAR archive.",)

    if not manifest_names or manifest_text is None:
        return None, ()

    try:
        manifest = parse_manifest_tsv(manifest_text)
    except (UnicodeDecodeError, ValueError) as exc:
        return None, (f"Invalid PasarGuard manifest.tsv: {exc}",)
    return manifest, validate_manifest_members(
        manifest,
        members,
        manifest_path=manifest_names[0],
    )
