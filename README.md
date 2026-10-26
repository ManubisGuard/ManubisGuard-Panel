# ManubisGuard Panel

<p align="center">
  <strong>Open-source network infrastructure, under your control.</strong>
</p>

<p align="center">
  <a href="#english">🇬🇧 English</a> · <a href="#فارسی">🇮🇷 فارسی</a>
</p>

> **Fork / upstream:** ManubisGuard Panel is maintained as a feature-enhanced fork of [PasarGuard/panel](https://github.com/PasarGuard/panel), with ManubisGuard-specific architecture, UI, AmneziaWG support, migration/restore tooling, Domain & SSL management, and operational features built on top of the upstream-compatible foundation.

> **Current development branch:** `feature/amnezia-wg`

---

<a id="english"></a>

# 🇬🇧 English

## What is ManubisGuard Panel?

**ManubisGuard Panel** is an open-source, self-hosted control plane for modern network infrastructure. It provides a unified web interface for managing users, Nodes, Cores, Hosts, Groups, subscriptions, networking protocols, domains, TLS certificates, backups, restores, migrations, API access and operational settings.

The project follows a **Panel + Node** architecture and is designed to manage infrastructure rather than only individual protocol configurations.

ManubisGuard is based on the **PasarGuard Panel** codebase and preserves upstream-compatible operational concepts where required while extending the platform with ManubisGuard features and branding.

### Upstream project

- **Upstream Panel:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **ManubisGuard Panel:** [ManubisGuard/ManubisGuard-Panel](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **Matching Node:** [ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)

---

## ✨ Features

### Core platform

- Modern Command Center dashboard
- Panel + Node architecture
- Multi-Node management
- Multi-Core Node architecture
- Users and user management
- Groups
- Hosts
- Templates
- Bulk operations
- Statistics and traffic monitoring
- Subscription generation
- API Keys
- Reseller Admins
- Admin Roles and RBAC
- Docker / Docker Compose deployment
- PostgreSQL / TimescaleDB runtime
- Health checks and operational tooling

### Networking

- WireGuard
- AmneziaWG
- Xray
- Multiple WireGuard/AmneziaWG Cores on one Node
- Node/Core synchronization
- Peer synchronization
- Native WireGuard / AmneziaWG configuration generation
- AWG-specific parameters: `Jc`, `Jmin`, `Jmax`, `S1-S4`, `H1-H4`
- PersistentKeepalive preservation
- Subscription-aware AWG rendering
- Core metadata and runtime state management

### Domains & SSL

- Managed domains
- Multiple domains per Node
- Primary domain handling
- Domain-to-Node association
- Domain validation
- Certificate metadata
- Let's Encrypt workflow
- Existing certificate installation
- Certificate renewal lifecycle
- Expiration tracking
- Renewal attempts and next-renewal state
- Certificate error state
- Deployment status
- Manual Deploy / Re-deploy
- TLS serving controls
- Xray TLS certificate materialization
- Multi-domain TLS / SNI injection
- Deployment failure recording
- Runtime rollback after failed certificate application
- Reality SNI discovery and validation
- Auto Select Best SNI
- Latency-based SNI candidate ranking
- SNI override validation

### Backup, Restore & Migration

- Standard system-level backup and restore through the paired PasarGuard backup/restore engine, adapted for ManubisGuard
- Canonical archive directory: `/opt/manubisguard/backup/`
- Database-only exports and panel backup API remain separate under `/opt/manubisguard/backup/database/`
- Upstream archive integrity checks, database-engine compatibility checks, interactive restore and explicit fresh-host recovery where metadata permits
- Explicitly separate cross-panel migration command (`manubis migrate`); native restore never dispatches to migration
- AmneziaWG panel configuration is stored in the panel database; external node runtime state requires its own verified backup plan

### Security

- Authentication and RBAC
- Resource/action-based permissions
- Permission-aware Node/Core actions
- Protected Backup/Restore workflows
- API access controls
- Encrypted Telegram token storage
- Sensitive-token redaction from API responses
- No intentional secret/private-key logging
- Native restore archive preflight and explicit destructive restore flow
- Cross-panel migration remains a separate command and executor

---

## 🖥️ Command Center Dashboard

The dashboard is designed as an operational **Command Center**, not only a statistics page.

It provides visibility into:

- Online and total users
- Network traffic
- CPU usage
- Memory usage
- Disk usage
- Platform health
- User state
- Quick administrative actions
- Nodes, Users and Groups
- Operational status cards

The navigation is organized around administration workflows:

```text
Dashboard

Users
Statistics

Nodes & Cores
├── Nodes
├── Cores
├── WireGuard
└── Logs

Hosts & Groups
├── Hosts
└── Groups

Reseller
├── Admins
└── Admin Roles

API Keys
Templates
Bulk

Settings
├── General
├── Domains & SSL
├── Backup & Restore
├── Theme
└── other settings
```

---

## 🎨 Theme System

ManubisGuard includes a configurable dark-native theme system.

Available controls include:

- Primary color
- Secondary color
- Accent color
- Background color
- Surface color
- Border color
- Glow intensity
- Glass intensity
- Border intensity
- Shadow intensity
- Chart glow
- Background grid
- Ambient effects
- Animation intensity
- UI density

Presets include:

- Cyber Pulse
- Midnight Violet
- Neon Ocean
- Aurora
- Quantum
- Obsidian

Reduced-motion settings are available for users who prefer lower animation intensity.

---

## 🌐 Nodes, Cores & Multi-Core

A Node can be assigned to multiple Core configurations.

### WireGuard / AmneziaWG

Multiple WireGuard and AmneziaWG Core instances can run concurrently on the same Node and are tracked by interface.

The Node model retains the legacy single `core_config_id` representation for compatibility while supporting `core_config_ids` for multi-Core assignments.

### Xray

Xray is intentionally limited to one Core configuration per Node because the Node runtime uses a single Xray process for Xray inbounds.

### Synchronization

Core synchronization is additive where possible, so adding a compatible Core does not unnecessarily stop already-running compatible Cores.

---

## 🛡️ AmneziaWG

AmneziaWG is a first-class networking path in the current development branch.

The implementation covers:

- AmneziaWG Core metadata
- `Jc`
- `Jmin` / `Jmax`
- `S1-S4`
- `H1-H4`
- Native AWG interface support
- AWG-aware subscription generation
- Node Peer synchronization
- Public-key / Peer mapping
- Native WireGuard/AWG configuration rendering
- Host-side AWG runtime preparation
- AmneziaWG tools pinning
- Kernel/DKMS preparation
- Native interface smoke validation

The development/test workflow has also been used to validate real external AWG connectivity, including correct peer mapping, endpoint delivery, UDP traffic, handshake state and non-zero RX/TX counters.

Production and TEST environments are treated separately; a TEST result is not presented as a production deployment result.

> **Support note:** the current project work targets **AmneziaWG 2.x / the validated AWG runtime**. Do not assume AWG3 compatibility unless it is explicitly documented and tested in the project.

---

## 👥 Users, Groups, Hosts & Templates

Administrative workflows include:

- Users
- User templates
- Groups
- Hosts
- Bulk operations
- Statistics
- Node/Core assignments
- Subscription-related configuration

Hosts and Groups are presented as a unified workspace while retaining their respective routes and permission model.

---

## 🔑 API Keys & Automation

The Panel provides API key management for administrative integrations and automation.

API access is separated from browser UI state and follows the project's authentication and authorization model.

Use API access for automation only after reviewing the current API contract and permissions exposed by the deployed version.

---

## 🔐 Reseller & RBAC

ManubisGuard includes:

- Admin management
- Reseller Admins
- Admin Roles
- Resource/action-based permissions
- Settings permission gating
- Backup/restore authorization
- Node/Core permission checks
- API access controls

Sensitive operations remain protected by authentication and RBAC.

---

## 🌍 Domains & SSL

The Domains & SSL workspace provides domain and certificate lifecycle management.

### Domain management

- Managed domains
- Multiple domains per Node
- Primary-domain handling
- Domain-to-Node association
- Domain validation

### Certificates

- Let's Encrypt issuance workflow
- Existing certificate installation
- Certificate metadata
- Expiration state
- Renewal attempts
- Next renewal information
- Failure/error state
- Manual Deploy / Re-deploy
- TLS serving control

### Xray TLS

Managed certificate material can be injected into the existing Xray runtime configuration through the verified Node start/configuration path.

The implementation includes:

- Multi-domain TLS/SNI injection
- Deployment metadata
- Failure recording
- Previous-configuration rollback when runtime application fails

Private-key material is not returned by the API and is cleared from the relevant frontend form state after successful submission.

### Reality SNI intelligence

Reality tooling includes:

- SNI discovery
- SNI candidate validation
- Auto Select Best SNI
- Latency-based candidate ranking
- SNI override validation
- Persistence-safe selection behavior

Auto Select evaluates SNI candidates against the existing Reality target rather than silently replacing the target itself.

---

## 💾 Backup & Restore

Standard system-level backup and recovery use the paired original PasarGuard backup/restore implementation adapted for ManubisGuard. The standard archive format is intentionally separate from database-only exports and cross-panel migration.

### Standard system backup and restore

```bash
sudo manubis backup
sudo manubis restore
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

- System backup/restore archives are stored under `/opt/manubisguard/backup/`.
- The archive includes application configuration, persistent application files, and engine-aware database dumps with integrity/version metadata from the pinned upstream implementation.
- `--check` is a read-only archive preflight.
- `--fresh` is only for a new host with empty application/data directories and an archive containing recovery metadata and usable pinned image references. Legacy archives without those metadata require a compatible existing installation.
- The upstream archive key `pasarguard_data/` is intentionally preserved as a format identifier for compatibility.
- Archives contain secrets and may include private keys. Keep them root-only and maintain encrypted off-host copies.

### Database-only exports and panel backup API

```bash
sudo manubis backup-db
```

Database-only CLI/API exports remain under `/opt/manubisguard/backup/database/`. They are not full-system archives and must not be passed to the standard restore command as though they were native system backups.

### Separate cross-panel migration

```bash
sudo manubis migrate /path/to/source-archive.zip --apply
```

Use migration only when intentionally importing from another panel. Ordinary `manubis restore` uses the native backup/restore engine and never falls back to the migration executor.

### Legacy custom full archives

The earlier custom `manubisguard-full-*.zip` format under `/opt/manubisguard/backup/full/` is no longer the standard backup format. Existing archives are preserved, but they require explicit compatibility verification and must not be assumed compatible with the original native restore engine.

## 🗄️ PostgreSQL & TimescaleDB

The supported runtime uses PostgreSQL with TimescaleDB.

The migration architecture includes compatibility handling for:

- PostgreSQL major-version transitions
- TimescaleDB version transitions
- Hypertables
- Continuous aggregates
- Foreign keys
- Sequences
- Identity metadata
- Application migration state

A disposable PostgreSQL 17 / TimescaleDB 2.30 → PostgreSQL 16 / TimescaleDB 2.29 portable bridge E2E has been validated with durable counts and continuous-aggregate data.

The production database is not modified by disposable/local migration tests.

---

## 🧰 Native Manubis CLI

The Panel provides the `manubis` host CLI for lifecycle and restore operations.

Common commands:

```bash
sudo manubis status
sudo manubis start
sudo manubis stop
sudo manubis restart
sudo manubis logs
sudo manubis update
sudo manubis edit-env
```

### Standard backup and restore commands

```bash
sudo manubis backup
sudo manubis backup-db
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

System archives use `/opt/manubisguard/backup/`; database-only exports use `/opt/manubisguard/backup/database/`. The ordinary restore command uses the paired native PasarGuard engine adapted for ManubisGuard; `manubis migrate` is reserved for intentional cross-panel migration.

Restore is a state-changing operation. `--check` is the read-only preflight, not a rollback guarantee. Before restoring, verify the archive, make an independent backup of the destination, and test the archive on a disposable host. Fresh recovery with `--fresh` requires an empty destination and recovery metadata with pinned images. The former custom `/full/` archive format is legacy and is not interchangeable without explicit compatibility verification.

### Temporary admin key

The current Panel CLI entrypoint is:

```text
/code/manubisguard-cli.py
```

Generate a temporary admin key with:

```bash
docker exec manubisguard-panel-manubisguard-1 python /code/manubisguard-cli.py generate-temp-key
```

Never commit or publish generated keys.

---

## 🚀 Installation

### One-command installer

The installer is included in the repository.

A source-based installation can be started with:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh)" @ install --database timescaledb
```

The installer prepares the runtime, persistent directories, secrets, database, migrations and health checks according to the selected installation options.

### SSL installation modes

The installer supports documented SSL modes including:

- Let's Encrypt for a domain
- Server-IP certificate with IP SAN
- Custom certificate and private key
- HTTP/no-SSL installation

Examples:

```bash
# Domain certificate
--ssl-mode domain --ssl-domain panel.example.com

# IP certificate
--ssl-mode ip

# No SSL
--ssl-mode none --yes
```

The interactive SSL wizard reads terminal input from `/dev/tty` so it can be used with the documented remote installation flow.

For Let's Encrypt domain installs, the installer explicitly uses a certificate lineage named after the requested domain (for example, `de.qoqnusradio.top`). This keeps unrelated certificates already present on the host (such as an IP/service certificate) from being selected for expansion or replacement. The installer does not delete unrelated Certbot lineages.

---

## 🛰️ Matching ManubisGuard Node

Install the matching Node from:

[ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)

Example:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh)" @ install
```

The Node installer provides the interactive configuration for service port, API key, TLS/certificate mode and transport.

For AmneziaWG runtime preparation it can provision the required host-side components, including kernel headers, DKMS/build prerequisites, AmneziaWG tooling and native-interface validation.

---

## 🔄 Runtime Source of Truth

Core and Host runtime state uses PostgreSQL as the primary source of truth.

NATS/KV runtime state is retained as a fallback when database refresh fails.

This protects current database Core type, AWG metadata and prepared subscription/Host state from being silently replaced by stale runtime snapshots.

The subscription/runtime path has regression coverage around stale Core state, database reloads, HostManager reloads and native AWG rendering.

---

## 🧪 Testing & Validation

ManubisGuard uses layered validation instead of treating container startup as the only quality signal.

Validation areas include:

- Python regression tests
- Migration tests
- Backup/restore security tests
- Domain/SSL tests
- Node synchronization tests
- Frontend TypeScript validation
- Vite production builds
- Docker image builds
- Runtime health checks
- Ruff checks/formatting
- `git diff --check`
- Disposable PostgreSQL/TimescaleDB migration E2E
- AmneziaWG external handshake validation in TEST

Detailed milestones and execution evidence are maintained in `TODO.md`.

---

## 🐳 Docker

A source-based deployment can be built and started with:

```bash
cd /path/to/ManubisGuard-Panel
docker compose --env-file .env up -d --build
```

Verify the runtime with:

```bash
docker ps
curl -k https://your-domain.example/health
```

Expected health response:

```json
{"status":"ok"}
```

Use the deployment files in the selected branch as the source of truth for the exact service names and environment variables of that revision.

---

## 🔒 Security Principles

- Never commit real secrets, API keys, private keys or certificates.
- Telegram bot tokens are encrypted at rest where configured.
- Sensitive tokens are excluded from API responses.
- Sensitive values are not intentionally written to logs.
- Native restore preflight is read-only; applying a restore can change files and database state.
- Keep an independent destination backup and perform a disposable-host restore drill before production recovery.
- A successful archive check is not proof of a complete application-level recovery.
- Backup deployment configuration is not blindly imported.
- RBAC is preserved across administrative workflows.
- Destructive operations are separated from non-destructive validation.

---

## 📁 Canonical Paths

```text
/opt/manubisguard-panel
/opt/manubisguard/backup/
/var/lib/manubisguard/
/var/lib/manubisguard/migration/
/var/lib/manubisguard/certs/
```

Legacy paths such as `/var/lib/pasarguard` may appear in migration/reference material but are not the canonical ManubisGuard runtime paths.

---

## 📌 Development Status

The current development line includes completed implementation work across:

- Command Center dashboard
- Theme system
- Nodes & Cores workspace
- Multi-Core WireGuard/AmneziaWG runtime
- Hosts & Groups workspace
- Users, Templates and Bulk operations
- Reseller Admins / Admin Roles / RBAC
- API Keys
- Backup and restore workflows
- Backup scheduling and retention
- Native system backup/restore through the paired upstream engine; cross-panel migration remains separate
- Restore is a state-changing operation; isolated end-to-end recovery validation remains pending
- PostgreSQL / TimescaleDB migration bridge
- Domain management foundation
- Certificate lifecycle
- Managed certificate deployment and rollback
- Domains & SSL UI lifecycle
- Reality SNI intelligence
- Native `manubis` CLI
- SSL installer workflow
- AmneziaWG runtime and subscription validation
- PostgreSQL source-of-truth runtime hardening

Some operational actions remain intentionally environment-dependent, such as real ACME issuance, real Cloudflare DNS mutations, destructive production restore/cutover and live multi-Node/multi-Core E2E validation.

See `TODO.md` for the authoritative development checkpoints and remaining gates.

---

## 🤝 Contributing

Contributions are welcome.

Useful contribution areas include:

- Bug reports
- Reproduction cases
- Tests
- Documentation
- UI improvements
- Networking integrations
- Migration compatibility
- Backup/restore validation
- API improvements
- Developer tooling

Before opening a PR, review the repository's current contribution guidance and `TODO.md`.

---

## 📚 Project Links

- Panel: https://github.com/ManubisGuard/ManubisGuard-Panel
- Node: https://github.com/ManubisGuard/ManubisGuard-Node
- Upstream Panel: https://github.com/PasarGuard/panel
- Upstream Node: https://github.com/PasarGuard/node
- Issues: https://github.com/ManubisGuard/ManubisGuard-Panel/issues
- Discussions: https://github.com/ManubisGuard/ManubisGuard-Panel/discussions

---

<a id="فارسی"></a>

# 🇮🇷 فارسی

## ManubisGuard Panel چیست؟

**ManubisGuard Panel** یک Control Plane متن‌باز و Self-hosted برای مدیریت زیرساخت‌های مدرن شبکه است.

این پنل مدیریت مواردی مانند کاربران، Nodeها، Coreها، Hostها، Groupها، Subscriptionها، پروتکل‌های شبکه، Domain، SSL/TLS، Backup، Restore، Migration، API و تنظیمات عملیاتی را در یک رابط یکپارچه فراهم می‌کند.

معماری پروژه بر پایه **Panel + Node** است و هدف آن فقط ساخت کانفیگ یک پروتکل نیست؛ بلکه مدیریت کل زیرساخت شبکه است.

### این پروژه Fork کدام پنل است؟

ManubisGuard Panel بر پایه کدبیس **PasarGuard Panel** توسعه داده شده است.

- **Upstream Panel:** [PasarGuard/panel](https://github.com/PasarGuard/panel)
- **ManubisGuard Panel:** [ManubisGuard/ManubisGuard-Panel](https://github.com/ManubisGuard/ManubisGuard-Panel)
- **Matching Node:** [ManubisGuard/ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)

در کنار حفظ بخش‌های لازم از سازگاری Upstream، قابلیت‌ها و معماری‌های اختصاصی ManubisGuard روی این پایه توسعه داده شده‌اند.

---

## ✨ قابلیت‌های اصلی

### پلتفرم

- داشبورد Command Center
- معماری Panel + Node
- مدیریت چند Node
- معماری Multi-Core
- مدیریت کاربران
- Groups
- Hosts
- Templates
- Bulk Operations
- Statistics و Traffic Monitoring
- Subscription Generation
- API Keys
- Reseller Admins
- Admin Roles و RBAC
- Docker / Docker Compose
- PostgreSQL / TimescaleDB
- Health Check و ابزارهای عملیاتی

### شبکه و پروتکل‌ها

- WireGuard
- AmneziaWG
- Xray
- اجرای چند Core از نوع WireGuard/AmneziaWG روی یک Node
- همگام‌سازی Node و Core
- Peer Synchronization
- تولید Native کانفیگ WireGuard / AmneziaWG
- پارامترهای AWG شامل `Jc`، `Jmin`، `Jmax`، `S1-S4` و `H1-H4`
- حفظ PersistentKeepalive
- تولید Subscription سازگار با AWG
- مدیریت Metadata و Runtime State مربوط به Core

### Domain و SSL

- Managed Domains
- چند Domain روی یک Node
- Primary Domain
- اتصال Domain به Node
- اعتبارسنجی Domain
- Certificate Metadata
- Let's Encrypt
- نصب Certificate موجود
- چرخه Renewal
- Expiration Tracking
- Renewal Attempts
- Next Renewal
- خطاهای Certificate
- Deployment Status
- Deploy / Re-deploy دستی
- TLS Serving Control
- Xray TLS Materialization
- Multi-domain TLS/SNI
- ثبت خطای Deployment
- Rollback در صورت شکست اعمال Certificate
- Reality SNI Discovery
- اعتبارسنجی SNI
- Auto Select Best SNI
- رتبه‌بندی Candidateها بر اساس Latency
- اعتبارسنجی SNI Override

### Backup / Restore / Migration

- بکاپ و بازیابی استاندارد سیستم با موتور اصلی و جفت‌شدهٔ PasarGuard، سازگارشده برای ManubisGuard
- مسیر اصلی آرشیوها: `/opt/manubisguard/backup/`
- بکاپ دیتابیس‌تنها و API پنل جداگانه در `/opt/manubisguard/backup/database/`
- بررسی صحت آرشیو و سازگاری نسخه دیتابیس با موتور اصلی
- فرمان مستقل `manubis migrate` برای مهاجرت عمدی بین پنل‌ها؛ Restore معمولی هرگز به Migration هدایت نمی‌شود
- تنظیمات AWG ذخیره‌شده در دیتابیس پنل داخل بکاپ دیتابیس قرار می‌گیرد؛ وضعیت اجرایی نودهای خارجی نیازمند بکاپ مستقل و تأییدشده است

### امنیت

- Authentication و RBAC
- Permission بر اساس Resource/Action
- کنترل دسترسی Node/Core
- محافظت از Backup/Restore
- API Access Control
- رمزنگاری Token تلگرام در محل ذخیره‌سازی
- عدم بازگرداندن Secretهای حساس در API
- عدم ثبت عمدی Secret/Private Key در Log
- پیش‌بررسی آرشیو Native Restore فقط‌خواندنی است؛ اجرای Restore می‌تواند فایل‌ها و دیتابیس را تغییر دهد.
- قبل از بازیابی Production، بکاپ مستقل مقصد و تست روی سرور آزمایشی لازم است.

---

## 🖥️ داشبورد Command Center

Dashboard به جای یک صفحه ساده آمار، به شکل یک **Command Center عملیاتی** طراحی شده است.

مواردی که در آن قابل مشاهده است:

- تعداد کاربران آنلاین و کل کاربران
- Traffic شبکه
- CPU
- RAM
- Disk
- Health سیستم
- وضعیت کاربران
- Quick Actions
- Nodeها
- Userها
- Groupها

ساختار اصلی Navigation:

```text
Dashboard

Users
Statistics

Nodes & Cores
├── Nodes
├── Cores
├── WireGuard
└── Logs

Hosts & Groups
├── Hosts
└── Groups

Reseller
├── Admins
└── Admin Roles

API Keys
Templates
Bulk

Settings
├── General
├── Domains & SSL
├── Backup & Restore
├── Theme
└── سایر تنظیمات
```

---

## 🎨 سیستم Theme

ManubisGuard دارای Theme System قابل تنظیم و Dark-native است.

موارد قابل تنظیم:

- Primary Color
- Secondary Color
- Accent Color
- Background
- Surface
- Border
- Glow Intensity
- Glass Intensity
- Border Intensity
- Shadow Intensity
- Chart Glow
- Background Grid
- Ambient Effects
- Animation Intensity
- UI Density

Presetها:

- Cyber Pulse
- Midnight Violet
- Neon Ocean
- Aurora
- Quantum
- Obsidian

برای کاربرانی که حرکت کمتر را ترجیح می‌دهند، Reduced Motion نیز در نظر گرفته شده است.

---

## 🌐 Node، Core و Multi-Core

هر Node می‌تواند به چند Core Configuration متصل شود.

### WireGuard / AmneziaWG

چند Core از نوع WireGuard و AmneziaWG می‌توانند به صورت همزمان روی یک Node اجرا شوند و بر اساس Interface مدیریت شوند.

برای سازگاری، مدل قدیمی `core_config_id` حفظ شده و در کنار آن `core_config_ids` برای Multi-Core استفاده می‌شود.

### Xray

Xray به یک Core Configuration در هر Node محدود است، چون Runtime مربوط به Xray از یک Process برای Inboundهای Xray استفاده می‌کند.

### Synchronization

همگام‌سازی Core تا حد امکان به صورت Additive انجام می‌شود تا اضافه کردن یک Core سازگار باعث توقف غیرضروری Coreهای در حال اجرا نشود.

---

## 🛡️ AmneziaWG

AmneziaWG یکی از مسیرهای اصلی Networking در Branch فعلی است.

موارد پشتیبانی‌شده شامل:

- Metadata مربوط به AWG
- `Jc`
- `Jmin` / `Jmax`
- `S1-S4`
- `H1-H4`
- Native AWG Interface
- AWG-aware Subscription Generation
- Peer Synchronization
- Public Key / Peer Mapping
- Native WireGuard/AWG Config Rendering
- آماده‌سازی Runtime روی Host
- AmneziaWG Tools
- Kernel/DKMS Preparation
- Native Interface Validation

در محیط TEST، اتصال واقعی خارجی AmneziaWG نیز با بررسی Peer Mapping، Endpoint، UDP Traffic، Handshake و RX/TX validation شده است.

محیط TEST و Production از یکدیگر جدا در نظر گرفته می‌شوند و PASS شدن TEST به معنی تغییر یا تأیید Production نیست.

> **نکته:** تمرکز فعلی پروژه روی **AmneziaWG 2.x و Runtime تأییدشده پروژه** است. سازگاری با AWG3 نباید بدون تست و مستندات صریح فرض شود.

---

## 👥 Users، Groups، Hosts و Templates

پنل برای مدیریت موارد زیر Workflow دارد:

- Users
- User Templates
- Groups
- Hosts
- Bulk Operations
- Statistics
- Node/Core Assignments
- Subscription Configuration

---

## 🔑 API Keys و Automation

پنل دارای مدیریت API Key برای Integration و Automation است.

API از State رابط گرافیکی جدا بوده و تحت مدل Authentication/Authorization پروژه کار می‌کند.

برای Automation باید API Contract و Permissionهای نسخه Deploy شده بررسی شود.

---

## 🔐 Reseller و RBAC

قابلیت‌های دسترسی شامل:

- Admin Management
- Reseller Admins
- Admin Roles
- Resource/Action Permissions
- Settings Permission Gating
- Backup/Restore Authorization
- Node/Core Permission Checks
- API Access Controls

---

## 🌍 Domain و SSL

بخش Domains & SSL چرخه مدیریت Domain و Certificate را پوشش می‌دهد.

### Domain

- Managed Domains
- چند Domain روی یک Node
- Primary Domain
- Domain-to-Node Association
- Domain Validation

### Certificate

- Let's Encrypt
- نصب Certificate موجود
- Certificate Metadata
- Expiration
- Renewal Attempts
- Next Renewal
- Error State
- Deploy / Re-deploy
- TLS Serving Control

### Xray TLS

Certificateهای Managed می‌توانند از مسیر Runtime معتبر Xray به Configuration مربوطه تزریق شوند.

موارد پوشش داده‌شده:

- Multi-domain TLS/SNI
- Deployment Metadata
- Error Recording
- Rollback در صورت شکست اعمال Runtime

Private Key از API برگردانده نمی‌شود و پس از Submission موفق از State فرم مربوطه پاک می‌شود.

### Reality SNI

- SNI Discovery
- SNI Validation
- Auto Select Best SNI
- Latency Ranking
- SNI Override Validation
- Persistence-safe Selection

Auto Select، Candidateهای SNI را در برابر Target فعلی Reality بررسی می‌کند و Target را بدون منطق مشخص جایگزین نمی‌کند.

---

## 💾 Backup، Restore و Migration

بکاپ و بازیابی استاندارد سیستم از موتور اصلی و جفت‌شدهٔ PasarGuard استفاده می‌کند که برای نام‌ها و مسیرهای ManubisGuard سازگار شده است. آرشیو استاندارد سیستم از خروجی دیتابیس‌تنها و مهاجرت بین پنل‌ها جدا است.

### بکاپ و بازیابی استاندارد سیستم

```bash
sudo manubis backup
sudo manubis restore
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

- آرشیوهای سیستم در مسیر `/opt/manubisguard/backup/` ذخیره می‌شوند.
- آرشیو شامل تنظیمات برنامه، فایل‌های پایدار و خروجی سازگار دیتابیس به همراه بررسی‌های صحت و اطلاعات نسخه از موتور اصلی است.
- `--check` فقط آرشیو را بررسی می‌کند و نباید سرویس‌ها را تغییر دهد.
- `--fresh` فقط برای سرور جدید با مسیرهای برنامه/داده خالی و آرشیو دارای metadata بازیابی و image reference قابل استفاده است. آرشیوهای قدیمی فاقد این metadata به نصب سازگار موجود نیاز دارند.
- کلید ساختاری `pasarguard_data/` داخل فرمت آرشیو برای سازگاری حفظ می‌شود.
- آرشیوها ممکن است Secret و Private Key داشته باشند؛ دسترسی را محدود و نسخه خارج از سرور را رمزنگاری کنید.

### خروجی دیتابیس‌تنها و API پنل

```bash
sudo manubis backup-db
```

خروجی دیتابیس‌تنها و API پنل در `/opt/manubisguard/backup/database/` باقی می‌مانند. این فایل‌ها بکاپ کامل سیستم نیستند و نباید به‌عنوان آرشیو native سیستم به Restore داده شوند.

### مهاجرت مستقل بین پنل‌ها

```bash
sudo manubis migrate /path/to/source-archive.zip --apply
```

از Migration فقط برای وارد کردن عمدی داده از پنل دیگر استفاده کنید. فرمان معمولی `manubis restore` از موتور بکاپ/بازیابی native استفاده می‌کند و هرگز به Migration منتقل نمی‌شود.

### آرشیوهای سفارشی قدیمی

فرمت سفارشی قبلی `manubisguard-full-*.zip` در مسیر `/opt/manubisguard/backup/full/` دیگر فرمت استاندارد بکاپ نیست. آرشیوهای موجود حذف نمی‌شوند، اما پیش از استفاده باید سازگاری آن‌ها جداگانه تأیید شود.

## 🗄️ PostgreSQL و TimescaleDB

Runtime پشتیبانی‌شده بر پایه PostgreSQL و TimescaleDB است.

Migration Layer برای موارد زیر منطق Compatibility دارد:

- PostgreSQL Major Versions
- TimescaleDB Versions
- Hypertables
- Continuous Aggregates
- Foreign Keys
- Sequences
- Identity Metadata
- Application Migration State

یک Portable Bridge تستی از PostgreSQL 17 / TimescaleDB 2.30 به PostgreSQL 16 / TimescaleDB 2.29 در محیط Disposable با بررسی Counts و Continuous Aggregate data اعتبارسنجی شده است.

تست‌های Disposable/Local دیتابیس Production را تغییر نمی‌دهند.

---

## 🧰 Manubis CLI

CLI میزبان با نام `manubis` برای مدیریت Lifecycle و Restore ارائه شده است.

```bash
sudo manubis status
sudo manubis start
sudo manubis stop
sudo manubis restart
sudo manubis logs
sudo manubis update
sudo manubis edit-env
```

### فرمان‌های استاندارد بکاپ و بازیابی

```bash
sudo manubis backup
sudo manubis backup-db
sudo manubis restore /path/to/backup.zip --check
sudo manubis restore /path/to/backup.zip
sudo manubis restore --fresh /path/to/backup.zip
sudo manubis backup-service
```

آرشیوهای سیستم در `/opt/manubisguard/backup/` و خروجی دیتابیس‌تنها در `/opt/manubisguard/backup/database/` ذخیره می‌شوند. فرمان Restore از موتور اصلی PasarGuard سازگارشده برای ManubisGuard استفاده می‌کند؛ `manubis migrate` فقط برای مهاجرت عمدی بین پنل‌ها است.

Restore عملیاتی تغییردهنده است. `--check` فقط پیش‌بررسی خواندنی است و تضمین Rollback محسوب نمی‌شود. قبل از Restore، آرشیو را بررسی کنید، از مقصد یک بکاپ مستقل بگیرید و آرشیو را روی سرور آزمایشی جداگانه امتحان کنید. بازیابی تازه با `--fresh` به مقصد خالی و آرشیو دارای metadata بازیابی و imageهای پین‌شده نیاز دارد. فرمت سفارشی قدیمی `/full/` با فرمت native قابل‌تعویض فرض نمی‌شود؛ سازگاری آن باید جداگانه بررسی شود.

### Temporary Admin Key

Entrypoint فعلی CLI پنل:

```text
/code/manubisguard-cli.py
```

ساخت Temporary Key:

```bash
docker exec manubisguard-panel-manubisguard-1 python /code/manubisguard-cli.py generate-temp-key
```

Keyهای تولیدشده را Commit یا منتشر نکنید.

---

## 🚀 نصب

### نصب یک‌دستوری

Installer داخل Repository قرار دارد.

نمونه نصب Source-based:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh)" @ install --database timescaledb
```

Installer بر اساس Optionهای انتخاب‌شده Runtime، Directoryهای دائمی، Secretها، Database، Migration و Health Check را آماده می‌کند.

### حالت‌های SSL

Installer حالت‌های زیر را پوشش می‌دهد:

- Let's Encrypt برای Domain
- Certificate بر اساس IP با IP SAN
- Custom Certificate + Private Key
- HTTP / بدون SSL

نمونه:

```bash
--ssl-mode domain --ssl-domain panel.example.com
--ssl-mode ip
--ssl-mode none --yes
```

Wizard تعاملی SSL از `/dev/tty` برای دریافت Input استفاده می‌کند تا با روش نصب Remote نیز قابل استفاده باشد.

---

## 🛰️ ManubisGuard Node

Node هماهنگ با Panel:

[ManubisGuard-Node](https://github.com/ManubisGuard/ManubisGuard-Node)

نمونه نصب:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh)" @ install
```

Node Installer تنظیماتی مانند Port، API Key، TLS/Certificate و Transport را دریافت می‌کند.

برای Runtime مربوط به AmneziaWG نیز می‌تواند اجزای لازم Host از جمله Kernel Headers، DKMS/Build prerequisites، AWG tools و Native Interface validation را آماده کند.

---

## 🔄 Source of Truth در Runtime

PostgreSQL Source of Truth اصلی برای Core و Host Runtime State است.

NATS/KV در صورت شکست Refresh از Database به عنوان Fallback نگه داشته می‌شود.

این مدل از جایگزین شدن State فعلی Database با Snapshotهای قدیمی جلوگیری می‌کند و برای Core Type، AWG Metadata و Subscription/Host State اهمیت دارد.

---

## 🧪 تست و Validation

پروژه فقط به بالا آمدن Container اکتفا نمی‌کند.

لایه‌های Validation شامل:

- Python Regression Tests
- Migration Tests
- Backup/Restore Security Tests
- Domain/SSL Tests
- Node Synchronization Tests
- TypeScript Validation
- Vite Production Build
- Docker Image Build
- Runtime Health Checks
- Ruff
- `git diff --check`
- PostgreSQL/TimescaleDB Disposable E2E
- AmneziaWG External Handshake Validation در TEST

جزئیات Checkpointها و شواهد تست در `TODO.md` نگهداری می‌شوند.

---

## 🐳 Docker

نمونه اجرای Source-based:

```bash
cd /path/to/ManubisGuard-Panel
docker compose --env-file .env up -d --build
```

بررسی Runtime:

```bash
docker ps
curl -k https://your-domain.example/health
```

پاسخ Health مورد انتظار:

```json
{"status":"ok"}
```

نام دقیق Serviceها و Environment Variableها را از فایل‌های همان Branch به عنوان Source of Truth بررسی کنید.

---

## 🔒 اصول امنیتی

- Secret، API Key، Private Key و Certificate واقعی را Commit نکنید.
- Telegram Token در صورت فعال بودن قابلیت مربوطه به صورت رمزنگاری‌شده نگهداری می‌شود.
- Secretهای حساس در API Response بازگردانده نمی‌شوند.
- مقدارهای حساس عمداً در Log ثبت نمی‌شوند.
- پیش‌بررسی آرشیو Restore قبل از اعمال تغییرات
- فرمان Restore بومی از Migration بین پنل‌ها جدا است.
- آرشیوها ممکن است Secret و Private Key داشته باشند؛ دسترسی و نگهداری آن‌ها باید محدود باشد.
- فایل‌های Deployment مقصد نباید بدون بررسی و تأیید کورکورانه جایگزین شوند.
- RBAC در Workflowهای مدیریتی حفظ می‌شود.
- Validation غیرمخرب از عملیات مخرب جدا شده است.

---

## 📁 مسیرهای اصلی

```text
/opt/manubisguard-panel
/opt/manubisguard/backup/
/var/lib/manubisguard/
/var/lib/manubisguard/migration/
/var/lib/manubisguard/certs/
```

شناسه‌های ساختاری آرشیوهای قدیمی PasarGuard در صورت نیاز برای سازگاری حفظ می‌شوند؛ مسیرهای اجرای فعلی از مسیرهای ManubisGuard بالا استفاده می‌کنند.

---

## 📌 وضعیت توسعه

در خط توسعه فعلی، کار روی بخش‌های زیر انجام شده است:

- Command Center Dashboard
- Theme System
- Nodes & Cores
- Multi-Core WireGuard/AmneziaWG
- Hosts & Groups
- Users / Templates / Bulk
- Reseller Admins / Admin Roles / RBAC
- API Keys
- Backup / Restore
- Backup Scheduling / Retention
- Native backup/restore بر پایه موتور اصلی PasarGuard با مسیرهای ManubisGuard
- Cross-panel migration به‌صورت فرمان مستقل
- PostgreSQL / TimescaleDB Migration Bridge
- Domain Management
- Certificate Lifecycle
- Managed Certificate Deployment / Rollback
- Domains & SSL UI
- Reality SNI Intelligence
- Native `manubis` CLI
- SSL Installer
- AmneziaWG Runtime / Subscription Validation
- PostgreSQL Source-of-Truth Hardening

برخی عملیات همچنان به شرایط واقعی محیط وابسته هستند؛ از جمله ACME واقعی، تغییر واقعی Cloudflare DNS، Production Restore/Cutover مخرب و E2E زنده چند Node/Multi-Core.

مرجع اصلی Checkpointها و موارد باقی‌مانده `TODO.md` است.

---

## 🤝 مشارکت

Contributionها استقبال می‌شوند.

زمینه‌های مفید:

- Bug Reports
- Reproduction Cases
- Tests
- Documentation
- UI Improvements
- Networking Integrations
- Migration Compatibility
- Backup/Restore Validation
- API Improvements
- Developer Tooling

قبل از PR، راهنمای Contribution و `TODO.md` را بررسی کنید.

---

## 📚 لینک‌های پروژه

- Panel: https://github.com/ManubisGuard/ManubisGuard-Panel
- Node: https://github.com/ManubisGuard/ManubisGuard-Node
- Upstream Panel: https://github.com/PasarGuard/panel
- Upstream Node: https://github.com/PasarGuard/node
- Issues: https://github.com/ManubisGuard/ManubisGuard-Panel/issues
- Discussions: https://github.com/ManubisGuard/ManubisGuard-Panel/discussions
