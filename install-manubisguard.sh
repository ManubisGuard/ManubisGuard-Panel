#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${MANUBISGUARD_REPO:-https://github.com/ManubisGuard/ManubisGuard-Panel.git}"
BRANCH="${MANUBISGUARD_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${MANUBISGUARD_INSTALL_DIR:-/opt/manubisguard-panel}"
DATA_DIR="${MANUBISGUARD_DATA_DIR:-/var/lib/manubisguard}"
BACKUP_DIR="/opt/manubisguard/backup"
ENV_FILE="$INSTALL_DIR/.env"
DATABASE="timescaledb"
ASSUME_YES=false
SSL_MODE=""
SSL_DOMAIN=""
SSL_CERTFILE=""
SSL_KEYFILE=""
SERVER_IP=""
OVERRIDE=false
MIN_FREE_MB="${MANUBISGUARD_MIN_FREE_MB:-6144}"
PANEL_IMAGE="ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg"
BOOTSTRAP_URL="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh"

log() { printf '[manubisguard-install] %s\n' "$*"; }
die() { printf '[manubisguard-install] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "run this installer as root"

usage() {
  cat <<'EOF'
ManubisGuard installer

Usage:
  install-manubisguard.sh install [--database sqlite|timescaledb] [--ssl-mode domain|ip|custom|none] [--ssl-domain DOMAIN] [--yes] [--override]

After installation:
  manubis status
  manubis start
  manubis stop
  manubis restart
  manubis logs
  manubis update
  manubis restore
  manubis restore-check /path/to/backup.zip

Defaults:
  database: timescaledb
  branch:   feature/amnezia-wg
  install:  /opt/manubisguard-panel
  data:     /var/lib/manubisguard

Options:
  --database sqlite|timescaledb
  --ssl-mode domain|ip|custom|none
  --ssl-domain DOMAIN
  --ssl-cert FILE --ssl-key FILE
  --yes|-y      non-interactive safe defaults
  --override    replace the checked-out source with the selected branch;
                persistent database credentials/data are preserved

Restore:
  restore       restore an available backup with production cutover (--apply)
  restore-check validate a specified backup in staging only (no production changes)
EOF
}

parse_args() {
  [ "${1:-}" = "@" ] && shift || true
  local command="${1:-install}"
  if [ $# -gt 0 ]; then shift; fi

  case "$command" in
    install) ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown command: $command" ;;
  esac

  while [ $# -gt 0 ]; do
    case "$1" in
      --database) [ $# -ge 2 ] || die "--database requires a value"; DATABASE="$2"; shift 2 ;;
      --database=*) DATABASE="${1#*=}"; shift ;;
      --ssl-mode) [ $# -ge 2 ] || die "--ssl-mode requires a value"; SSL_MODE="$2"; shift 2 ;;
      --ssl-mode=*) SSL_MODE="${1#*=}"; shift ;;
      --ssl-domain) [ $# -ge 2 ] || die "--ssl-domain requires a value"; SSL_DOMAIN="$2"; shift 2 ;;
      --ssl-domain=*) SSL_DOMAIN="${1#*=}"; shift ;;
      --ssl-cert) [ $# -ge 2 ] || die "--ssl-cert requires a value"; SSL_CERTFILE="$2"; shift 2 ;;
      --ssl-cert=*) SSL_CERTFILE="${1#*=}"; shift ;;
      --ssl-key) [ $# -ge 2 ] || die "--ssl-key requires a value"; SSL_KEYFILE="$2"; shift 2 ;;
      --ssl-key=*) SSL_KEYFILE="${1#*=}"; shift ;;
      --yes|-y) ASSUME_YES=true; shift ;;
      --override) OVERRIDE=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
  done

  case "$DATABASE" in
    sqlite|timescaledb) ;;
    *) die "unsupported database '$DATABASE' (use sqlite or timescaledb)" ;;
  esac
  if [ -n "$SSL_MODE" ]; then
    case "$SSL_MODE" in domain|ip|custom|none) ;; *) die "unsupported SSL mode: $SSL_MODE" ;; esac
  fi
}

