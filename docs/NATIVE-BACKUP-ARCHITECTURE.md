# Native PasarGuard Backup and Restore

## Architecture contract

The standard system-level commands call the paired original PasarGuard backup/restore implementation pinned to commit `21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7`. The upstream CLI and its matching libraries remain intact. The adapter `scripts/manubisguard-native-backup.sh` makes only the compatibility changes needed by this installation: explicit official PasarGuard paths, an override for the archive destination, and the cron command path for the public `pasarguard` CLI. It does not rename upstream functions, libraries, archive members, or recovery markers.

- System backup/restore root: `/opt/pasarguard/backup/`
- Application root: `/opt/pasarguard/`
- Persistent application data: `/var/lib/pasarguard/`
- Database-only exports: `/opt/pasarguard/backup/database/`
- Restore safety snapshots and per-install lock: `/var/backups/pasarguard/restore-safety/` (override with `PASARGUARD_RESTORE_SAFETY_DIR`; intentionally outside APP_DIR/DATA_DIR)
- Cross-panel migration workspace: `/var/lib/pasarguard/migration/`

The upstream CLI/library bundle is pinned and cached under `/usr/local/lib/pasarguard-scripts/`. On first use, HTTPS access to GitHub is required to fetch that exact commit. The adapter verifies all downloaded files with `bash -n` before caching them, then copies the bundle to a temporary working directory and validates the minimally patched copy before running any backup/restore command. It does not expose upstream install/update/uninstall operations.

`APP_NAME=pasarguard` is intentional: the installer uses that Compose project name. `APP_DIR`, `DATA_DIR`, and `BACKUP_DIR` are explicitly set so the original engine targets this panel and the canonical archive directory without changing the archive format.

## Commands

```bash
sudo pasarguard backup
sudo pasarguard restore
sudo pasarguard restore /path/to/backup.zip --check
sudo pasarguard restore /path/to/backup.zip
sudo pasarguard restore --fresh /path/to/backup.zip
sudo pasarguard backup-service
```

Restore without a path offers the upstream interactive archive selection. `--fresh` is intended only for a new host with empty application/data directories and compatible recovery metadata/image information. Legacy archives without this metadata require a compatible existing installation. A normal restore is destructive and must be tested only in an isolated environment before production use.

The upstream archive keys, including `pasarguard_data/` and `.pasarguard-fresh-restore`, remain unchanged. These are compatibility identifiers inside the archive, not runtime paths.

## Separation of responsibilities

- `pasarguard backup` / `pasarguard restore`: standard host/panel backup and recovery using the paired original PasarGuard engine.
- `pasarguard backup-db` and the panel backup API: database-only exports.
- `pasarguard migrate`: intentional cross-panel import using its separate migration executor and staging logic.

Do not pass a full native system archive to the migration command as a substitute for normal restore. The installer disables the custom full-backup timer and restore-agent service, removes obsolete helper executables, and preserves existing custom-format archives and their encryption keys. The custom restore validator has been removed; those archives are not assumed to be compatible with the upstream engine.

## Archive coverage and limitations

Panel-side Node records and connection material (including the `nodes` row's `api_key`, `server_ca`, address/ports and Core assignments) are stored in the panel database and are included when the configured application database is captured. Treat the archive as sensitive. The panel backup does not include remote Node runtime state or Node-local secrets, nor external host files such as `/etc/letsencrypt` and Nginx configuration. The separate ManubisGuard Node service stores generated runtime configuration and TLS material under `/var/lib/pg-node/` by default; back up that state on each relevant node/host separately.

## Validation status (updated 2026-10-27)

- The native adapter and offline compatibility fixture have passed their focused shell checks.
- A disposable end-to-end native backup, `restore --check`, and real restores were completed. The 2026-10-26 round-trip tested all 16 code-defined lower-case AWG keys (`jc/jmin/jmax/s1-s4/h1-h4/i1-i5`), `type=amneziawg`, and the Node-to-Core relationship. See `docs/AWG-BACKUP-COVERAGE.md`, `docs/backup-restore-progress.md`, and the isolated logs under `/opt/manubisguard-work/awg-native-roundtrip-20261026/`.
- On 2026-10-27, a separate full-schema PostgreSQL rollback test created all 33 ORM tables in a disposable DB, captured a full `pg_dump` plus globals/manifest/checksums, mutated the AWG user, host/inbound, group associations, Core/Node relationship and WireGuard subnet allocator, and added an injected-failure table. After invoking the database rollback helper with distinct restore/admin credentials, the JSON representations of all 11 linked fixture rows exactly matched their pre-mutation state; the injected table and temporary group were absent. Markers and evidence are in `docs/AWG-BACKUP-COVERAGE.md` and `/opt/manubisguard-work/backup-restore-final-validation/awg-linked-roundtrip.PyZqqw/`.
- This expands database rollback coverage beyond `core_configs` and `nodes`; the expanded AWG fixture is still a direct database rollback-helper test, not a full native archive/CLI round-trip. Separately, the actual `restore_command --file ... --yes` cleanup path passed a PostgreSQL fault-injection test with the service lifecycle mocked: the import was forced to fail after mutating the DB, the real rollback helper restored the pre-restore row, the injected table disappeared, and `DATABASE_ROLLBACK=PASS` was written to the restore log. Evidence: `/opt/manubisguard-work/backup-restore-final-validation/restore-command-e2e.9IJh34/`.
- The focused Python suite (`tests/test_backup_restore_fail_closed.py`, `tests/test_native_backup_architecture.py`, `tests/migration`, and `tests/compatibility`) passed: 94 tests. Ruff and shell syntax checks also passed.
- A follow-up review on 2026-10-27 corrected the PostgreSQL rollback helper to pass administrative credentials separately from restore credentials. The focused safety/architecture tests now pass 11 tests, plus Ruff and shell adapter/transform checks.
- The database rollback helper and the actual `restore_command` failure/cleanup orchestration have both now passed isolated PostgreSQL fault-injection tests after the credential and safety-path fixes. The latter deliberately returned exit code 1 because the injected import failed, while the rollback marker and pre-restore DB state were verified. Keep production API restore disabled until full-suite/CI and the remaining release gates pass.
- The full pytest suite and the GitHub Actions result for the latest revision are still unconfirmed. Do not enable production API restore or deploy until full-suite/CI gates and the remaining recovery-safety requirements pass. Production restore endpoints remain fail-closed.
- Tests used disposable environments only; no production restore, restart, or deploy was performed.
