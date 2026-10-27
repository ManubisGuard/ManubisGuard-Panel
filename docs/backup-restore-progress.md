# گزارش پیشرفت بکاپ و ریستور ManubisGuard
تاریخ آخرین ثبت: 2026-10-26
مخزن: `/opt/manubisguard-panel`
شاخه: `feature/amnezia-wg`
HEAD در زمان آخرین بازبینی: `ed72211f5e5264e895c06eb587033fc3d5b233e5`
وضعیت: کار در حال انجام، آماده انتشار نیست.

## هدف و خط قرمزها
- حفظ موتور اصلی بکاپ/ریستور PasarGuard؛ از طراحی فرمت یا موتور موازی جدید خودداری شود.
- سازگاری فورک ManubisGuard و رکوردهای AmneziaWG/AWG Core بدون حذف فرمت اصلی آرشیو.
- هر آزمون Restore فقط در محیط ایزوله و با داده آزمایشی؛ هیچ Restore واقعی یا `--apply` روی پنل عملیاتی اجرا نشود.
- به `/var/lib/manubisguard`، دیتابیس عملیاتی، سرویس‌ها و کانتینرهای تولید دست زده نشود.
- شاخه `main` و Node/N2 خارج از محدوده‌اند.
- هیچ Secret، توکن، URL اتصال دارای اطلاعات محرمانه یا داده مشتری در گزارش ثبت نشود.

## ثبت مراحل

### مرحله A: تطبیق با موتور اصلی
- موتور اصلی و کتابخانه‌های هم‌نسخه از `PasarGuard/scripts` با commit پین‌شده `21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7` بررسی شده‌اند.
- بررسی قبلی گزارش کرده بود که هشت فایل upstream انتخاب‌شده با نسخه پین‌شده منطبق‌اند؛ مقایسه قبلی با `main` نیز اختلافی نشان نداده بود. قبل از هر ارتقای نسخه، این تطبیق باید دوباره در همان اجرای قابل ثبت تکرار شود.
- آداپتر `scripts/manubisguard-native-backup.sh` همچنان wrapper باریک برای CLI اصلی است و مسیرهای پروژه/داده/آرشیو را تنظیم می‌کند؛ فرمت آرشیو و نام‌های سازگاری upstream نباید بازنویسی شوند.

### مرحله B: آزمون واقعی اما ایزوله Native Restore
- در محیط آزمایشی جداگانه `/opt/manubisguard-work/pr7-merged-roundtrip`، آرشیو آزمایشی `backup_20261026184557.zip` ایجاد و بررسی شد.
- لاگ `restore-apply-safe.log` نشان می‌دهد Restore دیتابیس آزمایشی TimescaleDB، داده‌های برنامه و فایل‌های برنامه در همان پروژه آزمایشی انجام شده است.
- آرشیو خراب/ناقص در `invalid-check.log` به‌درستی به‌عنوان ZIP نامعتبر رد شد.
- این نتیجه مربوط به پروژه و دیتابیس آزمایشی است، نه Restore تولید. Round-trip قبلی، به‌تنهایی اثبات نمی‌کند که تمام فیلدهای AWG Core در نسخه جاری به‌طور اختصاصی بررسی شده‌اند.

### مرحله C: بررسی تست‌ها و اصلاح وابستگی منسوخ
- تست قدیمی `tests/api/test_restore_agent.py` به اسکریپتی ارجاع می‌داد که در معماری Native حذف شده است.
- در `app/routers/admin_backup.py` مسیر API ریستور تولید از وابستگی به Restore Agent حذف شد و به‌صورت fail-closed با HTTP 503 باقی ماند؛ هیچ Restore اجرا نمی‌کند.
- فایل تست قدیمی در وضعیت کاری حذف شده است. قبل از Commit باید اطمینان حاصل شود که حذف آن با تست‌های جدید مناسب جایگزین شده یا علت حذف آن در تست‌های معماری پوشش دارد.
- اجرای تست‌های ایزوله با Python 3.14 در یک کانتینر موقت، به دلیل راه‌اندازی خودکار مهاجرت‌های دیتابیس در `tests/conftest.py` طولانی شد و پیش از پایان جمع‌آوری تست‌ها متوقف شد. بنابراین **مجموعه کامل pytest موفق اعلام نمی‌شود**.
- پوشه کاری موقت `/opt/manubisguard-work/native-backup-ci-check` پس از بررسی حذف شد.

### مرحله D: بررسی‌های موفق پس از تغییر
- `bash tests/test_native_backup_adapter.sh`: PASS
- `bash tests/test_native_backup_transform.sh`: PASS
- تجزیه نحوی Python برای `app/routers/admin_backup.py`: PASS
- `ruff check app/routers/admin_backup.py`: PASS
- `bash -n scripts/manubisguard-native-backup.sh install-manubisguard.sh`: PASS
- `git diff --check`: PASS

## وضعیت Git در زمان ثبت
- شاخه محلی: `feature/amnezia-wg`
- HEAD محلی و `origin/feature/amnezia-wg`: هر دو `4312e72bfff2d080ae5aed77ab29b586c677eb19`
- تغییرات کاری شناخته‌شده: `app/routers/admin_backup.py` و حذف `tests/api/test_restore_agent.py`.
- فایل محلی از قبل موجود `AI_HANDOFF_PROMPT_2026-10-25.md` دست‌نخورده باقی مانده است؛ پیش از Commit باید محتوای آن جداگانه بررسی شود و به‌صورت ناخواسته اضافه نشود.
- هیچ Commit یا Push جدیدی انجام نشده است.

## وضعیت عملیاتی
آخرین بررسی فقط خواندنی نشان داد کانتینرهای `manubisguard-panel-manubisguard-1` و `manubisguard-panel-timescaledb-1` در حالت healthy هستند. هیچ Restart، تغییر دیتابیس تولید، Restore یا Deploy در این مرحله انجام نشده است.

