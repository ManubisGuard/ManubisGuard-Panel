# ManubisGuard Panel

**ManubisGuard Panel** is a modern, AmneziaWG-enabled management panel for managing users, nodes, cores, hosts, groups, networking, domains, TLS certificates, backups, restores and operational settings from a unified web interface.

> Current development branch: `feature/amnezia-wg`

ManubisGuard is maintained as a PasarGuard-compatible fork. Existing upstream-compatible CLI arguments, installation flow and operational behavior are preserved where required, while ManubisGuard-specific features and branding are added on top.

---

## ✨ Highlights

- Modern dark Command Center dashboard
- AmneziaWG and WireGuard support
- Multiple Core configurations per Node
- Nodes, Cores, WireGuard and Logs in one navigation workspace
- Hosts and Groups in one tabbed workspace
- Users, Statistics, Templates, Bulk operations and API Keys
- Reseller Admins and Admin Roles
- Domains & SSL lifecycle management
- Let's Encrypt and existing certificate workflows
- Xray TLS/SNI and Reality SNI intelligence
- Backup, scheduling, retention and restore workflows
- Native Manubis CLI
- PostgreSQL / TimescaleDB runtime
- PasarGuard-family backup compatibility
- MariaDB/MySQL to PostgreSQL restore bridge
- Migration validation, staging restore and rollback safety
- RBAC-aware frontend and backend APIs
- Dark glass/cyber theme customization
- Docker/Compose based deployment
- Health checks and production-oriented validation

---

## 🖥️ Dashboard & UI

The dashboard has been redesigned as a **Command Center** rather than a simple statistics page.

It provides:

- Online and total user status
- Network traffic visibility
- CPU load and system resources
- Memory and disk visibility
- Platform health/status
- User state overview
- Quick actions for creating users and opening Nodes, Users and Groups
- Dense operational cards designed for administration workflows

### Navigation

