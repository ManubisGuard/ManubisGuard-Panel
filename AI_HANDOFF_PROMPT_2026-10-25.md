# MANUBISGUARD PANEL — AI CONTINUATION HANDOFF
**تاریخ ثبت:** 2026-10-25
**هدف:** تحویل وضعیت واقعی پروژه به هوش مصنوعی بعدی؛ ادامه از آخرین باگ تأییدشده، بدون تکرار کارهای انجام‌شده یا از دست‌دادن تغییرات.

## 1) دستور اصلی به هوش مصنوعی بعدی

تو مهندس ارشد نرم‌افزار و مسئول ادامه پروژه موجود هستی. باید ابتدا وضعیت واقعی سرور، Git، کد، تست‌ها و گزارش‌ها را بررسی کنی؛ سپس از آخرین باگ شرح‌داده‌شده در این سند ادامه بدهی. گزارش‌های قدیمی را حقیقت قطعی فرض نکن؛ با کد و شواهد فعلی تطبیق بده.

**قواعد غیرقابل‌مذاکره**
- پیش از هر تغییری، دستگاه، مسیر پروژه، branch، commit، وضعیت working tree، سرویس‌ها و فایل‌های گزارش را تأیید کن.
- هرگز از `git reset --hard`، `git clean`، حذف گسترده فایل‌ها یا revert کلی استفاده نکن. هیچ تغییر موجودی را بدون بررسی و تأیید حذف یا بازنویسی نکن.
- تغییرات متعدد و هنوز commit نشده وجود دارند. آن‌ها متعلق به کار جاری‌اند و باید حفظ شوند؛ حتی اگر بعضی بخش‌ها به موضوع باگ فعلی مربوط نباشند.
- فایل‌های گزارش را بخوان و با کد تطبیق بده؛ قابلیت‌های تکمیل‌شده را دوباره نساز.
- قبل از تغییر بک‌اند/فرانت‌اند، مسیرهای مرتبط، تست‌ها، مدل‌های داده و الگوی مجوزدهی موجود را دنبال کن. برای `Own` معنای جدید اختراع نکن؛ معنای واقعی آن را از پیاده‌سازی فعلی استخراج کن.
- اول تست و بازبینی؛ استقرار فقط بعد از پشتیبان‌گیری قابل‌تأیید و ارزیابی ریسک. اگر استقرار لازم شد، تا وقتی دلیل فنی وجود ندارد دیتابیس را recreate نکن.
- commit و push هنوز انجام نشده‌اند. هیچ‌وقت force-push نکن و به branch اصلی منتقل نکن. فقط بعد از بازبینی کل تغییرات و موفقیت تست‌ها درباره commit/push تصمیم بگیر و SHA را در گزارش ثبت کن.
- هیچ موفقیت، تست، backup، deploy یا رفع باگی را بدون اجرای واقعی و خروجی قابل‌بررسی ادعا نکن.

## 2) اتصال و مسیرهای اصلی

- **دستگاه Remote Desktop Commander:** display ID `8017638839-32c511`
- **deviceId:** `889bb61a-a98c-4c4b-8b1b-8fea06f7f10b`
- **مسیر مخزن:** `/opt/manubisguard-panel`
- **Branch مشاهده‌شده:** `feature/amnezia-wg`
- **HEAD مشاهده‌شده:** `4fb41c5c80deecc7491dd327564f099f0ad1884f`
- **عنوان آخرین commit:** `docs: point installer instructions to updated feature branch` (checkout در گزارش قبلی به‌صورت grafted توصیف شده بود؛ مجدداً بررسی کن)
- **Remote مورد انتظار:** `origin/feature/amnezia-wg`
- **Production container گزارش‌شده:** `manubisguard-panel-manubisguard-1`
- **Database container گزارش‌شده:** `manubisguard-panel-timescaledb-1`
- **Production image گزارش‌شده:** `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg`

این مشخصات از آخرین بررسی ثبت‌شده‌اند، نه تضمین وضعیت فعلی؛ در شروع کار مجدداً تأییدشان کن.

## 3) فایل‌های کلیدی روی سرور — حتماً بخوان

1. `/opt/manubisguard-panel/TODO.md`
   گزارش اصلی و append-only پروژه. بخش انتهایی با عنوان
   `CONTINUATION HANDOFF — 2026-10-25 — PERSONAL HOST NAME + ADMIN ROLE HOST SCOPE BUG`
   شامل خلاصه تغییرات، باگ، وضعیت کار و پرامپت ادامه است. این فایل اکنون شامل handoff قبلی نیز هست.
