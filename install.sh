#!/usr/bin/env bash
set -Eeuo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"
DATA_DIR="/var/lib/pasarguard"
ENV_FILE="$INSTALL_DIR/.env"
DATABASE="sqlite"
ASSUME_YES=false
OVERRIDE=false
SSL_MODE="none"
SSL_IDENTIFIER=""
SSL_EMAIL=""
SSL_CERTFILE=""
SSL_KEYFILE=""
CERT_DIR="$DATA_DIR/certs"
CERTBOT_CONFIG_DIR="$CERT_DIR/letsencrypt"
CERTBOT_WORK_DIR="$CERT_DIR/work"
CERTBOT_LOGS_DIR="$CERT_DIR/logs"

[[ "$EUID" -eq 0 ]] || { echo "ERROR: run this installer as root."; exit 1; }

log() { echo "[PasarGuard] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

ask_yes_no() {
  local prompt="$1" default="${2:-N}" answer
  if [[ "$ASSUME_YES" == true ]]; then return 0; fi
  while true; do
    if [[ "$default" == "Y" ]]; then
      read -r -p "$prompt [Y/n]: " answer || true
      answer="${answer:-Y}"
    else
      read -r -p "$prompt [y/N]: " answer || true
      answer="${answer:-N}"
    fi
    case "${answer,,}" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "Please answer yes or no." ;;
    esac
  done
}

usage() {
  echo "Usage: $0 install [--database sqlite|timescaledb] [--yes] [--override]"
  echo
  echo "Database:"
  echo "  sqlite       SQLite (default)"
  echo "  timescaledb  TimescaleDB/PostgreSQL 16"
  echo
  echo "Options:"
  echo "  --yes        Accept safe reuse choices automatically; never deletes data"
  echo "  --override   Explicitly allow replacement/update of an existing PasarGuard installation"
  echo
  echo "SSL is selected interactively during installation:"
  echo "  1) Domain SSL"
  echo "  2) IP SSL (short-lived)"
  echo "  3) No SSL"
}

parse_args() {
  [[ "${1:-}" == "@" ]] && shift
  COMMAND="${1:-}"
  [[ -n "$COMMAND" ]] && shift || true

  case "$COMMAND" in
    install) ;;
    -h|--help|"") usage; exit 0 ;;
    *) die "unknown command: $COMMAND" ;;
  esac

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --database)
        [[ $# -ge 2 ]] || die "--database requires a value"
        DATABASE="$2"
        shift 2
        ;;
      --database=*)
        DATABASE="${1#*=}"
        shift
        ;;
      --yes|-y)
        ASSUME_YES=true
        shift
        ;;
      --override)
        OVERRIDE=true
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *) die "unknown option: $1" ;;
    esac
  done

  case "$DATABASE" in
    sqlite|timescaledb) ;;
    *) die "unsupported database '$DATABASE'. Use sqlite or timescaledb." ;;
  esac
}

