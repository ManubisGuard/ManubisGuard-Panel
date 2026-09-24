#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${MANUBISGUARD_REPO:-https://github.com/ManubisGuard/ManubisGuard-Panel.git}"
BRANCH="${MANUBISGUARD_BRANCH:-feature/amnezia-wg}"
ROOT="${MANUBISGUARD_ROOT:-/opt/manubisguard-panel}"
ENV_FILE="$ROOT/.env"
MIN_FREE_MB="${MANUBISGUARD_MIN_FREE_MB:-8192}"
IMAGE="ghcr.io/arsamnikzaad/manubisguard-panel:feature-amnezia-wg"

log() { printf '[manubisguard-install] %s\n' "$*"; }
die() { printf '[manubisguard-install] ERROR: %s\n' "$*" >&2; exit 1; }

[ "${EUID:-$(id -u)}" -eq 0 ] || die "Run as root."
command -v git >/dev/null 2>&1 || die "git is required."
command -v curl >/dev/null 2>&1 || die "curl is required."
command -v openssl >/dev/null 2>&1 || die "openssl is required."

install_docker_if_missing() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return 0
  fi

  log "Installing Docker Engine and Compose plugin..."
  apt-get clean
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl git openssl

  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi

  systemctl enable --now docker
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is unavailable."
}

check_disk() {
  local available
  available="$(df -Pm / | awk 'NR==2 {print $4}')"
  [[ "$available" =~ ^[0-9]+$ ]] || die "Could not determine free disk space."
  if [ "$available" -lt "$MIN_FREE_MB" ]; then
    apt-get clean || true
    available="$(df -Pm / | awk 'NR==2 {print $4}')"
  fi
  [ "$available" -ge "$MIN_FREE_MB" ] ||
    die "At least ${MIN_FREE_MB}MB free space is required; available=${available}MB."
}

checkout_source() {
  if [ -d "$ROOT/.git" ]; then
    log "Updating existing checkout to $BRANCH..."
    git -C "$ROOT" fetch --prune origin "$BRANCH"
    git -C "$ROOT" checkout -B "$BRANCH" "origin/$BRANCH"
    git -C "$ROOT" reset --hard "origin/$BRANCH"
  else
    log "Cloning $BRANCH..."
    mkdir -p "$(dirname "$ROOT")"
    git clone --branch "$BRANCH" --single-branch "$REPO" "$ROOT"
  fi
}

generate_env() {
  if [ -s "$ENV_FILE" ]; then
    log "Keeping existing $ENV_FILE"
    return 0
  fi

  local password
  password="$(openssl rand -hex 32)"
  umask 077
  cat >"$ENV_FILE" <<EOF
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
POSTGRES_DB=manubisguard
POSTGRES_USER=manubisguard
POSTGRES_PASSWORD=$password
SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://manubisguard:$password@127.0.0.1:5432/manubisguard
MANUBISGUARD_COMPOSE_SERVICE=manubisguard
MANUBISGUARD_DB_SERVICE=timescaledb
MANUBISGUARD_DATA_DIR=/var/lib/manubisguard
EOF
  chmod 600 "$ENV_FILE"
}

prepare_runtime_root() {
  mkdir -p /var/lib/manubisguard/timescaledb /var/lib/manubisguard/migration
  chmod 700 /var/lib/manubisguard /var/lib/manubisguard/timescaledb /var/lib/manubisguard/migration
}

start_panel() {
  cd "$ROOT"
  POSTGRES_PASSWORD="$(grep '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)" \
    docker compose -f docker-compose.yml config -q
  log "Pulling latest branch image and TimescaleDB image..."
  docker compose -f docker-compose.yml pull --policy always --ignore-buildable
  log "Starting ManubisGuard without a local Docker build..."
  docker compose -f docker-compose.yml up -d --no-build --remove-orphans --wait --wait-timeout 180
}

verify_install() {
  cd "$ROOT"
  local service container
  service="manubisguard"
  container="$(docker compose -f docker-compose.yml ps -q "$service")"
  [ -n "$container" ] || die "ManubisGuard container was not created."

  docker inspect -f '{{.State.Status}}' "$container" | grep -qx running || die "ManubisGuard container is not running."
  docker exec "$container" python -c 'import app; print("IMPORT_OK")' | grep -qx IMPORT_OK ||
    die "Python application import check failed."
  curl -fsS --max-time 10 http://127.0.0.1:8000/health >/dev/null ||
    die "Panel health endpoint did not respond successfully."

  log "Installation checks completed: container running, Python import check executed, HTTP health check executed."
  log "Compose service: manubisguard"
  log "Install root: $ROOT"
}

install_docker_if_missing
check_disk
checkout_source
generate_env
prepare_runtime_root
start_panel
verify_install
