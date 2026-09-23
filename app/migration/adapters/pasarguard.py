from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.migration.async_utils import run_async
from app.migration.detector import BackupDetection
from app.migration.schema import (
    LEGACY_COLUMN_ALIASES,
    is_supported_core_type,
    normalize_core_type,
)
from app.migration.staging import MigrationSafetyError


LEGACY_SNAPSHOT_NODE_CERTIFICATE = "_manubisguard_legacy_node_certificate"


@dataclass(frozen=True)
class PasarGuardMigrationReport:
    source: str
    detection: BackupDetection
    source_revision: str | None
    target_revision: str
    transformations: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers


class PasarGuardAdapter:
    """Legacy PasarGuard compatibility adapter.

    The adapter owns source-to-ManubisGuard normalization. It runs only after the
    database has been restored into an isolated staging database and upgraded by
    ManubisGuard Alembic.
    """

    name = "pasarguard"
    target_product = "manubisguard"

    @staticmethod
    def current_target_revision() -> str:
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        return ScriptDirectory.from_config(config).get_current_head()

    def plan(
        self,
        path: str,
        detection: BackupDetection,
    ) -> PasarGuardMigrationReport:
        blockers: list[str] = []
        warnings: list[str] = []
        transformations = (
            "preserve legacy primary keys where possible",
            "apply ManubisGuard Alembic migrations in staging",
            "normalize legacy column aliases when both forms exist",
            "normalize core_configs.type aliases",
            "preserve settings JSON and unknown keys unless explicitly unsafe",
            "validate foreign-key graph before production cutover",
        )

        if not detection.is_pasarguard:
            blockers.append("Backup is not positively identified as PasarGuard.")
        if not is_supported_core_type("amneziawg"):
            blockers.append("Target ManubisGuard build does not advertise AmneziaWG support.")

        warnings.append(
            "Historical telemetry is treated separately; missing telemetry never fabricates data."
        )

        return PasarGuardMigrationReport(
            source=str(path),
            detection=detection,
            source_revision=detection.schema_revision,
            target_revision=self.current_target_revision(),
            transformations=transformations,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    @staticmethod
    def normalize_core_type(value: str | None) -> str:
        return normalize_core_type(value)

    async def _prepare_async(self, database_url: str) -> tuple[str, ...]:
        parsed = make_url(database_url)
        if not parsed.drivername.startswith("postgresql"):
            raise MigrationSafetyError("PasarGuard adapter requires PostgreSQL/TimescaleDB.")
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
            raise MigrationSafetyError("verify-ca/verify-full requires an explicit SSL context.")

        engine = create_async_engine(
            parsed.render_as_string(hide_password=False),
            poolclass=NullPool,
            connect_args=connect_args,
        )
        try:
            async with engine.begin() as connection:
                tables = {
                    str(value)
                    for value in (
                        await connection.execute(
                            text(
                                "SELECT table_name FROM information_schema.tables "
                                "WHERE table_schema='public'"
                            )
                        )
                    ).scalars()
                }
                if "nodes" not in tables:
                    return ()

                columns = {
                    str(value)
                    for value in (
                        await connection.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_schema='public' AND table_name='nodes'"
                            )
                        )
                    ).scalars()
                }
                if "certificate" not in columns or "server_ca" in columns:
                    return ()

                await connection.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS public.{LEGACY_SNAPSHOT_NODE_CERTIFICATE} (
                            node_id integer PRIMARY KEY,
                            certificate varchar(2048)
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        f"""
                        INSERT INTO public.{LEGACY_SNAPSHOT_NODE_CERTIFICATE} (node_id, certificate)
                        SELECT id, certificate
                        FROM public.nodes
                        WHERE certificate IS NOT NULL
                        ON CONFLICT (node_id) DO UPDATE
                        SET certificate = EXCLUDED.certificate
                        """
                    )
                )
                return ("captured nodes.certificate before upstream Alembic removes it",)
        finally:
            await engine.dispose()

    def prepare(self, database_url: str) -> tuple[str, ...]:
        return run_async(self._prepare_async(database_url))

    async def _apply_async(self, database_url: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        parsed = make_url(database_url)
        if not parsed.drivername.startswith("postgresql"):
            raise MigrationSafetyError("PasarGuard adapter requires PostgreSQL/TimescaleDB.")

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
            raise MigrationSafetyError("verify-ca/verify-full requires an explicit SSL context.")

        engine = create_async_engine(
            parsed.render_as_string(hide_password=False),
            poolclass=NullPool,
            connect_args=connect_args,
        )
        transformations: list[str] = []
        warnings: list[str] = []
        try:
            async with engine.begin() as connection:
                table_names = {
                    str(value)
                    for value in (
                        await connection.execute(
                            text(
                                "SELECT table_name FROM information_schema.tables "
                                "WHERE table_schema='public'"
                            )
                        )
                    ).scalars()
                }

                if (
                    LEGACY_SNAPSHOT_NODE_CERTIFICATE in table_names
                    and "nodes" in table_names
                ):
                    columns = {
                        str(value)
                        for value in (
                            await connection.execute(
                                text(
                                    "SELECT column_name FROM information_schema.columns "
                                    "WHERE table_schema='public' AND table_name='nodes'"
                                )
                            )
                        ).scalars()
                    }
                    if "server_ca" in columns:
                        result = await connection.execute(
                            text(
                                f"""
                                UPDATE public.nodes AS n
                                SET server_ca = s.certificate
                                FROM public.{LEGACY_SNAPSHOT_NODE_CERTIFICATE} AS s
                                WHERE n.id = s.node_id
                                  AND (n.server_ca IS NULL OR n.server_ca = '')
                                  AND s.certificate IS NOT NULL
                                """
                            )
                        )
                        if result.rowcount:
                            transformations.append(
                                f"restored nodes.server_ca from legacy certificate for {result.rowcount} node(s)"
                            )

                # Refresh the table list because the adapter may have handled a
                # legacy table before the normal column-alias phase.
                for table, aliases in LEGACY_COLUMN_ALIASES.items():
                    if table not in table_names:
                        continue
                    rows = await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema='public' AND table_name=:table"
                        ),
                        {"table": table},
                    )
                    columns = {str(value) for value in rows.scalars()}
                    for legacy, current in aliases.items():
                        if legacy not in columns or current not in columns:
                            continue
                        result = await connection.execute(
                            text(
                                f'UPDATE "{table}" '
                                f'SET "{current}" = "{legacy}" '
                                f'WHERE "{current}" IS NULL AND "{legacy}" IS NOT NULL'
                            )
                        )
                        if result.rowcount:
                            transformations.append(
                                f"copied {table}.{legacy} → {table}.{current} for {result.rowcount} row(s)"
                            )

                if "core_configs" in table_names:
                    values = await connection.execute(
                        text(
                            "SELECT DISTINCT type::text FROM public.core_configs "
                            "WHERE type IS NOT NULL ORDER BY 1"
                        )
                    )
                    raw_values = [str(value) for value in values.scalars()]
                    unsupported = [
                        value
                        for value in raw_values
                        if not is_supported_core_type(normalize_core_type(value))
                    ]
                    if unsupported:
                        raise MigrationSafetyError(
                            "Legacy core_configs contains unsupported type value(s): "
                            + ", ".join(sorted(unsupported))
                        )
                    for raw in raw_values:
                        normalized = normalize_core_type(raw)
                        if normalized == raw:
                            continue
                        result = await connection.execute(
                            text(
                                "UPDATE public.core_configs SET type=:normalized "
                                "WHERE type::text=:raw"
                            ),
                            {"normalized": normalized, "raw": raw},
                        )
                        if result.rowcount:
                            transformations.append(
                                f"normalized core_configs.type {raw!r} → {normalized!r} "
                                f"for {result.rowcount} row(s)"
                            )
                if LEGACY_SNAPSHOT_NODE_CERTIFICATE in table_names:
                    await connection.execute(
                        text(f"DROP TABLE public.{LEGACY_SNAPSHOT_NODE_CERTIFICATE}")
                    )
                    transformations.append("removed temporary legacy snapshot table")


        finally:
            await engine.dispose()

        return tuple(transformations), tuple(warnings)

    def apply(self, database_url: str) -> tuple[str, ...]:
        transformations, _warnings = run_async(self._apply_async(database_url))
        return transformations