## کارهای باقی‌مانده، به ترتیب
1. افزودن/تأیید تست خودکار برای fail-closed بودن endpoint ریستور تولید و حذف ارجاع‌های مرده به Restore Agent.
2. اجرای تست‌های مرتبط با معماری Native و API در محیط ایزوله با دیتابیس آزمایشی و تنظیمات تست صریح، بدون مهاجرت ناخواسته یا اتصال به تولید.
3. اجرای مجدد Native backup → `restore --check` → Restore آزمایشی با تأیید داده‌ها، فرمت آرشیو و فایل‌های مقصد.
4. افزودن fixture مشخص AWG Core: رکورد نوع Core، پارامترهای obfuscation و ارتباط آن با Node را قبل و بعد از round-trip مقایسه کنیم؛ هیچ کلید/اطلاعات واقعی مشتری وارد fixture نشود.
5. بررسی دقیق اینکه runtime تولید Node و فایل‌های میزبان در دامنه بکاپ پنل نیستند؛ این موارد باید جداگانه و فقط طبق مستندات Node پوشش داده شوند، نه با تغییر فرمت آرشیو اصلی پنل.
6. بازبینی نهایی diff، ثبت نتیجه هر مرحله در همین گزارش، سپس Commit/Push فقط پس از عبور همه گیت‌ها و تأیید مسیرهای مجاز.

## قاعده به‌روزرسانی گزارش
پس از هر مرحله مستقل، تاریخ/ساعت، هدف، فرمان‌ها یا تست‌های اجراشده، نتیجه واقعی، مسیر لاگ‌ها و گام بعدی را به همین فایل اضافه کنید. نتیجه ناموفق یا ناقص نیز ثبت شود؛ تستی که timeout یا متوقف شده نباید PASS گزارش شود.

### مرحله E: پوشش رگرسیون مسیر API و اصلاح پیام راهنما (2026-10-26)
- در `tests/test_native_backup_adapter.sh` اضافه شد که مسیر API ریستور تولید باید fail-closed باشد و دیگر به `restore_agent`، کلید Secret آن یا `urlopen` وابسته نباشد.
- همان تست اکنون پیام API را برای ارجاع به فایل حذف‌شده `scripts/manubisguard-native-restore.py` بررسی می‌کند تا این رگرسیون برنگردد.
- متن خطای endpoint ریستور staging اصلاح شد: به‌جای ارجاع به اسکریپت حذف‌شده، دستور غیرمخرب `manubis restore <full-archive> --check` را برای بررسی آرشیو معرفی می‌کند و می‌گوید آزمون کامل Restore فقط باید با harness ایزوله انجام شود.
- تست‌های `tests/test_native_backup_adapter.sh` و `tests/test_native_backup_transform.sh` هر دو PASS شدند.
- `bash -n` برای اسکریپت‌های مربوط، AST parse فایل Router، `ruff check app/routers/admin_backup.py tests/test_native_backup_architecture.py` و `git diff --check` PASS شدند.
- تست‌های فعلی AWG در مخزن عمدتاً normalization نوع Core را پوشش می‌دهند؛ هنوز fixture اختصاصی Native backup/restore که مقدار `core_configs.type=amneziawg` و JSON پارامترهای obfuscation را قبل و بعد از round-trip مقایسه کند، وجود ندارد. این مورد هنوز مانع اعلام پذیرش کامل AWG restore است.

### مرحله F: آزمون fixture مربوط به AWG در آرشیو Native (2026-10-26، نتیجه ناقص)
- پروژه کاملاً جداگانه `/opt/manubisguard-work/awg-native-roundtrip-20261026` ساخته شد؛ نام Compose آن `manubisguard-awg-roundtrip` است و از دیتابیس آزمایشی TimescaleDB استفاده می‌کند. این پروژه به سرویس‌های تولید متصل نشده است.
- یک fixture ساختگی با `core_configs.type=amneziawg`، مقادیر JSON برای `Jc/Jmin/Jmax/S1/S2/H1-H4` و یک ردیف Node مرتبط ایجاد شد.
- موتور Native یک آرشیو ساخت: `backups/backup_20261026191001.zip`؛ فرمان `restore <archive> --check` نیز PASS داد و آرشیو را معتبر تشخیص داد.
- **تأیید نهایی AWG round-trip هنوز PASS نیست.** تلاش اول پس از Restore به‌خاطر quoting نادرست در کوئری بررسی، نتوانست نتیجه را درست ارزیابی کند؛ خروجی اولیه عبارت PASS داشت اما این نتیجه معتبر نیست و نباید به‌عنوان قبولی حساب شود. تلاش دوم به‌دلیل آماده نبودن دیتابیس مقصد در زمان اجرای Restore با خطای اتصال به socket متوقف شد. بنابراین هنوز اثبات نشده که fixture AWG پس از Restore همان مقادیر را دارد.
- این نتیجه صریحاً جایگزین هر عبارت قبلی `AWG_NATIVE_ROUNDTRIP=PASS` در خروجی موقت می‌شود. برای قبولی باید ابتدا آمادگی دیتابیس آزمایشی تأیید شود، سپس Restore در همان پروژه ایزوله اجرا و کوئری با `ON_ERROR_STOP=1` دقیقاً یک ردیف مطابق انتظار برگرداند.
- لاگ آزمون: `/opt/manubisguard-work/awg-native-roundtrip-20261026/awg-native-roundtrip.log`. آرشیو آزمایشی برای تحلیل باقی مانده است. پروژه با trap پاک‌سازی خودکار تنظیم شده بود؛ وضعیت نهایی کانتینر باید در بررسی بعدی دوباره تأیید شود.


