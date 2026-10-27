"""ManubisGuard migration and backup compatibility engine.

Legacy PasarGuard backups are handled as an external compatibility format.
Production databases are never used as staging targets.
"""

from app.migration.compatibility import (
    TimescaleCompatibility,
    analyze_timescale_sql,
    classify_restore_error,
)
from app.migration.detector import BackupDetection, detect_backup
from app.migration.inspector import SchemaSnapshot, inspect_database
from app.migration.runner import (
    BackupAnalysis,
    MigrationRunResult,
    analyze_backup,
    migrate_manubisguard_staging,
    resolve_staging_timescale_version,
)
from app.migration.staging import (
    MigrationSafetyError,
    StagingDatabase,
    assert_staging_target,
    create_staging_database,
    drop_staging_database,
    restore_backup_into_staging,
    upgrade_staging_database,
)
from app.migration.validator import ValidationResult, validate_migrated_database

__all__ = [
    "BackupAnalysis",
    "BackupDetection",
    "MigrationRunResult",
    "MigrationSafetyError",
    "SchemaSnapshot",
    "StagingDatabase",
    "TimescaleCompatibility",
    "ValidationResult",
    "analyze_backup",
    "analyze_timescale_sql",
    "assert_staging_target",
    "classify_restore_error",
    "create_staging_database",
    "detect_backup",
    "drop_staging_database",
    "inspect_database",
    "migrate_manubisguard_staging",
    "resolve_staging_timescale_version",
    "restore_backup_into_staging",
    "upgrade_staging_database",
    "validate_migrated_database",
]