The current navigation is organized around operational workspaces:

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
└── other Settings tabs
```

The redesign preserves existing routes, permission checks and backend endpoints.

---

## 🎨 Smart Theme System

ManubisGuard includes a configurable dark-native theme system.

### Theme controls

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

### Presets

- Cyber Pulse
- Midnight Violet
- Neon Ocean
- Aurora
- Quantum
- Obsidian

The visual system uses glass surfaces, controlled gradients, depth, glow and cyber-style accents while keeping the interface suitable for dense administration work.

Reduced-motion settings are available for users who prefer lower animation intensity.

---

## 🌐 Nodes, Cores & Networking

The Node workspace supports:

- Node management
- Core configuration management
- WireGuard management
- Node logs
- Node connection state
- Permission-aware actions
- Multiple Core assignments per Node

A Node can retain the legacy single `core_config_id` representation for compatibility while also using `core_config_ids` for multi-Core assignments.

### Multi-Core

The Node runtime supports additive Core assignment.

Multiple WireGuard/AmneziaWG Core instances can run concurrently on the same Node and are tracked by interface.

Xray remains intentionally limited to one Core per Node because the Node runtime uses a single Xray process for Xray inbounds.

---

## 🛡️ AmneziaWG

AmneziaWG is a first-class networking path in the current branch.

The validated runtime includes:

- AmneziaWG Core metadata
- Jc / Jmin / Jmax
- S1-S4
- H1-H4
- Native AWG interface support
- AWG-aware subscription generation
- Node Peer synchronization
- Host runtime installation requirements
- AmneziaWG tools pinning
- Kernel/DKMS runtime preparation

The TEST environment achieved a real external AmneziaWG handshake with:

- Correct generated AWG parameters
- Correct client public-key to Node Peer mapping
- Correct endpoint
- Real UDP packets reaching the Node
- Server replies
- Recent WireGuard/AWG handshake
- Non-zero RX/TX counters

Production/Main is kept separate from TEST validation and is not implicitly changed by a TEST PASS.

---

## 👥 Users, Groups & Hosts

The panel provides administrative workflows for:

- Users
- User templates
- Groups
- Hosts
- Bulk operations
- Statistics
- Node/Core assignments
- Subscription-related configuration

Hosts and Groups are presented as a single tabbed workspace while keeping their existing routes and permission model.

---

## 🔐 Reseller & Access Control

ManubisGuard includes:

- Admin management
- Admin Roles
- Resource/action based permissions
- Settings permission gating
- Backup/restore authorization
- Node/Core permission checks
- API access controls

Sensitive operations remain protected by authentication and RBAC.

---

## 🔑 API Keys

The panel includes API key management for administrative integrations and automation.

API access is kept separate from browser UI state and follows the existing authentication and authorization model.

---

## 🌍 Domains & SSL

The Domains & SSL workspace provides domain and certificate lifecycle management.

Supported functionality includes:

- Managed domains
- Multiple domains per Node
- Primary domain handling
- Domain-to-Node association
- Domain validation
- Certificate metadata
- Let's Encrypt certificate issuance
- Existing certificate installation
- Certificate renewal lifecycle
- Expiration tracking
- Renewal attempts
- Next-renewal information
- Certificate error state
- Deployment status
- Manual Deploy / Re-deploy
- TLS serving controls
- Xray TLS materialization
- Multi-domain TLS/SNI injection
- Deployment failure recording
- Runtime rollback after failed certificate application

Private-key material is not returned by the API and is cleared from the relevant frontend form state after successful submission.

### Reality SNI intelligence

Reality tooling includes:

- SNI discovery
- SNI candidate validation
- Auto Select Best SNI
- Latency-based candidate ranking
- SNI override validation
- Persistence-safe selection behavior

The Auto Select flow tests SNI candidates against the existing Reality target rather than replacing the target itself.

---

## 💾 Backup & Restore

Backup and restore is implemented as a safety-first operational workflow.

### Backup

Supported functionality includes:

- Manual backup creation
- Backup history
- ZIP download
- Backup upload
- Backup validation
- Backup retention
- Daily, weekly and monthly schedules
- Configurable retention count
- Opt-in scheduler
- Telegram notification configuration
- Encrypted Telegram token storage
- Secret non-disclosure in API responses and logs

Telegram notification tests use mocks and do not require a real production token.

### Restore

The restore pipeline supports:

- Native ManubisGuard backups
- PasarGuard-family backups
- PostgreSQL backups
- Legacy MariaDB/MySQL backup conversion
- Backup manifest detection
- Safe extraction
- Staging restore
- Schema and row-count validation
- TimescaleDB compatibility handling
- Production safety dumps
- Previous database retention
- Rollback-oriented cutover validation
- Restore logs and operation status

Production restore requires explicit confirmation and uses the validated migration engine rather than directly overwriting the live database.

### Migration safety

The migration architecture validates the backup before production cutover.

It preserves the installed deployment identity and does not blindly import backup deployment files such as:

- `.env`
- `docker-compose.yml`
- Repository/image configuration

The canonical runtime paths are:

```text
/var/lib/manubisguard
/opt/manubisguard/backup/
/var/lib/manubisguard/migration/
```

Legacy PasarGuard runtime paths are not used as ManubisGuard runtime paths.

---

## 🗄️ PostgreSQL & TimescaleDB

The supported installation path uses PostgreSQL 16 with TimescaleDB.

The migration system includes compatibility handling for:

- PostgreSQL major-version transitions
- TimescaleDB version transitions
- Hypertables
- Continuous aggregates
- Foreign keys
- Sequences
- Identity metadata
- Application migration state

A disposable PostgreSQL 17 / TimescaleDB 2.30 to PostgreSQL 16 / TimescaleDB 2.29 portable bridge E2E was validated with matching durable row counts and continuous aggregate data.

---

## 🧰 Native Manubis CLI

After installation, the user-facing host command is:

```bash
sudo manubis status
sudo manubis start
sudo manubis stop
sudo manubis restart
sudo manubis logs
sudo manubis update
sudo manubis edit-env
```

### Restore commands

```bash
sudo manubis restore
sudo manubis restore-check /path/to/backup.zip
```

`manubis restore` discovers available archives from:

```text
/opt/manubisguard/backup/
```

and presents them for selection.

`restore-check` performs non-destructive validation.

The internal migration commands required by the restore engine remain available through the canonical Panel CLI implementation.

### Temporary admin key

The current Panel container CLI entrypoint is:

```text
/code/manubisguard-cli.py
```

Generate a temporary admin key with:

```bash
docker compose exec -T manubisguard \
  python /code/manubisguard-cli.py generate-temp-key
