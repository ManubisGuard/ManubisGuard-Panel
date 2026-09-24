# وضعیت پروژه — ManubisGuard

## وضعیت کلی
- Branch فعال: `feature/amnezia-wg`
- `main` دست‌نخورده می‌ماند.
- PR #1 هنوز merge نشده است.
- Railway کنار گذاشته شده؛ اعتبارسنجی با GitHub Actions و سرور واقعی انجام می‌شود.
- `--apply` روی production ممنوع است تا staging/validation/rollback کامل شود.

## هدف Restore / Migration
1. Restore بکاپ رسمی PasarGuard روی ManubisGuard.
2. Restore بکاپ ManubisGuard روی ManubisGuard.
3. Compatibility/Bridge برای اختلاف نسخه PostgreSQL/Timescale.
4. جلوگیری از overwrite شدن identity، credentials و deployment مقصد.
5. staging، validation و rollback قبل از cutover.

## انجام‌شده
- [x] Detection → Preflight → Source-Compatible Staging → Transformation/Bridge → Alembic → Validation → Cutover architecture.
- [x] ZIP/TAR integrity، CRC، path traversal، duplicate normalized paths و special-file guards.
- [x] ZIP directory entries به‌عنوان مسیرهای مجاز شناخته می‌شوند؛ symlink/special file همچنان block می‌شود.
- [x] credential/deployment identity safety.
- [x] runtime asset staging/rollback architecture.
- [x] Compose integrity guard.
- [x] PostgreSQL major و Timescale version-aware staging.
- [x] جلوگیری از replay مستقیم Timescale internal catalog.
- [x] Portable Timescale Bridge برای newer → older.
- [x] انتقال hypertable data مستقل از `pg_dump` table data.
- [x] Continuous Aggregate rebuild/refresh خارج transaction.
- [x] row-count verifier برای tables/hypertables/CAGG.
- [x] local migration seed مقاوم در برابر preinstalled TimescaleDB extension.
- [x] رفع `ONLY` روی hypertable و refresh syntax در restore.
- [x] parser رسمی اولیه PasarGuard `manifest.tsv`.
- [x] archive-level validation برای dumpهای manifest.
- [x] اتصال manifest به Preflight برای ZIP/TAR.
- [x] پشتیبانی از manifest تو‌در‌تو؛ dump path نسبی به directory خود manifest resolve می‌شود.
- [x] regression fixture مربوط به archive PasarGuard با TSV واقعی اصلاح شد.
- [x] regression برای ZIPهای واقعی دارای directory entry اضافه شد.
- [x] `pg_dump --globals-only` / `globals.sql` از candidate database restore جدا شد؛ cluster roles/ACL dump دیگر با database dump رقابت نمی‌کند.
- [x] regression test برای `globals.sql` اضافه شد.

## تست‌شده روی سرور واقعی
- [x] Synthetic E2E: PostgreSQL 17 / TimescaleDB 2.30.0 → PostgreSQL 16 / TimescaleDB 2.29.2.
- [x] 3 device + 48 hypertable rows.
- [x] source/destination hypertable count = 48.
- [x] Continuous Aggregate = 48 rows.
- [x] Ruff lint/format قبلاً passed.
- [x] `bash scripts/run-local-tests.sh` روی commit `9185c6f`: 82 passed، ALL TESTS PASSED.
- [x] `bash scripts/run-local-tests.sh` روی `e51bc72`: 83 passed، ALL TESTS PASSED.
- [ ] تست commitهای `c61534d` و `b5eab48` روی سرور هنوز اجرا نشده است.

