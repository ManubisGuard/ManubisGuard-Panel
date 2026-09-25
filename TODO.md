# وضعیت پروژه — ManubisGuard

## Branch / قواعد
- Branch فعال: feature/amnezia-wg
- main و workflowها در این مسیر دست‌نخورده هستند.
- --apply فقط بعد از E2E، validation و rollback واقعی مجاز است.
- هیچ نتیجه‌ای بدون اجرای واقعی PASS اعلام نمی‌شود.

## Migration/Installer Corrections — 2026-09-24
- [x] **CRITICAL:** Removed legacy `/var/lib/pasarguard` runtime/installer path fallback; canonical runtime root is `/var/lib/manubisguard`. Legacy references remain only as migration-source/test evidence where required.
- [x] **CRITICAL:** Installer now creates canonical `/opt/manubisguard/backup/` independently of `MANUBISGUARD_DATA_DIR`.
- [x] **CRITICAL:** Verified the running Panel container mounts `/var/lib/manubisguard` to `/var/lib/manubisguard`; migration workspace is therefore container-visible.
- [ ] Never introduce `MANUBISGUARD_SSL_CERT`, `MANUBISGUARD_SSL_KEY`, or `MANUBISGUARD_DOMAIN` as replacements for the canonical `UVICORN_SSL_CERTFILE` / `UVICORN_SSL_KEYFILE` configuration without explicit evidence from the PasarGuard reference implementation.
- [x] SSL runtime uses canonical `UVICORN_SSL_CERTFILE` / `UVICORN_SSL_KEYFILE`; live `.env` verification confirmed both keys are quoted.
- [x] Installer changes preserve canonical Uvicorn SSL keys and do not introduce `MANUBISGUARD_SSL_*` or `MANUBISGUARD_DOMAIN` replacements.
- [x] Verified backup directory, Panel mount visibility, live SSL env keys and `docker compose config` before rerunning real backup check.
- [x] Confirmed `/root/backup_20260923210118.zip` is consumed as explicit test input; canonical backup directory remains `/opt/manubisguard/backup/`.
- [x] Historical failure documented; current migration workspace uses `/var/lib/manubisguard/migration/` and is container-visible.
- [x] Refactor/path contract verified and real `manubisguard-migrate --check /root/backup_20260923210118.zip` exited 0 without modifying staging or Production.


## Restore/Migration

## Backup / Migration Path Contract — NON-NEGOTIABLE
- [x] Canonical ManubisGuard backup directory is `/opt/manubisguard/backup/`.
- [x] Canonical ManubisGuard migration workspace is `/var/lib/manubisguard/migration/`.
- [x] `/root/backup_*.zip` files are manual test artifacts only; they are NOT the canonical backup location.
- [x] Legacy `/opt/pasarguard/backup/` is source/reference structure only and must not be recreated as the ManubisGuard runtime path.
- [x] Legacy `/var/lib/pasarguard/migration/` must never be used by the ManubisGuard migration runtime.
- [x] Previous migration failure was caused by staging the backup under `/var/lib/pasarguard/migration/` while the Panel container only mounted `/var/lib/manubisguard`.
- [x] Future sessions must verify these canonical paths before changing migration/backup code.
- [x] Do not invent or introduce alternate backup paths without first checking this section and the current installer contract.

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
- [x] real backup --check.
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

## Restore / Backup Gate — 2026-09-24 20:25 UTC
- [x] Source inspection confirmed the real entrypoint is `scripts/manubisguard-migrate.sh` and exact syntax is `manubisguard-migrate --check BACKUP`.
- [x] `/usr/local/bin/manubisguard-migrate` was synchronized to the repository script before the real check; both now have SHA256 `1153dac6a601872dd9d12ccd874b98a3f5af5a3adb4075503ff1fc576681354f`.
- [x] Initial real check exposed a runtime/image mismatch: the running Panel image lacked `validate_archive_integrity` from `app.migration.detector`, while the repository source contains it.
- [x] Minimal runtime alignment for this test: repository `app/migration/detector.py` was copied into the running Panel container. No production database was modified.
- [x] Real command executed successfully: `manubisguard-migrate --check /root/backup_20260923210118.zip`.
- [x] Execution result: exit code 0; source detected `pasarguard`, format `sql`, TimescaleDB `2.28.2`; backup contains TimescaleDB objects.
- [x] Check-only path reported: `CHECK-ONLY COMPLETE. No staging database or production database was modified.`
- [x] Post-check regression: Compose Panel/TimescaleDB remain running and HTTPS `/health` returned `{"status":"ok"}`; no staging/migration container is running.
- [ ] Panel image still needs a clean rebuild/redeploy from branch source before relying on the temporary container alignment across restarts.
- [x] Next gate: real staging restore using repository staging architecture; completed in the Restore / Migration Gates section below.


