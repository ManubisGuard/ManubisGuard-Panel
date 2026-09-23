# ManubisGuard Panel

Custom ManubisGuard Panel with AmneziaWG support and TimescaleDB/PostgreSQL 16.

## Fast installation

The installer uses the prebuilt GHCR image first. Normal installation does not compile the Panel on the VPS. If the image is unavailable, the installer falls back to building from this repository.

### Panel

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh) install --database timescaledb
```

### Node

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh) install
```

## Included

- AmneziaWG support
- TimescaleDB / PostgreSQL 16
- Docker Compose deployment
- Prebuilt GHCR images for fast deployment
- Automatic database migrations
- SSL certificate setup
- Persistent application data
- Matching Panel and Node installers
- Smart Domain / Smart SSL infrastructure

## Panel status

```bash
cd /opt/manubisguard-panel
docker compose ps
```

Logs:

```bash
cd /opt/manubisguard-panel
docker compose logs --tail=100 pasarguard
```

## Temporary admin key

After installation:

```bash
docker exec manubisguard-panel-pasarguard-1 /code/.venv/bin/python /code/pasarguard-cli.py generate-temp-key
```

Keep the generated key private.

## Node status

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh) status
```

## Source

Panel:
https://github.com/arsamnikzaad/ManubisGuard-Panel

Node:
https://github.com/arsamnikzaad/ManubisGuard-Node

Development branch:
`feature/amnezia-wg`
