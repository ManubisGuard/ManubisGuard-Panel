# وضعیت پروژه — ManubisGuard

## وضعیت کلی
- Branch فعال: feature/amnezia-wg
- main دست‌نخورده می‌ماند.
- PR #1: Draft / Open / Merge نشده.
- Railway کنار گذاشته شده؛ اعتبارسنجی پروژه با GitHub Actions و سپس سرور واقعی انجام می‌شود.
- --apply روی دیتابیس واقعی هنوز مجاز/تأییدشده نیست.
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
- [x] verifier برای مقایسه row count جدول‌ها و hypertableها.
- [x] workflow مستقل GitHub Actions برای integration.

## Restore / Migration — تست‌شده در GitHub Actions
- [x] unit testهای migration/restore safety/compatibility در CI موجود هستند.
- [x] syntax check برای scripts/manubisguard-migrate.sh در CI اضافه شده است.
- [x] integration workflow مستقل تعریف شده: PostgreSQL 17 + TimescaleDB 2.30.0 → PostgreSQL 16 + TimescaleDB 2.29.2.
- [ ] Integration workflow هنوز completed/successful تأیید نشده؛ Portable Bridge end-to-end در Actions هنوز passed نیست.
- [ ] PR #1 در آخرین وضعیت قابل مشاهده اجرای completed/successful قابل استناد ندارد؛ runهای مشاهده‌شده queued بوده‌اند و failure log قابل تحلیل وجود نداشته است.

## Restore / Migration — تست‌شده روی سرور واقعی
- [ ] --check روی backup واقعی PasarGuard.
- [ ] restore روی staging/isolated database.
- [ ] validation schema/table/hypertable/CAGG و count comparison روی backup واقعی.
- [ ] rollback واقعی.
- [ ] runtime asset restore و rollback.
- [ ] compatibility با deployment واقعی PostgreSQL 16 / TimescaleDB مقصد.
- [ ] --apply روی production انجام نشده و نباید تا پایان validation انجام شود.

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
| PasarGuard backup واقعی موجود | 17.10 | 2.28.2 | 5.4.1 / Alembic awg2026091901 | 16 | نسخه مقصد deployment؛ باید روی سرور تأیید شود | implementation موجود؛ E2E تست نشده |
| Integration synthetic | 17 | 2.30.0 | feature/amnezia-wg | 16 | 2.29.2 | workflow تعریف شده؛ pass هنوز تأیید نشده |
| ManubisGuard backup واقعی | باید ثبت شود | باید ثبت شود | نسخه مقصد | باید ثبت شود | باید ثبت شود | تست نشده |
| PasarGuard نسخه‌های جدیدتر | باید از backup واقعی ثبت شود | باید از backup واقعی ثبت شود | نسخه branch/release مربوطه | باید ثبت شود | باید ثبت شود | نیازمند regression test |

### قواعد ماتریس
- [ ] هیچ ترکیب جدیدی بدون اجرای واقعی supported علامت زده نشود.
- [ ] برای هر ردیف: source app version + PostgreSQL + Timescale + target ManubisGuard/Alembic ثبت شود.
- [ ] PostgreSQL cross-major فقط با source-compatible client/runtime یا bridge مناسب.
- [ ] Timescale newer → older با Portable Bridge؛ downgrade مستقیم ممنوع.
- [ ] Timescale older → newer با source-compatible restore و سپس upgrade در staging.
- [ ] backup نباید role password، DB identity، compose، image/container یا deployment identity مقصد را overwrite کند.

## GitHub Actions — آخرین وضعیت
- PR #1: #1 / Draft / Open / Not merged.
- Base: main.
- Head: feature/amnezia-wg.
- آخرین head ثبت‌شده PR در بررسی: 4a7d0e302461d612b436c6ce13b58d7492856243.
- برای این head، connector فعلی run completed قابل استناد برنگرداند؛ بنابراین green اعلام نمی‌شود.
- آخرین runهای مشاهده‌شده قبلی queued بودند؛ Portable Bridge Integration نیز runner نگرفته بود.
- Integration workflow فعلی در .github/workflows/timescale-portable-bridge.yml شامل source=Timescale 2.30.0/PG17، destination=Timescale 2.29.2/PG16، seed، bridge، dump، restore و count verification است.
- Railway: کنار گذاشته شده.

