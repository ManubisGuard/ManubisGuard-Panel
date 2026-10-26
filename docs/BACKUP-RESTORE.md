# Backup and Restore Runbook

## Scope and canonical storage

Standard system-level backup and restore use the paired original PasarGuard backup/restore engine, pinned to a reviewed upstream commit and minimally adapted for this installation. The upstream CLI, helper library names, archive members, and recovery markers are preserved.

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

The adapter downloads the pinned upstream CLI/library bundle on first use and caches it locally. Archives can contain secrets and private keys, so keep them root-only and maintain a secure off-server copy.

## 2. Restore a standard system backup

```bash
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
```

Running `manubis restore` without a path selects an archive interactively. Restore can modify application files and database state; run a complete restore round-trip only in an isolated environment before approving production use. Use `--fresh` only on a new host with empty application/data directories and compatible recovery metadata.

## 3. Create a database-only backup

```bash
manubis backup-db
```

This writes a PostgreSQL custom-format `.dump` file and SHA-256 sidecar under `/opt/manubisguard/backup/database/`, and validates the dump catalog with `pg_restore --list` before reporting success.

For another destination:

```bash
bash scripts/backup-db.sh /path/to/restricted-backup-directory
```

## 4. Verify a database dump

```bash
bash scripts/verify-backup.sh /opt/manubisguard/backup/database/<database>_<timestamp>.dump
```

A successful verification checks the checksum when the sidecar exists and confirms that PostgreSQL can read the archive catalog.

## 5. Restore a database dump into an isolated database

**Never use the production database as the restore target.** The isolated restore drill uses a disposable TimescaleDB container with `--network none` and tmpfs-only storage; it must not connect to the live database or mount its data directory.

```bash
bash scripts/restore-db.sh /opt/manubisguard/backup/database/<database>_<timestamp>.dump manubisguard_restore
```

The script restores the dump into a fresh temporary database, checks user-table and extension counts, and removes the test container on exit. It requires the TimescaleDB test image to already exist locally and does not attempt to pull an image.

## Historical custom full archives

The former `manubisguard-full-*.zip` archive format is separate from the original PasarGuard archive format. The installer disables the custom full-backup timer and restore-agent service, removes their obsolete executables, and preserves existing archives and encryption keys. The custom validator/restore helper has been removed. Do not pass a custom full archive to the original restore engine; use the native engine only for compatible original-format archives.

## Application-level restore test

A database restore is not production-ready until the restored database can be used by a disposable application instance. Minimum checks:

- application starts successfully;
- `/health` returns `{"status":"ok"}`;
- login/session flow works;
- users, subscriptions, nodes and configuration records are readable;
- no unexpected migration is required;
- no production database is modified by the test instance.

## Retention and off-host storage

Do not treat `/opt/manubisguard/backup/` on the same VPS as the disaster-recovery copy. Production policy should include encrypted off-host storage, retention limits, periodic restore drills, and failure monitoring. The panel archive may include `.env`, credentials, and TLS private keys under `/var/lib/manubisguard/`. It does not automatically include external `/etc/letsencrypt/`, Nginx, or remote-node `/var/lib/pg-node/` state. Back up those locations separately when required. Never send the encryption key alongside an off-host archive.
