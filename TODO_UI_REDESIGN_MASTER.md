# ManubisGuard UI Redesign — Master Prompt, TODO & Audit Log

**Created:** 2026-10-24
**Project:** `/opt/manubisguard-panel`
**Frontend:** `/opt/manubisguard-panel/dashboard`
**Branch observed:** `feature/amnezia-wg`
**Reference direction:** cyberpunk security operations console; dark navy/charcoal surfaces, restrained cyan/teal highlights, precise technical typography, compact cards, thin borders, subtle status indicators, high information density without clutter.

> This document is the source of truth for the UI redesign workflow. Work incrementally, one page at a time. Do not attempt a blind, all-at-once rewrite.

---

## 1. Master Prompt — Design and Implement the Entire Panel

Act as a senior product designer, frontend architect, accessibility specialist, and performance-focused UI engineer responsible for the ManubisGuard admin panel.

### Product goal
Transform the existing ManubisGuard dashboard into a distinctive, modern cyber-security control room inspired by the approved visual reference: a dark, precise, futuristic operations console that feels technical and hacker-oriented, but remains professional, readable, responsive, fast, and usable every day. The reference is a visual direction—not permission to invent product capabilities or replace working flows with mock UI.

### Visual language
- Core mood: cyberpunk SOC / network operations terminal / premium hacker console.
- Default dark palette: near-black/navy background, slightly lighter charcoal-blue panels, fine blue-gray borders, restrained cyan/teal active states and key metrics.
- Accent: bright cyan/teal used intentionally for active navigation, primary actions, focus, live state, progress, and selected data—not every icon or every border.
- Optional secondary colors: low-saturation blue, violet, amber, green, and red only where they communicate distinct statuses (e.g. online, warning, error, disabled).
- Typography: clear modern sans-serif, technical labels with controlled letter spacing, readable body text and numerals. Do not make the entire interface tiny or excessively uppercase.
- Shape: consistent compact cards, crisp thin borders, modest corner radius, clean alignment, consistent icon sizes, clear hierarchy, compact but breathable spacing.
- Hacker feel comes from layout, telemetry, status markers, precise grid, restrained signal lines and data visualization—not from visual noise.
- Light mode must remain supported and intentionally designed; do not force dark colors into light mode.
- Use the existing theme system and design tokens wherever possible. Avoid scattered hard-coded colors if a reusable token is appropriate.

### Layout direction
- Rework the information architecture and visual hierarchy, not merely the color palette.
- Dashboard: compact header/search/status/actions; KPI row; system resource cards for CPU/RAM/Disk/network as supported by existing data; platform/uptime state; user-state distribution; traffic/admin summaries where existing data supports them.
- Desktop: purposeful multi-column grid, aligned cards and restrained density.
- Mobile: one-column or compact two-column layout where legible; no horizontal overflow, clipped controls, or tiny touch targets. Reflow navigation and action rows intentionally.
- Reuse real existing API data and established loading/empty/error states. Do not fabricate values, trends, live maps, nodes, or metrics to make the design look impressive.
- Charts, graphs, maps, animated waveforms, glowing backgrounds and decorative visualizations are optional only if supported by real data and existing dependencies. Prefer a small static progress bar or existing chart over adding a new heavyweight charting package.

### Functional preservation — non-negotiable
- Preserve every existing route, tab, button, dropdown, dialog, form, filter, search, pagination action, table action, keyboard interaction, and role/permission restriction unless an explicitly approved requirement says otherwise.
- Do not convert functional controls into decorative mockups. Do not add dead buttons, fake success notifications, hard-coded metrics, or dummy chart data.
- Do not change API contracts, backend behavior, database schema, auth/session behavior, permissions, routing, or business rules as part of a visual-only change.
- Keep validation, destructive-action confirmation, error feedback, loading state, empty state, disabled state, and accessibility behavior intact.
- If an existing control is broken, document it separately with reproduction evidence; do not silently remove it or mask it with design.

### Performance constraints
- Treat load speed and low overhead as acceptance criteria.
- Prefer current dependencies, CSS, SVG icons already installed, and existing component primitives.
- Do not add packages without demonstrating a concrete need and measuring/estimating the bundle impact.
- No perpetual animation, animated full-screen backgrounds, particle systems, large blur/backdrop-filter effects, expensive box-shadow/glow stacks, or canvas effects for decoration.
- Respect `prefers-reduced-motion`; motion should be brief, purposeful, and optional.
- Avoid unnecessary rerenders, repeated API requests, polling increases, duplicate state, and loading the same heavy component eagerly on every route.
- Lazy-load existing heavy route-level features where the current architecture supports it; do not destabilize routing or code splitting just to chase a score.
- Do not introduce a charting/map/editor dependency solely to imitate the reference.
- Measure production build output before/after when feasible; report bundle warnings honestly. Never claim a performance improvement without measurements.

