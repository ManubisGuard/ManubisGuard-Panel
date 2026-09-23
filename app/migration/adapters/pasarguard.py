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
    target_revision = "awg2026091901"

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
            target_revision=self.target_revision,
            transformations=transformations,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    @staticmethod
    def normalize_core_type(value: str | None) -> str:
        return normalize_core_type(value)

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
                table_names = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT table_name FROM information_schema.tables "
                                "WHERE table_schema='public'"
                            )
                        )
                    ).scalars()
                )

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

        finally:
            await engine.dispose()

        return tuple(transformations), tuple(warnings)

    def apply(self, database_url: str) -> tuple[str, ...]:
        transformations, _warnings = run_async(self._apply_async(database_url))
        return transformations
