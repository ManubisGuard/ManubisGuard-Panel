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
OVERRIDE=false
MIN_FREE_MB="${MANUBISGUARD_MIN_FREE_MB:-6144}"

log() { printf '[manubisguard-install] %s\n' "$*"; }
die() { printf '[manubisguard-install] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "run this installer as root"

usage() {
  cat <<'EOF'
ManubisGuard installer

Usage:
  install-manubisguard.sh install [--database sqlite|timescaledb] [--yes] [--override]

Defaults:
  database: timescaledb
  branch:   feature/amnezia-wg
  install:  /opt/manubisguard-panel
  data:     /var/lib/manubisguard

Options:
  --database sqlite|timescaledb
  --yes|-y      non-interactive safe defaults
  --override    replace the checked-out source with the selected branch; persistent
                database credentials/data are preserved
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
  mkdir -p "$DATA_DIR" "$BACKUP_DIR"
  chmod 700 "$DATA_DIR" "$BACKUP_DIR"
  ensure_secret "$DATA_DIR/.postgres_password" 32
  ensure_secret "$DATA_DIR/.admin_password" 18

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
  upsert_env PASARGUARD_SSL_ENABLED False
  upsert_env PASARGUARD_SSL_MODE none
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
  docker compose -f docker-compose.yml build --pull manubisguard
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
  curl -kfsS --max-time 10 https://127.0.0.1:8000/health >/dev/null || die "Panel HTTPS health check failed."
}

install_helper() {
  install -m 0755 "$INSTALL_DIR/scripts/manubisguard-migrate.sh" /usr/local/bin/manubisguard-migrate
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
  echo "Panel:       http://SERVER-IP:8000"
  echo "Username:    admin"
  echo "Password:    $admin_password"
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

  prepare_source
  prepare_env
  validate_compose
  start_stack
  verify_stack
  install_helper
  show_result
}

main "$@"