### Engineering workflow
1. Inspect repository status, branch, recent commits, current routes, shared layout, theme tokens, and current component behavior before editing.
2. Read this file and the relevant existing project documentation. Treat current code and runtime evidence as authoritative over assumptions.
3. Establish a baseline for the page: screenshot or browser inspection if available, route/component inventory, important interactions, API dependencies, responsive behavior, build status, and existing known issues.
4. Create a timestamped backup or a scoped Git diff/commit before risky edits. Never use `git reset --hard`, `git clean`, broad reverts, or destructive cleanup. Do not overwrite unrelated or uncommitted work.
5. Design and implement exactly one page or one clearly bounded component group per phase.
6. Preserve all controls and data flows. Inspect all controls in the page and compare before/after.
7. Run the narrowest relevant tests, TypeScript/build checks available, `git diff --check`, and focused route/HTTP smoke checks where possible.
8. Review desktop and mobile widths; verify light and dark modes, keyboard focus, readable contrast, empty/loading/error states.
9. Record modified files, backup path, tests and actual results, remaining defects, and rollback steps in this file before proceeding.
10. Deploy only after explicit acceptance criteria pass. Do not push to GitHub, commit, restart services, or deploy production unless requested/authorized for that step. If deployment is authorized, preserve the previous image/build and verify health afterward.
11. Ask for visual approval after each page before moving to the next page, unless the user explicitly authorizes a batch of specified pages.

### Definition of done for each page
- Visual structure is meaningfully improved—not just recolored.
- All pre-existing controls and user workflows remain present and functional.
- Existing API/data source is preserved; no invented data.
- Responsive layout works without horizontal overflow at phone, tablet and desktop widths.
- Dark and light themes remain valid.
- Keyboard focus, semantic labels, contrast, reduced-motion preference and touch usability are considered.
- Relevant type/build/tests pass, or any pre-existing/unrelated failure is clearly separated and reported.
- Bundle/dependency impact is acceptable and documented.
- Screenshot/review notes and the TODO status are updated.

---

## 2. Page-by-page execution plan

Work in the following order. Each page is a separate reviewable phase; update status and evidence before continuing.

### Phase 0 — Baseline and shared shell
- [ ] Capture/record current route and feature inventory, baseline build, known warnings and live health.
- [ ] Audit shared dashboard shell: `dashboard/src/pages/_dashboard.tsx`, `dashboard/src/index.css`, theme system, sidebar/navigation, top bar, global dialogs and responsive breakpoints.
- [ ] Define reusable tokens for background, surfaces, borders, text, muted text, accent, status colors, radius, spacing, focus and elevation.
- [ ] Check light/dark mode and persistence; do not overwrite user-customized themes unnecessarily.
- [ ] Identify existing uncommitted work and keep it intact.

### Phase 1 — Dashboard overview (current first target)
- [x] Review `dashboard/src/pages/_dashboard._index.tsx` and `dashboard/src/features/dashboard/components/dashboard-overview.tsx` against the reference.
- [ ] Rebuild information hierarchy: compact header/quick actions, KPI cards, CPU/RAM/Disk/network resource cards, platform/uptime, user state, traffic and admin summaries where data exists.
- [ ] Keep existing real values, queries, polling and interactions; do not increase polling frequency.
- [ ] Check desktop/tablet/mobile and both themes.
- [ ] Run build/type checks and verify no new heavy dependencies or unnecessary assets.
- [ ] Request user visual approval before the next phase.

### Phase 2 — Users
- [ ] Audit `dashboard/src/pages/_dashboard.users.tsx` and `dashboard/src/features/users/**`.
- [ ] Redesign table/list, search, filters, pagination, selection, row actions, details and dialogs without losing any capability.
- [ ] Validate loading/empty/error states, supported page sizes and mobile table behavior.

