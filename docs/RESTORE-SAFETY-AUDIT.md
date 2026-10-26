# Native Restore Safety Audit

Date: 2026-10-26
Repository branch: feature/amnezia-wg
Observed code: pinned PasarGuard restore library cached at /usr/local/lib/pasarguard-scripts/lib/pasarguard-restore.sh and the tracked native-backup adapter. This is a source-level audit plus isolated test evidence; no production restore was executed.

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

## Implementation status (2026-10-27)

The tracked adapter now applies a versioned safety patch to a private copy of the pinned PasarGuard restore library; it does not rewrite the upstream cache or archive format.

The safety helper is installed independently at `/usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py`; the adapter prefers the checkout copy when present and falls back to the installed helper for restore workflows without a checkout. The `pasarguard install-script` bootstrap now downloads and syntax-checks this helper and installs it beside the adapter. Neither installer path was run on the production host as part of this validation.

- Implemented for local PostgreSQL/TimescaleDB: pre-restore dump of all connectable user databases plus globals, disk-space preflight, manifest/dump validation, SHA-256 inventory verification, per-install `flock` lock, database rollback attempt, APP_DIR/DATA_DIR rollback, and fail-closed service restart behavior if rollback is not verified.
- Implemented for SQLite: on a failed restore after destination mutation, restore and re-validate the pre-restore `.backup` snapshot; if no database existed beforehand, remove the partial destination; if rollback cannot be verified, leave application services stopped.
- The SQLite rollback behavior has runtime tests for valid snapshot, corrupt snapshot and previously absent database. The focused backup/restore-related Python set passes 111 tests; Ruff and the shell adapter/transform tests pass.
- The MySQL/MariaDB legacy restore branch is not covered by the new automatic rollback layer. Do not treat the PostgreSQL/TimescaleDB safety implementation as a universal guarantee for those legacy engine types.
- Staging and production FastAPI restore endpoints remain HTTP 503 / fail-closed. No production restore, restart, deploy or database mutation was performed.
- Release is still gated on the full test suite and review of any unrelated baseline failures. Three Phase 5 migration assertions currently fail on both the working tree and a clean archive of HEAD because they expect an earlier Alembic head (`awg2026091901`) while the current migration graph advances to `20261025_host_admin_names`; that unrelated migration test has not been modified.
- Follow-up review on 2026-10-27 found that the database rollback wrapper forwarded the restore credentials into both the restore and administrative argument slots. The wrapper now forwards `admin_user/admin_password` separately to `pg_restore_all_user_databases`, and the patch's idempotency guard refuses to treat a stale marked patch without this fix as complete.
- Regression coverage verifies the rollback function forwards distinct restore/admin credentials, validates a synthetic snapshot's manifest/checksums, rejects a stale marked patch, and confirms reapplying the current safety patch is idempotent. Focused architecture + safety tests: 11 passed; Ruff, shell adapter/transform checks, syntax checks and `git diff --check` passed.
- On 2026-10-27, a real disposable PostgreSQL/TimescaleDB rollback-helper E2E passed with different restore/admin credentials. A full 33-table ORM schema snapshot was validated, linked AWG rows and relationships were mutated, an injected table and temporary group were added, and the helper restored all 11 expected linked rows exactly; the injected table/group were absent afterward. The separate test database rollback also restored two related tables and a foreign-key row exactly. Evidence is under `/opt/manubisguard-work/backup-restore-final-validation/`.
- A second check found and fixed a path conflict: `BACKUP_DIR=/opt/pasarguard/backup` is inside `APP_DIR`, while safety lock/snapshot paths must be outside both `APP_DIR` and `DATA_DIR`. The patch now defaults both to `${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}` and rejects already-patched libraries that still contain the old path.
- The actual `restore_command --file ... --yes` fault-injection/cleanup path then passed in a dedicated disposable PostgreSQL 16 container with service functions mocked. The first import was deliberately failed after mutating the DB and creating a partial table; the real cleanup invoked the rollback helper, logged `DATABASE_ROLLBACK=PASS`, restored the exact pre-restore row, removed the injected table, and exited non-zero as expected for the injected failure. Snapshot and lock were confirmed outside APP_DIR/DATA_DIR. Evidence: `/opt/manubisguard-work/backup-restore-final-validation/restore-command-e2e.9IJh34/`.
- Focused tests after the path fix: 11 safety/architecture tests passed; Ruff, shell adapter/transform, installer update gate/preflight, CLI bootstrap, shell syntax, Python compilation, and `git diff --check` passed. Keep production restore endpoints fail-closed until full-suite/CI and remaining release gates pass.
