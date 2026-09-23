"""ManubisGuard migration and backup compatibility engine.

The migration package is intentionally independent from the product branding
inside the legacy database. Legacy PasarGuard backups are treated as an
external format and detected through explicit adapters.
"""

from app.migration.detector import BackupDetection, detect_backup

__all__ = ["BackupDetection", "detect_backup"]
