# وضعیت پروژه — ManubisGuard

## وضعیت کلی
- Branch فعال: `feature/amnezia-wg`
- `main` دست‌نخورده می‌ماند.
- PR #1: Draft / Open / Merge نشده.
- Railway کنار گذاشته شده؛ اعتبارسنجی پروژه با GitHub Actions و سپس سرور واقعی انجام می‌شود.
- `--apply` روی دیتابیس واقعی هنوز مجاز/تأییدشده نیست.
- queued یا وجود workflow هرگز به‌عنوان passed ثبت نمی‌شود.

## AmneziaWG
- [x] انجام‌شده و تست‌شده.
- [x] AmneziaWG دیگر جزو کارهای باقی‌مانده این branch نیست؛ فقط در صورت regression یا تغییر schema تست مجدد لازم است.

## هدف جدید: Restore / Migration
هدف این branch ساخت سیستم امن و version-aware برای:
1. Restore بکاپ‌های رسمی PasarGuard روی ManubisGuard.
2. Restore بکاپ‌های ManubisGuard روی ManubisGuard.
3. سازگاری با نسخه‌های جدیدتر PasarGuard از طریق compatibility/bridge.
4. جلوگیری از overwrite شدن DB/deployment identity مقصد.
5. staging، validation و rollback قبل از cutover.

## Restore / Migration — انجام‌شده
- [x] Detection → Preflight → Source-Compatible Staging → Transformation/Bridge → Alembic HEAD → Validation → Cutover.
- [x] Archive integrity برای ZIP/TAR، CRC، path traversal، duplicate normalized paths و special files.
- [x] Restore safety برای role/password و جلوگیری از overwrite credential مقصد.
- [x] Restore امن environment و جلوگیری از انتقال DB/deployment identity.
- [x] Runtime asset staging و rollback.
- [x] Compose integrity guard.
- [x] تشخیص PostgreSQL major و source-compatible runtime.
- [x] Timescale version-aware staging.
- [x] جلوگیری از replay مستقیم Timescale internal catalog.
- [x] Portable Timescale Bridge برای newer → older به‌صورت implementation اولیه.
- [x] انتقال داده واقعی hypertable با export/import مستقل از `pg_dump` table data.
- [x] بازسازی Continuous Aggregate و refresh خارج از transaction.
- [x] verifier برای مقایسه row count جدول‌ها و hypertableها.
- [x] workflow مستقل GitHub Actions برای integration.
- [x] تست robust برای preinstalled TimescaleDB extension در local migration seed.
- [x] رفع replay ناسازگار `ONLY` روی hypertable و refresh syntax در restore path.
- [x] parser اولیه `manifest.tsv` رسمی PasarGuard برای database/owner/Timescale/dump/version metadata.
- [x] validation archive-level برای اینکه dumpهای اعلام‌شده در `manifest.tsv` واقعاً داخل archive وجود داشته باشند.
- [x] اتصال `manifest.tsv` به Preflight برای PasarGuard ZIP/TAR؛ manifest malformed/missing dump اکنون قبل از staging قابل تشخیص است.

## Restore / Migration — تست‌شده در سرور واقعی
- [x] Synthetic E2E: PostgreSQL 17 / TimescaleDB 2.30.0 → PostgreSQL 16 / TimescaleDB 2.29.2.
- [x] Seed شامل 3 device و 48 ردیف hypertable.
- [x] Restore داده hypertable: source=48 / destination=48.
- [x] Continuous Aggregate: 48 ردیف پس از restore/refresh.
- [x] Migration unit tests قبلی: 65/65 passed.
- [x] Ruff lint: passed.
- [x] Ruff format: passed.
- [x] `bash scripts/run-local-tests.sh`: **ALL TESTS PASSED** در سرور واقعی قبل از تغییر manifest preflight.
- [ ] تست‌های جدید parser/preflight روی سرور واقعی.
- [ ] `--check` روی backup واقعی PasarGuard.
- [ ] restore روی staging/isolated database از backup واقعی.
- [ ] validation schema/table/hypertable/CAGG و count comparison روی backup واقعی.
- [ ] rollback واقعی.
- [ ] runtime asset restore و rollback.
- [ ] compatibility با deployment واقعی PostgreSQL 16 / TimescaleDB مقصد.
- [ ] `--apply` روی production انجام نشده و نباید تا پایان validation انجام شود.

## Restore / Migration — باقی‌مانده
- [ ] سبز شدن واقعی integration workflow در GitHub Actions.
- [ ] رفع failureهای واقعی Actions و re-test تا completion.
- [ ] E2E با backup واقعی PasarGuard.
- [ ] restore یک backup واقعی ManubisGuard.
- [ ] rollback در سناریوهای failure واقعی.
- [ ] تکمیل compatibility matrix با نسخه‌های واقعی PasarGuard.
- [ ] regression test دوره‌ای برای نسخه‌های جدید PasarGuard.
- [ ] تعریف معیار نهایی production cutover پس از validation.

## ماتریس سازگاری
> فقط اجرای واقعی موفق می‌تواند یک ترکیب version را supported/passed کند.