### مرحله G: Native AWG round-trip تکمیل شد (2026-10-26)
- پروژهٔ ایزولهٔ Compose با نام دقیق manubisguard-awg-roundtrip دوباره بالا آمد؛ قبل از هر Restore، شناسهٔ کانتینر خروجی Restore با docker compose ps -q timescaledb و برچسب Compose تطبیق داده شد. تنها سرویس تعریف‌شده timescaledb بود؛ هیچ پورت یا volume مشترکی با سرویس‌های عملیاتی نداشت.
- Restore اول از آرشیو backups/backup_20261026191001.zip با exit code صفر کامل شد.
- پس از Restore اول، کوئری با psql -v ON_ERROR_STOP=1 یک ردیف دقیق با این مقادیر برگرداند: core_configs.id=77، type=amneziawg، مقادیر Jc/Jmin/Jmax/S1/S2/H1-H4 برابر fixture ثبت‌شده، و nodes.id=88 با نام awg-fixture-node و FK برابر 77.
- برای اثبات واقعی Restore، مقصد را عمداً تغییر دادیم: type=mutated-awg، Jc=99، H1=999 و نام Node به awg-mutated-node تغییر کرد. سپس Restore دوم همان آرشیو با تأیید تعاملی در همان کانتینر ایزوله اجرا شد و با exit code صفر پایان یافت.
- پس از Restore دوم، مقایسهٔ دقیق تمام ستون‌ها با مقدار مورد انتظار پاس شد؛ هیچ‌کدام از مقادیر دستکاری‌شده باقی نماند. نشانگرها: AWG_SECOND_RESTORE_ROUNDTRIP=PASS، DESTINATION_COMPOSE_PRESERVED=PASS، DESTINATION_ENV_PRESERVED=PASS و DATA_DIRECTORY_RESTORED=PASS.
- نتیجهٔ قبلی AWG_NATIVE_ROUNDTRIP=PASS که به علت کنترل خطای نادرست چاپ شده بود همچنان نامعتبر محسوب می‌شود؛ قبولی معتبر فقط متعلق به این مرحلهٔ تکرارپذیر و کنترل‌شده است.
- تست قدیمی tests/api/test_restore_agent.py به scripts/manubisguard-restore-agent.py حذف‌شده وابسته بود؛ به‌جای از دست دادن پوشش رفتاری، tests/test_backup_restore_fail_closed.py اضافه شد تا endpointهای staging و production واقعاً با HTTP 503 و بدون اجرای عملیات متوقف بمانند.
- تست‌های shell tests/test_native_backup_adapter.sh و tests/test_native_backup_transform.sh هر دو PASS شدند؛ bash -n برای اسکریپت‌های مربوط PASS شد.
- اجرای ایزوله و بدون شبکهٔ pytest روی Python 3.14 برای tests/test_backup_restore_fail_closed.py، tests/test_native_backup_architecture.py، tests/migration و tests/compatibility: **94 passed in 30.23s**. اجرای Ruff با --no-fix روی فایل‌های تغییرکرده نیز **All checks passed** داد.
- این نتیجه جایگزین «Full pytest PASS» نیست؛ مجموعهٔ کامل تست‌های API در این مرحله اجرا نشده است. هیچ Restore، Restart یا Deploy تولیدی انجام نشد.
- مسیر لاگ Restore معتبر: /opt/manubisguard-work/awg-native-roundtrip-20261026/awg-native-roundtrip-retry.log. لاگ تست‌های متمرکز: /opt/manubisguard-work/awg-native-roundtrip-20261026/final-focused-tests.log (خروجی واقعی آخرین اجرای pytest/Ruff نیز در نشست ابزار ثبت شده است).
- قبل از Commit/Push: پاک‌سازی فقط کانتینر/شبکهٔ آزمایشی با شناسهٔ Compose صریح، git diff --check نهایی، بازبینی شاخهٔ remote، و افزودن مسیرهای مجاز به‌صورت صریح. فایل محلی AI_HANDOFF_PROMPT_2026-10-25.md نباید stage یا commit شود.


### مرحله H: پاک‌سازی و وضعیت عملیاتی نهایی (2026-10-26)
- کانتینر و شبکه فقط برای پروژهٔ manubisguard-awg-roundtrip با Compose صریح حذف شدند؛ هیچ پروژه یا volume عملیاتی و هیچ پروژهٔ آزمایشی دیگر هدف فرمان نبود.
- snapshot قبل و بعد برابر بود: manubisguard-panel-manubisguard-1 و manubisguard-panel-timescaledb-1 هر دو running/healthy با restart_count=0. پرچم‌های DISPOSABLE_TEST_CLEANUP=PASS و PRODUCTION_CONTAINERS_UNCHANGED=PASS ثبت شدند.
- خلاصهٔ قابل‌نگهداری نتایج تست در /opt/manubisguard-work/awg-native-roundtrip-20261026/final-focused-tests.log بازنویسی شد تا خروجی ناموفق اولیهٔ Ruff روی میزبان را با اجرای نهایی موفقِ Ruff در کانتینر ایزوله اشتباه نگیرد. لاگ Restore معتبر همچنان awg-native-roundtrip-retry.log است.
- git diff --check نهایی پیش از stage پاک بود. HEAD محلی 4312e72bfff2d080ae5aed77ab29b586c677eb19 بود و ls-remote تأیید کرد که origin/feature/amnezia-wg نیز همین commit است. فایل AI_HANDOFF_PROMPT_2026-10-25.md همچنان untracked و خارج از Commit می‌ماند.


### مرحله I: Commit و Push تأیید شد (2026-10-26)
- Commit: cd5be779734d3eac36d59b4bf1099f7dd9291f65
- پیام: test: verify native AWG backup restore round-trip
- Push به origin/feature/amnezia-wg موفق شد؛ مقدار ls-remote پس از Push دقیقاً با HEAD محلی برابر بود و COMMIT_PUSH_VERIFY=PASS ثبت شد.
- پنج مسیر بررسی‌شده داخل commit هستند: router بکاپ، گزارش پیشرفت، حذف تست obsolete، تست جدید fail-closed و تست shell adapter. هیچ فایل با git add -A اضافه نشد.
- وضعیت نهایی Git فقط AI_HANDOFF_PROMPT_2026-10-25.md را به‌صورت untracked نشان می‌دهد؛ این فایل محلی عمداً commit یا push نشده است.
- نتیجهٔ پذیرش این مرحله: Native AWG round-trip در محیط ایزوله PASS؛ 94 تست متمرکز PASS؛ Ruff PASS؛ API restore تولید و staging همچنان fail-closed. Full pytest هنوز اجرا/تأیید نشده و ادعای قبولی کامل آن وجود ندارد.
- هیچ Restore، Restart، Deploy یا تغییر داده‌ای در سرویس‌های تولید انجام نشد؛ پروژهٔ آزمایشی حذف و سلامت کانتینرهای تولید پس از پاک‌سازی تأیید شد.

