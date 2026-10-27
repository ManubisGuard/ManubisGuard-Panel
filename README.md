<!-- PasarGuard Pro project README -->

<p align="center">
  <img src="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/dashboard/public/statics/favicon/logo.png" alt="PasarGuard Pro logo" width="180">
</p>

<h1 align="center">PasarGuard Pro</h1>

<p align="center">
  <strong>A modern, self-hosted control plane for network infrastructure.</strong><br>
  Manage users, nodes, cores, subscriptions, domains, TLS, and system operations from one place.
</p>

<p align="center">
  <a href="#english">English</a> · <a href="#فارسی">فارسی</a>
</p>

<p align="center">
  <a href="https://github.com/ManubisGuard/ManubisGuard-Panel/issues">Issues</a> ·
  <a href="https://github.com/ManubisGuard/ManubisGuard-Panel/tree/feature/amnezia-wg">Development branch</a> ·
  <a href="https://github.com/PasarGuard/panel">Upstream project</a>
</p>

---

<a id="english"></a>

## 🇬🇧 English

### Overview

**PasarGuard Pro** is a self-hosted panel for managing network services and their supporting infrastructure. It follows a **Panel + Node** architecture and extends the upstream PasarGuard foundation with a custom dashboard, expanded networking workflows, operational tooling, and PasarGuard branding.

This repository's active feature line is `feature/amnezia-wg`. The default branch and the feature branch may not contain identical application code; use the branch you intend to deploy and verify its installer and configuration before upgrading an existing host.

### Highlights

| Area | Capabilities |
| --- | --- |
| **Command Center** | Operational dashboard, traffic and resource summaries, quick actions, health visibility |
| **Infrastructure** | Multi-node management, node/core assignment, hosts, groups, user templates and bulk workflows |
| **Networking** | WireGuard, AmneziaWG, Xray, peer synchronization and native configuration rendering |
| **Multi-core** | Multiple WireGuard/AmneziaWG core configurations on one node; Xray remains subject to its runtime constraints |
| **AmneziaWG** | AWG metadata and parameters including `Jc`, `Jmin`, `Jmax`, `S1-S4`, and `H1-H4` |
| **Subscriptions** | Subscription generation with protocol-aware configuration rendering |
| **Domains & TLS** | Managed domains, domain-to-node mapping, certificate lifecycle, deployment state and Xray TLS integration |
| **Reality SNI** | SNI discovery, validation, candidate ranking and controlled override selection |
| **Access control** | Admin roles, reseller workflows, resource/action permissions and API access controls |
| **Automation** | API keys, CLI commands and operational scripts |
| **Data layer** | PostgreSQL / TimescaleDB runtime and migration compatibility tooling |
| **Backup & recovery** | Native system backup/restore, database-only exports and a separate explicit migration workflow |
| **Deployment** | Docker Compose, installer options, health checks and operational lifecycle commands |

### Architecture

```text
                 ┌───────────────────────────┐
                 │      PasarGuard Pro       │
                 │  Dashboard · API · RBAC   │
                 └─────────────┬─────────────┘
                               │
                  PostgreSQL / TimescaleDB
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
        ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
        │  Node A │       │  Node B │       │  Node C │
        │ WG / AWG│       │ WG / AWG│       │  Xray   │
        └─────────┘       └─────────┘       └─────────┘
```

The exact protocols and core combinations available depend on the deployed Node runtime and the selected branch.

### Backup, restore and migration

The workflows are intentionally distinct:

- **System backup / restore:** use the native PasarGuard-compatible archive format.
- **Database-only backup:** export database data separately; it is not a full system archive.
- **Cross-panel migration:** use the explicit migration command when importing data from another panel. Ordinary restore is not a migration command.

Common commands:

```bash
sudo pasarguard backup
sudo pasarguard backup-db
sudo pasarguard restore /path/to/backup.zip --check
sudo pasarguard restore /path/to/backup.zip
sudo pasarguard migrate /path/to/source-archive.zip --apply
```

Default backup locations:

- System archives: `/opt/pasarguard/backup/`
- Database-only exports: `/opt/pasarguard/backup/database/`

**Safety:** archives may contain credentials, tokens, or private keys. Restrict access and encrypt off-host copies. Run `restore --check` first, keep an independent backup of the destination, and rehearse recovery on an isolated test system before production use. A check is a preflight, not a rollback guarantee.

### Install

The source-based installer for the active feature branch is:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh | sudo bash -s -- install --database timescaledb
```

The installer supports configurable SSL modes, including domain-based certificates, IP certificates where supported by the environment, custom certificates, and HTTP/no-SSL mode.

Before running an installer on an existing host, review the script and confirm the selected branch, database mode, paths, and SSL options. Do not run an installation or restore command against production unless that change is intended.

### Matching Node

The companion Node project is maintained separately:

- [PasarGuard Node repository](https://github.com/ManubisGuard/PasarGuard-Node)

Example installer for the matching feature line:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh | sudo bash -s -- install
```