2. `/opt/manubisguard-panel/TODO_UI_REDESIGN_MASTER.md`
   گزارش جزئی بازطراحی UI، تصمیم‌ها، محدوده تغییرات و موارد باقی‌مانده.
3. `/opt/manubisguard-panel/app/db/migrations/versions/20261025_host_admin_names.py`
   migration اضافه‌شده برای نام شخصی Host مدیر.
4. `/opt/manubisguard-panel/tests/test_network_connection_stats.py`
   تست جدید مربوط به آمار/هوش شبکه؛ وضعیت و پوشش آن را بررسی کن.
5. `/opt/manubisguard-panel/app/operation/permissions.py`
   پیاده‌سازی مجوزها، scope و enforcement را بررسی کن.
6. `/opt/manubisguard-panel/app/models/admin_role.py`
   مدل مجوزهای نقش مدیر؛ شامل تغییر مرتبط با `hosts.personal_name`.
7. `/opt/manubisguard-panel/app/routers/host.py`
   endpoint فهرست Host، endpoint نام شخصی و دیگر عملیات Host.
8. `/opt/manubisguard-panel/app/db/models.py`
   مدل `HostAdminName` و روابط/قیود آن.
9. `/opt/manubisguard-panel/app/models/host.py`
   مدل پاسخ Host و فیلد `personal_remark`.
10. `/opt/manubisguard-panel/dashboard/src/features/admin-roles/forms/admin-role-form.ts`
    تعریف کنترل‌های permission و scope در فرم نقش مدیر.
11. `/opt/manubisguard-panel/dashboard/src/features/admin-roles/components/permission-editor.tsx`
    رندر و رفتار UI مربوط به permission/scope؛ وجود و منطق واقعی فایل را با `find`/جست‌وجوی مخزن تأیید کن، اگر مسیر تغییر کرده بود.
12. `/opt/manubisguard-panel/dashboard/src/pages/_dashboard.hosts.tsx`
    صفحه Hosts و منطق دسترسی/نمایش آن.
13. `/opt/manubisguard-panel/dashboard/src/features/hosts/components/host-actions-menu.tsx`
    اکشن ویرایش نام شخصی Host.
14. `/opt/manubisguard-panel/dashboard/src/features/hosts/components/sortable-host.tsx`
    اصلاح نمایش نام شخصی در Grid.
15. `/opt/manubisguard-panel/dashboard/src/service/api/index.ts`
    API client مربوط به endpointها.
16. `/opt/manubisguard-panel/app/subscription/share.py`
    منطق اعمال نام شخصی در خروجی subscription؛ بررسی کن که مدل/کش سراسری Host mutate نشود.
17. فایل‌های ترجمه:
    - `/opt/manubisguard-panel/dashboard/public/statics/locales/en.json`
    - `/opt/manubisguard-panel/dashboard/public/statics/locales/fa.json`
    - `/opt/manubisguard-panel/dashboard/public/statics/locales/ru.json`
    - `/opt/manubisguard-panel/dashboard/public/statics/locales/zh.json`

اگر فایل یا مسیر بالا وجود نداشت، جست‌وجوی read-only انجام بده و مسیر واقعی را در گزارش ثبت کن؛ فایل جایگزین را حدس نزن.

## 4) وضعیت Git مشاهده‌شده در آخرین بررسی

آخرین فرمان `git status --short --branch` نشان داده:
`## feature/amnezia-wg...origin/feature/amnezia-wg`

فایل‌های تغییرکرده (tracked):
- `TODO.md`
- `app/db/crud/host.py`
- `app/db/models.py`
- `app/models/admin_role.py`
- `app/models/host.py`
- `app/models/system.py`
- `app/routers/host.py`
- `app/routers/system.py`
- `app/subscription/share.py`
- `app/utils/system.py`
- `dashboard/public/statics/locales/en.json`
- `dashboard/public/statics/locales/fa.json`
- `dashboard/public/statics/locales/ru.json`
- `dashboard/public/statics/locales/zh.json`
- `dashboard/src/components/layout/manubis-topbar.tsx`
- `dashboard/src/components/layout/sidebar.tsx`
- `dashboard/src/features/admin-roles/forms/admin-role-form.ts`
- `dashboard/src/features/dashboard/components/admin-statistics-card.tsx`
- `dashboard/src/features/dashboard/components/dashboard-overview.tsx`
- `dashboard/src/features/dashboard/components/users-statistics-card.tsx`
- `dashboard/src/features/dashboard/components/workers-health-card.tsx`
- `dashboard/src/features/hosts/components/host-actions-menu.tsx`
- `dashboard/src/features/hosts/components/hosts-list.tsx`
- `dashboard/src/features/hosts/components/sortable-host.tsx`
- `dashboard/src/features/hosts/components/use-hosts-list-columns.tsx`
- `dashboard/src/features/statistics/components/statistics-charts.tsx`
- `dashboard/src/features/statistics/components/system-statistics-section.tsx`
- `dashboard/src/features/users/components/data-table.tsx`
- `dashboard/src/features/users/components/filters.tsx`
- `dashboard/src/features/users/components/users-statistics.tsx`
- `dashboard/src/features/users/components/users-table.tsx`
- `dashboard/src/index.css`
- `dashboard/src/lib/theme-color.ts`
- `dashboard/src/locales/i18n.ts`
- `dashboard/src/pages/_dashboard._index.tsx`
- `dashboard/src/pages/_dashboard.hosts.tsx`
- `dashboard/src/pages/_dashboard.statistics.tsx`
- `dashboard/src/pages/_dashboard.users.tsx`
- `dashboard/src/service/api/index.ts`

