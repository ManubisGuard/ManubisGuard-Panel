# ManubisGuard Panel

## One-command installation

Install the ManubisGuard Panel from the `feature/amnezia-wg` branch with TimescaleDB/PostgreSQL 16:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh) install --database timescaledb
```

The installer prepares the panel, TimescaleDB, migrations, SSL, and the AmneziaWG-enabled application from this branch.

## Temporary admin key\n\nAfter installation, generate a temporary admin key from inside the Panel container:\n\n```bash\ndocker exec manubisguard-panel-pasarguard-1 /code/.venv/bin/python /code/pasarguard-cli.py generate-temp-key\n```\n\nThe command prints the temporary admin key. Use the exact key printed by the command and do not store it in a public document or repository.\n\n## Node installation

Install a ManubisGuard Node from the matching `feature/amnezia-wg` branch:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/arsamnikzaad/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh) install
```

The Node installer builds the Node image from the forked repository instead of using the upstream `pasarguard/node:latest` image. It generates a persistent API key and TLS certificate, enables host WireGuard routing, builds the bundled AmneziaWG tools, and starts the Node on gRPC port `62050`.

After installation, use the displayed Node address, port, API key, and certificate when registering the node in the Panel.