detect_environment() {
  echo
  echo "========== Environment detection =========="
  if command -v docker >/dev/null 2>&1; then
    DOCKER_VERSION="$(docker --version 2>/dev/null || true)"
    if docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
      log "Docker detected and healthy: $DOCKER_VERSION"
      log "Compose: $(docker compose version 2>/dev/null)"
    elif docker compose version >/dev/null 2>&1; then
      systemctl enable --now docker >/dev/null 2>&1 || true
      docker info >/dev/null 2>&1 || die "Docker cannot be started."
    else
      ask_yes_no "Docker exists but Compose v2 is missing. Install the plugin?" || die "Docker Compose v2 is required."
      apt-get update && apt-get install -y docker-compose-plugin
    fi
  else
    ask_yes_no "Docker is not installed. Install it now?" || die "Docker is required."
    install_docker
  fi

  EXISTING_PANEL=false
  EXISTING_DB="none"
  [[ -f "$INSTALL_DIR/.env" || -f "$INSTALL_DIR/docker-compose.yml" || -d "$INSTALL_DIR/.git" ]] && EXISTING_PANEL=true
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Eq '(^|/|_)pasarguard($|_)|pasarguard-panel' && EXISTING_PANEL=true || true
  [[ -s "$DATA_DIR/db.sqlite3" ]] && EXISTING_DB="sqlite" && log "SQLite detected: $DATA_DIR/db.sqlite3"
  if [[ -d "$DATA_DIR/timescaledb" ]] && find "$DATA_DIR/timescaledb" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .; then
    EXISTING_DB="timescaledb"
    log "TimescaleDB data detected: $DATA_DIR/timescaledb"
  fi
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Eq '(^|_)timescaledb$|pasarguard.*timescaledb'; then
    log "TimescaleDB container detected."
  fi
  if ss -lnt 2>/dev/null | grep -qE '127\.0\.0\.1:5432|0\.0\.0\.0:5432|\*:5432'; then
    log "Port 5432 is already in use."
    EXISTING_DB="timescaledb"
  fi

  if [[ "$EXISTING_PANEL" == true ]]; then
    echo
    echo "Existing PasarGuard installation detected: $INSTALL_DIR"
    echo "Detected database: $EXISTING_DB"
    echo "  1) Reuse/update existing installation (preserve data)"
    echo "  2) Override application source/config (preserve database)"
    echo "  3) Cancel"
    if [[ "$ASSUME_YES" == true ]]; then
      EXISTING_ACTION="reuse"
    else
      read -r -p "Select [1-3]: " EXISTING_ACTION
      case "$EXISTING_ACTION" in
        1) EXISTING_ACTION="reuse" ;;
        2) EXISTING_ACTION="override"; OVERRIDE=true ;;
        3|"") die "Installation cancelled. Existing data was not modified." ;;
        *) die "Invalid selection." ;;
      esac
    fi
  fi
  echo "==========================================="
}

install_docker() {
  export DEBIAN_FRONTEND=noninteractive
  local missing=()
  for cmd in curl git openssl python3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    apt-get update
    apt-get install -y ca-certificates curl git openssl python3
  fi

  apt-mark unhold docker.io docker-compose docker-compose-v2 containerd runc >/dev/null 2>&1 || true
  apt-get remove -y docker.io docker-compose docker-compose-v2 containerd runc >/dev/null 2>&1 || true
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 installation failed."
}

install_base() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Using existing Docker/Compose installation; no Docker package changes."
  else
    install_docker
  fi

  command -v curl >/dev/null 2>&1 || { apt-get update; apt-get install -y curl; }
  command -v git >/dev/null 2>&1 || { apt-get update; apt-get install -y git; }
  command -v openssl >/dev/null 2>&1 || { apt-get update; apt-get install -y openssl; }

  systemctl enable --now docker >/dev/null 2>&1 || true
  docker info >/dev/null 2>&1 || die "Docker is not running."
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is not available."
}

confirm_database() {
  local sqlite_exists=false timescale_exists=false port5432=false
  [[ -s "$DATA_DIR/db.sqlite3" ]] && sqlite_exists=true
  [[ "$EXISTING_DB" == "timescaledb" ]] && timescale_exists=true
  ss -lnt 2>/dev/null | grep -qE '127\.0\.0\.1:5432|0\.0\.0\.0:5432|\*:5432' && port5432=true || true

  if [[ "$DATABASE" == "sqlite" ]]; then
    if $timescale_exists || $port5432; then
      log "Existing TimescaleDB detected; it will be preserved."
      ask_yes_no "Continue with SQLite?" || die "Installation cancelled."
    fi
    if $sqlite_exists; then
      ask_yes_no "Use the existing SQLite database?" || die "Installation cancelled."
    fi
    return
  fi

  if $sqlite_exists; then
    log "Existing SQLite database detected."
    log "No automatic SQLite -> TimescaleDB migration is performed."
    ask_yes_no "Continue with TimescaleDB and preserve the SQLite file?" || die "Installation cancelled."
  fi

  if $timescale_exists || $port5432; then
    log "Existing PostgreSQL/TimescaleDB resources detected."
    $timescale_exists && log "  Data directory: $DATA_DIR/timescaledb"
    $port5432 && log "  Port 5432: already in use"
    if [[ "$OVERRIDE" == true ]]; then
      log "Override selected. Existing database will NOT be purged."
    else
      ask_yes_no "Reuse the existing TimescaleDB/PostgreSQL environment?" || die "Installation cancelled. Database was not modified."
    fi
  fi
}