```

Never commit or publish generated keys.

---

## 🚀 Installation

### One-command installation

The installer is included in the repository and supports PostgreSQL/TimescaleDB:



The installer:

1. Prepares Docker/Compose when required
2. Fetches the selected ManubisGuard branch
3. Creates persistent secrets
4. Prepares the runtime directories
5. Installs the restore/migration agent
6. Starts PostgreSQL/TimescaleDB and the Panel
7. Runs database migrations
8. Verifies the health endpoint

The Panel image is built from the selected branch source.

---

## 🔒 SSL / TLS Installer

The interactive installer provides:

1. Let's Encrypt certificate for a domain
2. Server-IP certificate with IP SAN
3. Custom certificate and private key
4. HTTP installation without SSL

### Let's Encrypt

Use the installer with `--ssl-mode domain --ssl-domain panel.example.com`.



### Server-IP certificate

Use the installer with `--ssl-mode ip`.



### No SSL

Use the installer with `--ssl-mode none --yes`.



The interactive SSL wizard is designed to work with the documented `curl | bash` installation flow by reading terminal input from `/dev/tty`.

---

## 🛰️ Node Installation

Install the matching AmneziaWG-enabled ManubisGuard Node:



The Node installer preserves the upstream-compatible interactive workflow for service port, API key, TLS/certificate mode and transport options while installing the ManubisGuard Node implementation.

The host runtime installer provisions the AmneziaWG prerequisites, including:

- Kernel headers
- DKMS/build prerequisites
- AmneziaWG DKMS
- AmneziaWG tools
- Boot-time module loading
- Native AWG interface smoke validation

The validated Node userspace currently uses the AmneziaWG tools line `v3.1.20260812`.

---

## 🔄 Node & Core Runtime Source of Truth

Core and Host runtime state uses PostgreSQL as the primary source of truth.

NATS/KV runtime state is retained as a fallback when database refresh fails.

This prevents stale runtime snapshots from silently overriding current database Core type, AWG metadata or prepared subscription host state.

The subscription/runtime path has regression coverage for stale Core state, database reloads, HostManager reloads and native AWG rendering.

---

## 🧪 Validation & Quality

The project uses layered validation instead of relying only on a successful container startup.

Validated gates include:

- Python regression tests
- Migration tests
- Backup/restore security tests
- Domain/SSL tests
- Node synchronization tests
- Frontend TypeScript checks
- Vite production builds
- Docker image builds
- Runtime health checks
- `bash -n`
- Ruff checks and formatting
- `git diff --check`
- Disposable PostgreSQL/TimescaleDB migration E2E
- Real TEST AmneziaWG external handshake validation

The current branch has passed the documented migration, backup/restore, Domain/SSL and AmneziaWG TEST gates recorded in `TODO.md`.

---

## 🐳 Docker

The production service is named:

```text
manubisguard
```

The database service uses PostgreSQL/TimescaleDB.

A standard source-based deployment is:

```bash
cd /path/to/ManubisGuard-Panel
docker compose --env-file .env up -d --build manubisguard
```

After deployment, verify:

```bash
docker ps
curl -k https://your-domain.example/health
```

Expected health response:

```json
{"status":"ok"}
```

---

## 🔐 Security Principles

ManubisGuard follows several operational safety rules:

- Never commit real secrets, API keys, private keys or certificates
- Telegram bot tokens are encrypted at rest
- Sensitive tokens are excluded from API responses
- Sensitive values are not intentionally written to logs
- Restore validation happens before production cutover
- Production restore requires explicit confirmation
- Production safety dumps are retained for rollback
- Backup deployment configuration is not blindly imported
- RBAC is preserved across administrative workflows
- Destructive operations are separated from non-destructive validation

---

## 📁 Canonical Paths

```text
/opt/manubisguard-panel
/opt/manubisguard/backup/
/var/lib/manubisguard/
/var/lib/manubisguard/migration/
/var/lib/manubisguard/certs/
```

Legacy PasarGuard paths such as `/var/lib/pasarguard` are treated as migration/reference evidence and are not the canonical ManubisGuard runtime paths.

---

## 📌 Current Development Status

### Completed / validated

- Command Center dashboard redesign
- Smart dark theme system
- Navigation/workspace redesign
- Nodes & Cores workspace
- Hosts & Groups workspace
- Backup & Restore UI and backend
- Backup scheduling and retention
- Staging restore
- Production restore safety flow
- PostgreSQL/TimescaleDB migration bridge
- Domain management foundation
- Certificate lifecycle
- Managed certificate deployment and rollback
- Domains & SSL UI lifecycle
- Reality SNI intelligence
- Native `manubis` CLI
- SSL installer wizard
- AmneziaWG runtime and subscription validation
- Multi-Core Node architecture
- PostgreSQL source-of-truth runtime hardening

### Explicitly pending / intentionally deferred

- Server Address semantics for `additional`, `alias` and `both` require an authoritative runtime/subscription contract before implementation.
- Real ACME issuance and real Cloudflare DNS mutations remain operational actions and are not treated as completed by mock tests.
- Full live Panel/Node multi-Core E2E remains a separate validation gate.
- ManubisGuard logo binary replacement and final branding sweep remain pending where noted in `TODO.md`.

---

## 📚 Documentation & Source

Panel repository:

https://github.com/ManubisGuard/ManubisGuard-Panel

Node repository:

https://github.com/ManubisGuard/ManubisGuard-Node

Current Panel branch:

`feature/amnezia-wg`

The detailed execution history, validation evidence and remaining gates are maintained in:

`TODO.md`

---

# 🇮🇷 راهنمای فارسی

## ManubisGuard Panel چیست؟

**ManubisGuard Panel** یک پنل مدیریتی مدرن برای مدیریت کاربران، Nodeها، Coreها، WireGuard/AmneziaWG، Hostها، Groupها، دامنه‌ها، SSL/TLS، Backup/Restore و تنظیمات عملیاتی است.

این پروژه بر پایه Fork سازگار با PasarGuard توسعه داده شده و در کنار قابلیت‌های جدید ManubisGuard، سازگاری رفتاری و ساختاری لازم با CLI و Installer قبلی حفظ شده است.

---

## ✨ قابلیت‌های اصلی

- داشبورد Command Center مدرن
- پشتیبانی از WireGuard و AmneziaWG
- پشتیبانی از چند Core روی یک Node
- مدیریت Nodes، Cores، WireGuard و Logs در یک محیط
- مدیریت Hosts و Groups در یک محیط تب‌دار
- مدیریت Users
- Statistics
- Templates
- Bulk Operations
- API Keys
- Reseller Admins و Admin Roles
- Domains & SSL
- Let's Encrypt
- نصب Certificate موجود
- مدیریت چرخه عمر Certificate
- Reality و هوشمندی SNI
- Backup و Restore
- زمان‌بندی و Retention
- Restore مرحله‌ای و ایمن
- Migration بین PostgreSQL/TimescaleDB
- سازگاری با Backupهای خانواده PasarGuard
- Bridge از MariaDB/MySQL به PostgreSQL
- CLI اختصاصی `manubis`
- RBAC و Permissionهای موجود
- Theme حرفه‌ای Dark/Glass/Cyber
- Docker و Docker Compose
- Health Check و Validation چندلایه

---

## 🖥️ داشبورد Command Center

داشبورد جدید به جای یک صفحه ساده آماری، به عنوان مرکز کنترل عملیاتی طراحی شده است.

موارد اصلی:

- کاربران آنلاین
- تعداد کل کاربران
- Network Traffic
- CPU Load
- CPU / Memory / Disk
- وضعیت Platform
- وضعیت کاربران
- Quick Action برای Create User، Nodes، Users و Groups

هدف این طراحی این است که اطلاعات مهم عملیاتی بدون رفت‌وآمد بین چند صفحه در دسترس باشد.

---

## 🧭 ساختار جدید پنل

ساختار فعلی:

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
└── سایر بخش‌های Settings
```

