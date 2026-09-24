# وضعیت پروژه — ManubisGuard

## Branch / قواعد
- Branch فعال: feature/amnezia-wg
- main و workflowها در این مسیر دست‌نخورده هستند.
- --apply فقط بعد از E2E، validation و rollback واقعی مجاز است.
- هیچ نتیجه‌ای بدون اجرای واقعی PASS اعلام نمی‌شود.

## Restore/Migration
- [x] Detection و Preflight architecture.
- [x] Source-compatible Timescale runtime selection.
- [x] Portable Timescale Bridge newer -> older.
- [x] Timescale catalog isolation.
- [x] Hypertable/CAGG transfer architecture.
- [x] Alembic/adapter/normalization architecture.
- [x] Validation architecture.
- [x] Production safety dump and rollback architecture.
- [x] Destination service discovery با MANUBISGUARD_COMPOSE_SERVICE و ambiguity error.
- [x] Discovery regression برای legacy، canonical، no-candidate و multi-candidate.

## Runtime / Installer
- [x] Compose destination service: manubisguard.
- [x] Canonical runtime root: /var/lib/manubisguard.
- [x] Destination DB defaults: manubisguard.
- [x] Isolated staging Compose: manubisguard-staging.
- [x] Canonical installer: install-manubisguard.sh.
- [x] Installer follows the PasarGuard-style install --database timescaledb operator contract.
- [x] Installer creates and persists DB/admin secrets.
- [x] Installer persists POSTGRES_* and SQLALCHEMY_DATABASE_URL.
- [x] Installer fetches feature/amnezia-wg, builds latest Panel source, starts Compose and runs import/health checks.
- [x] Duplicate installer entrypoint removed.

## Previous real tests
- [x] Synthetic E2E PG17 + Timescale 2.30.0 -> PG16 + Timescale 2.29.2.
- [x] 3 devices + 48 hypertable rows.
- [x] Continuous Aggregate = 48 rows.
- [x] 82 migration tests on 9185c6f.
- [x] 83 migration tests on e51bc72.
- [x] Real backup detected: /root/backup_20260923210118.zip, source PG17.10 / TimescaleDB 2.28.2.
- [x] Source-compatible image timescale/timescaledb:2.28.2-pg17-oss was previously verified on the server.

## Current installer revision tests
- [ ] Exact installer execution on server.
- [ ] docker compose config.
- [ ] bash -n.
- [ ] discovery regression.
- [ ] Ruff.
- [ ] full run-local-tests.sh.
- [ ] import/health after installer.
- [ ] real backup --check.
- [ ] staging restore.
- [ ] schema/table/row/hypertable/CAGG/FK/identity validation.
- [ ] Timescale bridge/upgrade E2E.
- [ ] real rollback.
- [ ] production cutover.

## Required order
1. Run the stable one-command installer.
2. Verify manubisguard + timescaledb.
3. Run bash -n, discovery regression and Ruff.
4. Run the full local test suite.
5. Run the real backup --check.
6. Run real staging restore.
7. Full validation.
8. Timescale bridge/upgrade and staging dump.
9. Real rollback.
10. Repeat after each blocker until all gates are green.
11. Only then consider cutover.
12. After Restore/Migration, continue Domain/SSL Intelligence.

## Safety
- Do not delete production data during E2E.
- Backup .env/Compose/image/container metadata are not authoritative deployment config.
- /opt/pasarguard and /var/lib/pasarguard are legacy source evidence only.
- Never commit real secrets.
- N2 stays outside installer removal scope.
- The test server is disposable; feature/amnezia-wg is the source of truth.

## Domain / SSL Intelligence — Persistent Context
- [x] Domain DNS verified for `ua.qoqnusradio.top` -> `160.202.132.252`.
- [x] Existing certificate files verified on the server under `/var/lib/manubisguard/certs/ua.qoqnusradio.top/`.
- [x] The Panel is responsible for its own domain/SSL handling; do NOT introduce Nginx, Caddy, or another reverse proxy unless explicitly required by the project.
- [x] `network_mode: host` is intentional for the `manubisguard` service.
- [x] The main Panel runtime listens on Uvicorn port `8000`; do not assume port 443 or add a reverse proxy just to expose the domain.
- [x] SSL activation requires the Uvicorn certificate/key environment variables pointing to the existing certificate files:
  - `UVICORN_SSL_CERTFILE=/var/lib/manubisguard/certs/ua.qoqnusradio.top/fullchain.pem`
  - `UVICORN_SSL_KEYFILE=/var/lib/manubisguard/certs/ua.qoqnusradio.top/privkey.pem`
- [x] Do NOT add `MANUBISGUARD_DOMAIN` to the main Panel `.env` merely to configure SSL/domain. The main `.env` should contain only variables actually consumed by the application.
- [ ] After changing SSL env values, recreate the `manubisguard` container so the new environment is loaded.
- [ ] Verify the process binds externally with TLS, then test the HTTPS health endpoint.
- [ ] Verify certificate validity/renewal behavior and document the final production SSL flow.
- [ ] Future sessions MUST read this TODO section before repeating domain/SSL setup; do not re-discover or re-add the same configuration from scratch.