### Phase 3 — Nodes and host management
- [ ] Audit `dashboard/src/pages/_dashboard.nodes.tsx`, `_dashboard.nodes._index.tsx`, `_dashboard.hosts.tsx`, `_dashboard.hosts.content.tsx`, and `dashboard/src/features/nodes/**`, `dashboard/src/features/hosts/**`.
- [ ] Treat node operations, connection state, forms, logs, host configuration and destructive actions as high-risk; preserve confirmations and permissions.

### Phase 4 — Groups and bulk operations
- [ ] Audit `_dashboard.groups.tsx`, `_dashboard.bulk.tsx`, `_dashboard.bulk.create.tsx`, `_dashboard.bulk.data.tsx`, `_dashboard.bulk.expire.tsx`, `_dashboard.bulk.groups.tsx`, `_dashboard.bulk.proxy.tsx` and `dashboard/src/features/groups/**`, `dashboard/src/features/bulk/**`.
- [ ] Keep all bulk workflows, selection states, validation and confirmation gates.

### Phase 5 — Statistics and traffic
- [ ] Audit `_dashboard.statistics.tsx` and `dashboard/src/features/statistics/**`.
- [ ] Reuse existing charting/data dependencies and actual API results; optimize empty states and date/range filters without inventing telemetry.

### Phase 6 — Plans/templates/subscriptions
- [ ] Audit `_dashboard.templates.tsx`, `_dashboard.templates.client.tsx`, `_dashboard.templates.user.tsx`, `_dashboard.settings.subscriptions.tsx`, and `dashboard/src/features/templates/**`, `dashboard/src/features/subscriptions/**`.
- [ ] Preserve template editors, subscription settings, save/cancel flows and validation.

### Phase 7 — Admins, roles and API keys
- [ ] Audit `_dashboard.admins.tsx`, `_dashboard.admin-roles.tsx`, `_dashboard.api-keys.tsx` and corresponding `dashboard/src/features/admins/**`, `dashboard/src/features/admin-roles/**`, `dashboard/src/features/api-keys/**`.
- [ ] Treat credentials, secret visibility, permissions and destructive actions carefully; never expose secrets in logs/screenshots/reports.

### Phase 8 — Settings, one subsection at a time
- [ ] `_dashboard.settings.tsx` and `_dashboard.settings.general.tsx`
- [ ] `_dashboard.settings.theme.tsx`
- [ ] `_dashboard.settings.notifications.tsx` and `_dashboard.settings.telegram.tsx`
- [ ] `_dashboard.settings.webhook.tsx`
- [ ] `_dashboard.settings.domains.tsx`
- [ ] `_dashboard.settings.hwid.tsx`
- [ ] `_dashboard.settings.cleanup.tsx`
- [ ] `_dashboard.settings.backup.tsx`
- [ ] For every subsection, preserve existing settings, validation, dangerous-action confirmations and backend behavior.

### Phase 9 — Core editor and node-specific views
- [ ] Audit `_dashboard.nodes.cores.tsx`, `_dashboard.nodes.cores._index.tsx`, `_dashboard.nodes.cores.editor.tsx`, `_dashboard.nodes.logs.tsx`, `_dashboard.nodes.wireguard.tsx`, `dashboard/src/features/core-editor/**`.
- [ ] Prioritize editor usability, readable configuration, unsaved-change protection, validation and safe actions. Do not reformat or change config semantics as a styling side effect.

### Phase 10 — Login and global interaction states
- [ ] Audit `dashboard/src/pages/login.tsx`, global dialogs/toasts, loading/error/404 states and route transitions.
- [ ] Preserve authentication behavior, redirects and session safety.

### Phase 11 — Full regression and release review
- [ ] Compare route inventory before/after; every prior route must remain reachable.
- [ ] Test all visible controls and major user workflows page by page.
- [ ] Check responsive layouts, light/dark themes, keyboard navigation, reduced motion and contrast.
- [ ] Run production build, type checks, `git diff --check`, focused tests and health/HTTP smoke checks.
- [ ] Report build size/warnings and known pre-existing issues honestly.
- [ ] Confirm rollback artifact/image and deployment health before closing the redesign.

---

## 3. Initial server audit / handoff report — 2026-10-24

### Verified facts
- [x] Connected target hostname verified as `8017638839-32c511`.
- [x] Project path verified as `/opt/manubisguard-panel`.
- [x] Frontend path verified as `/opt/manubisguard-panel/dashboard`.
- [x] Git branch at audit time: `feature/amnezia-wg`, tracking `origin/feature/amnezia-wg`.
- [x] Pre-existing local modifications found and must be preserved:
  - `dashboard/src/features/dashboard/components/dashboard-overview.tsx`
  - `dashboard/src/index.css`
  - `dashboard/src/lib/theme-color.ts`
  - `dashboard/src/pages/_dashboard._index.tsx`
