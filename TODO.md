# وضعیت پروژه

## انجام‌شده

- [x] ایجاد معماری مهاجرت امن PasarGuard → ManubisGuard با مسیر Detection → Preflight → Staging → Transformation → Alembic HEAD → Validation → Cutover.
- [x] پیاده‌سازی تشخیص و Preflight بکاپ و جلوگیری از Restore مستقیم روی Production.
- [x] اضافه‌کردن اعتبارسنجی سخت‌گیرانه‌ی Archive برای ZIP/TAR:
  - CRC validation برای ZIP
  - جلوگیری از path traversal
  - جلوگیری از duplicate normalized paths
  - رد symlink / hardlink / device / FIFO / special files
  - محدودیت تعداد entryها
- [x] سخت‌سازی Restore credentialها در `app/migration/restore_safety.py`:
  - پشتیبانی از CREATE/ALTER ROLE و USER
  - حذف password clauseهای بکاپ
  - حذف کامل statement مربوط به role مقصد
  - پشتیبانی از statementهای چندخطی
  - پردازش streaming برای dumpهای بزرگ
- [x] سخت‌سازی Restore محیط در `scripts/manubisguard-restore-env.py`:
  - جلوگیری از import هویت PostgreSQL/DB
  - جلوگیری از import تنظیمات Docker/Compose/Image/Container
  - جلوگیری از archive symlink و special file
  - Stage کردن certificate/key به‌جای overwrite مستقیم
- [x] سخت‌سازی Cutover در `scripts/manubisguard-migrate.sh`:
  - Production safety backup قبل از تغییر
  - compose integrity guard
  - stage/apply/rollback برای runtime assets
  - rollback برای env/assets در خطا
  - rollback در rename/start/health/integrity failure
- [x] پیاده‌سازی تشخیص PostgreSQL major از dump و استفاده از source-compatible PostgreSQL/Timescale runtime.
- [x] اصلاح image tagهای Timescale به الگوی واقعی `timescale/timescaledb:<version>-pg<major>-oss`.
- [x] استفاده از source runtime برای restore و `pg_dump` مجدد، به‌جای تکیه بر dump client محیط مقصد.
- [x] اضافه‌کردن فیلتر بسیار محدود PostgreSQL compatibility برای `SET transaction_timeout` فقط هنگام Restore به PostgreSQL قدیمی‌تر.
- [x] جلوگیری از replay مستقیم TimescaleDB catalog و حذف DDL مربوط به extension مقصد در مسیر cutover.
- [x] اضافه‌کردن منطق تشخیص نسخه دقیق TimescaleDB از SQL/manifest/sidecar و بررسی conflict.
- [x] اضافه‌کردن مستندات Restore Hardening در `docs/migration/PASARGUARD_RESTORE_HARDENING.md`.
- [x] اضافه‌کردن تست‌های migration برای detector، preflight، restore safety، environment restore، runner، Timescale و compatibility.
- [x] API compatibility audit اولیه در سطح route/method با PasarGuard انجام شده؛ routeهای اختصاصی Domain Intelligence/Certificate نیز شناسایی شده‌اند.
- [x] تصمیم معماری ثبت شد که source Timescale قدیمی‌تر می‌تواند در runtime خودش restore و سپس در staging ارتقا داده شود؛ downgrade کورکورانه‌ی Timescale مجاز نیست.

## وضعیت فعلی

- Branch فعال: `feature/amnezia-wg`
- تمرکز فعلی روی Migration/Restore Safety و Bridge بین نسخه‌های PostgreSQL/TimescaleDB است.
- فایل‌های اصلی درگیر:
  - `app/migration/detector.py`
  - `app/migration/preflight.py`
  - `app/migration/runner.py`
  - `app/migration/staging.py`
  - `app/migration/timescale.py`
  - `app/migration/restore_safety.py`
  - `scripts/manubisguard-migrate.sh`
  - `scripts/manubisguard-restore-env.py`
  - `docs/migration/PASARGUARD_RESTORE_HARDENING.md`
  - `tests/migration/*`
- وضعیت migration engine در حال حاضر برای source Timescale قدیمی‌تر → destination جدیدتر، مسیر source-compatible staging و upgrade ایزوله را در نظر گرفته است.
- تست `tests/migration/test_runner.py` این رفتار version-aware را پوشش می‌دهد، اما مسیر کامل orchestration هنوز نیازمند تست end-to-end واقعی است.
- CI باید از GitHub Actions به‌صورت واقعی بررسی شود؛ صرف وجود workflow یا queued run به‌عنوان green تلقی نمی‌شود.
- نسخه Alembic فعلی پروژه: `awg2026091901`.
- آخرین migration state شناخته‌شده‌ی پروژه بر پایه‌ی staging/backup واقعی: PostgreSQL 17.10 و TimescaleDB 2.28.2 در source backup، در حالی که deployment مقصد PostgreSQL 16 است.

## مرحله‌ی بعد