## Restore / Migration Gates  - 2026-09-24 21:20 UTC
- [x] Real backup check: `manubisguard-migrate --check /root/backup_20260923210118.zip` exited 0; detected PasarGuard SQL, PostgreSQL 17, TimescaleDB 2.28.2; check-only reported no production/staging DB modification.
- [x] Runtime/image mismatch found and isolated: running Panel image was older than branch source; temporary runtime alignment was applied for migration execution only. Clean image rebuild was attempted but stalled during final image assembly, so this remains an image deployment gate.
- [x] Minimal source fixes validated with real execution: ZIP detector skips `globals.sql`; restore safety rewrites `OWNER TO` clauses to the destination role; staging orchestration refreshes the staging URL after the Timescale runtime port changes; JSON staging output is normalized before parsing.
- [x] Targeted regression tests: `tests/migration/test_detector.py` + `tests/migration/test_restore_safety.py` = 19 passed. `bash -n scripts/manubisguard-migrate.sh` and `git diff --check` pass.
- [x] Real staging restore completed from `/root/backup_20260923210118.zip` into isolated source-compatible TimescaleDB 2.28.2 / PostgreSQL 17 runtime. Production was not modified.
- [x] Full migration validation completed: `valid=true`; pre/post durable row counts matched for admins=42, core_configs=9, groups=19, hosts=30, inbounds=28, nodes=7, user_templates=0, users=2147; no count losses; no missing target tables; no orphan-check failures; Alembic reached `awg2026091901`.
- [x] Explicit metadata validation on final isolated TimescaleDB 2.30.1 runtime: hypertables=0 and continuous aggregates=0, matching 0 source rows in the backup Timescale catalog; foreign keys=22; public sequences=26; identity columns=0; TimescaleDB extension=2.30.1.
- [x] Real Timescale compatibility upgrade completed in isolation: TimescaleDB 2.28.2 -> 2.30.1 on PostgreSQL 17; post-upgrade validation passed.
- [x] Staging dump completed and integrity checked: `/var/lib/manubisguard/migration/4c0b28444c03/manubisguard-staging.sql`, 3.2M, SHA256 `8c3f9cc6a448f8c422cc4b3c3b10c8e8c97b70ef58c5ece62fe90e28f67a2`, PostgreSQL completion marker present.
- [x] Real rollback test on disposable PostgreSQL/Timescale staging environment: simulated database rename to cutover, forced rollback rename, restored original database name and verified `OLD_PRODUCTION` marker; validated cutover database retained `VALIDATED_CUTOVER`. Production was not involved.
- [ ] PostgreSQL 17 -> production PostgreSQL 16 cutover/bridge restore is intentionally not executed yet because that path is tied to the destructive `--apply` cutover.
- [ ] Production cutover remains blocked until the clean branch image is rebuilt/deployed and the cross-major cutover gate is explicitly executed in a disposable cutover database.

## Restore / Migration Gates - 2026-09-25 00:52 UTC
- [x] Previous Restore / Migration gates recorded above remain verified by real execution.
- [ ] Disposable PostgreSQL 17 -> PostgreSQL 16 bridge gate: attempted with TimescaleDB 2.29.2 on PG16; first attempt was blocked by host disk exhaustion during image extraction, then disk space was reclaimed from unused Docker build cache/images.
- [ ] Bridge logical restore retry exposed an important compatibility boundary: direct filtered full staging dump still references TimescaleDB catalog/CAGG objects (`granular_refresh_enabled`) that are not portable to the PG16 target; the intended `portable_bridge.py` path must be used instead of the generic full-dump filter. No production DB was modified.
- [ ] Next gate: rerun the disposable PG17 source -> portable bridge plan -> PG16 target using the dedicated portable bridge path, then validate durable row counts, schema/FK/sequence/Timescale metadata.
- [ ] Clean branch image rebuild/redeploy remains blocked by limited 25G host disk and the previously observed build final-assembly stall; do not mark this gate green until a clean branch image is built and deployed.

