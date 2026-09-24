# Runtime Healthcheck Investigation — 2026-09-24

## Scope
Investigation of the ManubisGuard Panel container reporting `unhealthy` while the application itself was running.

## Environment
- Repository: `ManubisGuard/ManubisGuard-Panel`
- Branch: `feature/amnezia-wg`
- Image: `ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg`
- Panel container: `manubisguard-panel-manubisguard-1`
- Database container: `manubisguard-panel-timescaledb-1`
- Panel runtime: PasarGuard v5.4.1 (all-in-one)
- Uvicorn application port: `8000`
- Compose runtime uses `network_mode: host` for the Panel.

## Observed failure
The original Compose healthcheck was:

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8000/health || exit 1"]
  interval: 5s
  timeout: 5s
  retries: 30
  start_period: 20s
```

The application log showed Uvicorn serving HTTPS on port 8000:

```text
Uvicorn running on https://0.0.0.0:8000
```

Therefore an HTTP request to `http://127.0.0.1:8000/health` produced:

```text
curl: (52) Empty reply from server
```

The container consequently remained `unhealthy` even though the application had completed startup.

## Root cause
The healthcheck protocol was hard-coded to HTTP while the active Uvicorn runtime was configured for HTTPS/TLS.

This was a healthcheck contract mismatch, not a frontend build failure and not a database startup failure.

The large Vite/Rolldown chunks reported during the build were warnings only. They were not the cause of the unhealthy state.

## Resolution
A protocol-aware `/code/healthcheck.sh` was already available and was used as the Compose healthcheck instead of hard-coding HTTP:

```yaml
healthcheck:
  test: ["CMD-SHELL", "/code/healthcheck.sh"]
  interval: 5s
  timeout: 5s
  retries: 30
  start_period: 20s
```

The script supports the project's actual binding modes and, when `UVICORN_SSL_CERTFILE` and `UVICORN_SSL_KEYFILE` are present and valid, checks HTTPS with certificate verification disabled for the local health probe.

Direct validation inside the running container passed:

```text
{"status":"ok"}
HEALTHCHECK SCRIPT PASS
```

The HTTPS health endpoint also passed:

```text
{"status":"ok"} HTTPS HEALTH PASS
```

## Final real-server result
After recreating the stack, the panel transitioned from `starting` to `healthy`.

Final state:

```text
manubisguard-panel-manubisguard-1   Up 2 minutes (healthy)
ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg
```

Final health log contained successful output:

```text
0 | {"status":"ok"}
```

The TimescaleDB dependency was also reported healthy before the Panel started.

## Timing observation
The final startup took approximately 2 minutes and 21 seconds from the first observed `starting` state to `healthy` in the captured run. This is longer than the nominal 20-second start period, but it is valid because the healthcheck retry window permits continued startup probing.

## Build observations
The frontend build completed successfully:

```text
✓ built in 1m 51s
PWA v1.3.0
mode generateSW
precache 308 entries (10453.84 KiB)
```

Rolldown/Vite emitted warnings for chunks larger than 500 kB, including editor-related chunks. These warnings do not fail the build and were not correlated with the healthcheck failure.

## Current healthcheck contract
Do not revert the Panel Compose healthcheck to a hard-coded HTTP request. Keep the protocol-aware script as the source of truth:

```text
/code/healthcheck.sh
```

Future healthcheck changes must preserve support for:
1. Unix socket binding.
2. Direct HTTP binding.
3. Direct HTTPS binding.
4. Local reverse-proxy scenarios where applicable to the project runtime.

## Follow-up
- Keep the corrected healthcheck in the branch.
- Preserve the successful real-server result in project status documentation.
- Do not treat bundle-size warnings as runtime health failures.
- Continue the remaining migration/installer gates only after the current runtime baseline remains green.