ensure_base_tools() {
  local missing=()
  command -v git >/dev/null 2>&1 || missing+=(git)
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v openssl >/dev/null 2>&1 || missing+=(openssl)

  if [ "${#missing[@]}" -gt 0 ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ca-certificates "${missing[@]}"
  fi

  command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh

  if ! docker compose version >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    if apt-get install -y docker-compose-plugin >/dev/null 2>&1; then
      :
    elif apt-get install -y docker-compose-v2 >/dev/null 2>&1; then
      :
    else
      die "Docker Compose v2 plugin could not be installed automatically."
    fi
  fi

  systemctl enable --now docker >/dev/null 2>&1 || true
  docker info >/dev/null 2>&1 || die "Docker daemon is not available."
}

configure_ssl_choice() {
  if [ -n "$SSL_MODE" ]; then return 0; fi
  if [ "$ASSUME_YES" = true ]; then SSL_MODE="none"; return 0; fi
  echo
  echo "=============================================="
  echo " ManubisGuard SSL / TLS Setup"
  echo "=============================================="
  echo " 1) Let's Encrypt - Domain"
  echo " 2) SSL Certificate - Server IP (self-signed)"
  echo " 3) Custom Certificate"
  echo " 4) Normal Install - No SSL"
  echo
  [ -r /dev/tty ] || die "interactive SSL setup requires a TTY; use --ssl-mode for non-interactive installation"
  printf "%s" "Select [1-4] (default: 1): " > /dev/tty
  IFS= read -r choice < /dev/tty || die "could not read SSL selection from terminal"
  choice="${choice:-1}"
  case "$choice" in
    1) SSL_MODE="domain"; printf "%s" "Domain (example.com): " > /dev/tty; IFS= read -r SSL_DOMAIN < /dev/tty || die "could not read domain from terminal"; [ -n "$SSL_DOMAIN" ] || die "domain is required" ;;
    2) SSL_MODE="ip"; SERVER_IP="$(curl -4fsS --max-time 5 https://api.ipify.org || true)"; [ -n "$SERVER_IP" ] || printf "%s" "Server public IP: " > /dev/tty; IFS= read -r SERVER_IP < /dev/tty || die "could not read server IP from terminal"; [ -n "$SERVER_IP" ] || die "server IP is required" ;;
    3) SSL_MODE="custom"; printf "%s" "Certificate file: " > /dev/tty; IFS= read -r SSL_CERTFILE < /dev/tty || die "could not read certificate path from terminal"; printf "%s" "Private key file: " > /dev/tty; IFS= read -r SSL_KEYFILE < /dev/tty || die "could not read private key path from terminal"; [ -f "$SSL_CERTFILE" ] || die "certificate file not found"; [ -f "$SSL_KEYFILE" ] || die "private key file not found" ;;
    4) SSL_MODE="none" ;;
    *) die "invalid SSL selection" ;;
  esac
}

prepare_ssl() {
  mkdir -p "$DATA_DIR/certs"; chmod 700 "$DATA_DIR/certs"
  case "$SSL_MODE" in
    domain)
      command -v certbot >/dev/null 2>&1 || { export DEBIAN_FRONTEND=noninteractive; apt-get update; apt-get install -y certbot; }
      log "Requesting Let's Encrypt certificate for $SSL_DOMAIN..."
      certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email -d "$SSL_DOMAIN" --preferred-challenges http --http-01-port 80
      cp "/etc/letsencrypt/live/$SSL_DOMAIN/fullchain.pem" "$DATA_DIR/certs/fullchain.pem"
      cp "/etc/letsencrypt/live/$SSL_DOMAIN/privkey.pem" "$DATA_DIR/certs/privkey.pem"
      ;;
    ip)
      log "Generating self-signed certificate with IP SAN $SERVER_IP..."
      openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 3650 -keyout "$DATA_DIR/certs/privkey.pem" -out "$DATA_DIR/certs/fullchain.pem" -subj "/CN=$SERVER_IP" -addext "subjectAltName=IP:$SERVER_IP"
      ;;
    custom)
      cp "$SSL_CERTFILE" "$DATA_DIR/certs/fullchain.pem"; cp "$SSL_KEYFILE" "$DATA_DIR/certs/privkey.pem"
      ;;
    none) rm -f "$DATA_DIR/certs/fullchain.pem" "$DATA_DIR/certs/privkey.pem" ;;
  esac
  [ "$SSL_MODE" = "none" ] || { chmod 644 "$DATA_DIR/certs/fullchain.pem"; chmod 600 "$DATA_DIR/certs/privkey.pem"; }
}