### مرحله J: تثبیت مبنای Git و تصحیح وضعیت مستندات (2026-10-26)
- هویت محیط بررسی‌شده: hostname `8017638839-32c511`، مسیر `/opt/manubisguard-panel`، شاخه `feature/amnezia-wg`.
- HEAD محلی و `origin/feature/amnezia-wg` برابر `7333b5a84895a922d230b9e9ce4e607012edae16` بودند؛ `git rev-list --left-right --count HEAD...origin/feature/amnezia-wg` نتیجهٔ `0 0` داد.
- هیچ تغییر tracked یا staged پیش از این اصلاح مستندات وجود نداشت. تنها مورد محلی untracked برابر `AI_HANDOFF_PROMPT_2026-10-25.md` است؛ محتوا خوانده نشده، تغییر نکرده و وارد Git نخواهد شد.
- `git diff --check` و `git diff --cached --check` قبل از اصلاح پاک بودند.
- در `docs/NATIVE-BACKUP-ARCHITECTURE.md` وضعیت قدیمی مبنی بر «round-trip هنوز تأیید نشده» اصلاح شد. اکنون مستندات نتیجهٔ AWG round-trip و 94 تست متمرکز را ذکر می‌کند و صریحاً می‌گوید Full pytest و GitHub Actions برای آخرین revision هنوز تأیید نشده‌اند.
- نتیجه: مرحلهٔ ۱ از نظر تطبیق Git، وضعیت کاری و مرجع مستندات تثبیت شد؛ هیچ سرویس یا دیتابیسی تغییر نکرد.

### مرحله K: ممیزی پوشش AWG و تست کل فیلدهای canonical (2026-10-26)
- فایل مستند جدید docs/AWG-BACKUP-COVERAGE.md ماتریس پوشش را ثبت می‌کند: core_configs.type/config، اتصال Node/Core، users.proxy_settings، تنظیمات hosts/inbounds، wireguard_subnets، فایل‌های پنل و مواردی که بیرون از آرشیو Native قرار دارند.
- بازبینی کد ثابت کرد AWG Core و رکوردهای panel-side Node در دیتابیس پنل ذخیره می‌شوند و Node API key / server_ca در رکورد پنل قرار دارند؛ بنابراین آرشیو محرمانه محسوب می‌شود. بند مستندات معماری که این credentials را خارج از آرشیو می‌دانست اصلاح شد. runtime و secretهای local روی Node، /var/lib/pg-node، باینری‌ها/پکیج‌های میزبان و Nginx/TLS خارجی داخل آرشیو پنل نیستند.
- tests/test_core_persistence.py گسترش یافت تا از AWG_OBFUSCATION_FIELDS به‌عنوان منبع واحد و کل 16 فیلد (jc, jmin, jmax, s1-s4, h1-h4, i1-i5) استفاده کند؛ تست create/modify/reload همهٔ این فیلدها را بررسی می‌کند.
- در محیط کاملاً آزمایشی manubisguard-awg-roundtrip آرشیو تازه ساخته شد: /opt/manubisguard-work/awg-native-roundtrip-20261026/stage2-backups/backup_20261026193255.zip. restore --check پاس شد؛ سپس دیتابیس آزمایشی عمداً تغییر کرد و Restore واقعی با مقصد و کانتینر صریح اجرا شد.
- کوئری نهایی با ON_ERROR_STOP=1 همهٔ 16 فیلد lowercase را دقیقاً با مقادیر fixture مقایسه کرد؛ type=amneziawg و ارتباط nodes.id=88 به core_configs.id=77 درست بود و مقادیر دستکاری‌شده باقی نماند. نشانگرها: NATIVE_AWG_16_FIELD_ROUNDTRIP=PASS، NODE_CORE_RELATIONSHIP_ROUNDTRIP=PASS و DESTINATION_MUTATION_REMOVED=PASS.
- تست‌های tests/test_core_persistence.py، tests/test_amneziawg.py و tests/test_amneziawg_subscription_render.py: 16 passed in 12.28s؛ Ruff روی app/core/amneziawg.py و tests/test_core_persistence.py نیز PASS شد.
- کانتینر و شبکهٔ آزمایشی حذف شدند. snapshot پیش و پس از cleanup برای manubisguard-panel-manubisguard-1 و manubisguard-panel-timescaledb-1 یکسان بود: هر دو running/healthy با restart_count=0.
- محدودیت مهم: fixture یکپارچهٔ مرحله K فقط جدول‌های core_configs و nodes را مستقیماً در round-trip آزمایش کرد. پوشش users.proxy_settings، hosts/inbounds و wireguard_subnets از dump کامل دیتابیس استنباط می‌شود، اما هنوز با fixture روابط واقعی به‌صورت end-to-end آزموده نشده؛ این یک گیت تکمیلی پیش از ادعای پذیرش کامل AWG است.
- گام بعد: افزودن fixture چندجدولی برای peer/host/subnet و سپس ممیزی مسیرهای safety backup و rollback پیش از هرگونه فعال‌سازی Restore API تولید.
- لاگ خلاصه: /opt/manubisguard-work/awg-native-roundtrip-20261026/stage2-awg-coverage.log؛ لاگ‌های اجرای فرمان در همان پوشه با پیشوند stage2- موجودند.


### مرحله L: ممیزی ایمنی Restore Native (2026-10-26)
- ممیزی سورس Native نشان داد که PostgreSQL/TimescaleDB در مسیر multi-db پیش از import، هر دیتابیس مقصد را terminate/drop/recreate می‌کند؛ مسیر single TimescaleDB نیز مقصد را drop/recreate می‌کند و مسیر PostgreSQL عادی ممکن است با dump دارای clean/drop، اشیای قبلی را پیش از پایان import حذف کند.
- مسیر SQLite از snapshot پیش از جایگزینی استفاده می‌کند، اما معادل آن برای PostgreSQL/TimescaleDB در مسیر بررسی‌شده وجود ندارد. کپی‌های APP_DIR و DATA_DIR پیش از جایگزینی فایل‌ها گرفته می‌شوند، ولی پس از import دیتابیس؛ بنابراین از خود دیتابیس قبل از DROP محافظت نمی‌کنند. در مسیر خطا، کد فعلی سرویس اپلیکیشن را دوباره start می‌کند و rollback دیتابیس خودکار ندارد.
- یک قفل صریح سراسری برای جلوگیری از دو Restore هم‌زمان در تابع مرورشده پیدا نشد؛ باید پیش از فعال‌سازی production API بررسی/پیاده‌سازی شود.
- گزارش تفصیلی در docs/RESTORE-SAFETY-AUDIT.md نوشته شد: گیت‌های فعلی، شکاف‌های blocking و طراحی اصلاحی مرحلهٔ بعد را ثبت می‌کند.
- تصمیم ایمنی: API staging و production با HTTP 503 غیرفعال می‌مانند. این مرحله فقط audit و مستندسازی بود؛ هیچ عملیات Restore/Restart/Deploy تولیدی انجام نشد.
- گام بعدی عملی: پیاده‌سازی snapshot دیتابیس قبل از هر تغییر، checksum/manifest validation، rollback دیتابیس و فایل‌ها با عدم restart در صورت شکست rollback، و قفل Restore؛ سپس اجرای سناریوی موفق و fault-injection فقط در محیط آزمایشی.


