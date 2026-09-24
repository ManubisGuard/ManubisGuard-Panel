# ManubisGuard Installer Progress

Date: 2026-09-24
Branch: feature/amnezia-wg

## Goal
A single stable installer entrypoint rebuilds the disposable test server from the current branch without manual .env or Compose preparation.

## Official PasarGuard reference inspected
The official PasarGuard scripts repository was inspected. The operator-facing model is a top-level pasarguard.sh installer with an install command and database selection using --database timescaledb. The official TimescaleDB Compose template supplies database credentials through environment variables.

## ManubisGuard implementation
Canonical installer: install-manubisguard.sh

Stable command:
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh | bash -s -- install --database timescaledb --yes

The installer:
- checks/install missing base tools and Docker Compose v2;
- does not replace an existing Docker installation just because package names differ;
- checks disk space and cleans only apt/build caches when low;
- fetches the latest feature/amnezia-wg source;
- creates persistent DB/admin secrets under /var/lib/manubisguard;
- writes POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD and SQLALCHEMY_DATABASE_URL into .env;
- validates docker-compose.yml;
- pulls the repository-selected TimescaleDB image;
- builds the latest Panel source;
- starts the stack and waits for health;
- runs import app and HTTP /health checks;
- installs /usr/local/bin/manubisguard-migrate.

## N2 protection
The installer does not stop/remove the separate N2 container. It does not use Docker volume pruning and does not uninstall Docker packages merely because older package layouts exist.

## Restore/Migration relation
The installer prepares the normal ManubisGuard runtime. Backup restore stays separate:
--check -> source-compatible staging -> restore -> bridge/normalization -> validation -> rollback -> cutover.

## Validation status
This exact installer revision has not yet been executed on the server. Full suite and real backup E2E are therefore still pending.

No new result is marked PASSED without an actual execution result.

## Next server command
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh | bash -s -- install --database timescaledb --yes
