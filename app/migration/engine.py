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
    """Build a non-destructive migration plan for a PasarGuard backup.

    The executable migration path lives in runner.py and the host-side
    production cutover helper. This function intentionally remains planning-only.
    """
    result = preflight_backup(path)
    actions = (
        "detect source backup and schema",
        "restore source into isolated staging database",
        "map legacy schema to current ManubisGuard schema",
        "run ManubisGuard Alembic migrations to head",
        "validate foreign keys, orphan rows, counts and protocol data",
        "validate and export the staged ManubisGuard database",
        "create production-server cutover database",
        "validate cutover database before production rename",
        "create production safety backup",
        "swap database names only after all validations pass",
        "apply only after validation succeeds",
    )
    return MigrationPlan(
        source=str(path),
        target_product="manubisguard",
        preflight=result,
        actions=actions,
    )
