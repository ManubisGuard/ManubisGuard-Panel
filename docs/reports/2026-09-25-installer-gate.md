# Installer Gate — 2026-09-25

## Scope
Real installer execution and clean branch image verification on the new disposable test server.

## Evidence
- Branch: `feature/amnezia-wg`
- Final branch commit during execution: `a3aea5b0961f8744876442ba137485bac7589f25`
- Exact command: `bash install-manubisguard.sh install --database timescaledb --yes`
- Installer exited `0`.
- Installer fetched the branch, validated Compose, pulled TimescaleDB, built the Panel image, started the stack, waited for both services to become healthy, ran the Python import check, and completed the result report.
- Clean Docker build reached Vite/Rolldown and produced `build/index.html` at `2.23 kB`; the Dockerfile's `test -s build/index.html` passed as part of the build step.
- PWA generation completed: 308 precache entries; `build/sw.js` and Workbox output were generated.
- Final Panel image was created and deployed as `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg`.
- Final runtime state: Panel healthy; TimescaleDB healthy.
- HTTP health endpoint returned `{"status":"ok"}` after installer deployment.
- Python application import check completed successfully inside the installed Panel container.

## Installer health correction
The installer health probe was corrected to select HTTP/HTTPS from the persisted `PASARGUARD_SSL_ENABLED` setting. The current installer writes `False` for the default no-TLS mode, so the real installer now probes HTTP; TLS-enabled deployments retain the HTTPS probe.

## Test infrastructure note
The VPS host has a restrictive Docker bridge forwarding policy that prevents ordinary bridge containers from reaching the public network. For the real installer execution only, the test host temporarily used a local `docker` wrapper that injected `--network=host` into `docker build`. The wrapper, temporary Docker daemon configuration, and temporary forwarding rules were removed after the test. No source-code change was made for this infrastructure condition.

## Local test gate
The complete `scripts/run-local-tests.sh` completed with exit code `0` in an isolated disposable copy of the repository. Evidence:
- portable bridge artifacts generated;
- source/destination counts matched (`devices=3`, `usage=48`);
- migrated continuous aggregate contained 48 rows;
- feature-scope Ruff lint passed;
- feature-scope Ruff format check passed;
- migration unit tests: `86 passed`.

The disposable test Compose definition was adapted only in the temporary copy to use host networking because of the VPS Docker bridge forwarding restriction; the repository source was not modified.

## Safety
- Production database was not modified.
- No `--apply` or production cutover was executed.
- No secrets were committed.