select_ssl() {
  echo
  echo "========== SSL configuration =========="
  echo "1) Domain SSL - Let's Encrypt"
  echo "2) IP SSL - Let's Encrypt short-lived certificate"
  echo "3) No SSL"
  if [[ "$ASSUME_YES" == true ]]; then SSL_MODE="none"; return; fi
  while true; do
    read -r -p "Select [1-3]: " choice
    case "$choice" in
      1)
        SSL_MODE="domain"
        read -r -p "Domain/subdomain: " SSL_IDENTIFIER
        [[ "$SSL_IDENTIFIER" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || { echo "Invalid domain."; continue; }
        read -r -p "Let's Encrypt email: " SSL_EMAIL
        [[ "$SSL_EMAIL" == *@*.* ]] || { echo "Invalid email."; continue; }
        break ;;
      2)
        SSL_MODE="ip"
        SERVER_PUBLIC_IP="$(curl -4fsS --max-time 10 https://api.ipify.org || true)"
        [[ -n "$SERVER_PUBLIC_IP" ]] || SERVER_PUBLIC_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
        read -r -p "IP address [$SERVER_PUBLIC_IP]: " SSL_IDENTIFIER
        SSL_IDENTIFIER="${SSL_IDENTIFIER:-$SERVER_PUBLIC_IP}"
        python3 - "$SSL_IDENTIFIER" <<'PY' || { echo "Invalid IP."; continue; }
import ipaddress,sys
try: ipaddress.ip_address(sys.argv[1])
except Exception: raise SystemExit(1)
PY
        read -r -p "Let's Encrypt email: " SSL_EMAIL
        [[ "$SSL_EMAIL" == *@*.* ]] || { echo "Invalid email."; continue; }
        break ;;
      3) SSL_MODE="none"; break ;;
      *) echo "Invalid selection." ;;
    esac
  done
  echo "SSL mode: $SSL_MODE"
}

check_ssl_prerequisites() {
  [[ "$SSL_MODE" == "none" ]] && return 0
  if ss -lntp 2>/dev/null | grep -qE ':80[[:space:]]'; then
    ss -lntp 2>/dev/null | grep -E ':80[[:space:]]' || true
    die "Port 80 is already in use. Free it before Let's Encrypt validation."
  fi
  if ss -lntp 2>/dev/null | grep -qE ':443[[:space:]]'; then
    ss -lntp 2>/dev/null | grep -E ':443[[:space:]]' || true
    die "Port 443 is already in use. Free it before enabling direct Uvicorn SSL."
  fi
  if [[ "$SSL_MODE" == "domain" ]]; then
    local resolved
    resolved="$(getent ahostsv4 "$SSL_IDENTIFIER" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
    [[ -n "$resolved" ]] || die "Domain $SSL_IDENTIFIER does not resolve."
    SERVER_PUBLIC_IP="$(curl -4fsS --max-time 10 https://api.ipify.org || true)"
    if [[ -n "$SERVER_PUBLIC_IP" && " $resolved " != *" $SERVER_PUBLIC_IP "* ]]; then
      log "WARNING: $SSL_IDENTIFIER resolves to $resolved; this server is $SERVER_PUBLIC_IP"
      ask_yes_no "Continue anyway?" || die "Fix DNS before requesting SSL."
    fi
  fi
}

ensure_certbot() {
  if command -v certbot >/dev/null 2>&1; then
    local version
    version="$(certbot --version 2>&1 | awk '{print $2}' | sed 's/^v//')"
    if [[ -n "$version" ]] && dpkg --compare-versions "$version" ge "5.4.0"; then return 0; fi
  fi
  if ! command -v snap >/dev/null 2>&1; then
    apt-get update && apt-get install -y snapd
    systemctl enable --now snapd.socket >/dev/null 2>&1 || true
    sleep 2
  fi
  snap install core >/dev/null 2>&1 || true
  snap refresh core >/dev/null 2>&1 || true
  snap install --classic certbot >/dev/null 2>&1 || snap refresh certbot
  ln -sf /snap/bin/certbot /usr/local/bin/certbot
}

