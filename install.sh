#!/usr/bin/env bash
set -Eeuo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"
DATA_DIR="/var/lib/pasarguard"
ENV_FILE="$INSTALL_DIR/.env"

[[ "$EUID" -eq 0 ]] || { echo "ERROR: run this installer as root."; exit 1; }

log() { echo "[PasarGuard] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

install_base() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl git openssl python3 docker.io docker-compose-v2
  systemctl enable --now docker
  docker info >/dev/null 2>&1 || die "Docker is not running."
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is not available."
}

install_base

mkdir -p "$DATA_DIR/timescaledb"
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

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Updating existing source..."
  git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
  git -C "$INSTALL_DIR" clean -fd
else
  rm -rf "$INSTALL_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
[[ -f docker-compose.yml ]] || die "docker-compose.yml not found in $BRANCH."
[[ -f .env.example ]] || die ".env.example not found in $BRANCH."

cat > "$ENV_FILE" <<EOF
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
ROLE=all-in-one
SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://pasarguard:$POSTGRES_PASSWORD@127.0.0.1:5432/pasarguard
SQLALCHEMY_POOL_SIZE=5
SQLALCHEMY_MAX_OVERFLOW=5
SQLALCHEMY_POOL_RECYCLE=300
SQLALCHEMY_POOL_TIMEOUT=5
SQLALCHEMY_CONNECT_TIMEOUT=5
SUDO_USERNAME=admin
SUDO_PASSWORD=$ADMIN_PASSWORD
DISABLE_RECORDING_NODE_USAGE=False
ENABLE_RECORDING_NODES_STATS=True
EOF
chmod 600 "$ENV_FILE"

export POSTGRES_PASSWORD
log "Validating Docker Compose configuration..."
docker compose config >/dev/null

log "Starting TimescaleDB..."
docker compose up -d timescaledb

log "Waiting for TimescaleDB..."
for i in {1..60}; do
  if docker compose exec -T timescaledb pg_isready -U pasarguard -d pasarguard >/dev/null 2>&1; then
    break
  fi
  [[ "$i" -eq 60 ]] && die "TimescaleDB did not become ready."
  sleep 2
done

log "Building PasarGuard image..."
docker compose build --pull

log "Starting PasarGuard..."
docker compose up -d pasarguard

log "Waiting for PasarGuard..."
for i in {1..90}; do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  [[ "$i" -eq 90 ]] && {
    docker compose logs --tail=120 pasarguard || true
    die "PasarGuard health check failed."
  }
  sleep 2
done

echo
echo "=============================================="
echo " PasarGuard + AmneziaWG installation complete"
echo "=============================================="
echo "Panel:       http://SERVER-IP:8000"
echo "Username:    admin"
echo "Password:    $ADMIN_PASSWORD"
echo "Database:    TimescaleDB/PostgreSQL 16"
echo "DB name:     pasarguard"
echo "DB user:     pasarguard"
echo "DB port:     127.0.0.1:5432"
echo "Source:      $REPO"
echo "Branch:      $BRANCH"
echo
echo "Data:        $DATA_DIR"
echo "Compose:     $INSTALL_DIR/docker-compose.yml"
echo "=============================================="
docker compose ps
