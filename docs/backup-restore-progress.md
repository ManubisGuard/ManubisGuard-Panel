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
