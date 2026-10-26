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
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

Restore without an archive path offers the upstream numbered archive selection from the canonical backup root. An explicit archive path is supported by the upstream restore CLI. Use `--fresh` only on a new host with empty application/data directories and an archive that contains recovery metadata plus pinned image references; legacy archives without this metadata require a compatible existing installation. The standard restore command is separate from `manubis migrate`; migration is still the explicit cross-panel workflow and retains its own staging and validation logic.

The internal archive key `pasarguard_data/` and fresh-restore marker are intentionally preserved for format compatibility; these are archive schema identifiers, not ManubisGuard runtime paths.

## Archive coverage and limitations

The upstream backup/restore implementation captures the panel configuration under `/opt/manubisguard-panel/`, persistent application data under `/var/lib/manubisguard/`, and the configured database using engine-aware dump routines rather than copying a live database data directory. Core definitions, AWG parameters and other panel records persisted in the database are covered by that database dump. The original archive format is retained; this adapter does not substitute the custom `manubisguard-full-*.zip` format.

The installer retires the newer custom full-backup timer without deleting any existing archives. Panel-stored AWG/WireGuard core definitions and obfuscation parameters are covered by the database dump. The separate ManubisGuard Node service persists generated runtime configuration and TLS material under `/var/lib/pg-node/` by default; that node-side state, node API credentials, and host proxy/ACME files outside `/var/lib/manubisguard/` are **not** included by the panel backup and must be backed up on each relevant node/host separately. Do not add remote node paths to the panel archive or imply they are covered without a coordinated, tested node recovery design.

## Separation of responsibilities

- `manubis backup` / `manubis restore`: standard host/panel backup and recovery.
- `manubis backup-db` and the panel's backup API: database-only exports.
- `manubis migrate`: intentional import from another panel, using migration adapters and isolated staging.

Do not pass a full native system backup to the migration command as a substitute for normal restore.

## Validation status

The code path and documentation have been updated on the isolated recovery branch. The repository shell syntax/static check is wired into PR CI, but no CI result or end-to-end restore pass has yet been confirmed for this revision. Before enabling this branch in production, run CI, generate a backup on a disposable test host, run `--check`, and complete a restore round-trip in an isolated environment. Do not test destructive restore against the live server or database.
