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

## تست‌شده روی سرور واقعی
- [x] Synthetic E2E: PostgreSQL 17 / TimescaleDB 2.30.0 → PostgreSQL 16 / TimescaleDB 2.29.2.
- [x] 3 device + 48 hypertable rows.
- [x] source/destination hypertable count = 48.
- [x] Continuous Aggregate = 48 rows.
- [x] Ruff lint/format قبلاً passed.
- [x] `bash scripts/run-local-tests.sh` قبل از تغییرات اخیر manifest: ALL TESTS PASSED.

## آخرین وضعیت تست
- [ ] اجرای سرور بعد از commitهای `88440a5b` و `f87bd43e` هنوز انجام نشده است.
- آخرین اجرای سرور روی `2659238` شامل 80 passed و 2 failed بود:
  - nested manifest path fixture انتظار داشت `db-001.sql` نسبت به `pg_dump/manifest.tsv` resolve شود.
  - runner regression fixture به‌اشتباه literal `\\t` نوشته بود و manifest معتبر تولید نمی‌کرد.
- هر دو مورد اصلاح شده‌اند.

## مرحله بعدی فوری
1. `git pull --ff-only origin feature/amnezia-wg`
2. `bash scripts/run-local-tests.sh`
3. اگر سبز شد: ثبت نتیجه در همین TODO.
4. سپس `--check` روی backup واقعی PasarGuard.
5. سپس staging restore از backup واقعی و validation کامل.
6. سپس rollback واقعی و runtime assets.
7. در پایان compatibility matrix را فقط با اجرای واقعی update کن.

## Backup واقعی PasarGuard
- [x] ساختار رسمی backup و manifest بررسی شده است.
- [x] `manifest.tsv` شامل database/owner/Timescale/dump/version metadata است.
- [x] `pg_dump/manifest.tsv` و `pg_dump/db-<NNN>.sql` پشتیبانی می‌شوند.
- [x] sidecar `db_backup.timescaledb-version` شناخته شده است.
- [ ] backup واقعی هنوز با restore کامل روی staging اجرا نشده است.
- [ ] `--check` روی artifact واقعی.
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