| Source / Backup | PG Source | Timescale Source | Target ManubisGuard | PG Target | Timescale Target | وضعیت |
|---|---:|---:|---|---:|---:|---|
| Synthetic integration E2E | 17 | 2.30.0 | feature/amnezia-wg | 16 | 2.29.2 | **PASSED on real server** |
| PasarGuard backup واقعی موجود | 17.10 | 2.28.2 | 5.4.1 / Alembic awg2026091901 | 16 | نسخه مقصد deployment؛ باید روی سرور تأیید شود | implementation موجود؛ E2E تست نشده |
| ManubisGuard backup واقعی | باید ثبت شود | باید ثبت شود | نسخه مقصد | باید ثبت شود | باید ثبت شود | تست نشده |
| PasarGuard نسخه‌های جدیدتر | باید از backup واقعی ثبت شود | باید از backup واقعی ثبت شود | نسخه branch/release مربوطه | باید ثبت شود | باید ثبت شود | نیازمند regression test |

### قواعد ماتریس
- [ ] هیچ ترکیب جدیدی بدون اجرای واقعی supported علامت زده نشود.
- [ ] برای هر ردیف: source app version + PostgreSQL + Timescale + target ManubisGuard/Alembic ثبت شود.
- [ ] PostgreSQL cross-major فقط با source-compatible client/runtime یا bridge مناسب.
- [ ] Timescale newer → older با Portable Bridge؛ downgrade مستقیم ممنوع.
- [ ] Timescale older → newer با source-compatible restore و سپس upgrade در staging.
- [ ] backup نباید role password، DB identity، compose، image/container یا deployment identity مقصد را overwrite کند.

## PasarGuard Backup Format — بررسی‌شده از منبع رسمی
- [x] repository رسمی `PasarGuard/scripts` و مستندات Backup & Disaster Recovery بررسی شد.
- [x] backup کامل PasarGuard شامل application configuration، persistent state و database dumps است.
- [x] configuration شامل `docker-compose.yml` و `.env` است؛ این فایل‌ها در Restore مقصد نباید authoritative باشند.
- [x] persistent state در `/var/lib/pasarguard/` قرار دارد و می‌تواند theme/assets/certificates/local state داشته باشد.
- [x] PostgreSQL/TimescaleDB backup چند-database است و ساختار مورد انتظار شامل `globals.sql` و `pg_dump/db-<NNN>.sql` به‌همراه `manifest.tsv` است.
- [x] `manifest.tsv` باید database name، owner، Timescale presence و exact extension version را ثبت کند.
- [x] PasarGuard برای Timescale sidecar با نام `db_backup.timescaledb-version` نیز version metadata را پشتیبانی می‌کند.
- [x] backup دستی در مسیر `/opt/pasarguard/backup/` تولید و به ZIP یا tarball بسته‌بندی می‌شود.
- [x] checksum SHA256 و validation/truncation checks بخشی از جریان backup/restore رسمی هستند.
- [x] restore رسمی archive را در staging موقت extract و قبل از destructive change validation می‌کند.
- [x] mismatch نسخه Timescale در Restore رسمی fail-closed است؛ ManubisGuard باید به‌جای رد صرف، در صورت پشتیبانی bridge مسیر compatible را انتخاب کند.
- [ ] فایل backup واقعی PasarGuard هنوز در اختیار test harness قرار نگرفته و E2E واقعی با artifact واقعی انجام نشده است.

## GitHub Actions — آخرین وضعیت
- PR #1: #1 / Draft / Open / Not merged.
- Base: main.
- Head: feature/amnezia-wg.
- Integration workflow در repository تعریف شده است؛ green بودن GitHub Actions فقط پس از completed/successful واقعی ثبت می‌شود.
- Railway: کنار گذاشته شده.
- آخرین commit مربوط به parser/tests: `8871b44`؛ پس از آن تغییرات manifest preflight هنوز روی سرور واقعی اجرا نشده‌اند.

## قانون ادامه کار
**از این مرحله به بعد بعد از هر تغییر کد یا تست مهم، همین `TODO.md` باید در همان branch به‌روزرسانی شود و سپس گزارش وضعیت داده شود.**

روال اجباری:
1. تغییر/رفع مشکل.
2. تست واقعی.
3. ثبت نتیجه دقیق در `TODO.md`.
4. ثبت commit/branch و failureهای باقی‌مانده در صورت وجود.
5. گزارش کوتاه به کاربر.
6. ادامه مستقیم به مرحله بعدی بدون رها کردن کار، تا رسیدن به completion یا یک blocker واقعی.

## مشکلات و نکات