## Compatibility Debug / Hardening - 2026-09-25
- [x] GitHub branch source re-read from `ManubisGuard/ManubisGuard-Panel@feature/amnezia-wg` before compatibility changes; local work remains uncommitted and `main`/workflows were not touched.
- [x] Root cause fixed in `portable_bridge.py`: generated `refresh_continuous_aggregate()` used quoted SQL identifiers instead of the required SQL string literal relation name. The renderer now emits `refresh_continuous_aggregate('schema.view', NULL, NULL)`.
- [x] Root cause fixed in `scripts/manubisguard-migrate.sh`: portable `pg_dump` argument arrays were escaped as literal shell text (`\${extra_args[@]}` / `\${args[@]}`), so exclude-table arguments and the command invocation could be malformed. They now use real Bash array expansion.
- [x] Removed the local test workaround that post-processed the bridge CAGG refresh SQL; the production migration path now generates the correct SQL directly.
- [x] Verified `tests/migration`: 86 passed with real execution on CLY823538.
- [x] Verified Ruff check, Ruff format check and `git diff --check`: all green after formatting.
- [x] Verified live production baseline after debugging: HTTPS `/health` returned `{"status":"ok"}`; Panel and TimescaleDB containers remained healthy; no temporary migration/rollback containers remained.
- [x] Confirmed PostgreSQL official documentation: `pg_dump --section=pre-data|data|post-data` is the supported logical-dump partitioning model, and cross-major older-target restores may require manual compatibility editing. `--quote-all-identifiers` is recommended for cross-major dumps.
- [x] Confirmed TimescaleDB upstream source/tests for 2.29.2 support `timescaledb.finalized` and `create_default_indexes`, so those are not the root cause of the observed bridge failure.
- [ ] Full isolated PG17/Timescale 2.30 -> PG16/Timescale 2.29 bridge E2E could not be completed in this run because the server reached 100% disk while pulling the large test images. The test process was terminated and temporary test resources were cleaned; this is NOT marked PASS.
- [x] Reclaimed Docker/cache space after the aborted E2E; filesystem returned to approximately 96% usage with ~1.1 GB free. Production containers remained running.
- [ ] Clean branch image rebuild/redeploy remains a separate open gate; do not mark it green until the branch image is rebuilt from source and deployed successfully.
- [ ] Next real gate: rerun the isolated PG17 -> portable bridge -> PG16 E2E after sufficient disk capacity is available, then validate rows, FKs, sequences, hypertables/CAGGs and target metadata end-to-end.


## Compatibility E2E - 2026-09-25
- [x] Reclaimed disposable Docker/test/cache resources without touching production database data; host disk recovered to ~4.2 GB free (83% used).
- [x] Fixed `scripts/run-local-tests.sh` ordering bug: the PG17 `ALTER TABLE ONLY` compatibility rewrite now runs after `post-data.prepared.sql` is created, not inside `build_bridge()` before the dump exists.
- [x] Disposable TimescaleDB 2.30.0/PostgreSQL 17 -> TimescaleDB 2.29.2/PostgreSQL 16 portable bridge E2E completed on CLY823538.
- [x] Source seeded: devices=3, usage=48, continuous aggregate=48 rows.
- [x] Portable bridge artifacts generated successfully.
- [x] Pre-data/data/post-data dump preparation and explicit hypertable row export completed.
- [x] Destination restore completed with hypertable reconstruction and CAGG refresh.
- [x] Source/destination counts matched: public.devices=3, public.usage=48; hypertable usage=48 on both sides.
- [x] Migrated continuous aggregate returned 48 rows.
- [x] Feature-scope Ruff lint and format checks passed.
- [x] Migration test suite passed: 86 passed in 6.35s.
- [x] Disposable test containers/volumes/network and generated local artifacts were removed after the run.
- [x] Production Panel and TimescaleDB containers remained healthy; no production cutover/apply was executed.
- [ ] Clean branch image rebuild/redeploy remains a separate open gate.
- [ ] Real production `--apply` cutover remains intentionally blocked until clean image + final approval gates are complete.

## Final Restore / Clean Image Gate - 2026-09-25
- [x] Backup restore compatibility E2E is complete and PASS: disposable TimescaleDB 2.30.0/PostgreSQL 17 source restored into TimescaleDB 2.29.2/PostgreSQL 16 destination.
- [x] Restore data integrity verified: devices=3, usage=48, hypertable usage=48 on both source/destination, migrated continuous aggregate=48 rows.
- [x] Real backup metadata/row-count, isolated restore, Timescale upgrade, and disposable rollback gates previously passed.
- [x] Clean branch Docker image build completed successfully: `manubisguard-panel:feature-amnezia-wg-clean` (image id `340bbb479218`).
- [x] Clean-image disposable application startup/health gate PASS on the new test server: clean image contains `/code/dashboard/build/index.html`; `import app` PASS; disposable container started and `http://127.0.0.1:8000/health` returned `{"status":"ok"}`; live Panel/TimescaleDB remained healthy.
- [ ] Production `--apply` cutover remains intentionally blocked; no production cutover was executed in this milestone.

## D0 Backup Restore checkpoint 2026-09-25
- [x] Backup ORM, migration, service, admin API and Fernet encryption implemented.
- [x] Encryption round-trip and plaintext log-scan tests passed.
- [x] Telegram token is encrypted in DB and hidden from API responses.
- [x] SQLite backup-ID regression fixed; Ruff and diff-check passed.
- [x] Commits: 8e06f568, 46dbff58.
- [ ] Finish Telegram mock/secret tests, frontend, retention, restore UI flow and final tests/build/runtime.

