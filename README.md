# ManubisGuard Panel

AmneziaWG-enabled ManubisGuard Panel from the `feature/amnezia-wg` branch.

## One-command installation

Install the Panel with TimescaleDB/PostgreSQL 16:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh) install --database timescaledb
```

The installer uses the prebuilt GHCR image first, so a normal installation does **not** build the Panel on the VPS. If the image is unavailable, it automatically falls back to building the Panel from this repository.

The installation includes:

- TimescaleDB/PostgreSQL 16
- database migrations
- AmneziaWG support
- SSL certificate setup
- persistent Panel data under `/var/lib/pasarguard`
- automatic Panel startup through Docker Compose

## Temporary admin key

After installation, generate a temporary admin key:

```bash
docker exec manubisguard-panel-manubisguard-1 /code/.venv/bin/python /code/pasarguard-cli.py generate-temp-key
```

Use the exact key printed by the command. Do not publish it in the repository.

## Panel status

```bash
cd /opt/manubisguard-panel
docker compose ps
```

Check the Panel logs:

```bash
cd /opt/manubisguard-panel
docker compose logs --tail=100 manubisguard
```

## Node installation

Install the matching AmneziaWG-enabled Node:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh) install
```

The Node installer also uses a prebuilt GHCR image first and falls back to a local build only if the image cannot be pulled.

## Source

Panel repository:

https://github.com/arsamnikzaad/ManubisGuard-Panel

Branch:

`feature/amnezia-wg`