- [x] Existing project TODO found at `/opt/manubisguard-panel/TODO.md`; this dedicated plan is kept in a separate file to avoid mixing detailed UI work with the large cross-project TODO history.
- [x] Page inventory discovered in `dashboard/src/pages/`; this plan enumerates all currently listed dashboard routes, including nested settings, bulk operations, core editor, login, admins and API keys.
- [x] Dashboard build script is `bun run build` / package script `vite build`; no dedicated dashboard test script was listed in `dashboard/package.json` at audit time.

### Current visual direction agreed with user
- [x] Dark minimal foundation, compact density, cyan/teal accent, light and dark themes.
- [x] User approved the more cyberpunk / hacker-console reference as the design baseline.
- [x] User explicitly requires a new layout/way of displaying content, not merely changing colors.
- [x] User explicitly requires the implementation to stay lightweight and not slow the panel.
- [ ] User has not yet approved a live browser screenshot of the implementation against the new reference; obtain page-by-page approval.

### Existing implementation notes from prior work (verify before relying on them)
- Earlier work modified the theme defaults and global CSS toward compact dark-minimal styling.
- Earlier work reworked the dashboard overview's CPU/RAM/Disk resource cards and KPI layout, and a Docker build was reported successful.
- A local pre-redesign backup was reported at `/opt/manubisguard-panel-ui-pre-redesign-20261024T194141Z.tar.gz` (reported SHA-256: `337a5c99fb5415bdfe5fdd9daafb1ffdd804796dcaf542e12bdfc3afdefb961f`). Verify the file exists and hash matches before using it for rollback.
- A local rollback image was reported as `manubisguard-panel:pre-ui-redesign-20261024`; verify it exists before relying on it.
- A dashboard component backup was reported at `/opt/manubisguard-dashboard-overview-before-redesign-20261024.tsx`; verify before relying on it.
- Previous report said the build had warnings about large JavaScript chunks (including the code editor). Treat this as a performance follow-up to measure, not as permission to add heavy effects or a new chart library.
- Changes listed in Git status above were uncommitted at this audit. Do not reset, clean, broadly revert, or overwrite them.

### Not yet verified in this audit
- [x] Live state rechecked: `manubisguard-panel-manubisguard-1` and `manubisguard-panel-timescaledb-1` are healthy; local `/health` returned HTTP 200 with `{"status":"ok"}`, and `/` returned HTTP 200 (201,846 bytes). Active panel image: `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg`.
- [x] Verified full UI backup exists: `/opt/manubisguard-panel-ui-pre-redesign-20261024T194141Z.tar.gz`, 1.6 MiB, SHA-256 `337a5c99fb5415bdfe5fdd9daafb1ffdd804796dcaf542e12bdfc3afdefb961f`. Verified overview backup exists: `/opt/manubisguard-dashboard-overview-before-redesign-20261024.tsx`, SHA-256 `cb91caba0a6af71692b58b3b87737f32ee3fd6d0aac325a3e0f2115628a32342`. Verified rollback image exists: `manubisguard-panel:pre-ui-redesign-20261024`, image ID `sha256:98d59ab8a334de4377b3585786bb0f360c8cbd96c113fe98a8f9dfbcb2a1f3e7`.
- [ ] Actual browser visual state at phone/tablet/desktop sizes.
- [ ] Whether all dashboard controls remain fully functional after the previous dashboard pass.
- [ ] Build size before/after and measured runtime performance impact.
- [ ] GitHub commit/push status for the current local UI changes. Current status shows local modifications; do not claim these are committed or pushed.

---

## 4. Change log (append-only)

### 2026-10-24 — Master design brief created
- Created this dedicated plan so future work can resume without repeating completed audit steps.
- No application code, backend, database, service configuration, or deployment was changed while creating this document.
- Verified full UI backup and its SHA-256, overview backup and its SHA-256, and rollback image ID.
- Runtime recheck: Panel and TimescaleDB containers healthy; `/health` HTTP 200 with `{"status":"ok"}`; dashboard root HTTP 200 (201,846 bytes).
- The current local UI changes remain uncommitted; this task added/updated documentation only.
- Next step: complete Phase 0/Phase 1 visual and interaction audit against the approved cyberpunk reference, then obtain user approval before proceeding to Users.