## NEXT EXECUTION ORDER
1. Verify feature/amnezia-wg, HEAD, clean tree, compose health and /health.
2. Verify Backup migration and columns; run authenticated manual-backup and Telegram-config tests in staging/disposable data only.
3. Verify list never exposes telegram_bot_token and scan logs for plaintext test token.
4. Finish Settings -> Backup & Restore UI: manual backup, schedule/retention, restore upload/check/staging restore, Telegram config/test, history.
5. Add retention/auto-delete and unit/API/integration/security tests.
6. Run Ruff, format, diff-check, full tests, clean Docker build and runtime.
7. After every real PASS update TODO.md, commit and push to origin feature/amnezia-wg.
8. Never run production --apply until every migration/cutover gate is green.

## CONTINUATION PROMPT
Continue MANUBISGUARD from GitHub ManubisGuard/ManubisGuard-Panel, branch feature/amnezia-wg, server /opt/manubisguard-panel. GitHub is source of truth; Remote Desktop Commander is execution source. Never modify main. Never claim PASS without execution evidence. Never commit secrets, tokens, private keys or certificates.
Restore/Migration gates already passed: real backup check, isolated restore, schema/tables/rows/FK/sequences/identity validation, Timescale upgrade, staging dump/integrity, disposable rollback, PG17/Timescale -> PG16/Timescale portable bridge E2E, 86 migration tests, clean branch image build and disposable runtime health. Production --apply has not been executed.
Current D0 backend: Backup model/migration/service/admin API; Fernet encryption using BACKUP_TELEGRAM_KEY; token hidden from API/logs; opt-in APScheduler job; SQLite backup-ID regression fix. Commits 8e06f568 and 46dbff58.
Next: finish D0 runtime/API regression, Telegram mock and secret non-disclosure, frontend, retention, restore UI flow, tests, clean build/runtime. On FAIL: evidence -> root cause -> minimal fix -> regression -> PASS -> TODO -> commit -> push.


## D0.2 Runtime/API Regression — 2026-09-25
- [x] Re-synced `feature/amnezia-wg` from origin; clean tree and HEAD `f4578393` verified before execution.
- [x] `docker compose ps`: Panel and TimescaleDB are healthy; no production cutover/apply was executed.
- [x] Panel runtime `/health` returned `{"status":"ok"}` with HTTP 200.
- [x] `docker compose exec -T manubisguard python -m alembic current` returned head `b7c8d9e0f1a4`.
- [x] Live `Backup` ORM inspection returned expected backup/Telegram columns, including `telegram_bot_token` and `telegram_chat_id`.
- [x] Unauthenticated `/api/admin/backup/list`, `/create`, and `/configure-telegram` requests were rejected with HTTP 401; no secret was supplied.
- [x] Superseded by D0.2 completion evidence: authenticated Backup API regression is green in disposable execution.
- [x] Superseded: authenticated manual-backup, Telegram mock, secret non-disclosure and RBAC regression tests are covered by the green D0.2/D0.3/D0.6 suites.

## D0.2 Runtime/API Regression — completion evidence 2026-09-25
- [x] Disposable authenticated Backup security regression suite executed successfully: `3 passed in 0.34s`.
- [x] Fernet encryption/decryption round-trip PASS.
- [x] Authenticated Telegram configuration PASS; response excludes `telegram_bot_token` and DB stores ciphertext.
- [x] Authenticated backup-list secret non-disclosure PASS.
- [x] Runtime log scan found no disposable plaintext token and no Telegram-token log entries.
- [x] No production secret was used and no production database was modified.

## D0.3 Telegram Security — 2026-09-25
- [x] Fernet encrypted Telegram token storage and API secret exclusion verified by authenticated disposable tests.
- [x] Backup history endpoint verified not to expose `telegram_bot_token`.
- [x] Runtime log scan found no disposable plaintext Telegram token.
- [x] Telegram notification path covered with a mocked HTTP client; test does not contact Telegram and uses only `DISPOSABLE_TEST_TOKEN`.
- [x] Mock notification regression passes together with existing Backup security tests: `4 passed in 0.41s`.
- [x] Ruff check, Ruff format check and `git diff --check` pass.
- [x] No real Telegram secret was used.
- [ ] Telegram real-message test remains intentionally unexecuted because it requires a real production/test secret; mock coverage is the current gate.