## آخرین وضعیت تست
- [x] دو failure قبلی مربوط به nested manifest و literal `\\t` اصلاح شدند.
- [x] `9185c6f`: 82 migration tests passed.
- [x] بکاپ واقعی `/root/backup_20260923210118.zip` شناسایی شد به‌عنوان ZIP با source_product=`pasarguard` و confidence=`high`.
- [x] Preflight directory-entry blocker رفع شد و 83 تست migration روی سرور سبز شدند.
- [!] مرحله `analyze_backup()` روی بکاپ واقعی اکنون به blocker بعدی رسید: archive شامل `pg_dump/db-001.sql` و `pg_dump/globals.sql` است و `_find_candidate()` هر دو را database backup تشخیص می‌داد.
- [x] `globals.sql` به‌عنوان PostgreSQL cluster globals-only dump از candidate selection خارج شد.
- [x] regression test مربوط به `globals.sql` اضافه شد.

## مرحله بعدی فوری
1. `git pull --ff-only origin feature/amnezia-wg`
2. `bash scripts/run-local-tests.sh`
3. اجرای مجدد `analyze_backup("/root/backup_20260923210118.zip")` و اطمینان از عبور Preflight + candidate selection.
4. ثبت ساختار واقعی manifest و dumpهای بکاپ.
5. اجرای staging restore از backup واقعی، بدون تغییر production.
6. validation کامل schema/table/row-count/hypertable/CAGG و identity safety.
7. rollback واقعی و سپس runtime assets.
8. در پایان compatibility matrix را فقط با اجرای واقعی update کن.

## Backup واقعی PasarGuard
- [x] ساختار رسمی backup و manifest بررسی شده است.
- [x] `manifest.tsv` شامل database/owner/Timescale/dump/version metadata است.
- [x] `pg_dump/manifest.tsv` و `pg_dump/db-<NNN>.sql` پشتیبانی می‌شوند.
- [x] sidecar `db_backup.timescaledb-version` شناخته شده است.
- [x] artifact واقعی `/root/backup_20260923210118.zip` روی سرور موجود و 2.2MB است.
- [x] archive detection روی artifact واقعی انجام شد.
- [x] directory entries واقعی PasarGuard از preflight عبور می‌کنند.
- [x] globals-only dump از database candidate selection جدا شد.
- [ ] تست تغییر globals-only روی سرور واقعی.
- [ ] preflight + candidate selection artifact واقعی پس از اصلاح globals-only.
- [ ] restore کامل artifact واقعی روی staging.
- [ ] schema/table/hypertable/CAGG validation روی artifact واقعی.
- [ ] rollback واقعی.

## Compatibility matrix
| Source | Target | وضعیت |
|---|---|---|
| PG17 + Timescale 2.30.0 synthetic | PG16 + Timescale 2.29.2 | **PASSED on real server** |
| PasarGuard واقعی، PG17.10 + Timescale 2.28.2 | ManubisGuard PG16 | implementation موجود؛ E2E واقعی باقی است |
| ManubisGuard backup واقعی | ManubisGuard target | تست نشده |
| PasarGuard نسخه‌های جدیدتر | target مربوطه | regression لازم |

## قواعد ایمنی
- [ ] cross-major PostgreSQL فقط با source-compatible runtime/bridge.
- [x] Timescale newer → older با Portable Bridge؛ downgrade مستقیم ممنوع.
- [ ] Timescale older → newer در staging با restore سپس upgrade.
- [ ] Timescale internal catalog نباید blind replay شود.
- [ ] role password و DB identity مقصد overwrite نشود.
- [ ] `.env`/Compose/image/container تنظیمات backup authoritative نیستند.
- [ ] runtime certificate/key فقط بعد از validation و safety backup وارد cutover شود.
- [ ] production restore فقط بعد از staging + validation + rollback test.

## GitHub Actions
- [ ] integration workflow باید completed/successful واقعی داشته باشد.
- queued/وجود workflow green محسوب نمی‌شود.
- [ ] failureهای واقعی Actions باید رفع و دوباره اجرا شوند.

## قانون ادامه کار
بعد از هر تغییر مهم:
1. تغییر/رفع مشکل.
2. تست واقعی.
3. بروزرسانی همین `TODO.md` در همان branch.
4. ثبت commit و نتیجه دقیق.
5. گزارش کوتاه.
6. ادامه مستقیم تا completion یا blocker واقعی.