### Implementation log template
For each future phase, append:
- **Phase/page:**
- **Baseline reviewed:**
- **Files changed:**
- **Backup / rollback:**
- **Interactions checked:**
- **Build/tests and exact results:**
- **Responsive/theme review:**
- **Performance/bundle impact:**
- **Deployment/health (if authorized):**
- **Remaining issues:**
- **User approval:** pending / approved



### 2026-10-24 — Phase 1 dashboard cyber-console pass deployed
- Updated `dashboard/src/features/dashboard/components/dashboard-overview.tsx`: new compact KPI/resource/platform/user-state hierarchy, with existing API-backed values and no fake telemetry.
- Updated `dashboard/src/pages/_dashboard._index.tsx`: cyber-console hero, static CSS network motif, command center action row. Existing create-user navigation, quick actions command palette, Nodes/Users/Groups links, admin filter and user modal behavior remain in source.
- Updated shared shell styling in `dashboard/src/components/layout/manubis-topbar.tsx`, `dashboard/src/components/layout/sidebar.tsx`, and `dashboard/src/index.css` to align the sidebar/topbar and surface palette with the reference. Updated `dashboard/src/features/dashboard/components/admin-statistics-card.tsx` to remove heavy glass/shadow treatment and tighten spacing while preserving lazy-loaded real usage chart.
- No dependency added; no API, database, polling interval or backend behavior changed. CSS network motif is static; no background image, canvas or perpetual animation added.
- `git diff --check`: PASS. Local direct `bun run build` was not available because host `dashboard/node_modules` is absent (`vite: not found`); Docker production build was used instead and passed.
- Docker build: `manubisguard-panel:cyber-dashboard-test`, image ID `sha256:2fbedca1786d81867713525c780da7e9d404df8e76a3da25c4710343087d60b6`; 5,588 modules transformed, build completed in 18.37s. Existing large chunk warnings remain (Monaco/editor workers and code editor chunks; up to ~6.9 MB raw TS worker and ~3.6 MB editor API chunk).
- Deployment: running service `manubisguard-panel-manubisguard-1` now uses `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg` pointing to the new local image. Container healthy; `/health` returned HTTP 200 and `{"status":"ok"}`; `/` returned HTTP 200.
- Rollback image for exact pre-deployment running container preserved as `manubisguard-panel:pre-cyber-dashboard-20261024`, image ID `sha256:2ab833ef1ac4012cded88b59128babb1301cc0e0d2f9b74932b5457283b4ca39`. Earlier baseline rollback image `manubisguard-panel:pre-ui-redesign-20261024` remains too.
- Remaining: browser visual/interaction acceptance on phone/desktop, light mode review, TypeScript check outside Vite build, and user approval. Do not start the Users page until user confirms the dashboard direction. No Git commit or push performed.


### 2026-10-24 — Dashboard card unification pass
- User reviewed the deployed dashboard and specifically requested all cards use one consistent visual style, not just updated colors.
- Added a backup before this pass: `/opt/manubisguard-dashboard-cards-before-unify-20261024T202106Z.tar.gz`.
- Normalized the dashboard KPI, resource, platform, user-state, admin summary, usage chart/skeleton and worker-health cards to the same flat dark surface, thin border, consistent radius, no heavy shadow/blur. Inner admin user rows now share the same compact dark row style with restrained cyan icon/percentage accents.
- Updated `dashboard/src/features/dashboard/components/admin-statistics-card.tsx`, `users-statistics-card.tsx`, `workers-health-card.tsx`, and `dashboard/src/index.css`; existing APIs, routes, chart loading, interactions, polling and permissions remain unchanged.
- Production Docker build passed: `manubisguard-panel:cyber-cards-unified-test`, final image `sha256:ecc5b127e48536eb9e799f7d7df1f28b2e5e7db0b6e444541ef0cd63820a253b`; Vite transformed 5,588 modules and built in 14.63s. Existing large editor/worker chunk warnings remain.
- Deployed to Compose service `manubisguard-panel-manubisguard-1`; `/health` returned HTTP 200 with `{"status":"ok"}` and `/` returned HTTP 200 (201846 bytes).
- Rollback image captured before this pass: `manubisguard-panel:pre-cyber-cards-unified-20261024`.
- `git diff --check`: PASS. No Git commit/push performed. Still needs user's visual acceptance on mobile and desktop; do not begin other pages until approval.


