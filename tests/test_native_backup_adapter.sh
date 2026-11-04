#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/pasarguard"
ADAPTER="$ROOT/scripts/manubisguard-native-backup.sh"
API_ROUTER="$ROOT/app/routers/admin_backup.py"

test -s "$CLI"
test -s "$ROOT/manubis"
test -s "$ADAPTER"
grep -Fq 'UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"' "$ADAPTER"
grep -Fq 'readonly BACKUP_DIR="/opt/pasarguard/backup"' "$ADAPTER"
grep -Fq 'readonly PROJECT_DIR="/opt/pasarguard"' "$ADAPTER"
grep -Fq 'readonly DATA_DIR="/var/lib/pasarguard"' "$ADAPTER"
grep -Fq 'export APP_NAME=pasarguard APP_DIR=' "$ADAPTER"
grep -Fq 'export DATA_DIR BACKUP_DIR' "$ADAPTER"
grep -Fq 'INSTALL_DIR="${PASARGUARD_INSTALL_DIR:-${MANUBISGUARD_INSTALL_DIR:-/opt/pasarguard}}"' "$ROOT/install-pasarguard.sh"
grep -Fq 'DATA_DIR="${PASARGUARD_DATA_DIR:-${MANUBISGUARD_DATA_DIR:-/var/lib/pasarguard}}"' "$ROOT/install-pasarguard.sh"
grep -Fq 'BACKUP_DIR="${PASARGUARD_BACKUP_DIR:-$INSTALL_DIR/backup}"' "$ROOT/install-pasarguard.sh"
grep -Fq 'pasarguard:' "$ROOT/docker-compose.yml"
grep -Fq '/var/lib/pasarguard/timescaledb:/var/lib/postgresql/data' "$ROOT/docker-compose.yml"
grep -Fq '/opt/pasarguard/backup:/opt/pasarguard/backup' "$ROOT/docker-compose.yml"
grep -Fq 'local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"' "$ADAPTER"
grep -Fq "datallowconn = true AND datname <> 'postgres'" "$ADAPTER"
grep -Fq 'local script_path="/usr/local/bin/pasarguard"' "$ADAPTER"
grep -Fq 'command -v pasarguard' "$ADAPTER"
# Backup size regression: the adapter reapplies these exclusions to its
# temporary upstream library on every invocation, even if its cache refreshes.
grep -Fq -- "--exclude '/.git'" "$ADAPTER"
grep -Fq -- "--exclude '/backups/incoming/***'" "$ADAPTER"
grep -Fq -- "--exclude '/backups/full-transfer/***'" "$ADAPTER"
grep -Fq -- "--exclude '/backups/staging/***'" "$ADAPTER"
grep -Fq -- "--exclude '/backups/pre-restore/***'" "$ADAPTER"
grep -Fq -- "--exclude '/backups/*.enc'" "$ADAPTER"
grep -Fq 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' "$ADAPTER"
# Native restore safety is patched into a private copy of the pinned upstream
# library; the cached upstream files and archive format remain untouched.
SAFETY_PATCH="$ROOT/scripts/manubisguard-native-restore-safety.py"
test -s "$SAFETY_PATCH"
grep -Fq 'safety_patch="$PROJECT_DIR/scripts/manubisguard-native-restore-safety.py"' "$ADAPTER"
grep -Fq 'safety_patch="$SAFETY_PATCH_FALLBACK"' "$ADAPTER"
grep -Fq 'python3 "$safety_patch" "$work/lib/pasarguard-restore.sh"' "$ADAPTER"
grep -Fq 'manubisguard-native-restore-safety.py" /usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py' "$ROOT/install-pasarguard.sh"
grep -Fq 'PASARGUARD_CLI_URL="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/pasarguard"' "$CLI"
grep -Fq 'PASARGUARD_SAFETY_HELPER_URL="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/scripts/manubisguard-native-restore-safety.py"' "$CLI"
grep -Fq '"safety|$PASARGUARD_SAFETY_HELPER_URL|manubisguard-native-restore-safety.py"' "$CLI"
grep -Fq 'install -o root -g root -m 0644 "$tmp_dir/manubisguard-native-restore-safety.py" /usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py' "$CLI"
grep -Fq 'pg_dump_all_user_databases' "$SAFETY_PATCH"
grep -Fq 'manubisguard_rollback_restore_database_safety' "$SAFETY_PATCH"
grep -Fq 'DATABASE_ROLLBACK=PASS' "$SAFETY_PATCH"
grep -Fq 'sqlite_restore_started=true' "$SAFETY_PATCH"
grep -Fq 'SQLITE_ROLLBACK=PASS' "$SAFETY_PATCH"
grep -Fq 'SQLITE_ROLLBACK=FAIL' "$SAFETY_PATCH"
grep -Fq 'rollback_safe=true' "$SAFETY_PATCH"
grep -Fq 'MANUBISGUARD_RESTORE_SAFETY_V1_LOCK' "$SAFETY_PATCH"
grep -Fq 'flock -n "$restore_lock_fd"' "$SAFETY_PATCH"
# Production restore stays fail-closed in the API; only the native CLI owns restore.
grep -Fq '@router.post("/restore/production/{backup_id}"' "$API_ROUTER"
grep -Fq 'Native production restore is disabled until destination preservation' "$API_ROUTER"
if grep -Eq 'restore_agent|manubisguard_restore_agent_key|urlopen' "$API_ROUTER"; then
  echo "FAIL: production restore API still depends on the retired restore agent" >&2
  exit 1