- [ ] **Cross-major PostgreSQL:** source backup می‌تواند PostgreSQL 17 باشد ولی deployment مقصد PostgreSQL 16 است؛ dump تولیدشده توسط PG17 الزاماً بدون ویرایش روی PG16 قابل replay نیست. فیلتر compatibility باید محدود و explicit باقی بماند.
- [x] **Timescale newer → older:** downgrade مستقیم TimescaleDB انجام نمی‌شود؛ Portable Schema/Data Bridge مسیر اختصاصی آن است و synthetic E2E آن روی سرور واقعی سبز شده است.
- [ ] **Timescale catalog era:** sourceهای pre-2.29 از catalog layout قدیمی `schema_name` استفاده می‌کنند و sourceهای جدیدتر ممکن است layout متفاوت داشته باشند؛ نباید catalog داخلی Timescale به‌صورت blind replay شود.
- [ ] **Credentials:** role passwordهای داخل backup داده‌ی source هستند و نباید password/identity مقصد را overwrite کنند.
- [ ] **Deployment identity:** `.env`، Docker Compose، image/container settings و DB identity بکاپ authoritative نیستند و نباید جایگزین deployment مقصد شوند.
- [ ] **Runtime assets:** certificate/key فقط بعد از validation و safety backup باید وارد cutover شوند و در failure باید rollback شوند.
- [ ] **Production safety:** هیچ restore یا migration واقعی روی Production نباید قبل از عبور از staging و validation کامل انجام شود.
- [ ] **CI status:** وضعیت سبز فقط وقتی ثبت می‌شود که GitHub Actions اجرای completed/successful گزارش کرده باشد؛ queued یا نبودن run، green محسوب نمی‌شود.
- [ ] **End-to-end validation:** synthetic Bridge روی سرور واقعی سبز شده، اما اجرای روی backup واقعی PasarGuard و GitHub Actions completed/successful همچنان لازم است.
- [ ] **AmneziaWG:** داده‌ی legacy مربوط به AmneziaWG نباید در migration به‌صورت fabricated ساخته شود؛ هر mapping باید بر اساس schema/source واقعی انجام شود.
- [ ] **Backup safety:** backup واقعی production نباید compose، image، Dockerfile یا deployment identity مقصد را overwrite کند.
- [ ] **مرجع‌پذیری:** هر کد جدید در migration باید قبل از commit بر اساس مستندات رسمی یا source معتبر پروژه‌های مرجع پیاده‌سازی و سپس با test پوشش داده شود.

### آخرین مرحله ثبت‌شده

- Portable Bridge synthetic E2E روی سرور واقعی با commit `15d2092` اجرا شد.
- خروجی نهایی: `ALL TESTS PASSED`.
- 65 migration unit test passed.
- Source hypertable `public.usage`: 48 rows.
- Destination hypertable `public.usage`: 48 rows.
- Migrated continuous aggregate `public.daily_usage`: 48 rows.
- Ruff lint/format هر دو passed.
- `scripts/run-local-tests.sh` اکنون سناریوی preinstalled TimescaleDB، hypertable data transfer و CAGG refresh را پوشش می‌دهد.

## مرحله بعدی — PasarGuard Backup Compatibility Matrix
- [x] فرمت رسمی backup PasarGuard از repository و documentation مرجع بررسی و ثبت شد.
- [x] مسیر/ساختار manifest رسمی بررسی شد؛ نمونه رسمی شامل `appdb\tappuser\t1\tdb-001.sql\t2.27.2` است.
- [x] parser اولیه `manifest.tsv` با validation صریح برای 4/5 ستون و Timescale flag/version اضافه شد.
- [x] تست‌های parser برای row معتبر، rowهای malformed و comment/blank lines اضافه شد.
- [x] validation جدید برای duplicate database name و dump path اضافه شد.
- [x] parser به preflight برای ZIP/TAR متصل شد؛ manifest malformed یا dump missing قبل از staging به‌عنوان blocking error ثبت می‌شود.
- [x] نبودن manifest در archive blocking نیست و به‌صورت warning ثبت می‌شود تا backupهای قدیمی/دستی بدون metadata نیز بدون حدس‌زدن compatibility بررسی شوند.
- [ ] اجرای تست‌های parser/preflight روی سرور واقعی و ثبت نتیجه.
- [ ] `--check` روی backup واقعی PasarGuard بدون تغییر مقصد.
- [ ] restore در isolated staging از backup واقعی.
- [ ] مقایسه schema، table counts، hypertable counts و CAGG counts.
- [ ] تست credential/deployment identity isolation.
- [ ] تست rollback.
- [ ] ثبت هر ترکیب واقعی در compatibility matrix.

### آخرین تغییر TODO
- Commit `7d329c2`: archive manifest reader و validation برای dump paths اضافه شد.
- Commit `8e92792`: تست‌های parser/archive ZIP/TAR و validation اضافه شد.
- Commit `460c769`: `manifest.tsv` به Preflight وصل شد و `PreflightResult` metadata manifest را نگه می‌دارد.
- Commit `3720923`: تست‌های preflight برای manifest معتبر، malformed و absent اضافه شد.
- این تغییرات هنوز **روی سرور واقعی اجرا نشده‌اند**؛ بنابراین هیچ supported/pass جدیدی ثبت نشده است.
- مرحله بعدی: **روی سرور واقعی `feature/amnezia-wg` pull بگیر، تست migration را اجرا کن، نتیجه را ثبت کن و سپس `--check` را به مسیر اجرایی متصل/تست کن.**
