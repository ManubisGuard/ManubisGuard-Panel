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

- [ ] تکمیل **Portable Timescale Bridge** برای حالت source Timescale جدیدتر از destination:
  1. Restore فقط در source-compatible runtime.
  2. استخراج metadata قابل‌حمل hypertableها، dimensionها، continuous aggregateها، policyها و constraintها.
  3. عدم اتکا به replay مستقیم `_timescaledb_*` catalog.
  4. ساخت schema/data قابل‌حمل برای Timescale مقصد.
  5. بازسازی hypertable/dimension با API رسمی Timescale.
  6. انتقال داده به‌صورت کنترل‌شده و قابل‌اعتبارسنجی.
  7. بازسازی post-data indexes/constraints و objectهای Timescale قابل‌حمل.
  8. بازسازی continuous aggregate/policy در صورت وجود.
  9. ANALYZE و اجرای validation کامل قبل از cutover.
- [ ] قبل از هر implementation جدید، مستندات رسمی PostgreSQL و TimescaleDB و source مربوط به نسخه هدف بررسی شود؛ implementation بدون منبع معتبر اضافه نشود.
- [ ] تست‌های unit/integration مربوط به Bridge اضافه شود، مخصوصاً PostgreSQL 17 → 16 و اختلاف نسخه Timescale.
- [ ] orchestration واقعی `scripts/manubisguard-migrate.sh` با Python migration engine دوباره audit شود تا هیچ mismatch بین planner و shell path باقی نماند.
- [ ] تمام failure/rollback pathها یک دور دوم review شوند.
- [ ] GitHub Actions آخرین commit بررسی و خطاهای واقعی، در صورت وجود، قبل از ادامه‌ی فاز بعدی رفع شوند.
- [ ] پس از پایان هر مرحله، همین فایل `TODO.md` با وضعیت واقعی همان commit به‌روزرسانی شود.

## مشکلات و نکات

- [ ] **Cross-major PostgreSQL:** source backup می‌تواند PostgreSQL 17 باشد ولی deployment مقصد PostgreSQL 16 است؛ dump تولیدشده توسط PG17 الزاماً بدون ویرایش روی PG16 قابل replay نیست. فیلتر compatibility باید محدود و explicit باقی بماند.
- [ ] **Timescale newer → older:** downgrade مستقیم TimescaleDB تصمیم معماری مجاز نیست؛ برای این حالت Portable Schema/Data Bridge یا ارتقای مقصد لازم است.
- [ ] **Timescale catalog era:** sourceهای pre-2.29 از catalog layout قدیمی `schema_name` استفاده می‌کنند و sourceهای جدیدتر ممکن است layout متفاوت داشته باشند؛ نباید catalog داخلی Timescale به‌صورت blind replay شود.
- [ ] **Credentials:** role passwordهای داخل backup داده‌ی source هستند و نباید password/identity مقصد را overwrite کنند.
- [ ] **Deployment identity:** `.env`، Docker Compose، image/container settings و DB identity بکاپ authoritative نیستند و نباید جایگزین deployment مقصد شوند.
- [ ] **Runtime assets:** certificate/key فقط بعد از validation و safety backup باید وارد cutover شوند و در failure باید rollback شوند.
- [ ] **Production safety:** هیچ restore یا migration واقعی روی Production نباید قبل از عبور از staging و validation کامل انجام شود.
- [ ] **CI status:** وضعیت سبز فقط وقتی ثبت می‌شود که GitHub Actions اجرای completed/successful گزارش کرده باشد؛ queued یا نبودن run، green محسوب نمی‌شود.
- [ ] **End-to-end validation:** تا وقتی مسیر کامل source backup → isolated runtime → cutover DB → validation → production rollback در محیط واقعی اجرا نشده، migration را production-ready قطعی تلقی نمی‌کنیم.
- [ ] **AmneziaWG:** داده‌ی legacy مربوط به AmneziaWG نباید در migration به‌صورت fabricated ساخته شود؛ هر mapping باید بر اساس schema/source واقعی انجام شود.
- [ ] **Backup safety:** backup واقعی production نباید compose، image، Dockerfile یا deployment identity مقصد را overwrite کند.
- [ ] **مرجع‌پذیری:** هر کد جدید در migration باید قبل از commit بر اساس مستندات رسمی یا source معتبر پروژه‌های مرجع پیاده‌سازی و سپس با test پوشش داده شود.
