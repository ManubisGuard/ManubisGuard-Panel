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
grep -Fq '/usr/local/bin/manubisguard-native-backup" backup' "$CLI"
grep -Fq '/usr/local/bin/manubisguard-native-backup" restore' "$CLI"
grep -Fq 'manubisguard-migrate' "$CLI"
grep -Fq '/usr/local/bin/manubisguard-native-backup' "$ROOT/install-manubisguard.sh"
grep -Fq 'disable --now manubisguard-full-backup.timer' "$ROOT/install-manubisguard.sh"

if grep -Fq 'manubisguard-native-restore.py --apply' "$CLI"; then
  echo "FAIL: ordinary restore still points to the incomplete native restore validator" >&2
  exit 1
fi

bash -n "$CLI"
bash -n "$ADAPTER"
bash -n "$ROOT/install-manubisguard.sh"
echo "native backup adapter static checks: PASS"