## D0.4 Frontend — initial implementation 2026-09-25
- [x] Added `Settings -> Backup & Restore` route/page with ManubisGuard dark SaaS-compatible cards and dense operational layout.
- [x] Manual backup UI wired to `/api/admin/backup/create`.
- [x] ZIP upload UI wired to `/api/admin/backup/upload`.
- [x] Uploaded-backup validation UI wired to `/api/admin/backup/check/{id}`.
- [x] Backup history UI wired to `/api/admin/backup/list` with delete action.
- [x] Telegram configuration UI wired to encrypted backend configuration; token input is password-type and cleared after success.
- [x] RBAC visibility follows existing Settings permission gating; no new permission bypass was introduced.
- [x] Production restore/apply is explicitly unavailable in the UI.
- [x] Scheduler/retention controls are not falsely exposed as functional because the backend API is not implemented yet.
- [x] Dashboard production build PASS using Bun 1.2.21: Vite build completed successfully; existing chunk-size warnings only.
- [x] Built artifacts contain the new `/settings/backup` route.
- [x] Superseded: scheduling/retention and staging-restore backend milestones are implemented and represented in the UI.

## D0.5 Backup Scheduling & Retention — 2026-09-25
- [x] Added persisted `backup_schedules` model and Alembic migration `b7c8d9e0f1a5`.
- [x] Schedule supports opt-in enabled state, daily/weekly/monthly frequency, UTC hour/minute, weekday/day-of-month and retention count.
- [x] Added admin-only GET/PUT schedule API under `/api/admin/backup/schedule` using existing Settings RBAC.
- [x] Scheduler remains opt-in: default schedule is disabled; scheduler wakes once per minute and evaluates persisted configuration.
- [x] Scheduled backup execution records `last_run_at` and applies retention cleanup after successful backup.
- [x] Disposable SQLite `alembic upgrade head` completed successfully through `b7c8d9e0f1a5`; Production DB was not migrated.
- [x] Schedule due-rule regression tests pass: `9 passed in 0.48s` including encryption, Telegram security and scheduler rules.
- [x] Ruff check, Ruff format check and `git diff --check` pass for the changed backend/test files.
- [x] Dashboard build PASS after exposing schedule controls.
- [x] Live Panel/TimescaleDB remained healthy and `/health` returned HTTP 200; no Production schema change was executed.
- [x] Live runtime Alembic revision verified at `b7c8d9e0f1a4 (head)`; the deployed revision chain is current.

## D0.6 Restore Flow — 2026-09-25
- [x] Reviewed Rebecca v1.2.0-era backup design and current upstream implementation as a reference: binary-only Backup panel, explicit database/full scope, portable archive with manifest, safe extraction, import/restore result reporting, and warnings that import replaces current data. Rebecca's current source documents these behaviors and keeps Docker backup/import disabled. citeturn0search0
- [x] Rebecca source inspection confirmed `.rbbackup` manifest-driven export/import, safe archive extraction, SQLite/MySQL/MariaDB restore paths, and explicit database/full scopes; this informed ManubisGuard's separation of validation, isolated restore and future production cutover. citeturn0search0
- [x] Added ManubisGuard admin endpoint `/api/admin/backup/restore/staging/{id}` for isolated restore + migration validation only.
- [x] Endpoint creates an engine-generated staging database, runs the existing migration/Timescale safety pipeline, returns source format/counts/transformations/validation, and always drops the staging database in `finally`.
- [x] Production restore/apply remains unavailable from the API and UI; no live database overwrite is performed.
- [x] Added Backup & Restore UI `Staging Restore` action and result panel; upload → validate → isolated staging restore is now represented in the panel.
- [x] Dashboard production build PASS after restore-flow UI changes.
- [x] Migration regression subset PASS: `14 passed in 3.73s` (`tests/migration/test_staging.py` + `tests/migration/test_runner.py`).
- [x] Ruff check PASS and format check PASS after formatting `app/routers/admin_backup.py`; `git diff --check` PASS.
- [x] Live Panel/TimescaleDB healthy and `/health` HTTP 200; no Production migration/restore/apply executed.
- [x] Superseded by D0.6 completion evidence: authenticated API security regression is green.
- [x] Superseded by D0.6 completion evidence: deterministic staging-restore regression and authenticated security gate are green.

## D0.6 Restore Flow — completion evidence 2026-09-25
- [x] Authenticated Backup API security regression PASS: `9 passed in 0.55s` using disposable test data; no production secret/database was used.
- [x] Deterministic staging-restore endpoint regression added and PASS: `1 passed in 9.46s`; verifies the endpoint creates an isolated generated staging target, never uses the production database URL as the restore target, and always drops the staging database.
- [x] Combined migration restore/security targeted regression PASS: `15 passed in 9.89s` across staging, runner and endpoint restore tests.
- [x] Ruff check PASS for changed Backup/security test files; Ruff format applied only to the new restore test; `git diff --check` PASS.
- [x] The broad repository format check exposed pre-existing/unrelated formatting drift across 19 files; those unintended formatter changes were reverted and are not included in this milestone.
- [x] D0.6 authenticated regression and deterministic staging-restore test gates are now green; no production restore/apply was executed.
- [x] Superseded by D0.7/D0 Final Gate evidence recorded below.