ensure_disk_space() {
  local available
  available="$(df -Pm / | awk 'NR==2 {print $4}')"
  [[ "$available" =~ ^[0-9]+$ ]] || die "could not determine free disk space"

  if [ "$available" -lt "$MIN_FREE_MB" ]; then
    log "Low disk space (${available}MB); cleaning package and unused build caches only."
    apt-get clean >/dev/null 2>&1 || true
    docker builder prune -af >/dev/null 2>&1 || true
    available="$(df -Pm / | awk 'NR==2 {print $4}')"
  fi

  [ "$available" -ge "$MIN_FREE_MB" ] || die "At least ${MIN_FREE_MB}MB free space is required; available=${available}MB."
}

prepare_source() {
  mkdir -p "$(dirname "$INSTALL_DIR")"

  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating source from $BRANCH..."
    git -C "$INSTALL_DIR" remote set-url origin "$REPO" >/dev/null 2>&1 || true
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
    return 0
  fi

  log "Cloning $BRANCH..."
  git clone --depth 1 --branch "$BRANCH" --single-branch "$REPO" "$INSTALL_DIR"
}

ensure_secret() {
  local file="$1" bytes="$2"
  if [ -s "$file" ]; then return 0; fi
  openssl rand -hex "$bytes" >"$file"
  chmod 600 "$file"
}

upsert_env() {
  local key="$1" value="$2"
  touch "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  local tmp
  tmp="$(mktemp)"
  awk -v k="$key" -v v="$value" '
    BEGIN { done=0 }
    {
      if ($0 ~ "^[[:space:]]*" k "[[:space:]]*=") {
        if (!done) { print k "=" v; done=1 }
        next
      }
      print
    }
    END { if (!done) print k "=" v }
  ' "$ENV_FILE" >"$tmp"
  mv "$tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
}

prepare_env() {
  mkdir -p "$DATA_DIR" "$BACKUP_DIR" /etc/manubisguard
  chmod 700 "$DATA_DIR" "$BACKUP_DIR" /etc/manubisguard
  touch /etc/manubisguard/restore-agent.key
  chmod 600 /etc/manubisguard/restore-agent.key
  ensure_secret "$DATA_DIR/.postgres_password" 32
  ensure_secret "$DATA_DIR/.admin_password" 18
  ensure_secret /etc/manubisguard/restore-agent.key 32

  local db_password admin_password
  db_password="$(cat "$DATA_DIR/.postgres_password")"
  admin_password="$(cat "$DATA_DIR/.admin_password")"

  if [ "$DATABASE" = "timescaledb" ]; then
    upsert_env POSTGRES_DB manubisguard
    upsert_env POSTGRES_USER manubisguard
    upsert_env POSTGRES_PASSWORD "$db_password"
    upsert_env SQLALCHEMY_DATABASE_URL "postgresql+asyncpg://manubisguard:${db_password}@127.0.0.1:5432/manubisguard"
    mkdir -p "$DATA_DIR/timescaledb" "$DATA_DIR/migration"
  else
    upsert_env SQLALCHEMY_DATABASE_URL "sqlite+aiosqlite:////var/lib/manubisguard/db.sqlite3"
  fi

  upsert_env UVICORN_HOST 0.0.0.0
  upsert_env UVICORN_PORT 8000
  upsert_env ROLE all-in-one
  upsert_env SUDO_USERNAME admin
  upsert_env SUDO_PASSWORD "$admin_password"
  upsert_env MANUBISGUARD_COMPOSE_SERVICE manubisguard
  upsert_env MANUBISGUARD_DB_SERVICE timescaledb
  upsert_env MANUBISGUARD_DATA_DIR "$DATA_DIR"
  if [ "$SSL_MODE" = "none" ]; then
    upsert_env PASARGUARD_SSL_ENABLED False
    upsert_env PASARGUARD_SSL_MODE none
    upsert_env UVICORN_SSL_CERTFILE ""
    upsert_env UVICORN_SSL_KEYFILE ""
  else
    upsert_env PASARGUARD_SSL_ENABLED True
    upsert_env PASARGUARD_SSL_MODE "$SSL_MODE"
    upsert_env UVICORN_SSL_CERTFILE "$DATA_DIR/certs/fullchain.pem"
    upsert_env UVICORN_SSL_KEYFILE "$DATA_DIR/certs/privkey.pem"
    if [ "$SSL_MODE" = "ip" ]; then upsert_env UVICORN_SSL_CA_TYPE private; else upsert_env UVICORN_SSL_CA_TYPE public; fi
  fi
}

