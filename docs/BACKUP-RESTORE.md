# Backup and Restore Runbook

## Scope and canonical storage

The standard system-level backup and restore commands use the paired original PasarGuard backup/restore implementation, adapted for ManubisGuard. See [Native Backup Architecture](NATIVE-BACKUP-ARCHITECTURE.md) for the pinned source and current validation status.

- System backup/restore root: `/opt/manubisguard/backup/`
- Application root: `/opt/manubisguard-panel/`
- Persistent application data: `/var/lib/manubisguard/`
- Database-only exports: `/opt/manubisguard/backup/database/`
- Cross-panel migration staging: `/var/lib/manubisguard/migration/`

Do not use a database-only export as a full system backup. Cross-panel migration remains an explicit separate workflow.

## 1. Create a standard system backup

```bash
sudo manubis backup
```

The adapter uses a pinned upstream bundle. The first invocation needs HTTPS access to GitHub; later invocations use the local cached bundle. Archives can contain secrets and private keys, so keep them root-only and maintain a secure off-server copy.

## 2. Restore a standard system backup

```bash
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
```

Running `manubis restore` without a path selects an archive interactively. Restore can modify application files and database state; complete an isolated restore round-trip before using this branch on a production host.


## 2. Create a database-only backup

```bash
manubis backup-db
```

This writes a PostgreSQL custom-format `.dump` file and SHA-256 sidecar under `/opt/manubisguard/backup/database/`, and validates the dump catalog with `pg_restore --list` before reporting success.

For another destination:

```bash
bash scripts/backup-db.sh /path/to/restricted-backup-directory
```

## 2. Verify the backup

```bash
bash scripts/verify-backup.sh /opt/manubisguard/backup/database/<database>_<timestamp>.dump
```

A successful verification confirms the checksum when the sidecar exists and confirms that PostgreSQL can read the archive catalog.

## 3. Restore into an isolated database

**Never use the production database as the restore target.** The legacy scripts previously created a named test database inside the configured Compose PostgreSQL service. They now use a disposable TimescaleDB container with `--network none` and tmpfs-only storage; they do not connect to the live database or mount its data directory.

```bash
bash scripts/restore-db.sh /opt/manubisguard/backup/database/<database>_<timestamp>.dump manubisguard_restore
```

The script restores the dump into a fresh temporary database, checks user-table and extension counts, and removes the test container on exit. It requires the TimescaleDB test image to already exist locally and does not attempt to pull an image.

## 4. Native full-archive preflight and restore status

Run the read-only preflight against an archive stored under the canonical full-backup directory:

```bash
sudo python3 /opt/manubisguard-panel/scripts/manubisguard-native-restore.py --check /opt/manubisguard/backup/full/<manubisguard-full-...zip>
```

Preflight checks ZIP integrity, manifest identity, database and filesystem checksums, PostgreSQL archive readability using a disposable offline container when needed, filesystem member/path/link safety, required TLS files and checksums, TLS key/certificate pairing, and available staging disk space. `--check` does not extract files, change the database, or restart services.

Run a full staged restore drill using a temporary filesystem tree and a disposable PostgreSQL container with no network and tmpfs-only database storage:

```bash
sudo python3 /opt/manubisguard-panel/scripts/manubisguard-native-restore.py --stage-test /opt/manubisguard/backup/full/<manubisguard-full-...zip>
```

This verifies that the filesystem archive can be reconstructed without following archived symlinks and that the database dump can be restored and queried in isolation. For v2 archives, it imports PostgreSQL globals and restores each catalogued database into the disposable instance; it refuses the staging restore when the local test image PostgreSQL major or a required TimescaleDB extension version differs from the recorded source version. The temporary filesystem and test container are removed after the run.

**Production native restore is intentionally fail-closed and is not yet enabled.** The future full-backup script now captures cluster globals and every connectable non-template database except the built-in `postgres` database. This change has been syntax-checked and tested with a synthetic multi-database archive, but the new live backup path has deliberately not been run against production yet. A real v2 backup and full v2 staged restore drill are still required before claiming multi-database recovery is verified. `manubis restore <archive>` must not fall back to the migration engine; the CLI will report that the native apply engine is not enabled until destination-preservation rules, a verified safety backup, and rollback are implemented and tested. Application API staging/production restore routes are also fail-closed because the previous staging helper used the configured production PostgreSQL cluster. Use `manubis migrate <archive> --apply` only when you intentionally want a cross-panel migration.

## 5. Validate a database dump

```bash
bash scripts/validate-restore.sh /opt/manubisguard/backup/database/<database>_<timestamp>.dump
```

This compatibility wrapper delegates to the isolated restore drill above. It does not compare against production because the strict no-touch workflow must not query the live database during recovery testing. Application-level invariants should be checked against the isolated restored database before any future deployment approval.

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

Do not treat `/opt/manubisguard/backup/` on the same VPS as the disaster-recovery copy. Production backup policy should include encrypted off-host storage, retention limits, periodic restore drills, and monitoring/alerting for failed backups. The local full archive includes TLS private keys and other secrets; the Telegram delivery workflow must encrypt the archive before transmission and must not transmit the encryption key with it.
