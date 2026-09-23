from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db.base import Base
from app.migration.inspector import ForeignKeyInfo, SchemaSnapshot, _async_url, _quote
from app.migration.schema import is_supported_core_type, normalize_core_type


def current_model_tables() -> tuple[str, ...]:
    import app.db.models  # noqa: F401

    return tuple(sorted(Base.metadata.tables))


def application_head() -> str:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


@dataclass(frozen=True)
class OrphanCheck:
    table: str
    referred_table: str
    rows: int


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    blocking_errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    snapshot: SchemaSnapshot | None = None
    missing_target_tables: tuple[str, ...] = field(default_factory=tuple)
    orphan_checks: tuple[OrphanCheck, ...] = field(default_factory=tuple)


def _orphan_sql(fk: ForeignKeyInfo) -> str:
    join = " AND ".join(
        f"s.{_quote(source)} = t.{_quote(target)}"
        for source, target in zip(fk.constrained_columns, fk.referred_columns, strict=True)
    )
    nonnull = " AND ".join(f"s.{_quote(column)} IS NOT NULL" for column in fk.constrained_columns)
    target_null = f"t.{_quote(fk.referred_columns[0])} IS NULL"
    return (
        f"SELECT COUNT(*) FROM public.{_quote(fk.table)} AS s "
        f"LEFT JOIN public.{_quote(fk.referred_table)} AS t ON {join} "
        f"WHERE {nonnull} AND {target_null}"
    )


async def _orphan_checks(database_url: str, snapshot: SchemaSnapshot) -> tuple[OrphanCheck, ...]:
    url, connect_args = _async_url(database_url)
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        async with engine.connect() as connection:
            def run(sync_connection) -> tuple[OrphanCheck, ...]:
                existing = set(snapshot.tables)
                found: list[OrphanCheck] = []
                for fk in snapshot.foreign_keys:
                    if (
                        fk.referred_schema != "public"
                        or fk.table not in existing
                        or fk.referred_table not in existing
                    ):
                        continue
                    rows = int(sync_connection.execute(text(_orphan_sql(fk))).scalar_one())
                    if rows:
                        found.append(OrphanCheck(fk.table, fk.referred_table, rows))
                return tuple(found)

            return await connection.run_sync(run)
    finally:
        await engine.dispose()


def validate_migrated_database(
    database_url: str,
    *,
    expected_revision: str | None = None,
) -> ValidationResult:
    if not make_url(database_url).drivername.startswith("postgresql"):
        return ValidationResult(False, ("Integrity validation requires PostgreSQL/TimescaleDB.",))

    from app.migration.inspector import inspect_database

    snapshot = inspect_database(database_url)
    head = expected_revision or application_head()
    errors: list[str] = []
    warnings: list[str] = []

    required = current_model_tables()
    missing = tuple(sorted(set(required) - set(snapshot.tables)))
    if missing:
        errors.append("Missing target model tables: " + ", ".join(missing))

    if snapshot.alembic_versions != (head,):
        errors.append(
            f"Alembic revision mismatch: expected [{head}], found [{', '.join(snapshot.alembic_versions) or 'none'}]."
        )

    invalid_types = [
        value
        for value in snapshot.core_type_counts
        if not is_supported_core_type(normalize_core_type(value))
    ]
    if invalid_types:
        errors.append("Unsupported core_configs.type values: " + ", ".join(sorted(invalid_types)))

    if snapshot.settings_invalid_rows:
        errors.append(f"settings has {snapshot.settings_invalid_rows} invalid JSON object row(s).")

    orphan_checks = asyncio.run(_orphan_checks(database_url, snapshot))
    errors.extend(
        f"Foreign-key integrity failure: {check.table} -> {check.referred_table} has {check.rows} orphan row(s)."
        for check in orphan_checks
    )

    telemetry = {
        "node_usages",
        "node_user_usages",
        "node_usage_reset_logs",
        "admin_usage_logs",
        "user_usage_reset_logs",
        "node_stats",
    }
    if not (telemetry & set(snapshot.tables)):
        warnings.append("No telemetry tables were found; historical usage/statistics may be absent from the source.")

    return ValidationResult(
        valid=not errors,
        blocking_errors=tuple(errors),
        warnings=tuple(warnings),
        snapshot=snapshot,
        missing_target_tables=missing,
        orphan_checks=orphan_checks,
    )
