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
- [x] Real server runtime reaches healthy state with the feature-amnezia-wg image.
- [x] Real server HTTPS `/health` returns `{"status":"ok"}`.
- [x] Protocol-aware `/code/healthcheck.sh` passes inside the running Panel container.
- [x] Compose Panel healthcheck uses `/code/healthcheck.sh` instead of a hard-coded HTTP probe.
- [x] TimescaleDB dependency reaches healthy state before Panel startup.

## Runtime Healthcheck Investigation — 2026-09-24
- [x] Root cause identified: Compose healthcheck used `http://127.0.0.1:8000/health` while Uvicorn was serving HTTPS on port 8000.
- [x] Confirmed original failure signature: `curl: (52) Empty reply from server`.
- [x] Confirmed application startup completed successfully: `Application startup complete` and `Uvicorn running on https://0.0.0.0:8000`.
- [x] Confirmed `/code/healthcheck.sh` correctly detects the active TLS configuration and passes the local health probe.
- [x] Recreated stack with corrected healthcheck and observed `starting` -> `healthy`.
- [x] Final container status verified: `manubisguard-panel-manubisguard-1 ... (healthy)`.
- [x] Final health log contains successful `0 | {"status":"ok"}` result.
- [x] Build completed successfully; Vite/Rolldown >500 kB chunk messages are warnings only and are not a healthcheck failure.
- [x] Detailed report committed: `docs/reports/2026-09-24-runtime-healthcheck.md`.

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
- [x] Panel import/startup and health verification on the current feature image.
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
- [x] Verify the process binds externally with TLS, then test the HTTPS health endpoint.
- [ ] Verify certificate validity/renewal behavior and document the final production SSL flow.
- [ ] Future sessions MUST read this TODO section before repeating domain/SSL setup; do not re-discover or re-add the same configuration from scratch.

## Domain / SSL — Error Log & Non-Negotiable Rules
- [x] Previous assistant mistake recorded: `MANUBISGUARD_DOMAIN` was added to `.env` even though it is not part of the Panel's required SSL environment contract. Do NOT repeat this.
- [x] Previous assistant mistake recorded: invented `MANUBISGUARD_SSL_CERT` and `MANUBISGUARD_SSL_KEY` variables were added without evidence that the application consumes them. Do NOT create application-specific SSL variable names by assumption.
- [x] Previous assistant mistake recorded: `PASARGUARD_SSL_ENABLED`, `PASARGUARD_SSL_MODE`, `PASARGUARD_SSL_CERT`, and `PASARGUARD_SSL_KEY` were treated as Panel SSL configuration without first verifying that they belong to the current Panel's active ENV contract. Do NOT copy legacy PasarGuard variables into the ManubisGuard Panel ENV by assumption.
- [x] Correct variable names for Uvicorn TLS are exactly `UVICORN_SSL_CERTFILE` and `UVICORN_SSL_KEYFILE`.
- [x] Correct ENV formatting must preserve double quotes around certificate/key paths when matching the project's established ENV convention, e.g. `UVICORN_SSL_CERTFILE="..."` and `UVICORN_SSL_KEYFILE="..."`.
- [x] Do NOT rename, invent, substitute, or migrate these variables to `MANUBISGUARD_SSL_*` names unless the source code explicitly introduces and consumes those names.
- [x] Do NOT infer ENV names from legacy PasarGuard configuration, directory names, or intuition. Verify against the current source/installer/config contract first.
- [x] When correcting an ENV mistake, document the mistake and the corrected contract here so future sessions/devices/chats do not repeat it.
- [ ] Before any future Domain/SSL ENV edit, inspect the current source/installer contract and this section of TODO.md first.

## Reports
- `docs/reports/2026-09-24-runtime-healthcheck.md` — real-server healthcheck incident, root cause, fix, validation and final green state.


## AI Handoff Checkpoint — 2026-09-24 18:35 UTC
این بخش مرجع ادامه کار است؛ مراحل علامت‌خورده را دوباره اجرا نکنید مگر اینکه تغییر کد/کانفیگ یا regression جدیدی ایجاد شده باشد.