- [x] پیاده‌سازی هسته و orchestration اولیه‌ی **Portable Timescale Bridge** برای حالت source Timescale جدیدتر از destination:
  - planner و metadata extraction از informational views
  - جداسازی pre-data / data / post-data
  - بازسازی hypertable/dimension با API عمومی
  - بازسازی CAGG با refresh کامل
  - بازسازی policyهای پشتیبانی‌شده
  - جلوگیری از replay کاتالوگ داخلی
  - fail-closed برای metadata/policyهای ناشناخته
  - اتصال مسیر newer→older در `scripts/manubisguard-migrate.sh`
  1. [x] Restore فقط در source-compatible runtime.
  2. [x] استخراج metadata قابل‌حمل hypertableها، dimensionها، continuous aggregateها و policyها.
  3. [x] عدم اتکا به replay مستقیم `_timescaledb_*` catalog.
  4. [x] ساخت schema/data قابل‌حمل برای Timescale مقصد.
  5. [x] بازسازی hypertable/dimension با API رسمی Timescale.
  6. [x] انتقال داده به‌صورت کنترل‌شده و قابل‌اعتبارسنجی در cutover isolated DB.
  7. [x] بازسازی post-data indexes/constraints و objectهای relational.
  8. [x] بازسازی continuous aggregate/policyهای public و پشتیبانی‌شده؛ موارد ناشناخته fail-closed هستند.
  9. [x] ANALYZE در artifactهای bridge.
- [ ] قبل از هر implementation جدید، مستندات رسمی PostgreSQL و TimescaleDB و source مربوط به نسخه هدف بررسی شود؛ implementation بدون منبع معتبر اضافه نشود.
- [x] تست‌های unit مربوط به Bridge اضافه شد، مخصوصاً version direction، hypertable/dimension، CAGG، policy، dump exclusions و artifact generation.
- [ ] integration واقعی PostgreSQL 17 → 16 و اختلاف نسخه Timescale هنوز باید در محیط Docker/Railway مناسب اجرا شود.
- [x] orchestration `scripts/manubisguard-migrate.sh` برای مسیر newer→older به Portable Bridge متصل شد.
- [ ] یک اجرای end-to-end واقعی روی backup واقعی هنوز باقی است.
- [ ] تمام failure/rollback pathها یک دور دوم review شوند.
- [ ] GitHub Actions برای head فعلی از connector موجود نتیجه‌ی run قابل‌استناد برنگرداند؛ بنابراین CI را سبز اعلام نمی‌کنیم.
- [ ] Railway تست شد، اما ابزار deployment با وجود branch درخواستی deployment را روی `main` ثبت کرد؛ نتیجه‌ی آن برای branch فعلی معتبر نیست.
- [ ] پس از پایان هر مرحله، همین فایل `TODO.md` با وضعیت واقعی همان commit به‌روزرسانی شود.

## مشکلات و نکات

- [ ] **Cross-major PostgreSQL:** source backup می‌تواند PostgreSQL 17 باشد ولی deployment مقصد PostgreSQL 16 است؛ dump تولیدشده توسط PG17 الزاماً بدون ویرایش روی PG16 قابل replay نیست. فیلتر compatibility باید محدود و explicit باقی بماند.
- [x] **Timescale newer → older:** downgrade مستقیم TimescaleDB انجام نمی‌شود؛ Portable Schema/Data Bridge مسیر اختصاصی آن است.
- [ ] **Timescale catalog era:** sourceهای pre-2.29 از catalog layout قدیمی `schema_name` استفاده می‌کنند و sourceهای جدیدتر ممکن است layout متفاوت داشته باشند؛ نباید catalog داخلی Timescale به‌صورت blind replay شود.
- [ ] **Credentials:** role passwordهای داخل backup داده‌ی source هستند و نباید password/identity مقصد را overwrite کنند.
- [ ] **Deployment identity:** `.env`، Docker Compose، image/container settings و DB identity بکاپ authoritative نیستند و نباید جایگزین deployment مقصد شوند.
- [ ] **Runtime assets:** certificate/key فقط بعد از validation و safety backup باید وارد cutover شوند و در failure باید rollback شوند.
- [ ] **Production safety:** هیچ restore یا migration واقعی روی Production نباید قبل از عبور از staging و validation کامل انجام شود.
- [ ] **CI status:** وضعیت سبز فقط وقتی ثبت می‌شود که GitHub Actions اجرای completed/successful گزارش کرده باشد؛ queued یا نبودن run، green محسوب نمی‌شود.
- [ ] **End-to-end validation:** مسیر Bridge هنوز روی backup واقعی در PostgreSQL/Timescale runtime اجرا نشده؛ تا آن زمان migration را production-ready قطعی تلقی نمی‌کنیم.
- [ ] **AmneziaWG:** داده‌ی legacy مربوط به AmneziaWG نباید در migration به‌صورت fabricated ساخته شود؛ هر mapping باید بر اساس schema/source واقعی انجام شود.
- [ ] **Backup safety:** backup واقعی production نباید compose، image، Dockerfile یا deployment identity مقصد را overwrite کند.
- [ ] **مرجع‌پذیری:** هر کد جدید در migration باید قبل از commit بر اساس مستندات رسمی یا source معتبر پروژه‌های مرجع پیاده‌سازی و سپس با test پوشش داده شود.

### آخرین مرحله ثبت‌شده

- Portable Bridge commits: `335e431d1d5279f44bfcfa04414ef17523cdd6eb` تا `e132e12054610e700ef4c33dd073d13256adca85`
- CI syntax check برای `scripts/manubisguard-migrate.sh` اضافه شد.
- PR آزمایشی #1 برای فعال‌کردن CI ساخته شد و merge نشده است.
