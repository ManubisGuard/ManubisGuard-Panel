#!/usr/bin/env python3
"""Compare logical table and Timescale hypertable row counts after migration."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class CountRow:
    schema: str
    name: str
    count: int


async def fetch_counts(
    database_url: str,
) -> tuple[dict[tuple[str, str], CountRow], dict[tuple[str, str], CountRow]]:
    conn = await asyncpg.connect(database_url)
    try:
        tables = await conn.fetch(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_schema NOT LIKE '_timescaledb%'
            ORDER BY table_schema, table_name
            """
        )
        table_counts: dict[tuple[str, str], CountRow] = {}
        for row in tables:
            key = (row["table_schema"], row["table_name"])
            value = await conn.fetchval(
                'SELECT count(*) FROM "{}"."{}"'.format(
                    row["table_schema"].replace('"', '""'),
                    row["table_name"].replace('"', '""'),
                )
            )
            table_counts[key] = CountRow(*key, int(value))

        hypertables = await conn.fetch(
            """
            SELECT hypertable_schema, hypertable_name
            FROM timescaledb_information.hypertables
            WHERE is_distributed = false
            ORDER BY hypertable_schema, hypertable_name
            """
        )
        hypertable_counts: dict[tuple[str, str], CountRow] = {}
        for row in hypertables:
            key = (row["hypertable_schema"], row["hypertable_name"])
            value = await conn.fetchval(
                'SELECT count(*) FROM "{}"."{}"'.format(
                    row["hypertable_schema"].replace('"', '""'),
                    row["hypertable_name"].replace('"', '""'),
                )
            )
            hypertable_counts[key] = CountRow(*key, int(value))
        return table_counts, hypertable_counts
    finally:
        await conn.close()


def compare(
    source: tuple[dict[tuple[str, str], CountRow], dict[tuple[str, str], CountRow]],
    destination: tuple[dict[tuple[str, str], CountRow], dict[tuple[str, str], CountRow]],
) -> list[str]:
    errors: list[str] = []
    for label, source_rows, destination_rows in (
        ("table", source[0], destination[0]),
        ("hypertable", source[1], destination[1]),
    ):
        source_keys = set(source_rows)
        destination_keys = set(destination_rows)
        for key in sorted(source_keys | destination_keys):
            source_count = source_rows.get(key)
            destination_count = destination_rows.get(key)
            if source_count is None or destination_count is None:
                errors.append(
                    f"{label} {key[0]}.{key[1]} missing "
                    f"(source={source_count is not None}, destination={destination_count is not None})"
                )
                continue
            if source_count.count != destination_count.count:
                errors.append(
                    f"{label} {key[0]}.{key[1]} count mismatch: "
                    f"source={source_count.count}, destination={destination_count.count}"
                )
    return errors


async def main(source_url: str, destination_url: str) -> int:
    source = await fetch_counts(source_url)
    destination = await fetch_counts(destination_url)

    print("Source table counts:")
    for row in source[0].values():
        print(f"  {row.schema}.{row.name}={row.count}")
    print("Destination table counts:")
    for row in destination[0].values():
        print(f"  {row.schema}.{row.name}={row.count}")
    print("Source hypertable counts:")
    for row in source[1].values():
        print(f"  {row.schema}.{row.name}={row.count}")
    print("Destination hypertable counts:")
    for row in destination[1].values():
        print(f"  {row.schema}.{row.name}={row.count}")

    errors = compare(source, destination)
    if errors:
        print("COUNT VERIFICATION FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("COUNT VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--destination-url", required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.source_url, args.destination_url)))
