# PasarGuard restore hardening

This document records the restore-safety contract implemented by ManubisGuard.

## Reference implementations

- PasarGuard's official scripts project is the primary operational reference for backup/restore lifecycle and disaster-recovery gates.
- PGClockMG is a secondary implementation reference for practical restore failure modes: archive validation, environment preservation, credential reconciliation, TimescaleDB healing, and post-restore health checks.
- We do not copy third-party implementation code. ManubisGuard implements its own isolated staging/cutover architecture.

## Rules

1. Never restore directly into production. A backup is detected and preflighted first, then restored into an isolated staging database.
2. Archive integrity is a hard gate. ZIP/TAR path traversal, duplicate normalized paths, symlink/device/FIFO entries, excessive entry count, and ZIP CRC failures block the restore.
3. Destination DB identity wins. Backup database URL, user, database name, passwords, PostgreSQL environment identity, Docker/Compose/image/container settings are never imported from the backup.
4. Role passwords are source data, not deployment credentials. Plain SQL and Timescale SQL streams suppress the destination role's CREATE/ALTER ROLE password statements and remove password clauses from other role statements.
5. TimescaleDB is version-aware. The pre-2.29 schema_name catalog era and 2.29+ relid era are treated as incompatible catalog layouts. Exact source TimescaleDB version is required when a Timescale restore depends on extension metadata.
6. PostgreSQL compatibility filtering is narrow. PG17's SET transaction_timeout is filtered only when restoring into PostgreSQL <17; unrelated SQL is not silently discarded.
7. Runtime assets are staged, not copied directly. SSL assets referenced by imported runtime configuration must remain under the configured runtime root and are applied only during controlled cutover.
8. Production cutover is transactional at the orchestration layer. A production safety backup and compose-integrity checks are required before and after environment/assets/database changes. Failed health checks trigger rollback.
9. Success means verified startup, not merely successful SQL. Schema validation, durable row-count checks, Alembic head validation, orphan checks, and panel health are part of acceptance.

## Why these rules exist

PostgreSQL documents that cluster dumps can contain global roles and privilege objects and warns that restore executes source SQL with the privileges of the restore connection. It also documents --no-owner as a way to prevent ownership commands from forcing source identities onto the destination. ManubisGuard therefore treats source credentials and deployment identity as untrusted migration input.

PasarGuard has also documented real-world restore failures involving TimescaleDB catalog incompatibility after a restore. ManubisGuard therefore fails closed on TimescaleDB version/catalog mismatches instead of attempting an opaque best-effort restore.

## Validation requirement

Every change to this pipeline must be followed by:

- targeted migration tests;
- a second review of failure/rollback paths;
- GitHub Actions verification when a run is available;
- no claim of a green CI state when GitHub has not reported a completed successful run.


## Adaptive cross-version restore bridge

Version differences are handled as a migration plan, not by replaying a legacy catalog into the production runtime.

1. Detect the source PostgreSQL major from the dump header/TOC and the exact TimescaleDB version from trusted backup metadata/fingerprints.
2. Start an isolated Docker runtime using the **source PostgreSQL major + source TimescaleDB version**. Timescale publishes versioned image tags such as `2.28.2-pg17`, so the source catalog is restored by compatible binaries.
3. Restore the legacy backup only into that isolated runtime.
4. If the destination TimescaleDB is newer and the source is older, upgrade the isolated database extension to the destination TimescaleDB version before exporting. Timescale documents extension upgrades as a separate step and provides a PostgreSQL/Timescale compatibility matrix.
5. Export the validated staging database with the **staging runtime's** `pg_dump`, not the production client's. PostgreSQL recommends using the newer dump tool for cross-major migrations; its output may require targeted editing when loading into an older PostgreSQL major. `--quote-all-identifiers` is recommended for cross-version dumps.
6. Restore the logical SQL into a disposable cutover database on the production PostgreSQL major. Only explicitly known incompatible statements are filtered (currently PostgreSQL 17's `transaction_timeout` for a PostgreSQL 16 target) and destination Timescale extension DDL is suppressed because the cutover database already has the destination extension.
7. Run the complete ManubisGuard validation suite against the cutover database. Production is renamed only after the cutover database passes validation.

### Important boundary

An older source TimescaleDB → newer destination TimescaleDB can use this bridge because the source catalog is first restored in its native runtime and then upgraded in isolation.

A **newer source TimescaleDB → older destination TimescaleDB** is not treated as a blind downgrade. Timescale documents downgrade paths separately and notes that downgrade support is constrained; the engine must use a schema/data portability bridge or require a destination upgrade rather than silently attempting a catalog downgrade.
