from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


def _async_url(database_url: str) -> tuple[str, dict[str, Any]]:
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("Schema inspection requires PostgreSQL/TimescaleDB.")
    if parsed.drivername != "postgresql+asyncpg":
        parsed = parsed.set(drivername="postgresql+asyncpg")
    connect_args: dict[str, Any] = {}
    sslmode = parsed.query.get("sslmode")
    if sslmode == "require":
        connect_args["ssl"] = True
        query = dict(parsed.query)
        query.pop("sslmode", None)
        parsed = parsed.set(query=query)
    elif sslmode in {"verify-ca", "verify-full"}:
        raise ValueError("verify-ca/verify-full requires an explicit SSL context.")
    return parsed.render_as_string(hide_password=False), connect_args


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


@dataclass(frozen=True)
class ForeignKeyInfo:
    table: str
    constrained_columns: tuple[str, ...]
    referred_table: str
    referred_columns: tuple[str, ...]
    referred_schema: str = "public"


@dataclass(frozen=True)
class SchemaSnapshot:
    tables: tuple[str, ...]
    columns: dict[str, tuple[str, ...]]
    row_counts: dict[str, int]
    alembic_versions: tuple[str, ...]
    core_type_counts: dict[str, int]
    settings_invalid_rows: int
    foreign_keys: tuple[ForeignKeyInfo, ...]


def _inspect_sync(connection) -> SchemaSnapshot:
    inspector = inspect(connection)
    tables = tuple(sorted(inspector.get_table_names(schema="public")))
    columns = {
        table: tuple(column["name"] for column in inspector.get_columns(table, schema="public"))
        for table in tables
    }
    row_counts = {
        table: int(
            connection.execute(
                text(f"SELECT COUNT(*) FROM public.{_quote(table)}")
            ).scalar_one()
        )
        for table in tables
    }

    versions = ()
    if "alembic_version" in tables:
        versions = tuple(
            str(value)
            for value in connection.execute(
                text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            ).scalars()
        )

    core_types: dict[str, int] = {}
    if "core_configs" in tables and "type" in columns["core_configs"]:
        rows = connection.execute(
            text("SELECT type::text, COUNT(*) FROM public.core_configs GROUP BY type::text")
        ).all()
        core_types = {str(value): int(count) for value, count in rows}

    settings_invalid = 0
    settings_fields = (
        "telegram",
        "webhook",
        "notification_settings",
        "notification_enable",
        "subscription",
        "hwid",
        "general",
    )
    if "settings" in tables and all(field in columns["settings"] for field in settings_fields):
        conditions = " OR ".join(
            f"{_quote(field)} IS NULL OR json_typeof({_quote(field)}) <> 'object'"
            for field in settings_fields
        )
        settings_invalid = int(
            connection.execute(
                text(f"SELECT COUNT(*) FROM public.settings WHERE {conditions}")
            ).scalar_one()
        )

    foreign_keys: list[ForeignKeyInfo] = []
    for table in tables:
        for fk in inspector.get_foreign_keys(table, schema="public"):
            constrained = tuple(fk.get("constrained_columns") or ())
            referred = tuple(fk.get("referred_columns") or ())
            if fk.get("referred_table") and constrained and referred:
                foreign_keys.append(
                    ForeignKeyInfo(
                        table=table,
                        constrained_columns=constrained,
                        referred_table=str(fk["referred_table"]),
                        referred_columns=referred,
                        referred_schema=str(fk.get("referred_schema") or "public"),
                    )
                )

    return SchemaSnapshot(
        tables=tables,
        columns=columns,
        row_counts=row_counts,
        alembic_versions=versions,
        core_type_counts=core_types,
        settings_invalid_rows=settings_invalid,
        foreign_keys=tuple(foreign_keys),
    )


async def _inspect_async(database_url: str) -> SchemaSnapshot:
    url, connect_args = _async_url(database_url)
    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_sync)
    finally:
        await engine.dispose()


def inspect_database(database_url: str) -> SchemaSnapshot:
    return asyncio.run(_inspect_async(database_url))
