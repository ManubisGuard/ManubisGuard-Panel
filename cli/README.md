# Manubis CLI

The host-level Manubis CLI uses the short `manubis` command while preserving the PasarGuard-style command workflow.

## Usage

```bash
sudo manubis --help
sudo manubis status
sudo manubis backup
sudo manubis restore
```

### Restore

`manubis restore` follows the original backup-discovery workflow. It scans the ManubisGuard backup directory, lists available backup archives, lets the operator select one, and then passes the selected archive to the existing restore/migration safety pipeline. The backup path does not need to be typed manually.

For a non-destructive validation of a specific archive:

```bash
sudo manubis restore-check /path/to/backup.zip
```

The project-specific restore engine remains separate from the CLI selector so that backup validation and production safety gates are not bypassed.