فایل‌های untracked:
- `TODO_UI_REDESIGN_MASTER.md`
- `app/db/migrations/versions/20261025_host_admin_names.py`
- `dashboard/src/features/statistics/components/live-network-intelligence.tsx`
- `tests/test_network_connection_stats.py`

این فهرست snapshot قبلی است؛ قبل از تغییر حتماً دوباره وضعیت واقعی را بخوان. طبق آخرین ثبت، هیچ commit/push نهایی برای این مجموعه تغییرات انجام نشده بود. هیچ‌کدام از تغییرات موجود را بی‌اجازه پاک یا reset نکن.

## 5) آخرین باگ موردنیاز — از همین‌جا ادامه بده

### شرح مشکل کاربر
در Admin Role هنگام ساخت/ویرایش نقش مدیر، مجوزهای Hosts قابل انتخاب‌اند. قابلیت جدید `hosts.personal_name` برای تغییر نام شخصی Host اضافه شده، اما:
- اگر فقط مجوز نام شخصی Host را فعال کنیم، تب Hosts برای مدیر نمایش داده نمی‌شود.
- برای ظاهرشدن تب، مجبور می‌شویم مجوز عمومی مشاهده Host را هم فعال کنیم.
- با فعال‌کردن مجوز عمومی، مدیر می‌تواند همه Hostها را ببیند؛ این بیش از سطح دسترسی موردنیاز است.
- کنترل/منوی انتخاب scope به شکل `None / Own / All` که برای منابع scoped دیگر انتظار می‌رود، در بخش Hosts غایب یا به‌درستی متصل نیست.
- کاربر صریحاً رفع باگ در خود کد را می‌خواهد، نه mockup یا تصویر.

### رفتار مورد انتظار
- دسترسی و نمایش تب Hosts نباید به‌شکل نادرست به مجوز عمومی `hosts.read` وابسته باشد، اگر نقش فقط مجوز مستقلی دارد که برای نام شخصی لازم است. دقیقاً مشخص کن کدام داده‌ها و اکشن‌ها برای UI ضروری‌اند و هیچ اطلاعاتی را با دورزدن مجوز به کاربر نشان نده.
- scope برای Hosts باید طبق قرارداد واقعی پروژه و با کنترل UI متناظر قابل تنظیم شود؛ اگر معماری مجوزها `None / Own / All` را پشتیبانی می‌کند، مسیر Hosts را درست و کامل به آن متصل کن.
- مجوز `hosts.personal_name` باید مستقل و محدود بماند؛ فعال‌کردنش نباید به‌طور ضمنی مجوز عمومی مشاهده، ایجاد، ویرایش، حذف یا سایر عملیات Host را اعطا کند.
- enforcement سمت سرور اجباری است. پنهان‌کردن تب یا کنترل در فرانت‌اند به‌تنهایی راه‌حل نیست.
- شخصی‌سازی نام Host باید برای همان مدیر محدود باشد و نام canonical/global Host یا subscription/cache مشترک را تغییر ندهد.
- بررسی کن آیا `GET /api/hosts` فقط به `hosts.read` تکیه می‌کند و آیا فهرست/جزئیات/عملیات با scope فیلتر و enforce می‌شوند. همه endpointهای Host را audit کن، نه فقط یک route.
- `ProxyHost` در بررسی قبلی ظاهراً فیلد مالکیت creator نداشت. بدون مدرک، فیلد مالکیت یا معنی جدیدی برای `Own` اختراع نکن. از مدل scope موجود و semantics سایر منابع پیروی کن؛ اگر معنای `Own` برای Host مشخص نیست، قبل از تغییر پرخطر آن را مستند کن و مسئله را شفاف گزارش بده.