issue_ssl_certificate() {
  [[ "$SSL_MODE" == "none" ]] && return 0
  check_ssl_prerequisites
  ensure_certbot
  mkdir -p "$CERT_DIR" "$CERTBOT_CONFIG_DIR" "$CERTBOT_WORK_DIR" "$CERTBOT_LOGS_DIR"
  chmod 700 "$CERT_DIR"
  mkdir -p "$CERTBOT_CONFIG_DIR/renewal-hooks/deploy"
  cat > "$CERTBOT_CONFIG_DIR/renewal-hooks/deploy/restart-pasarguard.sh" <<HOOK
#!/bin/sh
set -eu
cd "$INSTALL_DIR"
docker compose restart pasarguard >/dev/null 2>&1 || true
HOOK
  chmod 700 "$CERTBOT_CONFIG_DIR/renewal-hooks/deploy/restart-pasarguard.sh"

  local common_args=(certonly --standalone --non-interactive --agree-tos --email "$SSL_EMAIL" --cert-name pasarguard --config-dir "$CERTBOT_CONFIG_DIR" --work-dir "$CERTBOT_WORK_DIR" --logs-dir "$CERTBOT_LOGS_DIR")
  log "Requesting Let's Encrypt certificate..."
  if [[ "$SSL_MODE" == "ip" ]]; then
    certbot "${common_args[@]}" --preferred-profile shortlived --ip-address "$SSL_IDENTIFIER"
  else
    certbot "${common_args[@]}" -d "$SSL_IDENTIFIER"
  fi
  SSL_CERTFILE="$CERTBOT_CONFIG_DIR/live/pasarguard/fullchain.pem"
  SSL_KEYFILE="$CERTBOT_CONFIG_DIR/live/pasarguard/privkey.pem"
  [[ -s "$SSL_CERTFILE" && -s "$SSL_KEYFILE" ]] || die "SSL certificate/key was not created."
  chmod 644 "$SSL_CERTFILE"
  chmod 600 "$SSL_KEYFILE"
  log "SSL certificate: $SSL_CERTFILE"
  log "SSL private key: $SSL_KEYFILE"
}

prepare_source() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    if git -C "$INSTALL_DIR" status --porcelain 2>/dev/null | grep -q . && [[ "$ASSUME_YES" != true ]]; then
      log "The existing source directory contains local changes."
      if ! ask_yes_no "Replace local source changes with branch $BRANCH?"; then
        die "Installation cancelled to protect local source changes."
      fi
    fi
    log "Updating source from $BRANCH..."
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
    git -C "$INSTALL_DIR" clean -fd
  else
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
  fi

  cd "$INSTALL_DIR"
  [[ -f docker-compose.yml ]] || die "docker-compose.yml not found."
  [[ -f Dockerfile ]] || die "Dockerfile not found."
  [[ -f .env.example ]] || die ".env.example not found."
}

prepare_passwords() {
  mkdir -p "$DATA_DIR"
  chmod 700 "$DATA_DIR"

  if [[ -s "$DATA_DIR/.postgres_password" ]]; then
    POSTGRES_PASSWORD="$(cat "$DATA_DIR/.postgres_password")"
  else
    POSTGRES_PASSWORD="$(openssl rand -hex 32)"
    printf '%s' "$POSTGRES_PASSWORD" > "$DATA_DIR/.postgres_password"
    chmod 600 "$DATA_DIR/.postgres_password"
  fi

  if [[ -s "$DATA_DIR/.admin_password" ]]; then
    ADMIN_PASSWORD="$(cat "$DATA_DIR/.admin_password")"
  else
    ADMIN_PASSWORD="$(openssl rand -hex 18)"
    printf '%s' "$ADMIN_PASSWORD" > "$DATA_DIR/.admin_password"
    chmod 600 "$DATA_DIR/.admin_password"
  fi
}

