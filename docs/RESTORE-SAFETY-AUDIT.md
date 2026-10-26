# Native Restore Safety Audit

Date: 2026-10-26
Repository branch: feature/amnezia-wg
Observed code: pinned PasarGuard restore library cached at /usr/local/lib/manubisguard-native/lib/pasarguard-restore.sh and the tracked native-backup adapter. This is a source-level audit plus isolated test evidence; no production restore was executed.

## Finding: current PostgreSQL/TimescaleDB restore is destructive without a destination DB snapshot

Severity: release-blocking for any API that promises safe production restore.

### Existing protections that do work

- The non-destructive --check path validates archive structure, checksum inventory, database dump shape, recorded server/TimescaleDB versions and exits before stopping services or changing destination data.
- The Restore engine checks engine family and uses TimescaleDB version gates before its destructive database step.
- The SQLite path creates a live database safety snapshot with sqlite3 .backup before replacing it.
- The current implementation saves DATA_DIR and APP_DIR copies before it overwrites those directories. It preserves the destination Compose file and database credentials.
- The production and staging FastAPI restore endpoints remain fail-closed with HTTP 503.

### Identified PostgreSQL/TimescaleDB gaps

1. In the multi-database path, pg_restore_all_user_databases iterates manifest entries, terminates connections, drops each destination database, recreates it and imports the archive dump. There is no snapshot of the current destination cluster before these DROP operations.
2. In the single TimescaleDB path, the engine terminates database connections, drops and recreates the destination database, then imports the dump. It does not take a pre-restore dump of the destination database first.
3. The plain PostgreSQL path feeds a dump containing clean/drop statements into psql. A failure can therefore occur after existing objects have been removed.
4. The error cleanup restarts application services for PostgreSQL/TimescaleDB restores but does not automatically reconstruct the original database state.
5. APP_DIR and DATA_DIR safety copies are made after the database import, immediately before replacing those filesystem trees. They protect those file operations, not a database that has already been dropped.
6. No explicit whole-restore concurrency lock was found in the reviewed restore function. Concurrent restores should be prevented before production activation.

### Required corrective design

- After the operator confirms the operation and application writers are stopped, create a root-only pre-restore database snapshot of all connectable user databases and global role/grant metadata. Use the existing paired native dump helpers and their manifest/version checks rather than inventing another archive format.
- Verify every database dump, the manifest, TimescaleDB version metadata and SHA-256 checksums before any destination database is dropped. If snapshot creation or available-space preflight fails, abort before touching the database and bring the unchanged app back online.
- Keep the original DB snapshot and APP_DIR/DATA_DIR safety copies until the restored application and database have passed post-restore verification.
- If the restore fails after DB mutation, restore the full destination snapshot. If any database or filesystem rollback fails, do not restart the application; report a critical recovery state and retain all snapshots for manual recovery.
- Use a per-install restore lock and record a non-secret operation ID, target container identity, source archive digest, snapshot path, failure stage and rollback outcome.
- Exercise successful restore and injected failure/rollback only on a disposable database/container. Verify the pre-restore DB returns exactly after fault injection; do not run destructive tests against production.
- Keep the FastAPI staging and production restore endpoints disabled until the above is implemented, tested, and the full pytest/CI gates pass.

## Scope limits

This audit inspected panel-side code only. It did not connect to the production database or access remote Node/N2. Node runtime state under /var/lib/pg-node and external host configuration remain a separate recovery workstream described in docs/AWG-BACKUP-COVERAGE.md.