### نقاط شروع در کد
- `app/routers/host.py`: فهرست Host طبق بررسی قبلی از `require_permission("hosts", "read")` استفاده می‌کرد؛ endpoint نام شخصی از `require_permission("hosts", "personal_name")` استفاده می‌کرد. دوباره بررسی کن.
- `app/operation/permissions.py`: کلاس/enum `PermissionScope`، توابع `_resolve_scope`, `enforce_permission`, `enforce_scope`, `is_scope_all`, `get_scope_admin_id` (نام‌ها را در کد فعلی تأیید کن). بررسی قبلی نشان می‌داد enforcement عمدتاً برای Users پیاده شده بود.
- `dashboard/src/features/admin-roles/forms/admin-role-form.ts`: گروه Hosts و تنظیم `scoped` برای `hosts.read` را بررسی کن.
- `dashboard/src/features/admin-roles/components/permission-editor.tsx`: ببین scope selector به چه شرطی render می‌شود و داده فرم را چگونه serialize می‌کند.
- جست‌وجو کن تا همه مصرف‌کنندگان `hosts.read`, `hosts.personal_name` و scope را پیدا کنی؛ فقط به این فهرست محدود نشو.

## 6) تغییرات قبلی که باید حفظ و بررسی شوند

### A. نام شخصی Host
- مدل `HostAdminName` در `app/db/models.py` با فیلدهای گزارش‌شده `admin_id`, `host_id`, `remark` و قید یکتایی `(admin_id, host_id)`.
- migration: `app/db/migrations/versions/20261025_host_admin_names.py`.
- `HostsPermissions` در `app/models/admin_role.py` دارای `personal_name: RoleActionValue | None = None`.
- `app/models/host.py` فیلد `personal_remark`.
- `app/routers/host.py` endpoint نام شخصی که قبلاً گزارش شده `PUT /api/host/{host_id}/personal-name`.
- `app/db/crud/host.py` ظاهراً `personal_remark` را از فیلدهای canonical ذخیره‌شونده کنار می‌گذارد.
- `app/subscription/share.py` نام شخصی را بر اساس admin/subscriber روی کپی مدل اعمال می‌کند تا Host/کش سراسری mutate نشود.
تمام موارد بالا را با کد واقعی و migration/DB موجود تأیید کن؛ این توضیحات صرفاً مبنای شروع‌اند.

### B. UI redesign و سایر کارها
تغییرات گسترده‌ای در layout و صفحات Dashboard، Hosts، Users و Statistics، تم/CSS، localization و live network intelligence وجود دارد. کاربر می‌خواهد این کارهای قبلی حفظ شوند. جزئیات را از `TODO_UI_REDESIGN_MASTER.md` و `TODO.md` بخوان. در این مرحله هدف اصلی رفع باگ scope/permissions است، نه بازطراحی مجدد کل UI. از تداخل ناخواسته با کارهای UI پرهیز کن.

### C. Grid نام Host
در `dashboard/src/features/hosts/components/sortable-host.tsx` اصلاحی گزارش شده که از `host.personal_remark || host.remark || ''` استفاده می‌کند. بررسی کن و regression آن را حفظ کن.

### D. Network intelligence
فایل جدید `dashboard/src/features/statistics/components/live-network-intelligence.tsx` و تست `tests/test_network_connection_stats.py` در working tree هستند. محتوا، تست و integration آن‌ها را بررسی کن و بدون دلیل حذف نکن.

## 7) بکاپ و وضعیت Deploy قبلی — فقط بعد از راستی‌آزمایی استفاده کن

موارد زیر در handoff قبلی گزارش شده‌اند؛ قبل از هر deploy، وجود و صحت‌شان را بررسی کن:
- DB backup: `/opt/backups/manubisguard-pre-host-personal-name-20261025.dump`
- rollback image tag: `manubisguard-panel:rollback-before-host-personal-name-20261025`
- image tag دیگر: `manubisguard-panel:personal-name-grid-fix-20261025`
- production image: `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg`
- گزارش قبلی می‌گفت container پس از Grid fix سالم بوده و `/health` پاسخ HTTP 200 داده؛ این وضعیت فعلی را ثابت نمی‌کند.
- E2E واقعی مرورگر در گزارش قبلی انجام نشده بود.

قبل از deploy، بکاپ تازه و قابل‌بررسی بگیر، image فعلی و compose/config را ثبت کن، rollback plan مشخص داشته باش. اگر deploy انجام شد، فقط سرویس لازم را recreate کن؛ DB را بی‌دلیل دست‌کاری نکن. سپس container health، endpoint health، logs و رفتار واقعی permissionها را تأیید کن.

