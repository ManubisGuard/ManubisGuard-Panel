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
  echo "  --override   Explicitly allow replacement of detected PasarGuard DB/data"
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
    if docker compose version >/dev/null 2>&1; then
      COMPOSE_VERSION="$(docker compose version 2>/dev/null || true)"
      if docker info >/dev/null 2>&1; then
        log "Docker detected and healthy: $DOCKER_VERSION"
        log "Compose detected: $COMPOSE_VERSION"
        log "Action: reuse existing Docker installation."
      else
        log "Docker is installed but the daemon is not healthy."
        systemctl enable --now docker >/dev/null 2>&1 || true
        docker info >/dev/null 2>&1 || die "Docker is installed but cannot be started."
      fi
    else
      log "Docker detected but Docker Compose v2 is missing."
      if ask_yes_no "Install only the missing Docker Compose plugin?"; then
        apt-get update
        apt-get install -y docker-compose-plugin
      else
        die "Docker Compose v2 is required."
      fi
    fi
  else
    log "Docker not detected."
    if ask_yes_no "Install Docker using the official Docker repository?"; then
      install_docker
    else
      die "Docker is required."
    fi
  fi

  if [[ -f "$DATA_DIR/db.sqlite3" ]]; then
    log "Existing SQLite database detected: $DATA_DIR/db.sqlite3"
  fi

  if [[ -d "$DATA_DIR/timescaledb" ]] && find "$DATA_DIR/timescaledb" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .; then
    log "Existing TimescaleDB data detected: $DATA_DIR/timescaledb"
  fi

  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Eq '(^|_)timescaledb$|pasarguard.*timescaledb'; then
    log "Existing TimescaleDB container detected."
  fi

  if ss -lnt 2>/dev/null | grep -qE '127\.0\.0\.1:5432|0\.0\.0\.0:5432|\*:5432'; then
    log "Port 5432 is already in use."
  fi

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Existing PasarGuard source detected: $INSTALL_DIR"
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
  if [[ -d "$DATA_DIR/timescaledb" ]] && find "$DATA_DIR/timescaledb" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .; then
    timescale_exists=true
  fi
  ss -lnt 2>/dev/null | grep -qE '127\.0\.0\.1:5432|0\.0\.0\.0:5432|\*:5432' && port5432=true || true

  if [[ "$DATABASE" == "sqlite" ]]; then
    if $sqlite_exists; then
      echo
      log "SQLite database already exists."
      if [[ "$OVERRIDE" == true ]]; then
        log "Override requested, but existing SQLite data will NOT be deleted automatically."
      elif ! ask_yes_no "Use the existing SQLite database?"; then
        die "Installation cancelled to protect the existing SQLite database."
      fi
    fi
    return
  fi

  if $timescale_exists || $port5432; then
    echo
    log "Existing PostgreSQL/TimescaleDB resources detected."
    $timescale_exists && log "  Data directory: $DATA_DIR/timescaledb"
    $port5432 && log "  TCP port 5432: already in use"
    echo
    if [[ "$OVERRIDE" == true ]]; then
      log "Override requested. Existing database is still preserved; the installer will not purge or delete an external database."
    elif ! ask_yes_no "Use the existing TimescaleDB/PostgreSQL environment if compatible?"; then
      die "Installation cancelled. No database data was modified."
    fi
  fi
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

  cat > "$ENV_FILE" <<EOF
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
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
  for i in {1..90}; do
    if curl -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
      return 0
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
  prepare_source
  confirm_database
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
  echo "=============================================="
  docker compose ps
}

main "$@"