ساختار جدید بدون حذف Endpointها، Permissionها یا قابلیت‌های قبلی پیاده‌سازی شده است.

---

## 🎨 سیستم Theme هوشمند

سیستم Theme کاملاً قابل تنظیم است.

امکانات:

- Primary
- Secondary
- Accent
- Background
- Surface
- Border
- Glow
- Glass
- Border Intensity
- Shadow Intensity
- Chart Glow
- Grid
- Ambient Effects
- Animation Intensity
- Density

Presetهای آماده:

- Cyber Pulse
- Midnight Violet
- Neon Ocean
- Aurora
- Quantum
- Obsidian

Theme پیش‌فرض بر پایه Dark UI، Glass Surface، Glow کنترل‌شده، Gradientهای محیطی و Cyber Accent طراحی شده است.

---

## 🌐 Nodes، Cores و Multi-Core

در بخش Nodes & Cores:

- مدیریت Node
- مدیریت Core
- WireGuard
- Logs
- وضعیت اتصال
- Permissionهای مربوط به Node/Core
- تخصیص چند Core به یک Node

مدل جدید از `core_config_ids` پشتیبانی می‌کند و برای سازگاری، `core_config_id` قدیمی نیز حفظ شده است.

چند Core از نوع WireGuard/AmneziaWG می‌توانند به صورت همزمان روی یک Node اجرا شوند.

