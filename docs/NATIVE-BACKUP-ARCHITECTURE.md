# Native ManubisGuard Backup and Restore

## Architecture contract

The standard system-level commands are backed by the paired PasarGuard backup/restore implementation, adapted for ManubisGuard. The CLI adapter is `scripts/manubisguard-native-backup.sh`; it pins upstream source to commit `21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7`, uses the upstream CLI and matching helper libraries together, and applies the ManubisGuard product names and paths in a temporary working copy.

- Canonical system backup root: `/opt/manubisguard/backup/`
- Application/configuration root: `/opt/manubisguard-panel/`
- Persistent application data: `/var/lib/manubisguard/`
- Database-only panel exports: `/opt/manubisguard/backup/database/`
- Cross-panel migration workspace: `/var/lib/manubisguard/migration/`

The installer places the adapter at `/usr/local/bin/manubisguard-native-backup`, including for a standalone CLI bootstrap used during fresh recovery. It caches the pinned upstream bundle under `/usr/local/lib/manubisguard-native/`. On the first use, it requires HTTPS access to GitHub to fetch that exact commit. It checks that all files are present and pass `bash -n` before publishing the cache. Subsequent runs use the cached bundle. The upstream bundle is not used for install/update/uninstall commands.

## Commands

```bash
sudo manubis backup
sudo manubis restore
sudo manubis restore /path/to/backup.zip
sudo manubis restore /path/to/backup.zip --check
sudo manubis backup-service
```

Restore without an archive path offers the upstream numbered archive selection from the canonical backup root. An explicit archive path is supported by the upstream restore CLI. The standard restore command is separate from `manubis migrate`; migration is still the explicit cross-panel workflow and retains its own staging and validation logic.

## Archive coverage and limitations

The upstream backup/restore implementation captures the panel configuration, persistent application data, and database using engine-aware backup routines rather than copying a live database data directory. It includes validation and compatibility checks from the pinned upstream implementation. The original archive format is retained; this adapter does not substitute the custom `manubisguard-full-*.zip` format.

AmneziaWG/WireGuard-specific runtime state must only be added after its actual configured storage locations, secrets, service definitions, and restore ordering have been verified. The installer retires the newer custom full-backup timer without deleting any existing archives. The current adapter does not claim that remote-node runtime state is included; panel-stored AWG/WireGuard configuration remains covered by the database backup, while external node state requires a separately verified backup plan. A separate, tested extension is required for any state stored elsewhere.

## Separation of responsibilities

- `manubis backup` / `manubis restore`: standard host/panel backup and recovery.
- `manubis backup-db` and the panel's backup API: database-only exports.
- `manubis migrate`: intentional import from another panel, using migration adapters and isolated staging.

Do not pass a full native system backup to the migration command as a substitute for normal restore.

## Validation status

The code path and documentation have been updated on the isolated recovery branch. Shell syntax and end-to-end restore have **not yet been reported as passing** in this repository revision. Before enabling this branch in production, run CI, generate a backup on a disposable test host, run `--check`, and complete a restore round-trip in an isolated environment. Do not test destructive restore against the live server or database.
