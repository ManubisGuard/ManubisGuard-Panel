# وضعیت پروژه — ManubisGuard

## Branch / قواعد
- Branch فعال: `feature/amnezia-wg`
- `main` و workflowها در این مرحله دست‌نخورده هستند.
- Railway کنار گذاشته شده است.
- `--apply` فقط بعد از E2E، validation و rollback واقعی مجاز است.
- هیچ نتیجه‌ای بدون اجرای واقعی PASS اعلام نمی‌شود.

## هدف Restore / Migration
پشتیبانی از restore بکاپ PasarGuard نسخه‌های جدیدتر روی ManubisGuard حتی با اختلاف major PostgreSQL/TimescaleDB؛ نمونه هدف فعلی: PasarGuard با PostgreSQL 17.10 + TimescaleDB 2.28.2 به مقصد PostgreSQL 16.

## قابلیت‌های پیاده‌سازی‌شده در کد
- [x] Archive Detection برای ZIP/TAR و metadata/manifest.
- [x] Preflight integrity، CRC، path traversal و special-file/symlink guards.
- [x] Source-compatible Timescale runtime selection بر اساس source PostgreSQL/Timescale version.
- [x] Portable Timescale Bridge برای newer → older.
- [x] Timescale catalog isolation و جلوگیری از blind replay catalog.
- [x] Hypertable data transfer مستقل از COPY مستقیم pg_dump.
- [x] Continuous Aggregate reconstruction/refresh.
- [x] Alembic/adapter/normalization و validation architecture.
- [x] Row-count / hypertable / CAGG validation.
- [x] Production safety dump قبل از rename.
- [x] Database rename rollback و panel health rollback architecture.
- [x] Compose integrity guard.
- [x] Runtime asset staging/rollback architecture.
- [x] Destination service discovery مستقل از legacy naming با `MANUBISGUARD_COMPOSE_SERVICE` و ambiguity error.
- [x] Regression discovery برای legacy، canonical، no-candidate و multi-candidate.

## Runtime / Deployment changes
- [x] `docker-compose.yml` روی branch به service مقصد `manubisguard` منتقل شد.
- [x] runtime root مقصد `/var/lib/manubisguard` شد.
- [x] database defaults مقصد `manubisguard` هستند.
- [x] panel healthcheck و `depends_on: service_healthy` اضافه شد.
- [x] staging compose ایزوله با project name `manubisguard-staging` ایجاد شد.
- [x] staging database روی `/tmp/manubisguard-staging-db` است.
- [x] staging panel روی port محلی `18000` و PostgreSQL روی `127.0.0.1:5433` است.
- [x] default runtime-root در `manubisguard-restore-env.py` به `/var/lib/manubisguard` تغییر کرد؛ source backup paths فقط source evidence هستند.
- [x] `scripts/install-manubisguard.sh` اضافه شد: clone/update branch، تولید `.env` در صورت نبود، pull image، اجرای stack بدون local build و import/health check.

## تست‌های واقعی قبلی
- [x] Synthetic E2E: PostgreSQL 17 / TimescaleDB 2.30.0 → PostgreSQL 16 / TimescaleDB 2.29.2.
- [x] 3 device + 48 hypertable rows.
- [x] Continuous Aggregate = 48 rows.
- [x] 82 migration tests روی `9185c6f`.
- [x] 83 migration tests روی `e51bc72`.
- [x] Backup واقعی `/root/backup_20260923210118.zip` شناسایی شد: PostgreSQL 17.10 / TimescaleDB 2.28.2.
- [x] `timescale/timescaledb:2.28.2-pg17-oss` روی سرور قبلی pull و PostgreSQL 17.10 آن تأیید شد.

## تست این تغییرات جدید
- [ ] `bash -n scripts/install-manubisguard.sh` روی سرور اجرا نشده است.
- [ ] `docker compose -f docker-compose.yml config` روی سرور اجرا نشده است.
- [ ] installer روی سرور fresh اجرا نشده است.
- [ ] import/health واقعی بعد از installer اجرا نشده است.
- [ ] `bash scripts/run-local-tests.sh` بعد از تغییرات جدید اجرا نشده است.
- [ ] E2E واقعی restore با `/root/backup_20260923210118.zip` هنوز اجرا نشده است.
- [ ] rollback واقعی هنوز روی این نسخه جدید اجرا نشده است.
- [ ] production cutover هنوز انجام نشده است.

## مراحل باقی‌مانده — ترتیب اجباری
1. Fresh install با `scripts/install-manubisguard.sh` روی سرور تستی.
2. بررسی Compose و وضعیت `manubisguard` + `timescaledb`.
3. `bash -n`، regression discovery و Ruff.
4. `bash scripts/run-local-tests.sh`.
5. `manubisguard-migrate.sh --check /root/backup_20260923210118.zip`.
6. staging restore واقعی بدون `--apply`.
7. schema/table/row-count/hypertable/CAGG/FK/identity validation.
8. Timescale bridge/upgrade و staging dump.
9. rollback واقعی.
10. تکرار E2E بعد از هر blocker تا همه gateها سبز شوند.
11. فقط پس از green gates بررسی cutover.

## ایمنی
- Production DB قبلی نباید در E2E حذف شود.
- Backup/runtime `.env` و Compose source authoritative برای deployment مقصد نیستند.
- `/opt/pasarguard` و `/var/lib/pasarguard` نباید prerequisite موفقیت مقصد باشند.
- Secret واقعی در Git commit نمی‌شود.
- سرور تستی می‌تواند حذف و از صفر نصب شود؛ source of truth کد و TODO همین branch است.