برای Xray همچنان یک Core در هر Node انتخاب می‌شود، چون Runtime مربوط به Xray از یک فرآیند Xray برای Inboundها استفاده می‌کند.

---

## 🛡️ AmneziaWG

AmneziaWG یکی از مسیرهای اصلی Branch فعلی است.

پشتیبانی شامل:

- Jc
- Jmin
- Jmax
- S1 تا S4
- H1 تا H4
- Native AWG Interface
- AWG Subscription
- Peer Synchronization
- Host Runtime
- DKMS
- AWG Tools
- Kernel Module

در محیط TEST یک اتصال واقعی خارجی AmneziaWG با Handshake موفق، Packet واقعی، Reply سرور و RX/TX غیرصفر اعتبارسنجی شده است.

---

## 👥 Users، Hosts و Groups

پنل امکانات مدیریتی زیر را فراهم می‌کند:

- Users
- Groups
- Hosts
- Templates
- Bulk Operations
- Statistics
- Node/Core Assignment
- Subscription configuration

Hosts و Groups در یک Workspace با Tab داخلی قرار گرفته‌اند.

---

## 🔐 Reseller و Permission

سیستم مدیریتی شامل:

- Admins
- Admin Roles
- Resource permissions
- Action permissions
- Settings RBAC
- Backup/Restore authorization
- Node/Core permissions
- API authorization

است.

---

## 🌍 Domains & SSL

بخش Domains & SSL شامل:

- مدیریت Domain
- چند Domain برای یک Node
- Primary Domain
- Domain/Node Association
- Let's Encrypt
- Existing Certificate
- Certificate Renewal
- Expiration Tracking
- Renewal Attempts
- Next Renewal
- Error State
- Deployment Status
- Deploy / Re-deploy
- TLS Serving
- Xray TLS
- Multi-domain SNI
- Deployment Rollback

است.

کلید خصوصی از API برگردانده نمی‌شود و پس از ارسال موفق نیز از State مربوط به فرم Frontend پاک می‌شود.

### Reality SNI

امکانات:

- Discover SNI
- بررسی Candidateها
- Auto Select Best SNI
- رتبه‌بندی بر اساس Latency
- اعتبارسنجی SNI
- Persistence امن

---

## 💾 Backup & Restore

سیستم Backup شامل:

- Manual Backup
- Backup History
- ZIP Download
- Upload
- Validation
- Retention
- Daily / Weekly / Monthly Schedule
- Telegram Notification
- Encryption برای Telegram Token
- جلوگیری از افشای Secret در API و Log

است.

### Restore

Restore از موارد زیر پشتیبانی می‌کند:

- Backup native خود ManubisGuard
- Backupهای PasarGuard-family
- PostgreSQL
- MariaDB/MySQL legacy
- Manifest detection
- Safe extraction
- Staging Restore
- Row-count validation
- Schema validation
- TimescaleDB compatibility
- Safety dump
- Previous database retention
- Rollback validation
- Restore Logs

Restore واقعی Production با تأیید صریح انجام می‌شود و از Migration Engine ایمن استفاده می‌کند.

---

## 🗄️ PostgreSQL و TimescaleDB

Runtime اصلی بر پایه PostgreSQL 16 و TimescaleDB است.

Migration Layer برای موارد زیر تست شده است:

- PostgreSQL major-version migration
- TimescaleDB migration
- Hypertables
- Continuous Aggregates
- Foreign Keys
- Sequences
- Identity metadata
- Alembic state

یک E2E واقعی در محیط Disposable برای انتقال PostgreSQL 17/TimescaleDB 2.30 به PostgreSQL 16/TimescaleDB 2.29 با Portable Bridge با موفقیت انجام شده است.

---

## 🧰 CLI

دستور اصلی روی Host:

```bash
sudo manubis status
sudo manubis start
sudo manubis stop
sudo manubis restart
sudo manubis logs
sudo manubis update
sudo manubis edit-env
```

Restore:

```bash
sudo manubis restore
sudo manubis restore-check /path/to/backup.zip
```

دستور `restore` فایل‌های موجود در:

```text
/opt/manubisguard/backup/
```

را پیدا کرده و امکان انتخاب آن‌ها را می‌دهد.

### Temporary Admin Key

Entry point فعلی:

```text
/code/manubisguard-cli.py
```

دستور:

```bash
docker compose exec -T manubisguard \
  python /code/manubisguard-cli.py generate-temp-key
```