install_restore_agent() {
  install -m 0755 "$INSTALL_DIR/scripts/manubisguard-restore-agent.py" /usr/local/bin/manubisguard-restore-agent
  cat > /etc/systemd/system/manubisguard-restore-agent.service <<EOF
[Unit]
Description=ManubisGuard production restore agent
After=network.target docker.service

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/manubisguard-restore-agent
Restart=on-failure
RestartSec=2
User=root

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now manubisguard-restore-agent.service
}

validate_compose() {
  cd "$INSTALL_DIR"
  docker compose -f docker-compose.yml config -q
}

start_stack() {
  cd "$INSTALL_DIR"
  log "Pulling database image..."
  docker compose -f docker-compose.yml pull timescaledb
  log "Building latest Panel source from $BRANCH..."
  docker build --pull -t "$PANEL_IMAGE" "$INSTALL_DIR"
  log "Starting ManubisGuard + TimescaleDB..."
  docker compose -f docker-compose.yml up -d --remove-orphans --wait --wait-timeout 180
}

verify_stack() {
  cd "$INSTALL_DIR"
  local container
  container="$(docker compose -f docker-compose.yml ps -q manubisguard)"
  [ -n "$container" ] || die "ManubisGuard container was not created."
  docker inspect -f '{{.State.Status}}' "$container" | grep -qx running || die "ManubisGuard container is not running."
  docker exec "$container" python -c 'import app; print("IMPORT_OK")' | grep -qx IMPORT_OK || die "Python import check failed."
  if grep -Eq "^[[:space:]]*PASARGUARD_SSL_ENABLED=(True|true|1)[[:space:]]*$" "$ENV_FILE"; then
    curl -kfsS --max-time 10 https://127.0.0.1:8000/health >/dev/null || die "Panel HTTPS health check failed."
  else
    curl -fsS --max-time 10 http://127.0.0.1:8000/health >/dev/null || die "Panel HTTP health check failed."
  fi
}

install_helper() {
  install -m 0755 "$INSTALL_DIR/scripts/manubisguard-migrate.sh" /usr/local/bin/manubisguard-migrate
  cat > /usr/local/bin/manubis <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

INSTALLER="/opt/manubisguard-panel/install-manubisguard.sh"
BOOTSTRAP_URL="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-manubisguard.sh"
APP_DIR="/opt/manubisguard"
BACKUP_DIR="$APP_DIR/backup"
PROJECT_DIR="/opt/manubisguard-panel"

show_help() {
  cat <<'HELP'
Manubis CLI

Usage: manubis [command]

Commands:
  up              Start services
  down            Stop services
  restart         Restart services
  status          Show status
  logs            Show logs
  cli             Open the panel CLI
  tui             Open the terminal UI
  install         Install ManubisGuard
  update          Update ManubisGuard
  uninstall       Uninstall ManubisGuard
  install-script  Install the Manubis CLI script
  install-node    Install a Manubis node
  backup          Create a backup
  backup-service  Configure automated backups
  restore         Restore from an available backup
  edit            Edit docker-compose.yml
  edit-env        Edit environment file
  version-script  Show script version
  completion      Install shell completion
  help            Show this help
HELP
}

find_backups() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  find "$dir" -maxdepth 1 -type f \( \
    -name '*backup*.gz' -o -name '*backup*.tar.gz' -o -name '*.tar.gz' \
    -o -name '*backup*.zip' -o -name '*.zip' \
  \) -print0 2>/dev/null | sort -z -V
}