Panel and Node versions should be selected as a compatible pair. Validate connectivity, runtime prerequisites, protocol support and node health after deployment.

### Runtime and operations

Useful commands:

```bash
sudo pasarguard status
sudo pasarguard start
sudo pasarguard stop
sudo pasarguard restart
sudo pasarguard logs
sudo pasarguard update
sudo pasarguard edit-env
```

Generate a temporary panel key from the running Compose service:

```bash
docker compose exec pasarguard pasarguard-cli generate-temp-key
```

Treat generated keys as secrets. Never commit them or paste them into public logs or issues.

### Development and validation

The project includes automated checks for application behavior, migration compatibility, backup/restore paths, installer behavior, and supporting scripts. Validation must be interpreted per command and per environment; a passing targeted suite does not imply that the entire test suite or every production workflow has passed.

The latest recorded test snapshot for the active development work was **not fully green**: targeted migration/compatibility tests and selected shell checks passed, while the broader suite still had known failures and errors. Check the latest test run and project TODO/checkpoint notes before treating any feature as fully validated. External ACME, DNS-provider changes, production cutover/restore, and full live multi-node scenarios require environment-specific testing.

Suggested local checks:

```bash
uv run ruff check --no-fix app/migration tests/migration tests/compatibility scripts/manubisguard-restore-env.py
uv run pytest -q tests/migration tests/compatibility
git diff --check
```

### Security principles

- Never commit `.env` files, API keys, tokens, certificates or private keys.
- Keep panel and node secrets private and rotate exposed credentials.
- Apply least-privilege access and review role permissions.
- Treat backup archives as sensitive data.
- Verify changes on a test host before production deployment.
- Keep production changes, destructive restore operations and infrastructure cutovers explicit and separately approved.

### Project links

