#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/manubis"
ADAPTER="$ROOT/scripts/manubisguard-native-backup.sh"

test -s "$CLI"
test -s "$ADAPTER"
grep -Fq 'UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"' "$ADAPTER"
grep -Fq 'readonly BACKUP_DIR="/opt/manubisguard/backup"' "$ADAPTER"
grep -Fq 'readonly PROJECT_DIR="/opt/manubisguard-panel"' "$ADAPTER"
grep -Fq 'readonly DATA_DIR="/var/lib/manubisguard"' "$ADAPTER"
grep -Fq 'export APP_NAME=manubisguard-panel APP_DIR=' "$ADAPTER"
grep -Fq 'local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"' "$ADAPTER"
grep -Fq 'local script_path="/usr/local/bin/manubis"' "$ADAPTER"
grep -Fq 'command -v manubis' "$ADAPTER"
grep -Fq 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' "$ADAPTER"
grep -Fq 'backup) bash "$work/pasarguard.sh" backup "$@" ;;' "$ADAPTER"
grep -Fq '/usr/local/bin/manubisguard-native-backup" backup' "$CLI"
grep -Fq '/usr/local/bin/manubisguard-native-backup" restore' "$CLI"
grep -Fq 'manubisguard-migrate' "$CLI"
grep -Fq '/usr/local/bin/manubisguard-native-backup' "$ROOT/install-manubisguard.sh"
grep -Fq 'disable --now manubisguard-full-backup.timer' "$ROOT/install-manubisguard.sh"

# The adapter must not rename upstream libraries, CLI identifiers, or archive
# schema keys: compatibility depends on using the original paired engine.
if grep -Eq 'find .*sed -i|s/pasarguard/manubisguard/g|mv .*manubisguard-(backup|restore)' "$ADAPTER"; then
  echo "FAIL: adapter is rewriting the upstream PasarGuard architecture" >&2
  exit 1
fi
if grep -Fq 'manubisguard-native-restore.py --apply' "$CLI"; then
  echo "FAIL: ordinary restore still points to the custom restore validator" >&2
  exit 1
fi

bash -n "$CLI"
bash -n "$ADAPTER"
bash -n "$ROOT/install-manubisguard.sh"
echo "native backup adapter static checks: PASS"
