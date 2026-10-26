#!/usr/bin/env bash
set -Eeuo pipefail

# Thin compatibility adapter around the original PasarGuard backup/restore CLI.
# Keep the upstream CLI and paired libraries intact; only override host paths,
# the backup destination, and the scheduled command path needed by this install.
readonly UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"
readonly PROJECT_DIR="/opt/manubisguard-panel"
readonly DATA_DIR="/var/lib/manubisguard"
readonly BACKUP_DIR="/opt/manubisguard/backup"
readonly CACHE_DIR="/usr/local/lib/manubisguard-native"
readonly UPSTREAM_BASE="https://raw.githubusercontent.com/PasarGuard/scripts/${UPSTREAM_COMMIT}"

die() { printf '[pasarguard-backup] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "run as root"
[ "$#" -ge 1 ] || die "usage: manubisguard-native-backup backup|restore|backup-service [arguments...]"
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
# 1) Keep the upstream backup archive layout but write it to ManubisGuard's
#    configured backup directory.
# 2) Schedule the installed public CLI (manubis), not APP_NAME (which must
#    match the Docker Compose project name: manubisguard-panel).
sed -i 's/local backup_dir="$APP_DIR\/backup"/local backup_dir="${BACKUP_DIR:-$APP_DIR\/backup}"/g' "$work/lib/pasarguard-backup.sh" "$work/lib/pasarguard-restore.sh"
sed -i 's#local script_path="/usr/local/bin/\$APP_NAME"#local script_path="/usr/local/bin/manubis"#g' "$work/lib/pasarguard-backup.sh"
sed -i 's#script_path=$(which "\$APP_NAME" 2>/dev/null || echo "/usr/local/bin/\$APP_NAME")#script_path=$(command -v manubis 2>/dev/null || echo "/usr/local/bin/manubis")#g' "$work/lib/pasarguard-backup.sh"

bash -n "$work/pasarguard.sh" || die "upstream CLI failed syntax validation after compatibility patch"
for library in "$work"/lib/*.sh; do
  bash -n "$library" || die "upstream library failed syntax validation after compatibility patch: $(basename "$library")"
done

# APP_NAME must match the Compose project name generated from the app directory.
# DATA_DIR and BACKUP_DIR are explicit; no install/update action is exposed here.
export APP_NAME=manubisguard-panel APP_DIR="$PROJECT_DIR" DATA_DIR="$DATA_DIR" BACKUP_DIR="$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
case "$command_name" in
  backup) bash "$work/pasarguard.sh" backup "$@" ;;
  restore) bash "$work/pasarguard.sh" restore "$@" ;;
  backup-service) bash "$work/pasarguard.sh" backup-service "$@" ;;
esac
