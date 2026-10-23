# ManubisGuard UI redesign progress

## Safety boundary

- Production checkout: `/opt/manubisguard-panel`
- Isolated worktree: `/opt/manubisguard-ui-redesign`
- Working branch: `feature/ui-dark-pro-neon`
- The active dashboard, API, backend, database, Nginx, and running services have not been modified or restarted.
- Do not deploy this branch until a separate preview and functional review are complete.

## Phase 1 completed

- Added persistent `Dark Pro` and `Neon Mode` visual modes to the existing theme provider and theme settings page.
- Added localized visual-mode labels and descriptions for English, Persian, Russian, and Chinese.
- Added grouped sidebar headings: Workspace, Infrastructure, Access & Tools, and System, without changing route paths or permission checks.
- Simplified the top bar and added existing language/theme controls for larger viewports; mobile controls remain available through the sidebar.
- Reduced Dark Pro paint costs by disabling backdrop blur and decorative shadows; retained controlled ambient glow in Neon Mode.
- Deferred user-edit and advanced user-action dialogs until opened.
- Deferred the Recharts chunk from the HTML shell preload list so it is fetched when chart imports are needed.
- Excluded large lazy Monaco/Ace editor and worker assets from PWA shell precache.
- Updated the dashboard document title and PWA name to ManubisGuard, and restored mobile browser zoom support.

## Validation completed

- TypeScript: `tsc --noEmit -p tsconfig.json` passed.
- Production Vite build in the isolated worktree passed.
- Generated PWA precache: approximately 5.6 MiB; large Monaco/Ace assets were verified absent from the precache.
- Recharts was verified absent from `index.html` modulepreload links.
- Production panel and database containers remained healthy during isolated builds.
- No API or backend source files were changed.

## Known build warnings

- `mlkem` imports Node's `crypto` module, which Vite externalizes for browser compatibility. This warning predates the UI-only changes and needs a separate compatibility review if it is encountered at runtime.
- Monaco/Ace-related chunks remain large, but are lazy-loaded and excluded from the PWA shell precache. Do not remove these editor capabilities to silence the size warning.

## Next phase

1. Continue the Nexora-inspired redesign of the dashboard overview, tables, forms, and detail views.
2. Validate layouts at mobile (320/375 px), tablet (768 px), and desktop (1440 px) widths, including Persian RTL.
3. Smoke-test navigation, theme persistence, chart dialogs, user editing, and all existing routes in an isolated preview.
4. Only after approval, plan a reversible frontend-only release. Do not restart backend or node services as part of the UI deployment.