### مرحله M: ادامهٔ ممیزی ایمنی Native Restore (2026-10-27)
- تأیید شد که Remote Desktop Commander به دستگاه توسعه متصل است؛ مسیر مخزن `/opt/manubisguard-panel` و شاخه `feature/amnezia-wg` است. HEAD همچنان `eede24d8cf9784a704c373f369788c273001553a` است و هیچ Commit یا Push جدیدی از این مرحله انجام نشده است.
- `git diff --check`، `python3 -m py_compile scripts/manubisguard-native-restore-safety.py` و `bash -n` روی اسکریپت‌های مربوط PASS شدند. تست‌های `tests/test_native_backup_adapter.sh` و `tests/test_native_backup_transform.sh` نیز PASS شدند.
- Safety patch روی یک کپی موقت از کتابخانهٔ pinned اعمال شد؛ `bash -n`، اجرای دوبارهٔ patch به‌صورت idempotent و بارگذاری توابع Native در ترتیب واقعی کتابخانه‌ها PASS شدند. SHA-256 کش upstream قبل و بعد یکسان ماند: `fe35e83ed69c007e36bfa598c6104b9737cd83d88e7f6c3b51311abde457cf3a`.
- دیتابیس harness آزمایشی به‌صورت فقط‌خواندنی بررسی شد؛ ردیف‌های fixture در `core_configs` و `nodes` دقیقاً با فایل مورد انتظار پیش از rollback برابر بودند (`TEST_DB_EXACT_PRE_RESTORE_ROW=PASS`). این فقط وضعیت فعلی را تأیید می‌کند و اثباتی دربارهٔ نتیجهٔ Restore قبلی نیست.
- لاگ Restore قبلی هنوز به prompt تأیید تعاملی ختم می‌شود؛ هیچ فرایند Restore فعالی پیدا نشد و هیچ تأیید تعاملی ارسال نشد. چهار safety snapshot در harness نگه داشته شدند؛ چیزی پاک‌سازی نشد.
- بررسی دوبارهٔ سرویس‌های تولید فقط خواندنی بود: `manubisguard-panel-manubisguard-1` و `manubisguard-panel-timescaledb-1` هر دو `running` و `RestartCount=0` بودند. هیچ Restore، Rollback، Restart، Deploy یا تغییر دیتابیس تولید انجام نشد.
- یک `git push origin feature/amnezia-wg` قدیمی با PID `362281` و فرایندهای فرزند `362286/362287` هنوز بیش از یک روز در حال اجراست. برای جلوگیری از نتیجهٔ نامشخص، آن را نکشتیم و Push موازی جدیدی شروع نکردیم؛ وضعیت remote باید پیش از هر Push بعدی دوباره تأیید شود.
- محدودیت تست: `pytest` در Python میزبان نصب نیست؛ بنابراین تست‌های Python/Ruff برای revision فعلی در این مرحله اجرا نشده‌اند. نتایج تاریخی 94/16 تست، جایگزین اجرای مجدد روی این تغییرات نیستند.
- گام بعد: بازبینی کامل نهایی helper و طراحی fault-injection فقط روی harness disposable؛ تکمیل پوشش خطاهای snapshot/rollback/قفل و ثبت نتایج. تا عبور گیت‌ها، APIهای Restore تولید و staging fail-closed باقی می‌مانند و هیچ Commit/Push انجام نمی‌شود.


### مرحله N: پذیرش متمرکز و آزمون‌های خطای snapshot (2026-10-27)
- برای بررسی مبنا، فایل‌های Restore/Backup مرجع از مخزن رسمی PasarGuard Scripts بررسی شدند؛ این کد از همان موتور pinned در `scripts/manubisguard-native-backup.sh` استفاده می‌کند. منبع رسمی: `https://github.com/PasarGuard/scripts`؛ مخزن برنامهٔ پنل: `https://github.com/PasarGuard/panel`.
- `tests/migration`, `tests/compatibility`, `tests/test_backup_restore_fail_closed.py`, `tests/test_native_backup_architecture.py` و `tests/api/test_backup_security.py` در کانتینر disposable با شبکهٔ غیرفعال و کپی writable از مخزن اجرا شدند: **108 passed**. اجرای متمرکز قبلی روی 9 فایل Restore نیز **43 passed** بود.
- آزمون fault-injection مستقل با Docker mock در `/tmp` (بدون اتصال به دیتابیس واقعی) موفق شد: snapshot، بررسی checksum، rollback مسیر چند-دیتابیسی، رد دستکاری checksum، رد globals ناقص و رد SQL dump ناقص همگی PASS شدند. هیچ Restore واقعی اجرا نشد.
- `ruff check --no-fix` روی دو فایل Python تغییرکرده PASS شد. بررسی کل مخزن 39 خطای lint نشان داد؛ اجرای همان بررسی روی `HEAD` دست‌نخورده نیز دقیقاً 39 خطا داد، پس خطاها از این تغییرات نیستند و عمداً فایل‌های نامرتبط اصلاح نشدند.
- تست‌های shell: `tests/test_native_backup_adapter.sh`, `tests/test_native_backup_transform.sh`, `bash -n`, `python3 -m py_compile`, `git diff --check` و اعمال دوبارهٔ patch روی bundle موقت pinned همگی PASS شدند. SHA-256 کش upstream تغییری نکرد.
- اجرای کامل تمام 88 فایل تست در کانتینر disposable شروع شد اما کامل نشد؛ اجرای نخست با mount فقط‌خواندنی به مسیر SQLite برخورد کرد و اجرای دوم پس از آغاز مهاجرت‌های تستی و رسیدن به حدود 8٪ متوقف شد. بنابراین ادعای PASS برای کل suite نداریم؛ پذیرش فعلی محدود به مجموعهٔ متمرکز 108 تست است.
- هنوز هیچ Commit/Push انجام نشده است. Push قدیمی PID `362281` و فرایندهای فرزندش هنوز باید جداگانه تعیین تکلیف شوند؛ برای جلوگیری از تداخل، نه متوقف شدند و نه Push موازی آغاز شد.
- کنترل نهایی تولید باید دوباره تأیید کند که کانتینرهای پنل و TimescaleDB زنده‌اند، `RestartCount=0` دارند و Restore فعالی اجرا نمی‌شود. هیچ اقدام تغییردهنده‌ای روی پنل زنده انجام نشد.

