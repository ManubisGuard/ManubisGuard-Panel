#!/usr/bin/env bash
set -Eeuo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"
DATA_DIR="/var/lib/pasarguard"
ENV_FILE="$INSTALL_DIR/.env"
DATABASE="sqlite"

[[ "$EUID" -eq 0 ]] || { echo "ERROR: run this installer as root."; exit 1; }

log() { echo "[PasarGuard] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  echo "Usage: $0 install [--database sqlite|timescaledb]"
  echo
  echo "Database:"
  echo "  sqlite       SQLite (default)"
  echo "  timescaledb  TimescaleDB/PostgreSQL 16"
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

install_base() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl git openssl python3

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker and Compose v2 already available."
  else
    if ! command -v docker >/dev/null 2>&1; then
      log "Installing Docker using the official PasarGuard-compatible method..."
      apt-get remove -y docker.io docker-compose docker-compose-v2 containerd runc >/dev/null 2>&1 || true
      curl -fsSL https://get.docker.com | sh
    fi

    if ! command -v docker >/dev/null 2>&1; then
      die "Docker installation failed."
    fi

    if ! docker compose version >/dev/null 2>&1; then
      if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y docker-compose-plugin >/dev/null 2>&1 || true
      fi
    fi
  fi

  systemctl enable --now docker >/dev/null 2>&1 || true
  docker info >/dev/null 2>&1 || die "Docker is not running."
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is not available."
}

prepare_source() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Updating source from $BRANCH..."
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
    git -C "$INSTALL_DIR" clean -fd
  else
    rm -rf "$INSTALL_DIR"
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

  log "Validating Docker Compose configuration..."
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
  install_base
  prepare_source
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
