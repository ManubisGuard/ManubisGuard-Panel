# PasarGuard Installer Progress

Date: 2026-09-24
Branch: feature/amnezia-wg

## Goal
A single stable installer entrypoint rebuilds the disposable test server from the current branch without manual .env or Compose preparation.

## Official PasarGuard reference inspected
The official PasarGuard scripts repository was inspected. The operator-facing model is a top-level pasarguard.sh installer with an install command and database selection using --database timescaledb. The official TimescaleDB Compose template supplies database credentials through environment variables.

## ManubisGuard implementation
Canonical installer: install-pasarguard.sh (legacy compatibility wrapper: install-manubisguard.sh)

Stable command:
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh | bash -s -- install --database timescaledb --yes

The installer:
- checks/install missing base tools and Docker Compose v2;
- does not replace an existing Docker installation just because package names differ;
- checks disk space and cleans only apt/build caches when low;
- fetches the latest feature/amnezia-wg source;
- creates persistent DB/admin secrets under /var/lib/pasarguard;
- writes POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD and SQLALCHEMY_DATABASE_URL into .env;
- validates docker-compose.yml;
- pulls the repository-selected TimescaleDB image;
- builds the latest Panel source;
- starts the stack and waits for health;
- runs `import app` and validates the Compose healthcheck (which supports custom ports, TLS, and UDS);
- installs /usr/local/bin/manubisguard-migrate.

## N2 protection
The installer does not stop/remove the separate N2 container. It does not use Docker volume pruning and does not uninstall Docker packages merely because older package layouts exist.

## Restore/Migration relation
The installer prepares the normal ManubisGuard runtime. Backup restore stays separate:
--check -> source-compatible staging -> restore -> bridge/normalization -> validation -> rollback -> cutover.

## Validation status (updated 2026-10-27)

- Real installer run on the disposable test host, targeting `/opt/pasarguard` and `/var/lib/pasarguard`, with TimescaleDB and no TLS: **exit 0**. The installer fetched the branch, built the image, recreated the panel container, verified the built image ID, imported `app`, and installed the canonical CLI/helpers.
- Post-install checks: `GET http://127.0.0.1:8000/health` returned `{"status":"ok"}`; panel and TimescaleDB containers were both `running/healthy`; installed checkout and GitHub branch were at commit `60d23c4` at the time of the test; canonical CLI aliases, native backup helper, migration helper and restore-safety helper were present.
- The first real run exposed a source-fetch bug in existing checkouts with a restricted `remote.origin.fetch` refspec. The installer now fetches explicitly from `refs/heads/$BRANCH` into `refs/remotes/origin/$BRANCH`. Regression test: `tests/test_installer_source_fetch.sh` PASS.
- Focused CI-equivalent validation: Ruff PASS; `tests/migration` plus `tests/compatibility`: **98 passed**; installer source-fetch, CLI bootstrap, update gate/preflight and native backup adapter/transform shell tests PASS.
- Full repository suite was also attempted: **827 passed, 20 skipped, 34 failed, 3 errors**. The remaining failures span existing API/timezone/Node fixtures and phase-5 migration tests; the full suite is not green and these failures are not represented as passing. They are outside the installer source-fetch regression and require separate triage.
- This validates the real install/build/health path on the disposable test host. It does not claim a full native backup archive restore round-trip or a clean-host reinstall on a second machine.

## Deployment restriction
Do not run the installer against the live production host. Any end-to-end installer acceptance must use a disposable host with isolated data and explicit approval. The command above is intentionally not provided as a live-server instruction.

## Source-level acceptance evidence before the real install run (2026-10-27)

- Canonical paths are `/opt/pasarguard`, `/var/lib/pasarguard`, and `/opt/pasarguard/backup/`.
- The canonical `pasarguard` CLI and compatibility names `manubis` and `manubisguard` route to the same script; the legacy installer entrypoint delegates to `install-pasarguard.sh`.
- Mocked, network-isolated installer tests passed for preservation of existing database URL/credentials, admin credentials, SSL/TLS environment and certificate files, legacy restore-agent key retention, stack verification, rejection of a mismatched image ID, and preflight checks for a healthy existing panel/database. The tracked `tests/test_installer_update_preflight.sh` also verifies fail-closed behavior for unhealthy/stopped panel and unhealthy TimescaleDB states. An unhealthy baseline is rejected before build/up.
- CLI/shared-library bootstrap, backup adapter static checks, backup compatibility fixture, and focused restore/backup tests passed (9 tests). Bash syntax and `git diff --check` passed.
- These are source/mocked tests only. No real installation, production restore, database mutation, service restart, commit, or push was performed.
- Remaining acceptance gaps: full end-to-end install on a disposable host, full repository test suite, and full backup/restore E2E.
- Safety response to the update-safety blocker: the canonical installer now fails closed for all in-place `--update` requests before installing tools, building images, changing the checkout, or starting services. `tests/test_installer_update_gate.sh` covers this gate. The preflight health checks remain as additional protection for when updates are re-enabled, but they do not solve post-migration rollback. Re-enable in-place updates only after a database-aware rollback strategy is implemented and tested end-to-end on a disposable host.