کلید تولیدشده نباید در GitHub یا فایل‌های پروژه ذخیره شود.

---

## 🚀 نصب پنل



Installer:

1. Docker/Compose را آماده می‌کند
2. Branch انتخاب‌شده را دریافت می‌کند
3. Secretهای Persistent ایجاد می‌کند
4. Runtime directoryها را آماده می‌کند
5. Migration/Restore Agent را نصب می‌کند
6. Panel و TimescaleDB را اجرا می‌کند
7. Migrationها را اجرا می‌کند
8. Health Endpoint را بررسی می‌کند

---

## 🔒 نصب SSL

Installer چهار حالت دارد:

1. Let's Encrypt
2. Server IP Certificate
3. Custom Certificate
4. بدون SSL

مثال:

```bash
# Let's Encrypt
--ssl-mode domain --ssl-domain panel.example.com

# IP certificate
--ssl-mode ip

# بدون SSL
--ssl-mode none --yes
```

Wizard تعاملی SSL برای حالت `curl | bash` نیز اصلاح شده و ورودی را از `/dev/tty` دریافت می‌کند.

---

## 🛰️ نصب Node



Node Installer سازگاری Workflow تعاملی upstream را حفظ می‌کند و تنظیمات Port، API Key، TLS/Certificate و Transport را دریافت می‌کند.

برای AmneziaWG نیز Runtime لازم شامل DKMS، Kernel Headers، Tools و Module loading آماده می‌شود.

---

## 🔄 Source of Truth

PostgreSQL منبع اصلی وضعیت Core و Host Runtime است.

NATS/KV فقط زمانی به عنوان Fallback استفاده می‌شود که Refresh از DB با خطا مواجه شود.

این معماری جلوی برگشت State قدیمی WireGuard/AmneziaWG یا Host Subscription را می‌گیرد.

---

## 🧪 تست و Validation

پروژه با چند لایه Validation توسعه داده می‌شود:

- Python Tests
- Migration Tests
- Backup/Restore Security Tests
- Domain/SSL Tests
- Node Sync Tests
- TypeScript
- Vite Production Build
- Docker Build
- Runtime Health
- bash syntax
- Ruff
- git diff check
- Disposable PostgreSQL/TimescaleDB E2E
- Real TEST AmneziaWG Handshake

جزئیات کامل PASSها و Gateهای باقی‌مانده در `TODO.md` نگهداری می‌شود.

---

## 🔐 اصول امنیتی

- Secret واقعی در Git commit نمی‌شود
- Telegram Token به صورت encrypted ذخیره می‌شود
- Token حساس در API Response نمایش داده نمی‌شود
- Restore قبل از Cutover اعتبارسنجی می‌شود
- Production Restore نیازمند تأیید صریح است
- Safety Dump قبل از عملیات حساس ایجاد می‌شود
- Database قبلی برای Rollback حفظ می‌شود
- فایل‌های deployment داخل Backup کورکورانه Import نمی‌شوند
- RBAC در مسیرهای مدیریتی حفظ شده است

---

## 📌 وضعیت فعلی

### تکمیل‌شده و اعتبارسنجی‌شده

- Command Center
- Theme هوشمند
- Navigation جدید
- Nodes & Cores
- Hosts & Groups
- Backup & Restore
- Scheduling و Retention
- Staging Restore
- Production Restore Safety
- PostgreSQL/TimescaleDB Migration
- Domain Management
- Certificate Lifecycle
- Managed TLS Deployment
- Domains & SSL UI
- Reality SNI Intelligence
- `manubis` CLI
- SSL Installer
- AmneziaWG Runtime و Subscription
- Multi-Core Node Architecture
- PostgreSQL Runtime Source of Truth

### موارد باز / عمداً Deferred

- semantics مربوط به Server Address برای `additional`، `alias` و `both` تا زمان وجود Contract معتبر Runtime/Subscription.
- صدور واقعی ACME و تغییرات واقعی Cloudflare به عنوان عملیات عملیاتی جداگانه.
- E2E زنده کامل برای Multi-Core بین Panel و Node.
- جایگزینی نهایی Binaryهای Logo و Branding Sweep طبق TODO.

---

## 📚 منبع و مستندات

Panel:

https://github.com/ManubisGuard/ManubisGuard-Panel

Node:

https://github.com/ManubisGuard/ManubisGuard-Node

Branch فعلی:

`feature/amnezia-wg`

تاریخچه کامل تغییرات، تست‌ها، شواهد Validation و کارهای باقی‌مانده:

`TODO.md`