- **This project:** [PasarGuard Pro](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **Active development branch:** [feature/amnezia-wg](https://github.com/ManubisGuard/ManubisGuard-Panel/tree/feature/amnezia-wg)
- **Companion Node:** [PasarGuard Node](https://github.com/ManubisGuard/PasarGuard-Node)
- **Upstream panel:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **Issues:** [Report a bug or request a feature](https://github.com/ManubisGuard/ManubisGuard-Panel/issues)

---

<a id="فارسی"></a>

## 🇮🇷 فارسی

### معرفی PasarGuard Pro

**PasarGuard Pro** یک پنل خودمیزبان برای مدیریت متمرکز زیرساخت شبکه است. معماری پروژه بر پایهٔ **Panel + Node** است و در کنار حفظ پایهٔ سازگار با پروژهٔ اصلی PasarGuard، قابلیت‌های توسعه‌یافته، داشبورد اختصاصی، ابزارهای عملیاتی و هویت بصری PasarGuard Pro را ارائه می‌کند.

شاخهٔ توسعهٔ فعال این مجموعه `feature/amnezia-wg` است. محتوای شاخهٔ اصلی و شاخهٔ توسعه الزاماً از نظر کد اجرایی یکسان نیست؛ هنگام نصب، شاخهٔ موردنظر، نسخهٔ پنل و Node و گزینه‌های Installer را بررسی کنید.

### قابلیت‌های اصلی

- **داشبورد Command Center:** نمایش وضعیت عملیاتی، منابع سیستم، ترافیک و دسترسی سریع به عملیات
- **مدیریت زیرساخت:** چند Node، تخصیص Core، مدیریت Host، گروه‌ها، کاربران، Template و عملیات گروهی
- **پروتکل‌ها:** WireGuard، AmneziaWG و Xray بر اساس Runtime نسخهٔ نصب‌شده
- **Multi-Core:** اجرای چند Core از نوع WireGuard/AmneziaWG روی یک Node، با رعایت محدودیت‌های Runtime برای Xray
- **AmneziaWG:** نگهداری Metadata و پارامترهایی مانند `Jc`، `Jmin`، `Jmax`، `S1-S4` و `H1-H4`
- **Subscription:** تولید کانفیگ متناسب با پروتکل و اطلاعات Core
- **Domain و SSL:** مدیریت دامنه، اتصال دامنه به Node، چرخهٔ گواهی، وضعیت استقرار و یکپارچگی TLS برای Xray
- **Reality SNI:** کشف و اعتبارسنجی SNI، رتبه‌بندی گزینه‌ها و کنترل Override
- **امنیت دسترسی:** نقش‌های مدیر، Reseller، مجوزهای Resource/Action و کنترل دسترسی API
- **API و اتوماسیون:** API Key، CLI و اسکریپت‌های عملیاتی
- **دیتابیس:** PostgreSQL و TimescaleDB به همراه ابزارهای سازگاری Migration
- **Backup و Restore:** بکاپ کامل سیستم، خروجی دیتابیس‌تنها و مسیر مستقل برای مهاجرت بین پنل‌ها
- **نصب و نگهداری:** Docker Compose، Installer، Health Check و فرمان‌های مدیریت سرویس

### معماری کلی

پنل از طریق API و داشبورد با دیتابیس PostgreSQL/TimescaleDB کار می‌کند و Nodeهای جداگانه را مدیریت می‌کند. ترکیب پروتکل‌ها و Coreهای قابل استفاده به نسخهٔ Node و شاخهٔ نصب‌شده بستگی دارد.

### نصب

Installer شاخهٔ توسعهٔ فعال:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh | sudo bash -s -- install --database timescaledb
```

Installer گزینه‌های مختلف SSL از جمله دامنه، گواهی سفارشی و حالت HTTP بدون SSL را پوشش می‌دهد. پیش از اجرا روی سرور موجود، اسکریپت، شاخه، مسیرها، دیتابیس و گزینه‌های SSL را بررسی کنید.

### نصب Node همراه

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh | sudo bash -s -- install
```

نسخهٔ پنل و Node باید با هم سازگار انتخاب شوند. بعد از نصب، اتصال، پیش‌نیازهای Runtime، پروتکل‌ها و سلامت Node را بررسی کنید.

### فرمان‌های روزمره

```bash
sudo pasarguard status
sudo pasarguard start
sudo pasarguard stop
sudo pasarguard restart
sudo pasarguard logs
sudo pasarguard update
sudo pasarguard edit-env
```

### بکاپ، بازیابی و مهاجرت

این سه عملیات یکسان نیستند:

- **Backup/Restore سیستم:** استفاده از فرمت آرشیو Native سازگار با PasarGuard
- **Backup دیتابیس:** خروجی مستقل دیتابیس که جایگزین بکاپ کامل سیستم نیست
- **Migration:** وارد کردن عمدی داده از پنل دیگر با فرمان مجزا

```bash
sudo pasarguard backup
sudo pasarguard backup-db
sudo pasarguard restore /path/to/backup.zip --check
sudo pasarguard restore /path/to/backup.zip
sudo pasarguard migrate /path/to/source-archive.zip --apply
```

مسیرهای پیش‌فرض:

- بکاپ کامل سیستم: `/opt/pasarguard/backup/`
- خروجی دیتابیس: `/opt/pasarguard/backup/database/`

فایل‌های بکاپ ممکن است حاوی Token، Secret و Private Key باشند. دسترسی به آن‌ها را محدود کنید و نسخه‌های خارج از سرور را رمزنگاری کنید. ابتدا `restore --check` را اجرا کنید، از مقصد بکاپ مستقل بگیرید و بازیابی را روی محیط آزمایشی جداگانه تمرین کنید. بررسی اولیه به معنی تضمین Rollback نیست.

### تولید کلید موقت پنل

```bash
docker compose exec pasarguard pasarguard-cli generate-temp-key
```

کلید تولیدشده محرمانه است و نباید در Git، گزارش عمومی یا Issue منتشر شود.

### وضعیت تست‌ها

برای پروژه تست‌های خودکار مربوط به رفتار برنامه، Migration، Backup/Restore، Installer و اسکریپت‌های پشتیبان وجود دارد. نتیجهٔ هر تست فقط همان محدوده و محیط را پوشش می‌دهد و نباید از موفقیت چند تست هدفمند نتیجه گرفت که کل پروژه یا همهٔ سناریوهای Production تأیید شده‌اند.

طبق آخرین گزارش ثبت‌شده از توسعهٔ فعلی، **مجموعهٔ کامل تست‌ها هنوز کاملاً سبز نبود**: تست‌های هدفمند Migration/Compatibility و چند تست Shell موفق بودند، اما در اجرای کامل‌تر تعدادی شکست و خطا باقی مانده بود. قبل از انتشار یا استقرار، آخرین گزارش تست و یادداشت‌های TODO/Checkpoint را بررسی کنید. تست ACME واقعی، تغییر DNS Provider، بازیابی یا Cutover در Production و سناریوهای زندهٔ چند Node نیازمند اعتبارسنجی جداگانه هستند.

### اصول امنیتی

- فایل `.env`، کلید API، Token، Certificate و Private Key را Commit نکنید.
- Secretهای پنل و Node را محرمانه نگه دارید و در صورت افشا آن‌ها را تعویض کنید.
- مجوزها را بر اساس اصل حداقل دسترسی تنظیم کنید.
- آرشیو بکاپ را دادهٔ حساس در نظر بگیرید.
- تغییرات را قبل از Production روی سرور آزمایشی بررسی کنید.
- Restore مخرب، تغییر زیرساخت و Cutover باید آگاهانه و با تأیید جداگانه انجام شوند.

### لینک‌ها

- **PasarGuard Pro:** [مخزن پروژه](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **شاخهٔ توسعه:** [feature/amnezia-wg](https://github.com/ManubisGuard/ManubisGuard-Panel/tree/feature/amnezia-wg)
- **Node همراه:** [PasarGuard Node](https://github.com/ManubisGuard/PasarGuard-Node)
- **پروژهٔ پایه:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **گزارش مشکل:** [Issues](https://github.com/ManubisGuard/ManubisGuard-Panel/issues)