## D0.7 / D0 Final Gate — 2026-09-25
- [x] Re-synced `feature/amnezia-wg`; working tree clean and HEAD `fae0a8d3` matched origin before final gate.
- [x] Live Panel/TimescaleDB containers healthy; live `/health` returned HTTP 200 with `{"status":"ok"}`; Alembic current is `b7c8d9e0f1a4 (head)`.
- [x] Targeted Backup + restore/security regression PASS: `24 passed in 0.63s`.
- [x] Full repository migration/local integration gate PASS: `scripts/run-local-tests.sh` completed with `87 passed in 9.70s` and `ALL TESTS PASSED`.
- [x] Disposable portable bridge E2E remains PASS: PostgreSQL 17/TimescaleDB 2.30.0 -> PostgreSQL 16/TimescaleDB 2.29.2, durable counts and CAGG validated.
- [x] Dashboard production build PASS with Bun 1.2.21; only existing large-chunk warnings and Vite browser-external warning were emitted.
- [x] Clean branch Docker image build PASS from current branch source: `manubisguard-panel:feature-amnezia-wg-final`; image ID recorded by execution evidence.
- [x] Clean image smoke gate PASS: `import app` succeeded; dashboard `/code/dashboard/build/index.html`, `/code/start.sh`, and `/usr/bin/manubisguard-cli` exist and are executable as expected.
- [x] Feature-scope Ruff check/format and `git diff --check` PASS for Backup/restore/scheduler/security files.
- [x] Production restore-agent security regression PASS: `12 passed in 1.51s` covering agent authorization/path/confirmation and existing Backup restore security.
- [x] An attempted whole-repository Ruff check exposed 41 auto-fixable baseline style differences; all such unintended changes were immediately reverted. No unrelated formatter changes remain in the branch.
- [x] No real Telegram secret was used; no production restore/apply/cutover was executed.
- [x] D0 software gate is complete: backup, encryption, Telegram mock security, scheduling/retention, frontend, isolated staging restore, migration regression, full local migration E2E, clean image and runtime baseline are green.
- [x] Production restore is now exposed from the admin Backup panel through a localhost-only authenticated host restore agent that invokes the same `manubisguard-migrate ... --apply` path; the UI requires explicit `RESTORE_PRODUCTION` confirmation and the API accepts only validated backups.
- [ ] Actual production restore/cutover of a selected backup remains an operational action; do not execute it without a specifically selected backup and final live-service readiness check.
- [ ] Domain/SSL Intelligence remains the next non-destructive project phase after D0.

## Post-D0 Domain / SSL baseline — 2026-09-25
- [x] Existing ACME, managed-domain, certificate-store and domain-intelligence regression baseline executed: `51 passed in 12.74s`.
- [x] No Domain/SSL implementation change was invented or applied because the repository contains no concrete post-D0 acceptance checklist/specification beyond the single continuation note.
- [x] Current branch remains clean after D0; production `--apply`/cutover remains intentionally unexecuted.
- [ ] Define the concrete Domain/SSL Intelligence acceptance criteria before implementing additional behavior; do not infer requirements from test names alone.

## Full-suite execution note — 2026-09-25
- [x] Full `pytest -q` was started against disposable/local SQLite and migrations completed successfully; execution reached tests but was terminated after extended CPU-bound progress without a final suite result.
- [x] This does not invalidate the green feature-scoped gates: `run-local-tests.sh` = 87 passed, Backup/restore/security = 24 passed, Domain/SSL baseline = 51 passed.
- [x] No production database or secret was used by the full-suite attempt.

## D1-D5 Domains & SSL Completion Plan — 2026-09-25
- [x] D1 — Domain Management Foundation: normalize/validate domain records, explicit Domain→Node associations, multi-domain-per-node persistence/API, permission/RBAC coverage, migration safety.
- [x] D2 — Certificate Lifecycle: Let's Encrypt, Cloudflare DNS-01, Existing certificates; durable certificate metadata/store; request/install/renew/expire state transitions; renewal scheduler with pre-expiry window, locking/idempotency, failure recording and retry safety.
- [ ] D3 — Node Integration: certificate deployment to Node, verification/rollback, Managed SSL + Manual TLS inbound integration, and deterministic Server Address generation for `additional`, `alias`, and `both`.
- [ ] D4 — Dashboard & E2E: complete Settings → Domains & SSL workflows for CRUD/association, certificate lifecycle, health/inspection, deployment/TLS inbound and server-address operations; frontend/backend permission and error-state coverage.
- [ ] D5 — Final Gate: regression/unit/integration/E2E tests, migration dry-run on disposable DB, frontend production build, security audit, `git diff --check`, clean Docker smoke test, GitHub verification, and final TODO checkpoint.
- [ ] Rule: after every successful phase operation/test milestone, update this TODO.md, commit, push, and verify the branch before continuing.
- [ ] Rule: do not execute destructive production restore/cutover or real certificate issuance/deployment against production without explicit operational authorization.

