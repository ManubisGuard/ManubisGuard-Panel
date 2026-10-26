# Native PasarGuard Backup and Restore

## Architecture contract

The standard system-level commands call the paired original PasarGuard backup/restore implementation pinned to commit `21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7`. The upstream CLI and its matching libraries remain intact. The adapter `scripts/manubisguard-native-backup.sh` makes only the compatibility changes needed by this installation: explicit ManubisGuard paths, an override for the archive destination, and the cron command path for the public `manubis` CLI. It does not rename upstream functions, libraries, archive members, or recovery markers.

- System backup/restore root: `/opt/manubisguard/backup/`
- Application root: `/opt/manubisguard-panel/`
- Persistent application data: `/var/lib/manubisguard/`
- Database-only exports: `/opt/manubisguard/backup/database/`
- Cross-panel migration workspace: `/var/lib/manubisguard/migration/`

The upstream CLI/library bundle is pinned and cached under `/usr/local/lib/manubisguard-native/`. On first use, HTTPS access to GitHub is required to fetch that exact commit. The adapter verifies all downloaded files with `bash -n` before caching them, then copies the bundle to a temporary working directory and validates the minimally patched copy before running any backup/restore command. It does not expose upstream install/update/uninstall operations.

`APP_NAME=manubisguard-panel` is intentional: the installer uses that Compose project name. `APP_DIR`, `DATA_DIR`, and `BACKUP_DIR` are explicitly set so the original engine targets this panel and the canonical archive directory without changing the archive format.

## Commands

```bash
sudo manubis backup
sudo manubis restore
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

Restore without a path offers the upstream interactive archive selection. `--fresh` is intended only for a new host with empty application/data directories and compatible recovery metadata/image information. Legacy archives without this metadata require a compatible existing installation. A normal restore is destructive and must be tested only in an isolated environment before production use.

The upstream archive keys, including `pasarguard_data/` and `.pasarguard-fresh-restore`, remain unchanged. These are compatibility identifiers inside the archive, not runtime paths.

## Separation of responsibilities

- `manubis backup` / `manubis restore`: standard host/panel backup and recovery using the paired original PasarGuard engine.
- `manubis backup-db` and the panel backup API: database-only exports.
- `manubis migrate`: intentional cross-panel import using its separate migration executor and staging logic.

Do not pass a full native system archive to the migration command as a substitute for normal restore. The installer disables the custom full-backup timer and restore-agent service, removes obsolete helper executables, and preserves existing custom-format archives and their encryption keys. The custom restore validator has been removed; those archives are not assumed to be compatible with the upstream engine.

## Archive coverage and limitations

Panel-side Node records and connection material (including the `nodes` row's `api_key`, `server_ca`, address/ports and Core assignments) are stored in the panel database and are included when the configured application database is captured. Treat the archive as sensitive. The panel backup does not include remote Node runtime state or Node-local secrets, nor external host files such as `/etc/letsencrypt` and Nginx configuration. The separate ManubisGuard Node service stores generated runtime configuration and TLS material under `/var/lib/pg-node/` by default; back up that state on each relevant node/host separately.

## Validation status (updated 2026-10-26)

- The native adapter and offline compatibility fixture have passed their focused shell checks.
- A disposable end-to-end native backup, `restore --check`, and real restores were completed. The original round-trip tested a subset of AWG fields; a follow-up round-trip on 2026-10-26 tested all 16 code-defined lower-case AWG keys (`jc/jmin/jmax/s1-s4/h1-h4/i1-i5`) after deliberately mutating the destination, along with `type=amneziawg` and the Node-to-Core relationship. See `docs/AWG-BACKUP-COVERAGE.md`, `docs/backup-restore-progress.md`, and the isolated logs under `/opt/manubisguard-work/awg-native-roundtrip-20261026/`. The minimal fixture directly covers `core_configs` and `nodes`; user/host/subnet linked rows still need a broader integration fixture.
- The focused Python suite (`tests/test_backup_restore_fail_closed.py`, `tests/test_native_backup_architecture.py`, `tests/migration`, and `tests/compatibility`) passed: 94 tests. Ruff and shell syntax checks also passed.
- The full pytest suite and the GitHub Actions result for the latest revision are still unconfirmed. Do not enable production API restore or deploy until full-suite/CI gates and the remaining recovery-safety requirements pass. Production restore endpoints remain fail-closed.
- Tests used disposable environments only; no production restore, restart, or deploy was performed.
