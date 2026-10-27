#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/install"
printf '# test compose\n' > "$TMP/install/docker-compose.yml"
printf '# test env\n' > "$TMP/install/.env"

cat > "$TMP/bin/docker" <<'MOCK_DOCKER'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "$1" == compose ]]; then
  case "${*: -1}" in
    pasarguard) printf '%s\n' panel-id ;;
    timescaledb) printf '%s\n' db-id ;;
    *) echo "unexpected compose mock call: $*" >&2; exit 90 ;;
  esac
  exit 0
fi
if [[ "$1" == inspect ]]; then
  template="$3"
  case "$template" in
    '{{.State.Status}}') printf '%s\n' "${MOCK_PANEL_STATUS:-running}" ;;
    '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}') printf '%s\n' "${MOCK_PANEL_HEALTH:-healthy}" ;;
    '{{.State.Health.Status}}')
      if [[ "$4" == db-id ]]; then printf '%s\n' "${MOCK_DB_HEALTH:-healthy}"
      else printf '%s\n' "${MOCK_PANEL_HEALTH:-healthy}"; fi ;;
    *) echo "unexpected inspect template: $template" >&2; exit 91 ;;
  esac
  exit 0
fi
echo "unexpected docker call: $*" >&2
exit 92
MOCK_DOCKER
chmod +x "$TMP/bin/docker"

# Load only the function under test; this avoids running installer main().
eval "$(sed -n '/^preflight_update_baseline() {/,/^}/p' "$ROOT/install-pasarguard.sh")"
log() { printf '[test] %s\n' "$*"; }
die() { printf '[test] ERROR: %s\n' "$*" >&2; exit 1; }

export PATH="$TMP/bin:$PATH"
INSTALL_DIR="$TMP/install"
ENV_FILE="$TMP/install/.env"
DATABASE=timescaledb
UPDATE_MODE=true

preflight_update_baseline >/dev/null

if output="$(MOCK_PANEL_HEALTH=unhealthy preflight_update_baseline 2>&1)"; then
  echo "expected unhealthy panel to fail closed" >&2
  exit 1
fi
grep -q 'existing PasarGuard healthcheck is not healthy' <<<"$output"

if output="$(MOCK_DB_HEALTH=unhealthy preflight_update_baseline 2>&1)"; then
  echo "expected unhealthy database to fail closed" >&2
  exit 1
fi
grep -q 'existing TimescaleDB container is not healthy' <<<"$output"

if output="$(MOCK_PANEL_STATUS=exited preflight_update_baseline 2>&1)"; then
  echo "expected stopped panel to fail closed" >&2
  exit 1
fi
grep -q 'existing PasarGuard container is not running' <<<"$output"

echo "installer update preflight health gates: PASS"
