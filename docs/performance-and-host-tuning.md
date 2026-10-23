# Dashboard and Host Performance Notes

This document records the performance changes validated on the production ManubisGuard Panel host on 2026-10-23. The dashboard source changes are part of this branch and are included in normal builds from it. Host-level Nginx and swap tuning are intentionally documented separately because their safe values depend on each server's Nginx layout, available disk, and memory.

## Dashboard source changes

- Users and admins list queries use a 10-second stale time and 5-minute cache retention rather than discarding cached data immediately.
- Nodes list retains its 10-second refresh and uses a 5-second stale time / 2-minute cache retention.
- Connected-node realtime statistics polling changed from 1.5 seconds to 10 seconds.
- Dashboard system resource and user summary polling changed from 5 seconds to 15 seconds.
- User-table URL and persisted page-size values are limited to the values offered in the UI: 10, 20, 30, 40, and 50. Unsupported values such as `limit=500` fall back to the default of 10.
- The explicit refresh controls remain available; cache tuning is not intended to prevent users from requesting fresh data.

Validation on the production checkout: Vite production build passed, `bunx tsc --noEmit` passed, and `git diff --check` passed. The user reported the dashboard felt better after testing.

## Nginx gzip tuning

Nginx configuration is host-level and may be managed outside this repository. Back up the active vhost before editing, preserve the site's existing TLS, proxy, cache, and security directives, and validate before reloading.

The tested settings were:

```nginx
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_http_version 1.1;
gzip_buffers 16 8k;
gzip_disable "msie6";
gzip_types
    text/plain
    text/css
    text/xml
    application/xml
    application/xml+rss
    application/json
    application/javascript
    application/x-javascript
    application/ld+json
    application/manifest+json
    application/wasm
    image/svg+xml;
```

Do not add already-compressed formats such as WOFF/WOFF2 to the gzip list. Keep immutable caching for content-hashed assets and no-store behavior for the HTML entry point, unless the site's cache design intentionally differs.

Validation commands:

```sh
nginx -t && nginx -s reload
curl -sSI -H 'Accept-Encoding: gzip' https://YOUR_PANEL_HOST/dashboard/
```

On the tested host, JavaScript transfer size changed from 118,730 bytes to 34,015 bytes (71.4% reduction), and CSS changed from 219,610 bytes to 32,443 bytes (85.2% reduction). These are measurements from that build, not universal guarantees.

## Optional swap tuning

Swap size is a per-host operational decision and is **not automatically enabled by the application installer**. Only use a 4 GiB swapfile if the host has sufficient free disk and this is appropriate for its workload. Check existing swap first to avoid creating a duplicate:

```sh
free -h
swapon --show
df -h /
```

For a host where a 4 GiB swapfile has been explicitly chosen, a typical setup is:

```sh
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
printf 'vm.swappiness=10\n' > /etc/sysctl.d/99-manubisguard-memory.conf
sysctl --system
```

Do not blindly rerun these commands on a host with an existing swapfile or insufficient disk. Verify with `swapon --show`, `free -h`, and `sysctl vm.swappiness`.

## Known follow-up

Intermittent `/api/users` response latency remains unresolved. Historical requests ranged from tens of milliseconds to several seconds, and some logs show requests with `load_sub=false`; this does not prove a database bottleneck. Do not add indexes, enable verbose SQL logging, or install database extensions without first measuring database execution separately from application serialization/response time.
