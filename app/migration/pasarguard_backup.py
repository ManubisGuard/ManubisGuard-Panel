from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        columns = raw_line.split("\t")
        if len(columns) not in (4, 5):
            raise ValueError(
                f"Invalid manifest.tsv row {line_number}: expected 4 or 5 columns"
            )

        name, owner, timescale_raw, dump_file = (column.strip() for column in columns[:4])
        if not name or not owner or not dump_file:
            raise ValueError(f"Invalid manifest.tsv row {line_number}: empty required field")

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