## 8) برنامه اجرایی پیشنهادی

1. تأیید device ID و مسیر `/opt/manubisguard-panel`.
2. اجرای `git status --short --branch`, `git rev-parse HEAD`, `git log -1 --oneline`, بررسی remote و diffstat؛ هیچ فایل را تغییر نده.
3. خواندن بخش handoff انتهای `TODO.md` و `TODO_UI_REDESIGN_MASTER.md`.
4. ترسیم مدل واقعی permission/scope و مقایسه با حداقل یک منبع دیگر که scope آن درست کار می‌کند (مثلاً Users). مسیر ذخیره/خواندن role در API و UI را کامل دنبال کن.
5. فهرست‌کردن همه Host endpoints و دسته‌بندی آن‌ها: list/read, personal-name, create/update/delete, other actions. برای هرکدام permission و scope واقعی را ثبت کن.
6. پیاده‌سازی کمینه و امن برای اتصال Hosts به scope و رفع coupling اشتباه تب Hosts؛ تغییرات مستقل را از بازطراحی UI جدا نگه دار.
7. افزودن regression tests برای:
   - نقش بدون permission لازم: دسترسی رد شود.
   - نقش دارای فقط `hosts.personal_name`: هیچ مجوز عمومی Host به‌طور ضمنی نگیرد.
   - عدم افشای همه Hostها در حالت scope محدود.
   - scopeهای `None / Own / All` مطابق semantics واقعی پروژه.
   - عدم اجازه تغییر نام Host متعلق به خارج از scope، اگر مدل scope و مالکیت موجود چنین مفهومی را تعریف می‌کند.
   - عدم تغییر canonical host name و shared subscription/cache هنگام تغییر نام شخصی.
   - serialization و persistence مجوز/scope در API نقش مدیر و UI.
8. اجرای تست‌های backend هدفمند، تست‌های جدید و تست‌های مرتبط موجود؛ اجرای lint/typecheck/build فرانت‌اند طبق scripts واقعی `package.json`. قبل از ادعای موفقیت، خروجی exit code را بخوان.
9. `git diff --check` و بازبینی کامل diff، migration، localization، secret/config artifacts و status.
10. به‌روزرسانی `TODO.md` با یافته‌ها، فایل‌های تغییرکرده، تست‌های واقعی و موارد باقی‌مانده.
11. فقط پس از تأیید تست و مجوز کاربر/رویه پروژه درباره deploy، commit و push اقدام کن. قبل از commit کل تغییرات قبلی را بررسی کن تا کارهای unrelated اما عمدی تصادفاً از دست نروند. هیچ force-push انجام نده.

## 9) حداقل معیار پذیرش

- تب/صفحه Hosts با مجوزهای درست و بدون اعطای دسترسی بیش‌ازحد رفتار می‌کند.
- scope selector در Admin Role برای Hosts طبق مدل واقعی پروژه نمایش داده و ذخیره می‌شود.
- backend تمام endpointهای مربوط را مستقل از UI enforce می‌کند.
- `hosts.personal_name` به‌تنهایی هیچ مجوز عمومی دیگری را اعطا نمی‌کند.
- نام شخصی admin از canonical Host name و داده‌های مدیران دیگر جدا است.
- regression tests پاس می‌شوند؛ build/lint/typecheck مرتبط پاس می‌شوند یا شکست‌های موجود با شواهد مستند می‌شوند.
- تمام تغییرات قبلی، شامل UI redesign و network intelligence، حفظ شده‌اند.
- `TODO.md` حاوی وضعیت نهایی، تست‌ها، deploy/backup، commit SHA و موارد باقی‌مانده است.
- هیچ ادعای بی‌مدرک درباره تکمیل، تست، deploy یا push وجود ندارد.

## 10) دستور شروع برای هوش مصنوعی بعدی

ابتدا فقط بررسی read-only انجام بده و نتیجه را خلاصه کن: هویت دستگاه، مسیر پروژه، branch/HEAD، Git status، وجود گزارش‌ها و وضعیت container/image/health. سپس گزارش‌ها و کد مجوزها را بخوان و یک تحلیل علت ریشه‌ای مبتنی بر فایل/خط ارائه کن. پس از آن با حفظ تمام تغییرات فعلی، باگ Hosts scope و personal-name را برطرف کن، تست اضافه کن و نتایج واقعی را ثبت کن. از ابتدا پروژه را نساز، بازطراحی قبلی را تکرار نکن، تغییرات را reset نکن و تا پیش از تکمیل تست/بازبینی deploy یا commit/push نکن.
