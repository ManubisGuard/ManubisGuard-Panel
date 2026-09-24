#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/manubisguard-migrate.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

FAKE_BIN="$TMP/bin"
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [ "${1:-}" = "compose" ]; then
  shift
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -f) compose_file="$2"; shift 2 ;;
      config)
        if [ "${2:-}" = "--services" ]; then action="services"; shift 2; else shift; fi
        ;;
      ps) action="ps"; shift ;;
      -q) service="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  if [ "$action" = "ps" ]; then
    printf 'container-%s\n' "${service:-unknown}"
    exit 0
  fi
  if [ "$action" = "services" ]; then
    awk '/^  [a-zA-Z0-9_.-]+:$/ { gsub(":", "", $1); print $1 }' "$compose_file"
    exit 0
  fi
fi
printf 'unexpected fake docker invocation\n' >&2
exit 99
EOF
chmod +x "$FAKE_BIN/docker"

SOURCEABLE="$TMP/migrate-sourceable.sh"
sed '/^main "\$@"/d' "$SCRIPT" >"$SOURCEABLE"

run_case() {
  local name="$1" services="$2" expected="$3"
  local compose="$TMP/$name.yml"
  printf 'services:\n%s\n' "$services" >"$compose"

  unset MANUBISGUARD_COMPOSE_SERVICE MANUBISGUARD_DB_SERVICE
  MANUBISGUARD_COMPOSE_FILE="$compose"

  if output="$(MANUBISGUARD_COMPOSE_FILE="$compose" PATH="$FAKE_BIN:$PATH" bash -c 'set -Eeuo pipefail; source "$1"; find_services; printf "%s\n" "$COMPOSE_SERVICE"' _ "$SOURCEABLE" 2>&1)"; then
    if [ "$expected" = "__ERROR__" ]; then
      echo "FAIL: $name expected an error but succeeded: $output" >&2
      return 1
    fi
    [ "$output" = "$expected" ] || {
      echo "FAIL: $name expected '$expected', got '$output'" >&2
      return 1
    }
    echo "PASS: $name -> $output"
  else
    if [ "$expected" != "__ERROR__" ]; then
      echo "FAIL: $name expected '$expected' but errored: $output" >&2
      return 1
    fi
    case "$output" in
      *"No ManubisGuard panel service candidate found"*|*"Multiple ManubisGuard panel service candidates found"*)
        echo "PASS: $name -> expected clear error"
        ;;
      *)
        echo "FAIL: $name produced unexpected error: $output" >&2
        return 1
        ;;
    esac
  fi
}

run_case "legacy" $'  pasarguard:\n    image: example/panel:test\n  timescaledb:\n    image: postgres:16' "pasarguard"
run_case "canonical" $'  manubisguard:\n    image: example/panel:test\n  timescaledb:\n    image: postgres:16' "manubisguard"
run_case "none" $'  api:\n    image: example/api:test\n  timescaledb:\n    image: postgres:16' "__ERROR__"
run_case "multiple" $'  panel:\n    image: example/panel:test\n  pasarguard:\n    image: example/panel:test\n  timescaledb:\n    image: postgres:16' "__ERROR__"

echo "All service-discovery regression cases passed."