### 2026-10-24 — System Resources hacker-console visual pass
- User requested the `System Resources / Live resource utilization` section be redesigned in a more striking hacker/cyber style instead of a plain card.
- Backup before changes: `/opt/manubisguard-resources-before-hacker-pass-20261024T202650Z.tsx` and `/opt/manubisguard-resources-css-before-hacker-pass-20261024T202650Z.css`.
- Reworked the section header into a telemetry console: SYS.MON label, framed gauge emblem, live-monitor status chip, terminal strip, static grid/circuit ambience, and secure-link footer. CPU/RAM/Disk cards now have terminal-style typography, corner traces, numbered monitor nodes, segmented utilization meters, and explicit used/capacity labels.
- All decoration is static CSS; no images, canvas, animation loops or dependencies added. Resource values continue to use existing backend values and polling.
- Docker production build passed: image `sha256:b108a6eed6a8f6d33da5997ea2dd63c31a1f8c02f297de76ed94d9f560d112cb`, 5,588 modules transformed, Vite build succeeded in 15.17s. Existing large-chunk warnings remain for editor assets.
- Deployment attempted on Compose service `manubisguard-panel-manubisguard-1`; initial health probe raced startup and returned HTTP 000. Follow-up retry returned HTTP 200 for `/health` and HTTP 200 for `/` after startup; container healthy.
- Rollback image saved as `manubisguard-panel:pre-resource-hacker-20261024`. `git diff --check` passed. No commit/push performed.


### 2026-10-25 — Remaining dashboard panels unified to hacker telemetry style
- User approved the System Resources cyber console direction and requested the rest of the dashboard use the same visual language.
- Backup before this pass: `/opt/manubisguard-dashboard-rest-before-cyber-20261024T203111Z.tar.gz`.
- Extended the static CSS-only console treatment across KPI cards (Online/Total Users, Network Traffic, CPU Load), Platform Status and capacity, User State Overview, Admin statistics wrapper, user breakdown rows, deferred usage chart placeholder, and Workers Health. Shared details: thin cyan telemetry borders, corner traces, low-opacity technical grid, terminal typography/labels, segmented accents, consistent flat surfaces.
- No images, external assets, animation loops, new dependencies, backend changes, API changes, or interaction changes. Existing chart lazy-loading, permissions, live polling and actions remain intact.
- Production Docker build passed: `manubisguard-dashboard-full-cyber-test`, image `sha256:2bd3b2d55d28a4d53db41b1947498bb689b38d96202a6f3456c224291656c1e8`; 5,588 modules transformed and Vite succeeded. Existing large code-editor chunk warnings remain.
- Deployed to `manubisguard-panel-manubisguard-1`; `/health` and `/` HTTP smoke tests were run after restart.
- Rollback image saved as `manubisguard-panel:pre-dashboard-full-cyber-20261025`. `git diff --check` passed. No Git commit/push performed. Await user visual approval before redesigning other pages.


### 2026-10-25 — Statistics page redesigned in cyber operations style
- User asked to redesign the Statistics page (“Monitor your servers and users”) using the approved lightweight hacker-console style, including a different layout/spacing rather than simply recoloring existing cards.
- Backup before changes: `/opt/manubisguard-statistics-before-cyber-20261024T203724Z.tar.gz`.
- Reorganized page framing into a technical hero panel, compact node-selection console, inset statistics canvas, system telemetry block, and responsive chart grid. Applied unified cyan telemetry borders, fine static grid/corner traces, monospaced technical labels, reduced excessive spacing, and responsive mobile sizing.
- Preserved existing API hooks, node selector behavior, permission checks, 2-second master polling, 10-second connected-node polling, chart components, lazy loading, and chart refresh logic. CSS-only visual details; no images, external assets, or new dependencies.
- Production Docker build passed: `manubisguard-statistics-cyber-test`; Vite transformed 5,588 modules and built successfully in 16.22s (PWA generated). Existing large editor chunk warning remains.
- Deployed to `manubisguard-panel-manubisguard-1`; health/root HTTP checks executed after restart.
- Rollback image saved as `manubisguard-panel:pre-statistics-cyber-20261025`. `git diff --check` passed. No Git commit/push performed.


