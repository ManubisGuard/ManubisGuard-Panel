from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, insert, select, text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, JSONB
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, LargeBinary

from app.migration.schema import LEGACY_COLUMN_ALIASES


@dataclass(frozen=True)
class MariaDBBridgeReport:
    source_tables: int
    copied_tables: int
    skipped_tables: tuple[str, ...]
    source_counts: dict[str, int]
    target_counts: dict[str, int]
    transformations: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_tables": self.source_tables,
            "copied_tables": self.copied_tables,
            "skipped_tables": list(self.skipped_tables),
            "source_counts": self.source_counts,
            "target_counts": self.target_counts,
            "transformations": list(self.transformations),
            "warnings": list(self.warnings),
        }


def _normalize_value(value: Any, column) -> Any:
    if value is None:
        return None
    typ = column.type
    if isinstance(typ, (JSON, JSONB)):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(typ, ARRAY):
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
                return decoded if isinstance(decoded, list) else [value]
            except json.JSONDecodeError:
                return [part.strip() for part in value.split(",") if part.strip()]
        return value
    if isinstance(typ, Boolean):
        return bool(value)
    if isinstance(typ, LargeBinary) and isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(typ, LargeBinary) and isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(typ, DateTime) and isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    if isinstance(typ, Date) and isinstance(value, datetime):
        return value.date()
    return value


def _source_column_name(table: str, target_column: str, source_columns: set[str]) -> str | None:
    if target_column in source_columns:
        return target_column
    aliases = LEGACY_COLUMN_ALIASES.get(table, {})
    for legacy, current in aliases.items():
        if current == target_column and legacy in source_columns:
            return legacy
    if table == "nodes" and target_column == "server_ca" and "certificate" in source_columns:
        return "certificate"
    return None


def _topological_order(tables: dict[str, Table]) -> list[Table]:
    deps: dict[str, set[str]] = {name: set() for name in tables}
    for name, table in tables.items():
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in tables and parent != name:
                deps[name].add(parent)
    ordered: list[Table] = []
    pending = set(tables)
    while pending:
        ready = sorted(name for name in pending if not (deps[name] & pending))
        if not ready:
            ready = sorted(pending)
        for name in ready:
            ordered.append(tables[name])
            pending.remove(name)
    return ordered


async def _set_sequences(target_engine, target_tables: list[Table], copied: set[str]) -> None:
    async with target_engine.begin() as conn:
        for table in target_tables:
            if table.name not in copied:
                continue
            for column in table.columns:
                if not column.primary_key:
                    continue
                result = await conn.execute(
                    text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                    {"table_name": f"public.{table.name}", "column_name": column.name},
                )
                sequence = result.scalar_one_or_none()
                if not sequence:
                    continue
                await conn.execute(
                    text(
                        f'SELECT setval(:sequence, COALESCE((SELECT MAX("{column.name}") '
                        f'FROM public."{table.name}"), 1), '
                        f'COALESCE((SELECT MAX("{column.name}") FROM public."{table.name}"), 0) > 0)'
                    ),
                    {"sequence": sequence},
                )


async def migrate_mariadb_to_postgres(
    source_url: str,
    target_url: str,
    *,
    chunk_size: int = 500,
) -> MariaDBBridgeReport:
    source_engine = create_async_engine(source_url, pool_pre_ping=True)
    target_engine = create_async_engine(target_url, pool_pre_ping=True)
    source_meta = MetaData()
    target_meta = MetaData()
    transformations: list[str] = []
    warnings: list[str] = []
    skipped: list[str] = []
    source_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    copied: set[str] = set()

    try:
        async with source_engine.connect() as source_conn:
            await source_conn.run_sync(source_meta.reflect)
        async with target_engine.connect() as target_conn:
            await target_conn.run_sync(target_meta.reflect)

        source_tables = {
            name: table for name, table in source_meta.tables.items()
            if table.schema in (None, "pasarguard", "public")
        }
        target_tables = {
            name: table for name, table in target_meta.tables.items()
            if table.schema in (None, "public")
        }

        async with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for target in _topological_order(target_tables):
                name = target.name
                source = source_tables.get(name)
                if source is None:
                    continue

                source_cols = {c.name for c in source.columns}
                mappings = []
                for target_col in target.columns:
                    source_name = _source_column_name(name, target_col.name, source_cols)
                    if source_name:
                        mappings.append((target_col, source.c[source_name]))

                if not mappings:
                    skipped.append(name)
                    continue

                count = int((await source_conn.execute(select(text("COUNT(*)")).select_from(source))).scalar_one())
                source_counts[name] = count
                if count == 0:
                    copied.add(name)
                    continue

                result = await source_conn.stream(select(*(src for _, src in mappings)).select_from(source))
                batch: list[dict[str, Any]] = []
                async for row in result:
                    batch.append({
                        target_col.name: _normalize_value(value, target_col)
                        for (target_col, _), value in zip(mappings, row)
                    })
                    if len(batch) >= chunk_size:
                        await target_conn.execute(insert(target), batch)
                        batch.clear()
                if batch:
                    await target_conn.execute(insert(target), batch)

                copied.add(name)
                target_count = int((await target_conn.execute(select(text("COUNT(*)")).select_from(target))).scalar_one())
                target_counts[name] = target_count
                if target_count < count:
                    raise RuntimeError(
                        f"MariaDB bridge row loss in {name}: source={count}, target={target_count}"
                    )

        await _set_sequences(target_engine, _topological_order(target_tables), copied)
        transformations.append(
            f"MariaDB/MySQL -> PostgreSQL bridge copied {len(copied)} table(s) using reflected schemas and typed values."
        )
        transformations.append(
            "Legacy column aliases and nodes.certificate -> nodes.server_ca were mapped during transfer."
        )
        return MariaDBBridgeReport(
            source_tables=len(source_tables),
            copied_tables=len(copied),
            skipped_tables=tuple(skipped),
            source_counts=source_counts,
            target_counts=target_counts,
            transformations=tuple(transformations),
            warnings=tuple(warnings),
        )
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


def run_mariadb_to_postgres(source_url: str, target_url: str) -> MariaDBBridgeReport:
    return asyncio.run(migrate_mariadb_to_postgres(source_url, target_url))
