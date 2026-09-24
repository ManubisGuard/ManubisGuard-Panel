# Backup and Restore Runbook

## Scope

This runbook covers PostgreSQL/TimescaleDB backups for the ManubisGuard all-in-one deployment. The production database is the `timescaledb` Compose service and is persisted under `/var/lib/manubisguard/timescaledb`.

## 1. Create a backup

Run on the deployment host:

```bash
cd /opt/manubisguard-panel
bash scripts/backup-db.sh
```

The default destination is `/var/lib/manubisguard/backups`. A PostgreSQL custom-format `.dump` file and a SHA-256 sidecar are created. The archive is also opened with `pg_restore --list` before the command reports success.

For another destination:

```bash
bash scripts/backup-db.sh /var/backups/manubisguard
```

## 2. Verify the backup

```bash
bash scripts/verify-backup.sh /var/lib/manubisguard/backups/<database>_<timestamp>.dump
```

A successful verification confirms the checksum when the sidecar exists and confirms that PostgreSQL can read the archive catalog.

## 3. Restore into an isolated database

**Never use the production database as the restore target.**

```bash
bash scripts/restore-db.sh /var/lib/manubisguard/backups/<database>_<timestamp>.dump manubisguard_restore
```

The script drops/recreates only the named validation database and restores the archive there. It explicitly refuses to target the configured production database.

## 4. Validate the restored database

```bash
bash scripts/validate-restore.sh manubisguard_restore
```

The validation compares production and restored public table counts, Alembic revision, and Timescale hypertable counts. A future hardening pass should add application-specific row-count and invariant checks for the most important entities.

## 5. Application-level restore test

A database restore is not considered production-ready until the restored database can be used by a disposable application instance. The disposable instance must use the restored database and must not share the production write path.

Minimum checks:

- application starts successfully;
- `/health` returns `{"status":"ok"}`;
- login/session flow works;
- users, subscriptions, nodes and configuration records are readable;
- no migration is unexpectedly required;
- no production database is modified by the test instance.

## 6. Rollback test

The final disaster-recovery gate is a controlled rollback test. It should be performed against a disposable environment first. Record:

- backup timestamp;
- backup SHA-256;
- source database size;
- restore duration;
- restored table/hypertable counts;
- Alembic revision;
- application health result;
- application smoke-test result.

## Current deployment health gate

The all-in-one container health check uses `/code/healthcheck.sh`, which supports the deployment's HTTP/HTTPS/UDS binding modes. The current Compose health check invokes that script rather than assuming plain HTTP on port 8000.

## Retention and off-host storage

Do not treat `/var/lib/manubisguard/backups` on the same VPS as the disaster-recovery copy. Production backup policy should include encrypted off-host storage, retention limits, periodic restore drills, and monitoring/alerting for failed backups.
