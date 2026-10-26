#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

# Exercise actual main() ordering with a disposable fake existing install.
# Source the installer without its final auto-invocation so main can be called
# explicitly; the update gate must exit before any setup side effects.
mkdir -p "$TMP/install/.git" "$TMP/bin"
printf 'SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://fake\n' > "$TMP/install/.env"
printf '# fake compose\n' > "$TMP/install/docker-compose.yml"
export PASARGUARD_INSTALL_DIR="$TMP/install"
export PASARGUARD_DATA_DIR="$TMP/data"
export TEST_SIDE_EFFECT_MARKER="$TMP/side-effect"

if [[ "$EUID" -ne 0 ]]; then
  echo "installer fail-closed update gate: SKIP (root required by installer)"
  exit 0
fi

# Remove only the final main invocation.
source <(sed '$d' "$ROOT/install-pasarguard.sh")
ensure_base_tools() { touch "$TEST_SIDE_EFFECT_MARKER"; }
ensure_disk_space() { touch "$TEST_SIDE_EFFECT_MARKER"; }
preflight_update_baseline() { touch "$TEST_SIDE_EFFECT_MARKER"; }
prepare_source() { touch "$TEST_SIDE_EFFECT_MARKER"; }
start_stack() { touch "$TEST_SIDE_EFFECT_MARKER"; }

if output="$(main install --update 2>&1)"; then
  echo "expected main install --update to fail closed" >&2
  exit 1
fi
grep -q 'In-place update is disabled' <<<"$output"
grep -q 'database-aware rollback' <<<"$output"
[[ ! -e "$TEST_SIDE_EFFECT_MARKER" ]] || {
  echo "update gate ran after a setup side effect" >&2
  exit 1
}

# Fresh installs must not be blocked by the update-only safety gate.
UPDATE_MODE=false
require_verified_update_rollback

echo "installer main-flow fail-closed update gate: PASS"