### مرحله O: بستن شکاف rollback در SQLite و پذیرش مجدد (2026-10-27)
- در بازبینی عمیق‌تر یک باگ واقعی در مسیر SQLite پیدا شد: موتور قبل از Restore از دیتابیس فعلی snapshot می‌گرفت، اما در صورت شکست کپی دیتابیس یا شکست مرحلهٔ بعدی فایل‌های برنامه، cleanup از آن snapshot برای rollback استفاده نمی‌کرد. بنابراین امکان باقی‌ماندن دیتابیس ناقص وجود داشت.
- safety patch به نسخهٔ V2 ارتقا یافت. پیش از جایگزینی فایل SQLite، شروع mutation علامت‌گذاری می‌شود؛ در مسیر خطا snapshot قبلی برگردانده و integrity آن بررسی می‌شود. اگر قبل از Restore دیتابیسی وجود نداشته، فایل مقصد ناقص حذف می‌شود. اگر snapshot نامعتبر باشد یا rollback تأیید نشود، `rollback_safe=false` باقی می‌ماند و سرویس‌های برنامه restart نمی‌شوند.
- تست‌های runtime جدید در `tests/test_native_restore_safety.py` اضافه شدند: rollback با snapshot معتبر، fail-closed با snapshot خراب، و بازگرداندن وضعیت «دیتابیس قبلاً وجود نداشت». هر سه PASS شدند.
- اجرای مجموعهٔ متمرکز با شبکهٔ خاموش و کپی writable در کانتینر disposable: **111 passed in 1.86s**؛ Ruff برای فایل‌های تغییرکرده: **All checks passed**.
- بررسی مستقل روی کپی موقت کتابخانهٔ upstream pinned: اعمال patch، اجرای مجدد idempotent، `bash -n` روی فایل Restore تولیدشده، `py_compile`، تست‌های shell adapter/transform و `git diff --check` همگی PASS شدند. کش upstream تولیدی تغییر نکرد.
- سه تست `tests/test_phase5_migration.py` در اجرای جداگانه fail شدند (2 passed, 1 skipped). همان سه شکست روی آرشیو تمیز `HEAD` فعلی نیز تکرار شد: تست‌ها انتظار دارند revision نهایی `awg2026091901` باشد، در حالی که زنجیرهٔ فعلی تا `20261025_host_admin_names` می‌رود. این شکست‌ها baseline هستند و به تغییرات Backup/Restore این مرحله مربوط نیستند؛ فایل‌های migration خارج از محدوده باقی ماندند.
- پذیرش فعلی Backup/Restore متمرکز است، نه Full pytest: کل suite هنوز PASS اعلام نمی‌شود. Native AWG round-trip و fault-injection مربوط به PostgreSQL/TimescaleDB از مراحل G/N همچنان شواهد معتبر قبلی‌اند؛ تغییر این مرحله در مسیر SQLite بود.
- هیچ Restore/rollback/restart/deploy روی تولید انجام نشد. هیچ Commit/Push جدیدی انجام نشده است. فایل `AI_HANDOFF_PROMPT_2026-10-25.md` همچنان خارج از stage/commit باقی می‌ماند.
- اجرای کامل suite یک‌بار دیگر در کانتینر disposable با کپی writable و شبکهٔ خاموش آغاز شد، اما در حدود 8٪ عمداً متوقف شد تا بار CPU طولانی روی همان میزبان سرویس عملیاتی ایجاد نکند. این اجرا نتیجهٔ PASS/FAIL برای کل suite محسوب نمی‌شود؛ لاگ ناقص در `/opt/manubisguard-work/backup-restore-final-validation/full-suite.log` نگه داشته شده است.

### مرحله P: مستقل‌کردن safety patch برای Restore بدون Checkout (2026-10-27)
- بازبینی مسیر نصب نشان داد Adapter در `/usr/local/bin` نصب می‌شود، اما helper امنیتی فقط از `/opt/manubisguard-panel/scripts` خوانده می‌شد. در بازیابی میزبان بدون Checkout، این وابستگی باعث fail-closed غیرضروری می‌شد.
- Adapter اکنون ابتدا helper داخل Checkout را ترجیح می‌دهد و اگر وجود نداشت از `/usr/local/lib/manubisguard-native/manubisguard-native-restore-safety.py` استفاده می‌کند. Installer نسخهٔ helper را با مالکیت root و مجوز `0644` در آن مسیر نصب می‌کند. این فقط تغییر کد محلی است؛ installer اجرا نشده و فایل‌های تولید دست‌نخورده‌اند.
- تست‌های `tests/test_native_backup_architecture.py` و `tests/test_native_restore_safety.py`: **8 passed in 0.57s**. تست‌های shell adapter و transform، `bash -n` و `py_compile` نیز پس از انتقال cache پایتون به `/tmp` PASS شدند. تست‌ها در کانتینر disposable با شبکهٔ خاموش، محدودیت یک CPU و حافظهٔ 512 MiB اجرا شدند.
- در این مرحله suite کامل اجرا نشد؛ هیچ Commit/Push، نصب یا Restore تولیدی انجام نشد.

