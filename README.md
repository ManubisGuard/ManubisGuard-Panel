# ManubisGuard Panel

AmneziaWG-enabled ManubisGuard Panel from the `feature/amnezia-wg` branch.

## One-command installation

Install the Panel with TimescaleDB/PostgreSQL 16:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh | sudo bash -s -- install --database timescaledb --yes
```

The installer prepares Docker/Compose when missing, clones the selected branch, creates persistent secrets under `/var/lib/manubisguard`, installs the production restore agent, starts TimescaleDB and the Panel, runs database migrations, and verifies the health endpoint.

The installer builds the Panel image from the selected source so the target server always runs the exact branch revision being installed.

After the first installation, the native host CLI is available as:

```bash
manubisguard status
manubisguard start
manubisguard stop
manubisguard restart
manubisguard logs
manubisguard update
```

`manubisguard update` refreshes the selected branch and reapplies the safe installer configuration while preserving persistent database credentials and data.

## Temporary admin key

After installation, generate a temporary admin key:

```bash
cd /opt/manubisguard-panel
docker compose exec -T manubisguard /code/.venv/bin/python /code/manubisguard-cli.py generate-temp-key
```

Use the exact key printed by the command. Do not publish it in the repository.

## Panel status

```bash
manubisguard status
```

Check the Panel logs:

```bash
manubisguard logs
```

## Database restore

The installer also installs the production migration helper:

```bash
manubisguard-migrate /path/to/backup.zip --apply
```

The restore pipeline supports native ManubisGuard backups and PasarGuard-family backups, including automatic MariaDB/MySQL-to-PostgreSQL conversion for the supported legacy schema.

## Node installation

Install the matching AmneziaWG-enabled Node:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh) install
```

## Source

Panel repository:

```
https://github.com/ManubisGuard/ManubisGuard-Panel
```

Branch:

`feature/amnezia-wg`