write_env() {
  if [[ "$DATABASE" == "timescaledb" ]]; then
    DATABASE_URL="postgresql+asyncpg://pasarguard:$POSTGRES_PASSWORD@127.0.0.1:5432/pasarguard"
    mkdir -p "$DATA_DIR/timescaledb"
  else
    DATABASE_URL="sqlite+aiosqlite:////var/lib/pasarguard/db.sqlite3"
  fi

  if [[ "$SSL_MODE" != "none" ]]; then UVICORN_PORT=443; else UVICORN_PORT=8000; fi
  cat > "$ENV_FILE" <<EOF
UVICORN_HOST=0.0.0.0
UVICORN_PORT=$UVICORN_PORT
UVICORN_SSL_CERTFILE=$SSL_CERTFILE
UVICORN_SSL_KEYFILE=$SSL_KEYFILE
UVICORN_SSL_CA_TYPE=public
PASARGUARD_SSL_ENABLED=$([[ "$SSL_MODE" == "none" ]] && echo False || echo True)
PASARGUARD_SSL_MODE=$SSL_MODE
PASARGUARD_SSL_IDENTIFIER=$SSL_IDENTIFIER
PASARGUARD_SSL_CERTFILE=$SSL_CERTFILE
PASARGUARD_SSL_KEYFILE=$SSL_KEYFILE
ROLE=all-in-one
SQLALCHEMY_DATABASE_URL=$DATABASE_URL
SQLALCHEMY_POOL_SIZE=5
SQLALCHEMY_MAX_OVERFLOW=5
SQLALCHEMY_POOL_RECYCLE=300
SQLALCHEMY_POOL_TIMEOUT=5
SQLALCHEMY_CONNECT_TIMEOUT=5
SUDO_USERNAME=admin
SUDO_PASSWORD=$ADMIN_PASSWORD
DISABLE_RECORDING_NODE_USAGE=$([[ "$DATABASE" == "timescaledb" ]] && echo False || echo True)
ENABLE_RECORDING_NODES_STATS=$([[ "$DATABASE" == "timescaledb" ]] && echo True || echo False)
EOF
  chmod 600 "$ENV_FILE"
}

wait_for_timescaledb() {
  log "Waiting for TimescaleDB..."
  for i in {1..60}; do
    if docker compose exec -T timescaledb pg_isready -U pasarguard -d pasarguard >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  docker compose logs --tail=120 timescaledb || true
  die "TimescaleDB did not become ready."
}

install_panel() {
  export POSTGRES_PASSWORD
  docker compose config >/dev/null

  if [[ "$DATABASE" == "timescaledb" ]]; then
    log "Starting TimescaleDB..."
    docker compose up -d timescaledb
    wait_for_timescaledb
  else
    log "SQLite selected; TimescaleDB container will not be started."
    docker compose stop timescaledb >/dev/null 2>&1 || true
  fi

  log "Building PasarGuard + AmneziaWG..."
  docker compose build --pull pasarguard

  log "Starting PasarGuard..."
  docker compose up -d pasarguard

  log "Waiting for PasarGuard..."
  local health_url="http://127.0.0.1:8000/health"
  [[ "$SSL_MODE" != "none" ]] && health_url="https://127.0.0.1:443/health"
  for i in {1..90}; do
    if [[ "$SSL_MODE" != "none" ]]; then
      curl -kfsS --max-time 3 "$health_url" >/dev/null 2>&1 && return 0
    else
      curl -fsS --max-time 3 "$health_url" >/dev/null 2>&1 && return 0
    fi
    sleep 2
  done

  docker compose logs --tail=160 pasarguard || true
  die "PasarGuard health check failed."
}

main() {
  parse_args "$@"
  detect_environment
  install_base
  confirm_database
  select_ssl
  prepare_source
  issue_ssl_certificate
  prepare_passwords
  write_env
  install_panel

  echo
  echo "=============================================="
  echo " PasarGuard + AmneziaWG installation complete"
  echo "=============================================="
  echo "Panel:       http://SERVER-IP:8000"
  echo "Username:    admin"
  echo "Password:    $ADMIN_PASSWORD"
  if [[ "$DATABASE" == "timescaledb" ]]; then
    echo "Database:    TimescaleDB/PostgreSQL 16"
    echo "DB name:     pasarguard"
    echo "DB user:     pasarguard"
    echo "DB port:     127.0.0.1:5432"
  else
    echo "Database:    SQLite"
    echo "DB file:     $DATA_DIR/db.sqlite3"
  fi
  echo "Source:      $REPO"
  echo "Branch:      $BRANCH"
  echo "Data:        $DATA_DIR"
  echo "Compose:     $INSTALL_DIR/docker-compose.yml"
  if [[ "$SSL_MODE" != "none" ]]; then
    echo "SSL mode:    $SSL_MODE"
    echo "SSL host:    $SSL_IDENTIFIER"
    echo "SSL cert:    $SSL_CERTFILE"
    echo "SSL key:     $SSL_KEYFILE"
    echo "URL:         https://$SSL_IDENTIFIER"
  else
    echo "SSL:         disabled"
    echo "URL:         http://127.0.0.1:8000 (localhost only)"
  fi
  echo "=============================================="
  docker compose ps
}

main "$@"
