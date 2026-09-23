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
    "BackupDetection",
    "TimescaleCompatibility",
    "analyze_timescale_sql",
    "classify_restore_error",
    "MigrationSafetyError",
    "SchemaSnapshot",
    "StagingDatabase",
    "ValidationResult",
    "assert_staging_target",
    "create_staging_database",
    "detect_backup",
    "drop_staging_database",
    "inspect_database",
    "restore_backup_into_staging",
    "upgrade_staging_database",
    "validate_migrated_database",
]