## D1 — Domain Management Foundation — completed 2026-09-25
- [x] Extended managed-domain lifecycle metadata without breaking existing Settings persistence: issued/renewed timestamps, renewal attempts, next renewal, certificate error, deployment status.
- [x] Added authenticated certificate lifecycle API surface for managed-domain issuance and Existing-certificate installation under `/api/settings/domains/certificate/*`; private-key material is accepted only as request input and is never returned.
- [x] Preserved existing multi-domain-per-node and primary-domain Settings model; no destructive migration was introduced.
- [x] Added lifecycle service with normalized UTC timestamps, validation through the existing certificate engine/store, renewal-window calculation, failure state and bounded retry scheduling metadata.
- [x] Domain/certificate regression subset PASS: `40 passed in 11.01s`.
- [x] `git diff --check` and Python compilation PASS.
- [x] D1 formatting correction and lint re-run PASS; lifecycle regression re-run remains green after formatting.

## D2 — Certificate Lifecycle — completed 2026-09-25
- [x] Added durable lifecycle metadata for issue/renew/expire/failure state transitions on managed domains.
- [x] Added Existing-certificate installation path through the existing certificate validator/store; invalid pairs are rejected before persistence.
- [x] Added Let's Encrypt / Cloudflare issuance dispatch through the existing ACME engine; scheduler never performs initial issuance for a domain that has no recorded certificate expiration.
- [x] Added renewal scheduler job (`managed_certificate_renewal_tick`) with 15-minute cadence, single active instance, coalescing and the existing scheduler-role gate.
- [x] Added renewal locking/idempotency and bounded retry metadata; existing certificates are marked expired when their recorded expiration is past.
- [x] Lifecycle regression PASS: `22 passed in 2.25s`; Ruff and `git diff --check` PASS.
- [ ] Real ACME issuance and real Cloudflare DNS changes remain operational actions; tests use mocks/disposable data only.

## D3 — Certificate/TLS architecture verification — 2026-09-25
- [x] Verified existing Xray TLS parser supports `serveOnNode` as an explicit node-side certificate mode; this is an existing upstream contract, not a new invented field.
- [x] Verified Node Bridge still has no generic certificate/file upload RPC, while official Node configuration uses node-local certificate paths and Xray TLS accepts either file paths or direct certificate content.
- [x] Verified upstream panel history documents the `serveOnNode` handling in Xray certificate processing.
- [x] Exact deployed Node contract is now verified: installed `PasarGuardNodeBridge` is v0.9.1, exposes `start(config=...)`, and its REST maintenance surface uses `POST /node/core_update` without a generic certificate/file upload API.
- [x] The existing node start path transports complete Xray JSON, so managed TLS certificate/key material can be delivered as inline `certificate`/`key` content without a speculative file-transfer API.
- [x] Current Xray `TLSCertConfig` accepts `certificateFile`/`keyFile` or inline `certificate`/`key`; Rebecca v1.2.0 independently confirms the managed-certificate/SNI architecture used as reference.
- [x] Implemented node-specific managed certificate materialization through the existing Xray `start(config=...)` path; certificate/key content remains filesystem-backed on the panel and is injected into runtime config only.
- [x] Added regression coverage for multi-domain TLS/SNI injection, duplicate prevention, missing/ineligible artifacts, and non-Xray isolation: `42 passed in 4.65s`; `git diff --check` PASS.
- [x] Added durable deployment metadata (`certificate_deployed_at`, `deployment_error`) and a protected manual deployment API for managed certificates.
- [x] Issue/import paths now trigger node deployment when a managed domain is associated with a node; deployment failures are recorded separately from certificate issuance state.
- [x] Added failure rollback: when managed TLS runtime application fails, the previous core configuration is re-applied; deployment remains marked failed if rollback succeeds.
- [x] Renewal scheduler retries pending and failed deployment states on connected nodes without transferring private keys through NATS.
- [x] Added focused API deployment and Node start failure→rollback regression tests; protected orchestration does not require a live certificate or production Node.
- [x] Regression PASS: `50 passed in 2.56s`; Ruff and `git diff --check` PASS.

- [ ] Server Address `additional` / `alias` / `both` generation remains pending because the repository still lacks an authoritative runtime/subscription contract for those semantics; no speculative propagation is enabled.

