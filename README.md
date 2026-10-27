<!-- PasarGuard Pro | Bilingual project documentation -->

<p align="center">
  <img src="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/dashboard/public/statics/favicon/logo.png" alt="PasarGuard Pro logo" width="160">
</p>

<h1 align="center">PasarGuard Pro</h1>
<p align="center"><strong>A self-hosted control plane for modern network infrastructure</strong></p>

<p align="center">
  <a href="https://github.com/ManubisGuard/ManubisGuard-Panel/actions"><img src="https://img.shields.io/github/actions/workflow/status/ManubisGuard/ManubisGuard-Panel/run-tests.yml?branch=feature%2Famnezia-wg&style=flat-square" alt="Test workflow"></a>
  <a href="https://github.com/ManubisGuard/ManubisGuard-Panel"><img src="https://img.shields.io/github/license/ManubisGuard/ManubisGuard-Panel?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/Networking-WireGuard%20%7C%20AmneziaWG%20%7C%20Xray-5865F2?style=flat-square" alt="Networking">
</p>

<p align="center">
  <a href="#english">🇬🇧 English</a> ·
  <a href="#فارسی">🇮🇷 فارسی</a>
</p>

> **Project lineage:** PasarGuard Pro is a feature-enhanced fork based on the upstream panel project ([source repository](https://github.com/PasarGuard/panel)). The repository is hosted under the ManubisGuard GitHub organization; the product and interface branding is **PasarGuard Pro**.
>
> **Development branch for current AmneziaWG work:** `feature/amnezia-wg`. Review the target branch and its documentation before deploying.

---

<a id="english"></a>

# 🇬🇧 English

## Overview

**PasarGuard Pro** is a self-hosted control plane for managing network access infrastructure through a web interface. It connects a Panel with one or more worker Nodes and organizes administration around users, groups, hosts, cores, subscriptions, domains, TLS, access control, and operational recovery.

The project is intended for administrators who need to manage multiple nodes and supported networking runtimes from one place. It is not a substitute for firewall policy, host hardening, monitoring, or a tested recovery plan.

## Highlights

### Platform and administration

- Panel + Node architecture for centralized management
- Multi-Node administration
- Users, groups, hosts, templates, statistics, and bulk workflows
- Core configuration and synchronization
- API keys and automation entry points
- Reseller administrators, roles, and resource/action-based permissions
- Docker Compose deployment
- PostgreSQL / TimescaleDB runtime
- Operational status, logs, and health checks

### Networking

- Xray
- WireGuard
- Native AmneziaWG 2.x integration in the current development branch
- Multiple WireGuard/AmneziaWG Cores on a Node where configured
- Peer and configuration synchronization
- AWG parameters including `Jc`, `Jmin`, `Jmax`, `S1-S4`, and `H1-H4`
- Subscription-aware configuration rendering and PersistentKeepalive preservation

### Domains and TLS

- Domain-to-Node association and primary-domain handling
- Certificate lifecycle management and expiration visibility
- Let's Encrypt workflow and installation of existing certificates
- Manual deploy/re-deploy controls
- Xray TLS configuration integration
- Multi-domain TLS/SNI handling
- Deployment error recording and guarded recovery behavior
- Reality SNI discovery, validation, and latency-informed candidate selection

### Security and access control

- Authentication and role-based access control (RBAC)
- Resource/action permission checks for sensitive workflows
- API secret redaction and protected token storage where implemented
- Explicitly separated backup, restore, and cross-panel migration workflows
- Archive preflight before restore
- Operational guidance for keeping production recovery separate from test validation

## Architecture

At a high level:

```text
Administrator / API Client
          |
          v
   PasarGuard Pro Panel
          |
          +---- PostgreSQL / TimescaleDB
          |
          +---- Node A
          |       +---- Xray Core
          |       +---- WireGuard / AmneziaWG Core(s)
          |
          +---- Node B
                  +---- Supported Core(s)
```

The Panel stores and coordinates configuration. Nodes execute the configured runtime. Kernel-dependent features such as AmneziaWG require compatible host-level support on each relevant Node; installing the Panel alone does not install the remote Node's kernel module.

## AmneziaWG support

The current development branch includes AmneziaWG-aware configuration and Node runtime integration.

The matching Node repository is:

**[ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)**

For the current AWG path:

- Use a compatible Node runtime, version **0.6.0 or newer**.
- Install and verify the AmneziaWG 2.x kernel module on the Node's Linux host.
- Ensure kernel headers match the running kernel and DKMS can build the module.
- Confirm that the Panel's Core parameters and Node runtime agree.
- Verify handshake and traffic counters with a real client after configuration.

The Panel runtime guard is intended to reject older Node runtimes for AWG rather than reporting an unsupported runtime as ready. A successful UI save or install-time interface check is not proof of end-to-end connectivity.

> **Compatibility:** This documentation describes the project's current AmneziaWG 2.x target. Do not assume AmneziaWG 3 compatibility unless it is separately implemented, documented, and tested.

## Installation

Review the installer, environment variables, and deployment defaults before using them on a production system.

### One-command installer

The following command uses the current development branch so the AmneziaWG-related documentation and implementation are aligned:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh | sudo bash -s -- install --database timescaledb
```

The installer supports different SSL modes depending on the selected options and current branch, including a domain certificate, IP-based certificate, custom certificate/key, or no SSL. Check the installer's help and prompts before choosing a mode.

Examples of SSL mode options:

```bash
--ssl-mode domain --ssl-domain panel.example.com
--ssl-mode ip
--ssl-mode none --yes
```

For production deployments, prefer a correctly configured domain and TLS certificate. If using a custom certificate, protect the private key and verify the certificate chain and hostname.

### Source-based Docker Compose deployment

For an existing checkout:

```bash
cd /path/to/ManubisGuard-Panel
docker compose --env-file .env up -d --build
```

The exact service names and required environment variables may vary by branch. Treat the checked-out branch's Compose and environment examples as the source of truth.

### Install and configure a Node

Install the Node on its own Linux host, then add it to the Panel using the Node's address, API settings, transport, and public TLS certificate as required by the selected configuration.

Node installation guide:

[PasarGuard Pro Node README](https://github.com/ManubisGuard/ManubisGuard-Node#english)

The Node installer prints the public TLS certificate at the end of setup for copy/paste into the Panel. It does not print the TLS private key. Never publish the Node API key or private key.

## Users, groups, hosts, and cores

The Panel organizes administration around users and reusable configuration:

- **Users:** user lifecycle and subscription-related configuration
- **Groups:** user grouping and administrative organization
- **Hosts:** endpoint and host-level configuration
- **Cores:** runtime-specific configuration and synchronization
- **Templates and bulk operations:** reusable settings and multi-object workflows
- **Statistics:** usage and operational visibility, depending on the runtime and collected data

WireGuard and AmneziaWG can support multiple Core instances on a Node when configured and supported by the matching Node runtime. Xray runtime topology has different process constraints; confirm the behavior of the deployed branch before planning multi-Core Xray layouts.

## Domains, certificates, and Reality SNI

The Domains & SSL area is designed to manage domains and certificate lifecycle from the Panel.

Depending on the configured provider and deployed version, workflows may include domain validation, certificate issuance or installation, expiry tracking, deployment, and renewal state.

Reality SNI tools can help discover and validate candidate server names and rank candidates using latency measurements. Validate candidates against the intended Reality target and network policy before applying a change.

DNS provider changes, ACME issuance, firewall changes, and public certificate deployment depend on real external services and correct domain ownership. A local test alone does not prove that these external workflows are operational.

## Backup, restore, and migration

These are separate operations and must not be treated as interchangeable.

### Native system backup and restore

Common CLI commands in the compatible deployment:

```bash
sudo pasarguard backup
sudo pasarguard restore
sudo pasarguard restore /path/to/backup.zip --check
sudo pasarguard restore /path/to/backup.zip
sudo pasarguard restore --fresh /path/to/backup.zip
sudo pasarguard backup-service
```

- System archives are stored under `/opt/pasarguard/backup/`.
- `--check` performs a read-only archive preflight; it does not perform a restore.
- `--fresh` is intended for a new, empty destination and depends on recovery metadata and compatible image references in the archive.
- Archives can contain credentials, tokens, and private keys. Restrict file permissions and keep encrypted off-host copies.
- Backups should be tested on an isolated host before being trusted for disaster recovery.

### Database-only exports

```bash
sudo pasarguard backup-db
```

Database-only exports are separate from full system archives and must not be passed to the native system restore command as if they were complete system backups.

### Cross-panel migration

```bash
sudo pasarguard migrate /path/to/source-archive.zip --apply
```

Use migration only when intentionally importing from another panel. Verify the source archive and destination compatibility before applying it. Do not use a production migration as a substitute for testing the native restore process.

Legacy custom archives may use a different format from native PasarGuard Pro archives. Verify the format and recovery requirements before attempting restoration.

## CLI and temporary admin key

Common lifecycle commands:

```bash
sudo pasarguard status
sudo pasarguard start
sudo pasarguard stop
sudo pasarguard restart
sudo pasarguard logs
sudo pasarguard update
sudo pasarguard edit-env
```

Where supported by the installed CLI, a temporary admin key can be generated with:

```bash
docker compose exec pasarguard pasarguard-cli generate-temp-key
```

Use the actual Compose service name and CLI available in the deployed branch. Treat temporary keys as credentials: store them securely, do not commit them, and revoke or rotate them according to the deployment's access policy.

## Database and data safety

The supported runtime uses PostgreSQL with TimescaleDB. Database migrations and compatibility work should be validated against disposable test data before production use.

Do not assume that a successful unit test proves that a production restore, major-version database migration, external DNS change, certificate issuance, or multi-Node cutover has been tested. Keep evidence for each acceptance gate and separate test results from production status.

## Testing and development

The project uses multiple validation layers depending on the change, which may include:

- Python regression tests
- Backup/restore and migration tests
- Domain/TLS tests
- Node synchronization tests
- TypeScript checks and production frontend build
- Docker image builds
- PostgreSQL/TimescaleDB tests on disposable instances
- AmneziaWG runtime checks on isolated test Nodes
- Shell syntax checks and `git diff --check`

Run the relevant checks for the files changed. Kernel-dependent AWG integration tests must be performed on a compatible isolated host. Never use production as a test fixture for destructive restore or migration work.

## Security checklist

- Keep API keys, tokens, TLS private keys, and database credentials out of Git.
- Restrict access to backup archives; assume archives may contain secrets.
- Use TLS for public Panel access.
- Limit API and node ports with host/provider firewalls.
- Keep Panel and Node versions compatible.
- Validate backup archives and test recovery on an isolated host.
- Separate native restore from cross-panel migration.
- Redact secrets and production-sensitive details from logs and bug reports.

## Project links

- **PasarGuard Pro Panel:** [ManubisGuard/ManubisGuard-Panel](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **PasarGuard Pro Node:** [ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)
- **Upstream panel source:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **Issues:** [Report a bug](https://github.com/ManubisGuard/ManubisGuard-Panel/issues)

---

<a id="فارسی"></a>

# 🇮🇷 فارسی

## معرفی

**PasarGuard Pro** یک Control Plane خودمیزبان برای مدیریت متمرکز زیرساخت دسترسی شبکه است. این پلتفرم پنل را به یک یا چند Node متصل می‌کند و مدیریت کاربران، گروه‌ها، Hostها، Coreها، Subscriptionها، Domain، TLS، سطح دسترسی و بازیابی عملیاتی را در یک رابط وب فراهم می‌کند.

این پروژه برای مدیرانی طراحی شده که باید چند نود و Runtime شبکه را از یک محل مدیریت کنند. استفاده از پنل جایگزین Firewall Policy، ایمن‌سازی Host، Monitoring یا برنامه بازیابی آزمایش‌شده نیست.

## قابلیت‌های اصلی

### پلتفرم و مدیریت

- معماری Panel + Node برای مدیریت متمرکز
- مدیریت چند Node
- مدیریت Users، Groups، Hosts، Templates، Statistics و عملیات گروهی
- تنظیم و همگام‌سازی Coreها
- API Key و امکانات Automation
- Reseller Admin، Role و Permission بر اساس Resource/Action
- استقرار با Docker Compose
- Runtime مبتنی بر PostgreSQL / TimescaleDB
- نمایش وضعیت عملیاتی، Log و Health Check

### شبکه

- Xray
- WireGuard
- یکپارچه‌سازی بومی AmneziaWG 2.x در شاخه توسعه فعلی
- اجرای چند Core از نوع WireGuard/AmneziaWG روی یک Node، در صورت پیکربندی
- همگام‌سازی Peer و Configuration
- پارامترهای AWG شامل `Jc`، `Jmin`، `Jmax`، `S1-S4` و `H1-H4`
- تولید Configuration سازگار با Subscription و حفظ PersistentKeepalive

### Domain و TLS

- اتصال Domain به Node و مدیریت Primary Domain
- مدیریت چرخه Certificate و مشاهده زمان انقضا
- گردش‌کار Let's Encrypt و نصب Certificate موجود
- کنترل Deploy و Re-deploy
- یکپارچه‌سازی TLS با Xray
- مدیریت Multi-domain TLS/SNI
- ثبت خطاهای Deployment و رفتار بازیابی کنترل‌شده
- کشف و اعتبارسنجی Reality SNI و انتخاب Candidate بر اساس Latency

### امنیت و کنترل دسترسی

- Authentication و کنترل دسترسی مبتنی بر نقش یا RBAC
- بررسی Permission برای عملیات حساس
- حذف Secret از API Response و نگهداری محافظت‌شده Token در بخش‌های پیاده‌سازی‌شده
- تفکیک صریح Backup، Restore و Migration بین پنل‌ها
- بررسی اولیه آرشیو پیش از Restore
- راهنمای عملیاتی برای جدا نگه‌داشتن بازیابی Production از تست

## معماری

نمای کلی:

```text
مدیر سیستم / API Client
          |
          v
   پنل PasarGuard Pro
          |
          +---- PostgreSQL / TimescaleDB
          |
          +---- Node A
          |       +---- Xray Core
          |       +---- WireGuard / AmneziaWG Coreها
          |
          +---- Node B
                  +---- Coreهای پشتیبانی‌شده
```

پنل Configuration را نگهداری و هماهنگ می‌کند. Nodeها Runtimeهای پیکربندی‌شده را اجرا می‌کنند. قابلیت‌های وابسته به Kernel مانند AmneziaWG به پشتیبانی سازگار روی Host هر Node نیاز دارند؛ نصب پنل به‌تنهایی Kernel Module نودهای راه‌دور را نصب نمی‌کند.

## پشتیبانی AmneziaWG

شاخه توسعه فعلی شامل Configuration و Runtime یکپارچه با AmneziaWG است.

مخزن Node هماهنگ:

**[ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)**

برای استفاده از مسیر فعلی AWG:

- از Runtime سازگار Node با نسخه **0.6.0 یا جدیدتر** استفاده کنید.
- Kernel Module مربوط به AmneziaWG 2.x را روی Host لینوکسی نود نصب و بررسی کنید.
- مطمئن شوید Kernel Headerها با Kernel در حال اجرا منطبق هستند و DKMS می‌تواند Module را بسازد.
- پارامترهای Core در پنل و Runtime نود را با یکدیگر تطبیق دهید.
- پس از تنظیم، Handshake و شمارنده‌های ترافیک را با یک Client واقعی بررسی کنید.

Runtime Guard پنل برای رد کردن Runtimeهای قدیمی AWG در نظر گرفته شده است تا نسخه پشتیبانی‌نشده به‌اشتباه آماده نمایش داده نشود. ذخیره موفق فرم یا عبور از بررسی Interface هنگام نصب، اثبات‌کننده اتصال کامل Client نیست.

> **سازگاری:** هدف فعلی این مستندات AmneziaWG 2.x است. سازگاری با AWG3 را بدون پیاده‌سازی، مستندات و تست مستقل فرض نکنید.

## نصب

پیش از نصب روی Production، Installer، متغیرهای Environment و تنظیمات پیش‌فرض را بررسی کنید.

### نصب با یک فرمان

فرمان زیر از شاخه توسعه فعلی استفاده می‌کند تا مستندات و پیاده‌سازی AmneziaWG با یکدیگر هماهنگ باشند:

```bash
curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh | sudo bash -s -- install --database timescaledb
```

با توجه به گزینه‌ها و شاخه مورد استفاده، Installer می‌تواند حالت‌های مختلف SSL را پوشش دهد؛ از جمله Certificate برای Domain، Certificate مبتنی بر IP، Certificate/Key سفارشی یا حالت بدون SSL. پیش از انتخاب، Help و Promptهای Installer را بررسی کنید.

نمونه گزینه‌های SSL:

```bash
--ssl-mode domain --ssl-domain panel.example.com
--ssl-mode ip
--ssl-mode none --yes
```

برای Production، Domain و TLS را به‌درستی تنظیم کنید. هنگام استفاده از Certificate سفارشی، از Private Key محافظت کنید و Chain و نام میزبان را بررسی کنید.

### استقرار با Docker Compose از سورس

برای Checkout موجود:

```bash
cd /path/to/ManubisGuard-Panel
docker compose --env-file .env up -d --build
```

نام دقیق Serviceها و متغیرهای لازم ممکن است بین Branchها تفاوت داشته باشد. فایل Compose و نمونه Environment همان Branch مبنای معتبر تنظیمات هستند.

### نصب و اتصال Node

Node را روی Host لینوکسی جداگانه نصب کنید، سپس بر اساس تنظیمات انتخاب‌شده، آدرس نود، API، روش ارتباط و Certificate عمومی TLS را در پنل ثبت کنید.

راهنمای Node:

[راهنمای PasarGuard Pro Node](https://github.com/ManubisGuard/ManubisGuard-Node#فارسی)

Installer نود در پایان Certificate عمومی TLS را برای کپی در پنل نمایش می‌دهد و Private Key را چاپ نمی‌کند. API Key نود و Private Key را منتشر نکنید.

## Users، Groups، Hosts و Coreها

پنل مدیریت را حول کاربران و Configurationهای قابل استفاده مجدد سازمان‌دهی می‌کند:

- **Users:** چرخه مدیریت کاربر و تنظیمات مرتبط با Subscription
- **Groups:** گروه‌بندی کاربران و سازمان‌دهی مدیریتی
- **Hosts:** تنظیمات Endpoint و Host
- **Cores:** تنظیمات مخصوص Runtime و همگام‌سازی
- **Templates و Bulk Operations:** تنظیمات قابل استفاده مجدد و عملیات چندموردی
- **Statistics:** مشاهده مصرف و وضعیت عملیاتی، بر اساس Runtime و داده‌های جمع‌آوری‌شده

در صورت پشتیبانی و تنظیم Runtime مربوطه، WireGuard و AmneziaWG می‌توانند چند Core روی یک Node داشته باشند. ساختار اجرای Xray محدودیت‌های پردازشی متفاوتی دارد؛ پیش از طراحی Multi-Core برای Xray، رفتار Branch مستقرشده را بررسی کنید.

## Domain، Certificate و Reality SNI

بخش Domains & SSL برای مدیریت Domainها و چرخه Certificate از داخل پنل طراحی شده است.

با توجه به Provider و نسخه مستقرشده، امکانات می‌توانند شامل اعتبارسنجی Domain، صدور یا نصب Certificate، مشاهده انقضا، Deployment و وضعیت Renewal باشند.

ابزارهای Reality SNI به کشف و اعتبارسنجی نام‌های پیشنهادی و رتبه‌بندی آن‌ها بر اساس اندازه‌گیری Latency کمک می‌کنند. پیش از اعمال تغییر، Candidate را با Target موردنظر Reality و سیاست شبکه بررسی کنید.

تغییر DNS Provider، صدور ACME، تغییر Firewall و انتشار Certificate عمومی به سرویس‌های خارجی و مالکیت صحیح Domain وابسته‌اند. تست محلی به‌تنهایی اثبات نمی‌کند که این گردش‌کارهای خارجی در محیط واقعی کار می‌کنند.

## Backup، Restore و Migration

این عملیات از یکدیگر جدا هستند و نباید جایگزین یکدیگر در نظر گرفته شوند.

### بکاپ و بازیابی کامل سیستم

فرمان‌های رایج در نصب سازگار:

```bash
sudo pasarguard backup
sudo pasarguard restore
sudo pasarguard restore /path/to/backup.zip --check
sudo pasarguard restore /path/to/backup.zip
sudo pasarguard restore --fresh /path/to/backup.zip
sudo pasarguard backup-service
```

- آرشیوهای سیستم در مسیر `/opt/pasarguard/backup/` قرار می‌گیرند.
- `--check` پیش‌بررسی خواندنی آرشیو است و Restore انجام نمی‌دهد.
- `--fresh` برای مقصد جدید و خالی طراحی شده و به Metadata بازیابی و Image Referenceهای سازگار داخل آرشیو وابسته است.
- آرشیوها ممکن است Credential، Token و Private Key داشته باشند. دسترسی فایل را محدود کنید و نسخه خارج از سرور را رمزنگاری کنید.
- پیش از اعتماد به بکاپ برای Disaster Recovery، بازیابی آن را روی Host آزمایشی ایزوله انجام دهید.

### خروجی دیتابیس‌تنها

```bash
sudo pasarguard backup-db
```

خروجی دیتابیس‌تنها با آرشیو کامل سیستم فرق دارد و نباید به‌عنوان بکاپ کامل به فرمان Native Restore داده شود.

### Migration بین پنل‌ها

```bash
sudo pasarguard migrate /path/to/source-archive.zip --apply
```

از Migration فقط برای وارد کردن عمدی داده از پنل دیگر استفاده کنید. پیش از اعمال، آرشیو مبدأ و سازگاری مقصد را بررسی کنید. Migration در Production جایگزین تست فرایند Native Restore نیست.

آرشیوهای سفارشی قدیمی ممکن است با فرمت Native PasarGuard Pro متفاوت باشند. پیش از بازیابی، فرمت و پیش‌نیازهای Recovery را مشخص کنید.

## CLI و Temporary Admin Key

فرمان‌های رایج برای مدیریت سرویس:

```bash
sudo pasarguard status
sudo pasarguard start
sudo pasarguard stop
sudo pasarguard restart
sudo pasarguard logs
sudo pasarguard update
sudo pasarguard edit-env
```

در نسخه‌هایی که CLI نصب‌شده پشتیبانی می‌کند، می‌توان Temporary Admin Key را با فرمان زیر ساخت:

```bash
docker compose exec pasarguard pasarguard-cli generate-temp-key
```

نام Service و CLI را با نسخه مستقرشده تطبیق دهید. Temporary Key یک Credential است؛ آن را امن نگهداری کنید، در Git Commit نکنید و مطابق سیاست دسترسی محیط، آن را لغو یا تعویض کنید.

## ایمنی دیتابیس و داده‌ها

Runtime پشتیبانی‌شده از PostgreSQL و TimescaleDB استفاده می‌کند. Migration دیتابیس و تغییرات سازگاری باید پیش از Production روی داده آزمایشی Disposable اعتبارسنجی شوند.

موفقیت Unit Test به معنی تست موفق Restore در Production، Migration بین نسخه‌های اصلی دیتابیس، تغییر DNS خارجی، صدور Certificate یا Cutover چند Node نیست. برای هر مرحله شواهد تست نگه دارید و نتیجه محیط تست را از وضعیت Production جدا کنید.

## تست و توسعه

بسته به نوع تغییر، پروژه از چند لایه Validation استفاده می‌کند؛ از جمله:

- تست‌های Regression پایتون
- تست‌های Backup/Restore و Migration
- تست‌های Domain/TLS
- تست‌های همگام‌سازی Node
- بررسی TypeScript و Build نهایی Frontend
- Build ایمیج Docker
- تست PostgreSQL/TimescaleDB روی محیط Disposable
- تست Runtime مربوط به AmneziaWG روی Node آزمایشی ایزوله
- بررسی Syntax اسکریپت Shell و `git diff --check`

تست‌های مرتبط با فایل‌های تغییرکرده را اجرا کنید. تست Integration وابسته به Kernel AWG باید روی Host آزمایشی سازگار انجام شود. از Production برای تست مخرب Restore یا Migration استفاده نکنید.

## چک‌لیست امنیتی

- API Key، Token، TLS Private Key و اطلاعات ورود دیتابیس را وارد Git نکنید.
- دسترسی به آرشیوهای بکاپ را محدود کنید و فرض کنید ممکن است Secret داشته باشند.
- برای دسترسی عمومی به پنل از TLS استفاده کنید.
- دسترسی به پورت‌های API و Node را با Firewall میزبان و Provider محدود کنید.
- سازگاری نسخه Panel و Node را حفظ کنید.
- آرشیوها را بررسی و بازیابی را روی Host ایزوله آزمایش کنید.
- Native Restore را از Migration بین پنل‌ها جدا نگه دارید.
- Secretها و اطلاعات حساس Production را پیش از ارسال Log یا Bug Report حذف کنید.

## لینک‌های پروژه

- **پنل PasarGuard Pro:** [ManubisGuard/ManubisGuard-Panel](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **PasarGuard Pro Node:** [ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)
- **سورس بالادستی پنل:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **گزارش باگ:** [Issues](https://github.com/ManubisGuard/ManubisGuard-Panel/issues)