### 2026-10-25 — Statistics page v2: distinct cyber layout (user feedback: previous visual change not obvious)
- User explicitly requested a truly cyber-styled Statistics page with all areas redesigned and non-repetitive layout, not just color changes.
- V2 backup before changes: `/opt/manubisguard-statistics-layout-v2-backup-20261024T204240Z.tar.gz`.
- Rebuilt the visual hierarchy with a telemetry kicker (`MANUBIS / TELEMETRY`, `SYS.MON // 01`), node console strip, resource tiles with distinct roles (CPU, memory, disk, traffic/uptime), and an asymmetric responsive chart grid. On desktop, traffic gets 7/12 columns, user chart 5/12, subscription distribution 4/12, and timeline 8/12; tablet uses a separate 6-column composition; mobile stacks with compact spacing.
- Added explicit CSS hooks to resource and chart wrappers to avoid relying on generic UI library data-slot selectors. Added subtle static grid/radar gradients, clipped corner marks, thin telemetry strokes, terminal labels, distinct edge accents. CSS only; no images, external dependencies, polling/animation loops.
- Preserved data hooks, API behavior, permissions, node selection, chart filters, chart types and refresh logic.
- Production Docker build passed: `manubisguard-statistics-cyber-v2-test`; 5,588 modules transformed, Vite build completed and PWA generated. Existing >500KB chunk warnings remain.
- Deployed to `manubisguard-panel-manubisguard-1`; `/health` and root HTTP checks run after deployment.
- Rollback image: `manubisguard-panel:pre-statistics-cyber-v2-20261025`. `git diff --check` passed. No Git commit/push performed.


### 2026-10-25 — Real-Time Data / CPU live animation
- User requested a fresh animated design for “Real-Time Data / Live statistics and charts for your servers and users” and “CPU Usage”, lightweight and live-feeling.
- Backup: `/opt/manubisguard-realtime-cpu-before-20261024T204910Z.tar.gz`.
- Added a distinct real-time telemetry header with live radio indicator, signal bars, grid scan backdrop and terminal typography. CPU tile now has animated orbit rings, pulsing activity marker, scan shimmer on the CPU icon, live percentage styling and compact LIVE tag.
- Motion uses CSS keyframes only (no JS timers, no dependencies, no new polling). Honors `prefers-reduced-motion`; existing CPU value continues to reflect existing API updates.
- Docker production build passed (`manubisguard-realtime-cpu-test`, 5,588 modules transformed). Deployed to the panel; health endpoint checked. Existing large JS chunk warning persists due to editor bundles.
- Rollback image: `manubisguard-panel:pre-realtime-cpu-20261025`. No Git commit/push.


### 2026-10-25 — Live Network Intelligence and dashboard localization follow-up
- Added a permission-protected backend endpoint (`system:read`) and best-effort OS TCP/UDP socket metrics; unavailable values are not represented as zero.
- Added the Live Network Intelligence view to Statistics. The master server shows OS socket counts alongside the panel's existing online-user metric; node pages show supported bandwidth metrics and explicitly disclose that the current node-agent API does not provide node TCP/UDP socket counts.
- Added focused unit tests for TCP state counting, UDP sockets and access-denied handling; test execution/result still needs verification.
- Fixed hard-coded English UI strings in the newly changed dashboard/statistics areas by adding `mgUi` translations for English, Persian, Russian and Chinese. Localized the telemetry panel, dashboard labels, resource/status copy, quick actions and sidebar accessible labels. Verified all four locale files are served over HTTP 200 with expected translated strings.
- Docker build completed for `manubisguard-panel:localization-fix-20261025b` with a 1200 MiB build memory cap. Deployed only the panel service (no DB recreation); final `/health` returned HTTP 200 with `{"status":"ok"}`, container healthy and restart count 0 after startup. Available host memory after startup was about 1.7 GiB; 4 GiB swap is configured. No separate physical RAM upgrade was performed by this UI deployment.
- `git diff --check` passed. Current branch `feature/amnezia-wg`; current HEAD remains `4fb41c5` until a commit is intentionally made. The worktree contains uncommitted backend, frontend, locale, test and report changes.
- Rollback image: `manubisguard-panel:rollback-localization-intermediate-20261025`; source backup archive was created before the locale/component edits (confirm its exact timestamped filename under `/opt` before relying on it).
- Source backup archive: `/opt/manubisguard-localization-before-20261025T212435Z.tar.gz`. No commit or GitHub push performed. Next steps: run tests, inspect the complete diff, validate build output, then stage/commit/push only after the user authorizes the final reviewed changes.