## پیشنهاد تقسیم PR
**پیشنهاد می‌شود branch به دو PR تقسیم شود، اما فعلاً هیچ split یا merge انجام نشده است:**

1. **PR AmneziaWG** — فقط تغییرات AmneziaWG، مستقل و کوچک برای review و merge امن‌تر.
2. **PR Restore/Migration** — فقط Detection/Preflight/Restore Safety/Timescale Bridge/Compatibility و CI migration tooling؛ مستقل تا E2E کامل review شود.

## قانون ادامه کار
بعد از هر اجرای واقعی:
1. نتیجه دقیق ثبت شود.
2. فقط مرحله واقعاً passed با [x] علامت بخورد.
3. failure و علت و commit ثبت شود.
4. fix → test → re-test انجام شود.
5. تا green شدن integration و E2E واقعی، Restore/Migration «تکمیل و تست‌شده» اعلام نشود.

## مشکلات و نکات

- [ ] **Cross-major PostgreSQL:** source backup می‌تواند PostgreSQL 17 باشد ولی deployment مقصد PostgreSQL 16 است؛ dump تولیدشده توسط PG17 الزاماً بدون ویرایش روی PG16 قابل replay نیست. فیلتر compatibility باید محدود و explicit باقی بماند.
- [x] **Timescale newer → older:** downgrade مستقیم TimescaleDB انجام نمی‌شود؛ Portable Schema/Data Bridge مسیر اختصاصی آن است.
- [ ] **Timescale catalog era:** sourceهای pre-2.29 از catalog layout قدیمی `schema_name` استفاده می‌کنند و sourceهای جدیدتر ممکن است layout متفاوت داشته باشند؛ نباید catalog داخلی Timescale به‌صورت blind replay شود.
- [ ] **Credentials:** role passwordهای داخل backup داده‌ی source هستند و نباید password/identity مقصد را overwrite کنند.
- [ ] **Deployment identity:** `.env`، Docker Compose، image/container settings و DB identity بکاپ authoritative نیستند و نباید جایگزین deployment مقصد شوند.
- [ ] **Runtime assets:** certificate/key فقط بعد از validation و safety backup باید وارد cutover شوند و در failure باید rollback شوند.
- [ ] **Production safety:** هیچ restore یا migration واقعی روی Production نباید قبل از عبور از staging و validation کامل انجام شود.
- [ ] **CI status:** وضعیت سبز فقط وقتی ثبت می‌شود که GitHub Actions اجرای completed/successful گزارش کرده باشد؛ queued یا نبودن run، green محسوب نمی‌شود.
- [ ] **End-to-end validation:** مسیر Bridge روی دیتای نمونه در GitHub Actions تعریف شده اما هنوز completed/successful نشده؛ اجرای روی backup واقعی و سرور production همچنان لازم است.
- [ ] **AmneziaWG:** داده‌ی legacy مربوط به AmneziaWG نباید در migration به‌صورت fabricated ساخته شود؛ هر mapping باید بر اساس schema/source واقعی انجام شود.
- [ ] **Backup safety:** backup واقعی production نباید compose، image، Dockerfile یا deployment identity مقصد را overwrite کند.
- [ ] **مرجع‌پذیری:** هر کد جدید در migration باید قبل از commit بر اساس مستندات رسمی یا source معتبر پروژه‌های مرجع پیاده‌سازی و سپس با test پوشش داده شود.

### آخرین مرحله ثبت‌شده

- Portable Bridge commits: `335e431d1d5279f44bfcfa04414ef17523cdd6eb` تا `e132e12054610e700ef4c33dd073d13256adca85`
- CI syntax check برای `scripts/manubisguard-migrate.sh` اضافه شد.
- PR آزمایشی #1 برای فعال‌کردن CI ساخته شد و merge نشده است.

### وضعیت GitHub Actions در آخرین بررسی

- PR #1: Draft/Open و merge نشده؛ head=`feature/amnezia-wg`.
- Run `ManubisGuard CI` برای head فعلی: queued.
- Run `Timescale Portable Bridge Integration`: queued؛ job=`postgres-timescale-bridge` و هنوز runner نگرفته است.
- نتیجه‌ی pass/fail فعلاً ثبت نشده و عمداً هیچ موردی سبز اعلام نشده است.