### مرحله Q: تکمیل bootstrap مستقل Restore (2026-10-27)
- بازبینی مسیر `manubis install-script` نشان داد که این مسیر فقط CLI و Adapter را دانلود می‌کرد؛ بنابراین روی میزبان بدون Checkout، helper امنیتی fallback نصب نمی‌شد و Restore به‌درستی fail-closed می‌شد.
- `manubis install-script` اکنون helper را نیز دانلود می‌کند، قبل از نصب syntax/compile آن را بررسی می‌کند و در `/usr/local/lib/manubisguard-native/manubisguard-native-restore-safety.py` با مالکیت root و مجوز `0644` نصب می‌کند. Adapter همان مسیر را به‌عنوان fallback استفاده می‌کند. Installer و install-script روی میزبان واقعی اجرا نشده‌اند.
- `tests/test_native_backup_architecture.py` اکنون این مسیر bootstrap را بررسی می‌کند؛ نتیجهٔ آزمون‌های معماری و SQLite: **8 passed in 0.76s**. پس از همگام‌سازی فایل‌های تستی لازم در کپی disposable، `tests/test_native_backup_adapter.sh` و `tests/test_native_backup_transform.sh` هر دو PASS شدند. `bash -n` و `git diff --check` نیز PASS شدند.
- اجرای تست‌های دارای import گستردهٔ اپلیکیشن/مهاجرت در همین میزبان حتی با یک CPU و سقف حافظه، پیش از خروجی تست CPU را پیوسته مصرف کرد؛ برای جلوگیری از فشار بیشتر، اجراهای timeout شدند. بنابراین این مرحله به‌عنوان پذیرش متمرکز ثبت می‌شود، نه Full suite.
- محدودهٔ کاری عمداً روی PostgreSQL/TimescaleDB و SQLite باقی ماند؛ MySQL/MariaDB خارج از محدوده است. هیچ Restore، Restart، Deploy، تغییر دیتابیس، Commit یا Push تولیدی انجام نشد.


## Stage R — Restore official PasarGuard operational paths (2026-10-27)

- Updated source defaults for fresh installs to `/opt/pasarguard`, `/var/lib/pasarguard`, and `/opt/pasarguard/backup/`; PostgreSQL/TimescaleDB volume and SQLite/certificate/backup API defaults now use the official data root.
- Made `pasarguard` the canonical CLI name and kept `manubis` as a compatibility wrapper/symlink for older invocations. Native backup helper/cache paths now use `/usr/local/lib/pasarguard-scripts/`; the pinned upstream library and archive layout remain unchanged.
- Updated Compose service/project and default PostgreSQL database/user names to `pasarguard`. The custom fork image/repository identifiers are intentionally unchanged because changing them before publishing a matching feature-complete image/source would silently select incompatible code.
- This is source-only. No live panel, container, volume, database, node, or installed path was moved or modified. Existing installations using legacy paths require a separately planned migration before deploying these changes; do not run the installer as an in-place path migration.
- Focused isolated checks: `tests/test_pasarguard_install_script_bootstrap.sh` PASS using mocked `curl`/`install`/`ln` with all install targets redirected to a temporary root; native adapter static checks PASS; backup compatibility fixture PASS; architecture + SQLite rollback tests PASS (9 passed); Ruff and Python compilation PASS. Full suite not run.


## Stage S — Restore the official PasarGuard CLI/bootstrap architecture (2026-10-27)

- Rebased the canonical `pasarguard` script on the official `PasarGuard/scripts` CLI and shared-library layout under `lib/`; service-management commands now use the upstream implementation rather than the small legacy wrapper.
- Routed `install` and `update` through the fork-aware `install-pasarguard.sh`, preserving the custom AmneziaWG source/image build and existing update safety checks. `install-manubisguard.sh` remains a compatibility wrapper only.
- `install-script` now stages and validates the canonical CLI, all seven official shared libraries, the fork backup adapter, migration helper, and restore-safety helper before installing canonical `/usr/local/bin/pasarguard` plus legacy aliases.
- Kept custom native `backup`, `backup-service`, `restore`, `backup-db`, and `migrate` routing so the existing backup/restore safety behavior remains in force.
- Isolated checks PASS: CLI help smoke test, mocked CLI/shared-library bootstrap, native adapter static checks, backup compatibility fixture, and focused architecture/SQLite rollback tests (9 passed).
- Production services and paths remain untouched; no installer was executed on the host, no live containers or databases were changed, and no commit/push was made.


### مرحله T: اصلاح مسیر credential در rollback دیتابیس (2026-10-27)
- بازبینی مسیر rollback PostgreSQL/TimescaleDB نشان داد که `manubisguard_rollback_restore_database_safety` نام کاربری/رمز restore را دوباره به‌عنوان credential مدیریتی به `pg_restore_all_user_databases` می‌داد. در نصب‌هایی که این دو credential متفاوت‌اند، عملیات مدیریتی مانند DROP/CREATE دیتابیس یا بازگرداندن globals ممکن است با مجوز ناکافی شکست بخورد.
- helper اکنون credential مربوط به restore و credential مدیریتی را جداگانه می‌گیرد و فراخوانی cleanup نیز `admin_user/admin_password` را به‌طور مستقل عبور می‌دهد. گیت idempotency نیز بررسی می‌کند که نسخهٔ patch‌شده واقعاً این مسیر جدید را دارد؛ marker قدیمی نباید بی‌صدا به‌عنوان patch کامل پذیرفته شود.
- تست رگرسیون جدید `test_postgres_rollback_forwards_distinct_admin_credentials` یک snapshot با manifest/checksum معتبر می‌سازد، تابع rollback را با دو مجموعه credential متفاوت اجرا می‌کند و آرگومان‌های دقیق ارسال‌شده به موتور Restore را بررسی می‌کند. اجرای دوبارهٔ patch نیز idempotent تأیید شد.
- آزمون‌های ایزوله پس از تغییر: `tests/test_native_restore_safety.py` و `tests/test_native_backup_architecture.py`: **11 passed**؛ Ruff برای فایل‌های تغییرکرده PASS؛ `tests/test_native_backup_adapter.sh` و `tests/test_native_backup_transform.sh` هر دو PASS؛ `bash -n`، `py_compile` و `git diff --check` نیز PASS.
- کنترل فقط‌خواندنی روی دیتابیس disposable موجود نشان داد ردیف Core/Node با فایل مورد انتظار `stage3-expected-pre-rollback-row.txt` دقیقاً برابر است و هیچ فرایند Restore فعالی وجود ندارد. این فقط وضعیت فعلی را تثبیت می‌کند؛ به‌تنهایی اثبات نمی‌کند که تلاش fault-injection قبلی با موفقیت rollback شده است.
- تلاش اول برای PostgreSQL rollback E2E با probe نامناسب متوقف شد؛ این تلاش Restore را اجرا نکرد و به‌عنوان PASS ثبت نشد. در مرحلهٔ بعد harness اصلاح شد و آزمون واقعی helper در کانتینر disposable انجام شد؛ نتیجهٔ نهایی در مرحلهٔ U ثبت شده است.
- تا پیش از مرحلهٔ U، fixture چندجدولی AWG هنوز وجود نداشت. APIهای Restore در تمام مدت fail-closed ماندند.
- هیچ Restore/Restart/Deploy یا تغییر دیتابیس تولید، Commit یا Push انجام نشد. فایل `AI_HANDOFF_PROMPT_2026-10-25.md` همچنان خارج از stage/commit است.

