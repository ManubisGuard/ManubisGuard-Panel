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
  local user_databases_query="SELECT datname FROM pg_database WHERE datistemplate = false AND datname <> 'postgres';"
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
sed -i "s|WHERE datistemplate = false AND datname <> 'postgres';|WHERE datistemplate = false AND datallowconn = true AND datname <> 'postgres';|" "$tmp/lib/pasarguard-backup.sh"
sed -i 's#local script_path="/usr/local/bin/\$APP_NAME"#local script_path="/usr/local/bin/manubis"#g' "$tmp/lib/pasarguard-backup.sh"
sed -i 's#script_path=$(which "\$APP_NAME" 2>/dev/null || echo "/usr/local/bin/\$APP_NAME")#script_path=$(command -v manubis 2>/dev/null || echo "/usr/local/bin/manubis")#g' "$tmp/lib/pasarguard-backup.sh"

bash -n "$tmp/pasarguard.sh"
for library in "$tmp"/lib/*.sh; do bash -n "$library"; done
grep -Fq 'pasarguard-backup.sh pasarguard-restore.sh' "$tmp/pasarguard.sh"
grep -Fq 'source "$SHARED_LIB_DIR/pasarguard-backup.sh"' "$tmp/pasarguard.sh"
grep -Fq 'local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"' "$tmp/lib/pasarguard-backup.sh"
grep -Fq "WHERE datistemplate = false AND datallowconn = true AND datname <> 'postgres';" "$tmp/lib/pasarguard-backup.sh"
grep -Fq 'local backup_dir="${BACKUP_DIR:-$APP_DIR/backup}"' "$tmp/lib/pasarguard-restore.sh"
grep -Fq 'target="$temp_dir/pasarguard_data/"' "$tmp/lib/pasarguard-backup.sh"
grep -Fq 'source_dir="$temp_dir/pasarguard_data"' "$tmp/lib/pasarguard-restore.sh"
grep -Fq 'marker=".pasarguard-fresh-restore"' "$tmp/lib/pasarguard-restore.sh"
grep -Fq 'local script_path="/usr/local/bin/manubis"' "$tmp/lib/pasarguard-backup.sh"
grep -Fq 'script_path=$(command -v manubis 2>/dev/null || echo "/usr/local/bin/manubis")' "$tmp/lib/pasarguard-backup.sh"

echo "native backup compatibility fixture: PASS"
