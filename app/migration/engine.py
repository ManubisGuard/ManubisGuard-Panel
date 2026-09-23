from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.migration.preflight import PreflightResult, preflight_backup


@dataclass(frozen=True)
class MigrationPlan:
    source: str
    target_product: str
    preflight: PreflightResult
    actions: tuple[str, ...]


def plan_pasarguard_migration(path: str | Path) -> MigrationPlan:
    """Build a non-destructive migration plan.

    Phase 1 intentionally stops before writing to any database. Later phases
    will execute the plan against a temporary PostgreSQL/TimescaleDB database,
    validate it, and only then perform the production swap/restore.
    """
    result = preflight_backup(path)
    actions = (
        "detect source backup and schema",
        "restore source into isolated staging database",
        "map legacy schema to current ManubisGuard schema",
        "run ManubisGuard Alembic migrations to head",
        "validate foreign keys, orphan rows, counts and protocol data",
        "create production safety backup",
        "apply only after validation succeeds",
    )
    return MigrationPlan(
        source=str(path),
        target_product="manubisguard",
        preflight=result,
        actions=actions,
    )
