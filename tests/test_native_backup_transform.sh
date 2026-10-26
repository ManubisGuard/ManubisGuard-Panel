#!/usr/bin/env bash
set -Eeuo pipefail

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/lib"

cat > "$tmp/pasarguard.sh" <<'CLI'
#!/usr/bin/env bash
REQUIRED_SHARED_LIBS="common.sh system.sh docker.sh github.sh env.sh pasarguard-backup.sh pasarguard-restore.sh"
source "$SHARED_LIB_DIR/pasarguard-backup.sh"
source "$SHARED_LIB_DIR/pasarguard-restore.sh"
CLI

for lib in common system docker github env; do
  printf '#!/usr/bin/env bash\n' > "$tmp/lib/$lib.sh"
done

cat > "$tmp/lib/pasarguard-backup.sh" <<'BACKUP'
#!/usr/bin/env bash
backup_command() {
  local backup_dir="$APP_DIR/backup"
  local script_path="/usr/local/bin/$APP_NAME"
  script_path=$(which "$APP_NAME" 2>/dev/null || echo "/usr/local/bin/$APP_NAME")
  target="$temp_dir/pasarguard_data/"
}
BACKUP

cat > "$tmp/lib/pasarguard-restore.sh" <<'RESTORE'
#!/usr/bin/env bash
restore_command() {
  local backup_dir="$APP_DIR/backup"
  source_dir="$temp_dir/pasarguard_data"
  marker=".pasarguard-fresh-restore"
}
RESTORE

sed -i 's/local backup_dir="$APP_DIR\/backup"/local backup_dir="${BACKUP_DIR:-$APP_DIR\/backup}"/g' "$tmp/lib/pasarguard-backup.sh" "$tmp/lib/pasarguard-restore.sh"
find "$tmp" -type f -print0 | xargs -0 sed -i 's/pasarguard/manubisguard/g; s/PasarGuard/ManubisGuard/g'
sed -i 's/manubisguard_data/pasarguard_data/g; s/\.manubisguard-fresh-restore/.pasarguard-fresh-restore/g' "$tmp/lib/pasarguard-backup.sh" "$tmp/lib/pasarguard-restore.sh"
mv "$tmp/lib/pasarguard-backup.sh" "$tmp/lib/manubisguard-backup.sh"
mv "$tmp/lib/pasarguard-restore.sh" "$tmp/lib/manubisguard-restore.sh"
sed -i 's#local script_path="/usr/local/bin/\$APP_NAME"#local script_path="/usr/local/bin/manubis"#g' "$tmp/lib/manubisguard-backup.sh"
sed -i 's#script_path=$(which "\$APP_NAME" 2>/dev/null || echo "/usr/local/bin/\$APP_NAME")#script_path=$(command -v manubis 2>/dev/null || echo "/usr/local/bin/manubis")#g' "$tmp/lib/manubisguard-backup.sh"

bash -n "$tmp/pasarguard.sh"
for library in "$tmp"/lib/*.sh; do bash -n "$library"; done
grep -Fq 'manubisguard-backup.sh manubisguard-restore.sh' "$tmp/pasarguard.sh"
grep -Fq 'source "$SHARED_LIB_DIR/manubisguard-backup.sh"' "$tmp/pasarguard.sh"
grep -Fq 'local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"' "$tmp/lib/manubisguard-backup.sh"
grep -Fq 'target="$temp_dir/pasarguard_data/"' "$tmp/lib/manubisguard-backup.sh"
grep -Fq 'source_dir="$temp_dir/pasarguard_data"' "$tmp/lib/manubisguard-restore.sh"
grep -Fq 'marker=".pasarguard-fresh-restore"' "$tmp/lib/manubisguard-restore.sh"
grep -Fq 'local script_path="/usr/local/bin/manubis"' "$tmp/lib/manubisguard-backup.sh"
grep -Fq 'script_path=$(command -v manubis 2>/dev/null || echo "/usr/local/bin/manubis")' "$tmp/lib/manubisguard-backup.sh"

echo "native backup transform fixture: PASS"