### مرحله U: آزمون واقعی rollback دیتابیس و fixture کامل‌تر AWG (2026-10-27)
- پس از بررسی اینکه کانتینر `manubisguard-awg-roundtrip-timescaledb-1` واقعاً محیط آزمایشی جداگانه با TimescaleDB 16 است، یک دیتابیس آزمایشی با 33 جدول ORM ساخته شد؛ هیچ مهاجرتی روی دیتابیس تولید اجرا نشد.
- fixture دارای 11 ردیف مرتبط بود: Admin/Role، User و `proxy_settings` با 16 کلید AWG و peer IP، Host با `wireguard_overrides` و `inbound_tag`، Inbound، Group و هر دو association، CoreConfig، Node با `core_config_id/core_config_ids` و WireGuardSubnet با `next_offset/free_offsets`.
- از کل دیتابیس `pg_dump`، `globals.sql`، manifest و SHA-256 snapshot گرفته و قبل از Restore اعتبارسنجی شد. سپس peer IP، host/inbound، نوع و config هسته، Node/Core assignment، allocator subnet و هر دو association تغییر کردند؛ جدول و group آزمایشی اضافی نیز ساخته شدند.
- `manubisguard_rollback_restore_database_safety` با credentialهای جداگانهٔ Restore و admin اجرا شد. تلاش اولیه با کاربر محدود به دلیل نداشتن مجوز schema رد شد و fallback مدیریتی به‌درستی dump را بازگرداند. مقایسهٔ JSON تمام 11 ردیف با baseline قبل از تغییر **تطابق کامل** داشت؛ جدول partial و group اضافه پس از rollback وجود نداشتند.
- نتیجه‌ها: `POSTGRES_ROLLBACK_DISTINCT_CREDENTIALS_E2E=PASS`، `AWG_LINKED_ROUNDTRIP=PASS`، `USER_PROXY_SETTINGS_EXACT=PASS`، `HOST_INBOUND_AND_WIREGUARD_OVERRIDES_EXACT=PASS`، `INBOUND_GROUP_AND_USER_GROUP_LINKS_EXACT=PASS`، `CORE_AWG_FIELDS_AND_NODE_CORE_ASSIGNMENT_EXACT=PASS`، `WIREGUARD_SUBNET_ALLOCATOR_EXACT=PASS`.
- شواهد محلی در `/opt/manubisguard-work/backup-restore-final-validation/awg-linked-roundtrip.PyZqqw/`، baseline در `awg-linked-expected-before.txt` و خروجی نهایی در `awg-linked-actual-after.txt` نگه‌داری شده است.
- این آزمون helper واقعی rollback دیتابیس را پوشش می‌دهد؛ اجرای کامل native archive/CLI round-trip برای همین fixture همچنان باقی است. Restore API همچنان fail-closed است. محیط تولید، Commit و Push دست‌نخورده‌اند.

### مرحله V: رفع مسیر نامعتبر قفل/snapshot و fault-injection در `restore_command` (2026-10-27)
- در حین اجرای مرحلهٔ U، بازبینی مسیرهای safety نشان داد که lock و snapshot به‌طور پیش‌فرض زیر `BACKUP_DIR` ساخته می‌شدند، درحالی‌که مسیر رسمی `/opt/pasarguard/backup/` داخل `APP_DIR` است و helper عمداً مسیرهای داخل `APP_DIR`/`DATA_DIR` را رد می‌کند. این باعث می‌شد Restore پیش از تغییر دیتابیس fail-closed شود.
- هر دو مسیر اکنون از `${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}` استفاده می‌کنند؛ مسیر پیش‌فرض خارج از `APP_DIR` و `DATA_DIR` است و می‌توان آن را در محیط‌های آزمایشی override کرد. گیت idempotency نیز نسخهٔ patch‌شدهٔ قدیمی با مسیرهای نامعتبر را کامل نمی‌پذیرد.
- اجرای fault-injection واقعی روی `restore_command --file ... --yes` در کانتینر PostgreSQL 16 کاملاً disposable: ابتدا safety snapshot و lock بیرونی ساخته شدند؛ wrapper آزمایشی import اول را پس از تغییر مقدار ردیف و ساخت جدول partial عمداً fail کرد؛ cleanup مسیر واقعی `manubisguard_rollback_restore_database_safety` را اجرا کرد؛ log شامل `DATABASE_ROLLBACK=PASS` شد؛ مقدار اصلی `fixture(id=1,value='before')` برگشت و جدول injected وجود نداشت. خروج کد 1 مورد انتظار بود، چون import عمداً شکست داده شد.
- نشانگرها: `RESTORE_COMMAND_FAULT_INJECTION=PASS`، `DATABASE_ROLLBACK_MARKER=PASS`، `EXTERNAL_SAFETY_SNAPSHOT=PASS`، `RESTORE_LOCK_OUTSIDE_APP_AND_DATA=PASS`. شواهد در `/opt/manubisguard-work/backup-restore-final-validation/restore-command-e2e.9IJh34/`.
- پس از اصلاح مسیر: Ruff PASS؛ `tests/test_native_restore_safety.py` و `tests/test_native_backup_architecture.py`: **11 passed**؛ shell adapter، compatibility transform، installer update gate/preflight، CLI bootstrap، `py_compile`، `bash -n` و `git diff --check` همگی PASS.
- کانتینر PostgreSQL موقت بعد از تست حذف شد؛ دیتابیس‌های آزمایشی موقت پاک شدند. هیچ سرویس یا دیتابیس تولیدی لمس نشد.
