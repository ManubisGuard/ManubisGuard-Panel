#!/usr/bin/env bash
set -Eeuo pipefail

# Thin compatibility adapter around the original PasarGuard backup/restore CLI.
# Keep the upstream CLI and paired libraries intact; only override host paths,
# the backup destination, and the scheduled command path needed by this install.
readonly UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"
readonly PROJECT_DIR="/opt/pasarguard"
readonly DATA_DIR="/var/lib/pasarguard"
readonly BACKUP_DIR="/opt/pasarguard/backup"
readonly CACHE_DIR="/usr/local/lib/pasarguard-scripts"
readonly SAFETY_PATCH_FALLBACK="$CACHE_DIR/pasarguard-restore-safety.py"
readonly UPSTREAM_BASE="https://raw.githubusercontent.com/PasarGuard/scripts/${UPSTREAM_COMMIT}"

die() { printf '[pasarguard-backup] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "run as root"
[ "$#" -ge 1 ] || die "usage: pasarguard-native-backup backup|restore|backup-service [arguments...]"
command_name="$1"; shift
case "$command_name" in backup|restore|backup-service) ;; *) die "unsupported command: $command_name" ;; esac
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v bash >/dev/null 2>&1 || die "bash is required"

# Download the original CLI and its matching libraries as one pinned bundle.
# No command runs unless every required file is present and syntax-valid.
if [ "$(cat "$CACHE_DIR/.upstream-commit" 2>/dev/null || true)" != "$UPSTREAM_COMMIT" ] || [ ! -s "$CACHE_DIR/pasarguard.sh" ] || [ ! -s "$CACHE_DIR/lib/common.sh" ] || [ ! -s "$CACHE_DIR/lib/system.sh" ] || [ ! -s "$CACHE_DIR/lib/docker.sh" ] || [ ! -s "$CACHE_DIR/lib/github.sh" ] || [ ! -s "$CACHE_DIR/lib/env.sh" ] || [ ! -s "$CACHE_DIR/lib/pasarguard-backup.sh" ] || [ ! -s "$CACHE_DIR/lib/pasarguard-restore.sh" ]; then
  tmp="$(mktemp -d "${CACHE_DIR}.download.XXXXXX")"
  trap 'rm -rf -- "$tmp"' EXIT
  mkdir -p "$tmp/lib"
  for file in pasarguard.sh lib/common.sh lib/system.sh lib/docker.sh lib/github.sh lib/env.sh lib/pasarguard-backup.sh lib/pasarguard-restore.sh; do
    curl --fail --silent --show-error --location --retry 2 --connect-timeout 10 --max-time 120 "$UPSTREAM_BASE/$file" -o "$tmp/$file" || die "could not fetch pinned upstream file: $file"
    [ -s "$tmp/$file" ] || die "empty upstream file: $file"
  done
  bash -n "$tmp/pasarguard.sh" || die "upstream CLI failed shell syntax validation"
  for library in "$tmp"/lib/*.sh; do
    bash -n "$library" || die "upstream library failed shell syntax validation: $(basename "$library")"
  done
  install -d -m 0755 "$CACHE_DIR"
  [ ! -L "$CACHE_DIR" ] || die "refusing symlink cache directory"
  [ ! -L "$CACHE_DIR/lib" ] || die "refusing symlink cache library directory"
  rm -rf -- "$CACHE_DIR/lib"
  install -d -m 0755 "$CACHE_DIR/lib"
  install -m 0644 "$tmp"/lib/*.sh "$CACHE_DIR/lib/"
  install -m 0755 "$tmp/pasarguard.sh" "$CACHE_DIR/pasarguard.sh"
  printf '%s\n' "$UPSTREAM_COMMIT" > "$CACHE_DIR/.upstream-commit"
  chmod 0644 "$CACHE_DIR/.upstream-commit"
  rm -rf -- "$tmp"
  trap - EXIT
fi

# Work on a private copy so the pinned upstream cache remains pristine.
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
cp -a "$CACHE_DIR/." "$work/"

# Minimal compatibility patches only:
# 1) Keep the upstream backup archive layout but write it to PasarGuard's
#    configured backup directory.
# 2) Schedule the installed public CLI (pasarguard), not APP_NAME (which must
#    match the Docker Compose project name: pasarguard).
sed -i 's|local backup_dir="$APP_DIR/backup"|local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"|g' "$work/lib/pasarguard-backup.sh" "$work/lib/pasarguard-restore.sh"
# Skip stale databases that PostgreSQL explicitly marks as non-connectable;
# attempting to inspect one must not force the whole multi-database backup to
# fall back to a single-database archive.
sed -i "s|WHERE datistemplate = false AND datname <> 'postgres';|WHERE datistemplate = false AND datallowconn = true AND datname <> 'postgres';|" "$work/lib/pasarguard-backup.sh"
sed -i 's#local script_path="/usr/local/bin/\$APP_NAME"#local script_path="/usr/local/bin/pasarguard"#g' "$work/lib/pasarguard-backup.sh"
sed -i 's#script_path=$(which "\$APP_NAME" 2>/dev/null || echo "/usr/local/bin/\$APP_NAME")#script_path=$(command -v pasarguard 2>/dev/null || echo "/usr/local/bin/pasarguard")#g' "$work/lib/pasarguard-backup.sh"

# Keep the pinned upstream archive and restore engine, adding only a narrow
# safety layer for local PostgreSQL/TimescaleDB restores. Fail closed if the
# safety patch cannot be applied to the exact reviewed upstream library.
command -v python3 >/dev/null 2>&1 || die "python3 is required to apply the native restore safety patch"
safety_patch="$PROJECT_DIR/scripts/manubisguard-native-restore-safety.py"
[ -s "$safety_patch" ] || safety_patch="$SAFETY_PATCH_FALLBACK"
[ -s "$safety_patch" ] || die "native restore safety patch helper is missing"
python3 "$safety_patch" "$work/lib/pasarguard-restore.sh" || die "native restore safety patch failed"

bash -n "$work/pasarguard.sh" || die "upstream CLI failed syntax validation after compatibility patch"
for library in "$work"/lib/*.sh; do
  bash -n "$library" || die "upstream library failed syntax validation after compatibility patch: $(basename "$library")"
done

# APP_NAME must match the Compose project name generated from the app directory.
# DATA_DIR and BACKUP_DIR are explicit; no install/update action is exposed here.
export APP_NAME=pasarguard APP_DIR="$PROJECT_DIR"
export DATA_DIR BACKUP_DIR
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
case "$command_name" in
  backup) bash "$work/pasarguard.sh" backup "$@" ;;
  restore) bash "$work/pasarguard.sh" restore "$@" ;;
  backup-service) bash "$work/pasarguard.sh" backup-service "$@" ;;
esac