fi
if grep -Fq 'scripts/manubisguard-native-restore.py' "$API_ROUTER"; then
  echo "FAIL: API still points to the removed custom restore helper" >&2
  exit 1
fi
grep -Fq 'backup) bash "$work/pasarguard.sh" backup "$@" ;;' "$ADAPTER"
grep -Fq 'exec /usr/local/bin/pasarguard-native-backup backup' "$CLI"
grep -Fq 'exec /usr/local/bin/pasarguard-native-backup restore' "$CLI"
grep -Fq 'pasarguard-migrate' "$CLI"
grep -Fq '/usr/local/bin/pasarguard-native-backup' "$ROOT/install-pasarguard.sh"
grep -Fq 'disable --now manubisguard-full-backup.timer' "$ROOT/install-pasarguard.sh"
grep -Fq 'disable --now manubisguard-restore-agent.service' "$ROOT/install-pasarguard.sh"
grep -Fq -- '--update) UPDATE_MODE=true; ASSUME_YES=true; OVERRIDE=true; shift ;;' "$ROOT/install-pasarguard.sh"
grep -Fq '[ "$UPDATE_MODE" != true ]; then prepare_ssl' "$ROOT/install-pasarguard.sh"
grep -Fq 'Preserving existing SSL/TLS environment and certificate files during update.' "$ROOT/install-pasarguard.sh"
grep -Fq 'Preserving existing database URL, credentials, and persistent data.' "$ROOT/install-pasarguard.sh"
grep -Fq 'Preserving existing panel administrator credentials.' "$ROOT/install-pasarguard.sh"
grep -Fq 'In-place update: keeping the currently installed database image unchanged.' "$ROOT/install-pasarguard.sh"
grep -Fq -- '--update requires an existing PasarGuard checkout.' "$ROOT/install-pasarguard.sh"
grep -Fq 'In-place update refused: tracked local changes exist' "$ROOT/install-pasarguard.sh"
grep -Fq 'git -C "$INSTALL_DIR" diff --quiet' "$ROOT/install-pasarguard.sh"
grep -Fq 'git -C "$INSTALL_DIR" diff --cached --quiet' "$ROOT/install-pasarguard.sh"
grep -Fq 'run_fork_installer install --update' "$CLI"
grep -Fq 'rm -f /usr/local/bin/manubisguard-restore-agent' "$ROOT/install-pasarguard.sh"
if grep -Fq 'install_restore_agent' "$ROOT/install-pasarguard.sh"; then
  echo "FAIL: installer still installs the custom restore agent" >&2
  exit 1
fi
if grep -Fq 'restore-agent.key:/run/secrets' "$ROOT/docker-compose.yml"; then
  echo "FAIL: Compose still mounts the obsolete restore-agent secret" >&2
  exit 1
fi
for obsolete in scripts/manubisguard-restore-agent.py scripts/manubisguard-full-backup.py scripts/manubisguard-full-backup-deliver.py scripts/manubisguard-native-restore.py scripts/send-full-backup-telegram.py; do
  if [ -e "$ROOT/$obsolete" ]; then
    echo "FAIL: obsolete custom system backup component remains: $obsolete" >&2
    exit 1
  fi
done

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
bash -n "$ROOT/install-pasarguard.sh"
echo "native backup adapter static checks: PASS"
