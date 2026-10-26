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
grep -Fq 'scripts/manubisguard-native-backup.sh" backup' "$CLI"
grep -Fq 'scripts/manubisguard-native-backup.sh" restore' "$CLI"
grep -Fq 'manubisguard-migrate' "$CLI"

if grep -Fq 'manubisguard-native-restore.py --apply' "$CLI"; then
  echo "FAIL: ordinary restore still points to the incomplete native restore validator" >&2
  exit 1
fi

bash -n "$CLI" "$ADAPTER"
echo "native backup adapter static checks: PASS"