restore_command() {
  local dir="$BACKUP_DIR"
  local -a backups=()
  local item choice selected

  while IFS= read -r -d '' item; do backups+=("$item"); done < <(find_backups "$dir")

  if [ "${#backups[@]}" -eq 0 ]; then
    echo "No backup files found in $dir" >&2
    echo "Place the backup archive in $dir and run: manubis restore" >&2
    exit 1
  fi

  echo "Available ManubisGuard backups:"
  local i=1
  for item in "${backups[@]}"; do
    printf '  %d) %s (%s)\n' "$i" "$(basename "$item")" "$(du -h "$item" | cut -f1)"
    i=$((i + 1))
  done
  printf 'Select backup [1-%d]: ' "${#backups[@]}"
  read -r choice
  [[ "$choice" =~ ^[0-9]+$ ]] || { echo "Invalid backup selection." >&2; exit 2; }
  (( choice >= 1 && choice <= ${#backups[@]} )) || { echo "Invalid backup selection." >&2; exit 2; }
  selected="${backups[$((choice - 1))]}"

  exec /usr/local/bin/manubisguard-migrate "$selected" --apply
}

if [ -f "$INSTALLER" ]; then
  case "${1:-}" in
    status) cd "$PROJECT_DIR"; exec docker compose ps ;;
    up|start) cd "$PROJECT_DIR"; exec docker compose up -d ;;
    down|stop) cd "$PROJECT_DIR"; exec docker compose stop ;;
    restart) cd "$PROJECT_DIR"; exec docker compose restart ;;
    logs) cd "$PROJECT_DIR"; exec docker compose logs --tail="${MANUBISGUARD_LOG_TAIL:-100}" -f manubisguard ;;
    update) exec "$INSTALLER" install --yes --override ;;
    restore) shift; [ $# -eq 0 ] || { echo "Usage: manubis restore" >&2; exit 2; }; restore_command ;;
    restore-check)
      shift
      [ $# -eq 1 ] || { echo "Usage: manubis restore-check /path/to/backup.zip" >&2; exit 2; }
      exec /usr/local/bin/manubisguard-migrate --check "$1"
      ;;
    install|""|-h|--help) exec "$INSTALLER" "${@:-install}" ;;
    install-script) exec "$INSTALLER" install --yes ;;
    install-node) exec "$INSTALLER" install-node ;;
    backup|backup-service|cli|tui|edit|edit-env|version-script|completion)
      echo "Command '$1' is reserved for the upstream Manubis CLI workflow and is not yet wired in this installer build." >&2
      exit 2
      ;;
    uninstall) exec "$INSTALLER" uninstall ;;
    help) show_help ;;
    *) echo "Unknown command: $1" >&2; show_help >&2; exit 2 ;;
  esac
else
  command="${1:-install}"
  case "$command" in
    install|--help|-h)
      tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
      curl -fsSL "$BOOTSTRAP_URL" -o "$tmp"
      exec bash "$tmp" "${@:-install}"
      ;;
    *) echo "ManubisGuard is not installed. Run: manubis install" >&2; exit 1 ;;
  esac
fi
EOF
  chmod 0755 /usr/local/bin/manubis
  rm -f /usr/local/bin/manubisguard
}

show_result() {
  cd "$INSTALL_DIR"
  local admin_password
  admin_password="$(cat "$DATA_DIR/.admin_password")"
  echo "=============================================="
  echo " ManubisGuard installation"
  echo "=============================================="
  echo "Repository:  $REPO"
  echo "Branch:      $BRANCH"
  echo "Install:     $INSTALL_DIR"
  echo "Data:        $DATA_DIR"
  echo "Database:    $DATABASE"
  if [ "$SSL_MODE" = "none" ]; then echo "Panel:       http://SERVER-IP:8000"; elif [ "$SSL_MODE" = "domain" ]; then echo "Panel:       https://${SSL_DOMAIN}:8000"; else echo "Panel:       https://${SERVER_IP:-SERVER-IP}:8000"; fi
  echo "Username:    admin"
  echo "Password:    $admin_password"
  echo "CLI:         manubis {status|start|stop|restart|logs|update|restore|restore-check}"
  docker compose -f docker-compose.yml ps
  echo "=============================================="
}

main() {
  parse_args "$@"
  ensure_base_tools
  ensure_disk_space

  if [ -d "$INSTALL_DIR/.git" ] && [ "$OVERRIDE" = false ] && [ "$ASSUME_YES" != true ]; then
    if git -C "$INSTALL_DIR" status --porcelain 2>/dev/null | grep -q .; then
      die "Existing checkout has local changes; use --override to replace them."
    fi
  fi

  configure_ssl_choice
  prepare_source
  prepare_ssl
  prepare_env
  install_restore_agent
  validate_compose
  start_stack
  verify_stack
  install_helper
  show_result
}

main "$@"