### 2026-10-25 — Users section cyber operations redesign (first pass)
- User requested a full redesign of the Users section and its filter/status tabs in the approved cyber/hacker-console visual language; continue accumulating changes before the final GitHub push.
- Backup before edits: `/opt/manubisguard-users-before-cyber-redesign-20261024T213802Z.tar.gz` (users route, full users feature directory, and stylesheet).
- Updated the Users page frame/header, live user-statistics cards, filter/search toolbar, status filter tabs, advanced-filter indicators, refresh/sort controls, table shell/header/rows, bulk-action workspace, empty states and pagination styling. Added scoped `.mg-users-*` styles with responsive mobile treatment, restrained cyan/primary telemetry edges, technical typography, and reduced-motion support.
- Preserved existing user API calls, permission gates, search URL state, advanced search, status filters, sorting, auto-refresh, bulk actions, row expansion/edit behavior, pagination and dialogs. This pass is presentation-focused; no database/schema/API behavior was changed for Users.
- `git diff --check`: PASS. Host-side frontend build could not run because local `dashboard/node_modules`/Vite are absent. Docker build's Vite frontend stage transformed 5,589 modules and completed successfully in 14.67s; production image build was still exporting layers at last check. Existing warning remains for large editor chunks (>500 KB).
- No production deployment, commit, or GitHub push has been performed for this Users redesign yet. Next: confirm full image build result, run focused Python tests for the previously added network metrics, then deploy safely only after the candidate image is confirmed healthy; continue requested UI work and do one reviewed commit/push at the end.
- Follow-up verification: full Docker image build completed successfully as `manubisguard-users-cyber-test:20261025` (image digest `sha256:21c7ad1c198ff29159f1c6ce8fab988a251f929ffe3891c27ee9690a7f7ff1fe`). Vite transformed 5,589 modules and production frontend build passed. The standard pytest command could not run inside the production image because pytest is intentionally absent from its `--no-dev` environment; equivalent direct smoke assertions for TCP state counts, UDP sockets, and AccessDenied/null handling passed (`NETWORK_METRICS_SMOKE_PASS`).
- Deployed the candidate image to the existing `manubisguard` service only. Before replacement, preserved the prior image as `manubisguard-panel:rollback-before-users-cyber-20261025`. TimescaleDB was not recreated or restarted. Final container image digest matches the candidate; container status `running`, health `healthy`, restart count `0`; healthcheck returned `{"status":"ok"}`. `git diff --check` remains PASS.
- Git commit and GitHub push remain intentionally deferred until the remaining requested UI changes are completed and the complete diff is reviewed.

### 2026-10-25 — Statistics `mgUi.*` keys showing literally
- User reported raw keys (`mgUi.telemetry`, `mgUi.networkMaster`, `mgUi.networkIntelligence`, `mgUi.live3s`, TCP/UDP card labels and supporting text) visible in Statistics.
- Audited `dashboard/public/statics/locales/{en,fa,ru,zh}.json`: all 4 files parse successfully, each defines 79 `mgUi` translations; all 73 statically referenced `mgUi.*` keys exist in all four languages. The listed network labels have actual English, Persian, Russian and Chinese strings, so this is a locale-loading/cache issue rather than missing translation content.
- Updated i18next `loadPath` to use an explicit root fallback and a versioned query string (`v=20261025-mgui2`) to force fresh locale dictionaries rather than a stale browser/proxy response. Build and runtime verification still pending.
- Follow-up recovery completed: candidate image `manubisguard-locale-fix-test:20261025` built successfully and was deployed to the `manubisguard` Compose service only; current production tag points to image `sha256:0eec5b1dca2e7a87ec5619894faa680629cb4c4fdd2d0240ac9ba42d56d6cf54`. Rollback image preserved as `manubisguard-panel:rollback-before-locale-fix-20261025` (previous production image `sha256:21c7ad1c198ff29159f1c6ce8fab988a251f929ffe3891c27ee9690a7f7ff1fe`).
- Production `/health` returned HTTP 200 (`{"status":"ok"}`); panel is running/healthy with restart count 0. TimescaleDB remained running/healthy and was not recreated.
- Verified the deployed `/statics/locales/{en,fa,ru,zh}.json?v=20261025-mgui2` responses over the app's HTTPS listener. All four returned HTTP 200 and all 16 requested `mgUi` keys were present, including telemetry/network labels and TCP/UDP/proxy descriptions. Persian payload returned real Persian strings instead of raw key names.
- `git diff --check` passed. GitHub commit/push intentionally remains deferred until the broader requested UI changes and final review are complete.