### آخرین وضعیت واقعی روی سرور
- [x] Stack با image فعلی `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg` بالا آمده است.
- [x] `manubisguard-panel-timescaledb-1` قبل از Panel به وضعیت Healthy رسیده است.
- [x] `manubisguard-panel-manubisguard-1` پس از اصلاح healthcheck از `starting` به `healthy` رسیده است.
- [x] Uvicorn واقعی روی `https://0.0.0.0:8000` اجرا شده است.
- [x] `/health` از طریق HTTPS روی localhost با پاسخ `{"status":"ok"}` PASS شده است.
- [x] `/code/healthcheck.sh` داخل کانتینر PASS شده است.
- [x] Healthcheck Compose به `/code/healthcheck.sh` تغییر کرده و دوباره stack recreate شده است.
- [x] health log نهایی شامل `0 | {"status":"ok"}` است.
- [x] Frontend build کامل شده و PWA generation موفق بوده است.
- [x] هشدار chunkهای بزرگ Vite/Rolldown فقط warning است و blocker نیست.
- [x] علت دقیق unhealthy شدن ثبت شده: healthcheck قبلی HTTP بود ولی runtime با HTTPS روی همان port 8000 سرو می‌کرد.
- [ ] تست root روی HTTPS (`/`) در اجرای فعلی timeout شد؛ این مورد به‌تنهایی health/API failure محسوب نمی‌شود چون `/health` PASS است، ولی در smoke test نهایی باید علت رفتار root بررسی شود.
- [ ] certificate validity/renewal و flow نهایی production SSL هنوز gate باز است.

### وضعیت Restore / Backup — نقطه ادامه
آخرین backup واقعی شناخته‌شده:
- `/root/backup_20260923210118.zip`
- Source PostgreSQL: 17.10
- Source TimescaleDB: 2.28.2
- Source-compatible image قبلاً روی سرور با موفقیت بررسی شده: `timescale/timescaledb:2.28.2-pg17-oss`

گیت‌های Restore/Migration:
- [x] Architecture و migration implementation gates قبلی.
- [x] Synthetic E2E.
- [x] Real backup file detection.
- [x] Current Panel runtime/import/startup/health baseline.
- [ ] اجرای واقعی backup `--check` با command دقیق خود پروژه — **اول command را از source/installer استخراج کن؛ حدس نزن.**
- [ ] Real staging restore از همان backup.
- [ ] Schema/table/row validation.
- [ ] Hypertable validation.
- [ ] Continuous Aggregate validation.
- [ ] Foreign-key validation.
- [ ] Identity/sequence validation.
- [ ] Timescale bridge/upgrade E2E.
- [ ] Staging dump validation.
- [ ] Real rollback.
- [ ] Production cutover.

### ترتیب دقیق ادامه
1. Command واقعی backup `--check` را از repository/installer/source پیدا و اجرا کن.
2. اگر backup check PASS شد، همان backup را در staging restore کن؛ production data نباید حذف/overwrite شود.
3. بعد از restore، schema/table/row/hypertable/CAGG/FK/identity را validate کن.
4. سپس Timescale bridge/upgrade E2E و staging dump را اجرا کن.
5. سپس rollback واقعی را تست کن.
6. فقط بعد از سبز شدن همه gateها، cutover بررسی شود.
7. بعد از Restore/Migration سراغ Domain/SSL Intelligence باقی‌مانده برو.

### دستورالعمل مهم برای هوش مصنوعی بعدی
- Repository: `ManubisGuard/ManubisGuard-Panel`
- Branch: `feature/amnezia-wg`
- Server project root: `/opt/manubisguard-panel`
- Do not repeat the already-PASSed runtime healthcheck investigation.
- Do not revert `/code/healthcheck.sh` based healthcheck to hard-coded HTTP.
- Do not invent backup/restore commands. Read the current installer/source first.
- Do not introduce Nginx/Caddy/reverse proxy for SSL unless current source explicitly requires it.
- Do not invent `MANUBISGUARD_SSL_*` or `MANUBISGUARD_DOMAIN` environment variables.
- Do not claim PASS without real execution evidence.
- Do not delete production data during restore/migration E2E.
- Before modifying TODO again, preserve this checkpoint and append only new verified facts/results.