## D4 — Domains & SSL UI lifecycle — completed 2026-09-25
- [x] Added Issue/Renew controls for Let's Encrypt and Cloudflare-managed certificates.
- [x] Added Existing Certificate installation UI with local-only private-key form state; private keys are cleared from the UI after successful submission and are never returned by the API.
- [x] Added manual Deploy/Re-deploy controls and persistent deployment status/error/timestamp presentation.
- [x] Added expiration, days-remaining, renewal-attempts and next-renewal visibility plus explicit Expired status.
- [x] Added frontend lifecycle service outside the generated API client so future `gen:api` runs do not overwrite custom certificate hooks.
- [x] Frontend validation PASS: TypeScript `--noEmit` and Vite production build PASS; Vite emitted only existing bundle-size/browser-compatibility warnings.

## D5 — Domains & SSL regression — 2026-09-25
- [x] Domain/SSL + Node/Settings targeted regression PASS: `78 passed in 2.90s`; Ruff and `git diff --check` PASS.
- [x] Runtime health PASS: `GET /health` returned HTTP 200 with `{"status":"ok"}`.
- [x] Full project pytest started against disposable SQLite; migrations completed and the suite reached 42% with no reported test failure before it was intentionally interrupted because this environment made the full suite disproportionately long. This is not recorded as a full-suite PASS.
- [x] Added explicit per-domain `serve_tls` lifecycle control, modeled after the verified Rebecca v1.2.0 certificate contract; default remains enabled for backward compatibility, and runtime injection now honors the toggle.
- [x] Backend regression after the TLS-serving toggle: `27 passed in 3.18s`; Ruff and `git diff --check` PASS.
- [x] Frontend validation after the TLS-serving toggle: TypeScript `--noEmit` and Vite/PWA production build PASS; only existing chunk-size warnings remain.
- [x] Re-audited the actual subscription pipeline: `app/subscription/share.py` consumes `SubscriptionInboundData.address`, while `app/core/hosts.py` derives that field from each Host's configured address; `ManagedServerAddress` is not consumed by subscription generation today.
- [x] Re-audited Rebecca v1.2.0: its Host contract exposes address options/selection modes, but no authoritative mapping for ManubisGuard's requested `additional` / `alias` / `both` semantics was found.
- [x] Re-audited the actual PasarGuard upstream source (`PasarGuard/panel`): `BaseHost.address` is a `set[str]`, `_prepare_subscription_inbound_data()` copies it into `SubscriptionInboundData.address`, and subscription formatters consume that list; upstream provides multi-address publishing but no `alias`/`additional`/`both` contract for this feature.
- [ ] Overall Domain/SSL closure still has one specification-dependent item: Server Address `additional` / `alias` / `both` generation lacks an authoritative runtime/subscription contract in the repository, so no speculative propagation has been enabled.
- [ ] Real ACME issuance, real Cloudflare DNS mutation, and live production-node certificate deployment remain operational actions not executed in regression tests.

## Reality Inbound Auto-SNI completion — 2026-09-25
- [x] Root cause identified: the previous Auto Select implementation treated each configured SNI-pool entry as a new Reality **target**, so it replaced the inbound target instead of testing candidate SNI names against the existing target.
- [x] Added an optional TLS SNI override to the Reality scanner/API while preserving the original target host/IP and port.
- [x] Auto Select now probes the current inbound Reality target with each configured SNI candidate, filters by the existing Reality feasibility checks, ranks feasible candidates by measured TLS latency, and applies only the selected SNI.
- [x] Existing “Discover SNI set” behavior remains unchanged: it scans the current target and can apply the certificate SAN/server-name set.
- [x] Added validation for SNI override input; URLs, ports, paths, IP literals and malformed values are rejected.
- [x] Added regression coverage for SNI override parsing and scanner propagation; Reality scanner + SNI-pool regression: `75 passed, 2 skipped in 3.83s`.
- [x] Ruff check, Ruff format check and `git diff --check` PASS.
- [x] Live non-destructive scanner smoke: `example.com:443` tested with multiple SNI candidates; target remained `example.com:443`, feasible candidates were ranked by measured latency, and `www.cloudflare.com` was selected in that run. No inbound/core configuration was persisted and no node was restarted.
- [x] Frontend TypeScript `--noEmit` and production Vite build PASS; only existing large-chunk and browser-external warnings remain.
- [x] Production Panel image/runtime deployment of this source change is intentionally not executed in this milestone; source is committed/pushed for the next normal deployment.
- [x] Test deployment completed on the authorized server from branch `feature/amnezia-wg` at commit `bb5204a5`: existing TimescaleDB volume preserved, pre-deployment pg_dump saved outside Git, local image rebuilt, Panel recreated, runtime `/health` returned 200, and no production data restore/cutover was performed.
- [x] HTTPS test endpoint configured for `55.qoqnusradio.top` with Nginx reverse proxy and a real Let's Encrypt certificate; external `/` returned 200 and `/health` returned `{"status":"ok"}`. Certificate is valid through 2026-12-24 and Certbot renewal is scheduled.
