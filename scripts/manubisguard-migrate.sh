#!/usr/bin/env bash
set -Eeuo pipefail

# Safe host-side orchestration for legacy PasarGuard -> ManubisGuard migration.
# The panel container never receives the Docker socket. Temporary compatibility
# databases are created by this host script and reached only through localhost.
#
# Default: analyze + isolated staging + migration + validation + staging dump.
# Destructive production cutover requires: --apply
#
# The previous production database is NEVER deleted. A verified production safety
# dump is created immediately before the final database rename.

SCRIPT_NAME="manubisguard-migrate"
COMPOSE_FILE="${MANUBISGUARD_COMPOSE_FILE:-/opt/manubisguard-panel/docker-compose.yml}"
DATA_DIR="${MANUBISGUARD_DATA_DIR:-/var/lib/manubisguard}"
MIGRATION_ROOT="$DATA_DIR/migration"
ID="$(LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 12 || true)"
WORKDIR="$MIGRATION_ROOT/$ID"
INPUTDIR="$WORKDIR/input"

APPLY=false
CHECK_ONLY=false
KEEP_WORKDIR=true
BACKUP_SOURCE=""
MANUBISGUARD_SOURCE_TIMESCALE="${MANUBISGUARD_MIGRATION_SOURCE_TIMESCALE:-}"
PANEL_CONTAINER=""
DB_CONTAINER=""
COMPOSE_SERVICE=""
DB_SERVICE="timescaledb"

PROD_URL=""
PROD_HOST=""
PROD_PORT=""
DB_NAME=""
DB_USER=""
DB_PASS=""
ADMIN_USER=""
ADMIN_PASS=""
PG_MAJOR=""
PROD_TS_VERSION=""
PROD_HAS_TIMESCALE=false
SOURCE_PG_MAJOR=""
SOURCE_TS_VERSION=""

TEMP_CONTAINER=""
TEMP_VOLUME=""
TEMP_PORT=""
MARIADB_CONTAINER=""
MARIADB_VOLUME=""
MARIADB_PASSWORD=""
MARIADB_SOURCE_URL=""
TEMP_VOLUME=""
TEMP_PORT=""
STAGING_DB=""
STAGING_URL=""
PANEL_BACKUP=""
PANEL_DUMP=""
CUTOVER_DB=""
CUTOVER_URL=""
PREVIOUS_DB=""
FAILED_DB=""
COMPOSE_SHA256=""
CURRENT_ENV="/opt/manubisguard-panel/.env"
ENV_CANDIDATE=""
ENV_PREVIOUS=""
ENV_IMPORTED=false
RUNTIME_ASSET_STAGE=""
RUNTIME_ASSET_PREVIOUS=""
RUNTIME_ASSET_APPLIED=false

log() { printf '[%s] %s\n' "$SCRIPT_NAME" "$*"; }
warn() { printf '[%s] WARNING: %s\n' "$SCRIPT_NAME" "$*" >&2; }
die() { printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
ManubisGuard legacy migration

Usage:
  manubisguard-migrate BACKUP [--apply]
  manubisguard-migrate --check BACKUP

Default mode is staging-only and never changes the production database.
--apply performs the final production cutover after staging and cutover validation.

Options:
  --apply     Perform the final production cutover.
  --keep      Keep migration artifacts (default).
  --clean     Remove the workspace on successful exit except safety-critical errors.
  --help      Show this help.

The backup is copied under the configured ManubisGuard data directory before the panel reads it.
EOF
}

cleanup() {
  set +e
  if [ -n "$MARIADB_CONTAINER" ]; then docker rm -f "$MARIADB_CONTAINER" >/dev/null 2>&1 || true; fi
  if [ -n "$MARIADB_VOLUME" ]; then docker volume rm "$MARIADB_VOLUME" >/dev/null 2>&1 || true; fi
  if [ -n "$TEMP_CONTAINER" ]; then
    docker rm -f "$TEMP_CONTAINER" >/dev/null 2>&1 || true
  fi
  if [ -n "$TEMP_VOLUME" ]; then
    docker volume rm "$TEMP_VOLUME" >/dev/null 2>&1 || true
  fi
  if [ "$KEEP_WORKDIR" = false ] && [ -n "$WORKDIR" ] && [ -d "$WORKDIR" ]; then
    # Never remove a workspace containing a verified production safety dump.
    if [ ! -s "$WORKDIR/production-safety.dump" ]; then
      rm -rf -- "$WORKDIR"
    fi
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

require_root() {
  [ "$EUID" -eq 0 ] || die "Run as root."
  command -v docker >/dev/null 2>&1 || die "Docker is required."
  command -v python3 >/dev/null 2>&1 || die "python3 is required."
  command -v curl >/dev/null 2>&1 || die "curl is required."
  docker info >/dev/null 2>&1 || die "Docker daemon is not available."
  [ -f "$COMPOSE_FILE" ] || die "Compose file not found: $COMPOSE_FILE"
  mkdir -p "$INPUTDIR"
  chmod 700 "$MIGRATION_ROOT" "$WORKDIR" "$INPUTDIR"
}

url_field() {
  local url="$1"
  local field="$2"
  python3 - "$url" "$field" <<'PY'
import sys
from urllib.parse import unquote, urlsplit
url = sys.argv[1]
field = sys.argv[2]
p = urlsplit(url)
if field == "username":
    value = p.username or ""
elif field == "password":
    value = unquote(p.password or "")
elif field == "hostname":
    value = p.hostname or ""
elif field == "port":
    value = str(p.port or 5432)
elif field == "database":
    value = (p.path or "").lstrip("/")
else:
    raise SystemExit(2)
print(value)
PY
}

json_get() {
  local json="$1"
  local path="$2"
  JSON_VALUE="$json" JSON_PATH="$path" python3 - <<'PY'
import json, os
value = json.loads(os.environ["JSON_VALUE"])
path = os.environ["JSON_PATH"].lstrip(".")
for key in path.split(".") if path else []:
    value = value.get(key) if isinstance(value, dict) else None
if isinstance(value, (dict, list)):
    print(json.dumps(value, ensure_ascii=False))
elif value is None:
    print("")
else:
    print(str(value))
PY
}

extract_json_object() {
  local text="$1"
  JSON_TEXT="$text" python3 - <<'PY'
import json, os
text = os.environ["JSON_TEXT"]
start = text.find("{")
if start < 0:
    raise SystemExit("No JSON object found in command output.")
value, _ = json.JSONDecoder().raw_decode(text[start:])
print(json.dumps(value, ensure_ascii=False))
PY
}

find_services() {
  local services service
  local -a candidates=()
  services="$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || true)"
  [ -n "$services" ] || die "No services found in compose."

  if [ -n "${MANUBISGUARD_COMPOSE_SERVICE:-}" ]; then
    COMPOSE_SERVICE="$MANUBISGUARD_COMPOSE_SERVICE"
    printf '%s\n' "$services" | grep -qx "$COMPOSE_SERVICE" ||
      die "Configured ManubisGuard panel service not found in compose: $COMPOSE_SERVICE"
  else
    for service in manubisguard panel pasarguard; do
      if printf '%s\n' "$services" | grep -qx "$service"; then
        candidates+=("$service")
      fi
    done

    case "${#candidates[@]}" in
      0)
        die "No ManubisGuard panel service candidate found in compose (expected one of: manubisguard, panel, pasarguard)."
        ;;
      1)
        COMPOSE_SERVICE="${candidates[0]}"
        ;;
      *)
        die "Multiple ManubisGuard panel service candidates found in compose: ${candidates[*]}. Set MANUBISGUARD_COMPOSE_SERVICE explicitly."
        ;;
    esac
  fi

  if [ -n "${MANUBISGUARD_DB_SERVICE:-}" ]; then
    DB_SERVICE="$MANUBISGUARD_DB_SERVICE"
    printf '%s\n' "$services" | grep -qx "$DB_SERVICE" ||
      die "Configured database service not found in compose: $DB_SERVICE"
  elif printf '%s\n' "$services" | grep -qx 'timescaledb'; then
    DB_SERVICE="timescaledb"
  elif printf '%s\n' "$services" | grep -qx 'postgresql'; then
    DB_SERVICE="postgresql"
  else
    die "PostgreSQL/TimescaleDB service not found in compose."
  fi

  PANEL_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q "$COMPOSE_SERVICE" 2>/dev/null || true)"
  DB_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q "$DB_SERVICE" 2>/dev/null || true)"
  [ -n "$PANEL_CONTAINER" ] || die "Panel container is not running."
  [ -n "$DB_CONTAINER" ] || die "Database container is not running."
}

load_database_identity() {
  PROD_URL="$(docker exec "$PANEL_CONTAINER" printenv SQLALCHEMY_DATABASE_URL 2>/dev/null || true)"
  [ -n "$PROD_URL" ] || die "SQLALCHEMY_DATABASE_URL is unavailable in the panel container."

  PROD_HOST="$(url_field "$PROD_URL" hostname)"
  PROD_PORT="$(url_field "$PROD_URL" port)"
  DB_NAME="$(url_field "$PROD_URL" database)"
  DB_USER="$(url_field "$PROD_URL" username)"
  DB_PASS="$(url_field "$PROD_URL" password)"

  case "$PROD_HOST" in
    127.0.0.1|localhost|::1) ;;
    *) die "Production DB host is not local: $PROD_HOST" ;;
  esac
  [ -n "$DB_NAME" ] || die "Production DB name is empty."
  [ -n "$DB_USER" ] || die "Production DB user is empty."
  [ -n "$DB_PASS" ] || die "Production DB password is empty; refusing automated migration."

  ADMIN_USER="$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER 2>/dev/null || true)"
  ADMIN_PASS="$(docker exec "$DB_CONTAINER" printenv POSTGRES_PASSWORD 2>/dev/null || true)"
  ADMIN_USER="${ADMIN_USER:-$DB_USER}"
  ADMIN_PASS="${ADMIN_PASS:-$DB_PASS}"

  local server_num
  server_num="$(docker exec -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER"     psql -X -U "$ADMIN_USER" -d postgres -Atc 'SHOW server_version_num;' 2>/dev/null || true)"
  [[ "$server_num" =~ ^[0-9]+$ ]] || die "Could not determine PostgreSQL server major version."
  PG_MAJOR="$((server_num / 10000))"

  PROD_TS_VERSION="$(docker exec -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER"     psql -X -U "$ADMIN_USER" -d "$DB_NAME" -Atc     "SELECT COALESCE((SELECT extversion FROM pg_extension WHERE extname='timescaledb'), '');"     2>/dev/null || true)"
  if [ -n "$PROD_TS_VERSION" ]; then
    PROD_HAS_TIMESCALE=true
  fi
  log "Production DB=$DB_NAME PostgreSQL=$PG_MAJOR TimescaleDB=${PROD_TS_VERSION:-none}"
}

capture_compose_integrity() {
  [ -f "$COMPOSE_FILE" ] || die "Compose file not found: $COMPOSE_FILE"
  COMPOSE_SHA256="$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')"
  [ -n "$COMPOSE_SHA256" ] || die "Could not fingerprint the ManubisGuard compose file."
  printf '%s  %s\n' "$COMPOSE_SHA256" "$COMPOSE_FILE" >"$WORKDIR/compose.sha256"
  log "Compose integrity captured: $COMPOSE_SHA256"
}

env_get() {
  local file="$1"
  local key="$2"
  python3 - "$file" "$key" <<'PY'
import re, sys
path, key = sys.argv[1:]
try:
    text = open(path, encoding="utf-8").read()
except OSError:
    raise SystemExit(1)
pattern = re.compile(r"^\\s*" + re.escape(key) + r"\\s*=\\s*(.*?)\\s*$")
for raw in text.splitlines():
    match = pattern.match(raw)
    if match:
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\\\"":
            value = value[1:-1]
        print(value)
        break
PY
}

prepare_runtime_env() {
  [ -f "$CURRENT_ENV" ] || die "Current ManubisGuard .env not found: $CURRENT_ENV"
  ENV_CANDIDATE="$WORKDIR/.env.pre-restore"
  RUNTIME_ASSET_STAGE="$WORKDIR/runtime-assets"
  mkdir -p "$RUNTIME_ASSET_STAGE"
  # The installed ManubisGuard deployment is authoritative.
  # Backup deployment identity, docker-compose.yml, repo URLs and image settings are never imported.
  cp -- "$CURRENT_ENV" "$ENV_CANDIDATE"
  cp -- "$CURRENT_ENV" "$WORKDIR/.env.before-migration"
  chmod 600 "$ENV_CANDIDATE" "$WORKDIR/.env.before-migration"
  ENV_IMPORTED=false
  log "Preserving current ManubisGuard runtime .env; backup deployment environment and docker-compose are not imported."
}
apply_runtime_env() {
  [ "$ENV_IMPORTED" = true ] || return 0
  [ -s "$ENV_CANDIDATE" ] || die "Prepared .env candidate is missing."
  ENV_PREVIOUS="$WORKDIR/.env.pre-cutover"
  cp -- "$CURRENT_ENV" "$ENV_PREVIOUS"
  chmod 600 "$ENV_PREVIOUS"
  if ! install -m 600 "$ENV_CANDIDATE" "$CURRENT_ENV"; then
    rollback_runtime_env
    rollback_runtime_assets
    return 1
  fi
  log "Legacy runtime settings applied to ManubisGuard .env."
}

rollback_runtime_env() {
  [ -s "$ENV_PREVIOUS" ] || return 0
  install -m 600 "$ENV_PREVIOUS" "$CURRENT_ENV"
  log "Runtime .env rolled back to pre-migration state."
}

apply_runtime_assets() {
  [ -d "$RUNTIME_ASSET_STAGE" ] || return 0
  local assets=()
  while IFS= read -r -d '' asset; do
    assets+=("$asset")
  done < <(find "$RUNTIME_ASSET_STAGE" -type f -print0 2>/dev/null)

  [ "${#assets[@]}" -gt 0 ] || return 0
  RUNTIME_ASSET_PREVIOUS="$WORKDIR/runtime-assets-before-cutover"
  rm -rf -- "$RUNTIME_ASSET_PREVIOUS"
  mkdir -p "$RUNTIME_ASSET_PREVIOUS"
  : >"$RUNTIME_ASSET_PREVIOUS/.missing"

  local asset rel target backup_target
  for asset in "${assets[@]}"; do
    rel="${asset#"$RUNTIME_ASSET_STAGE"/}"
    case "$rel" in
      ""|/*|../*|*/../*|*/..|..)
        warn "Unsafe staged runtime asset path: $rel"
        return 1
        ;;
    esac
    target="$DATA_DIR/$rel"
    case "$target" in
      "$DATA_DIR"/*) ;;
      *) warn "Runtime asset escaped data directory: $rel"; return 1 ;;
    esac
    local target_parent
    target_parent="$(realpath -m "$(dirname "$target")")"
    case "$target_parent" in
      "$DATA_DIR"/*) ;;
      *) warn "Runtime asset parent escaped data directory: $rel"; return 1 ;;
    esac
    if [ -L "$target" ]; then
      warn "Refusing to overwrite symlinked runtime asset: $target"
      return 1
    fi
    if [ -e "$target" ]; then
      backup_target="$RUNTIME_ASSET_PREVIOUS/$rel"
      mkdir -p "$(dirname "$backup_target")"
      cp -a -- "$target" "$backup_target"
    else
      printf '%s\n' "$rel" >>"$RUNTIME_ASSET_PREVIOUS/.missing"
    fi
  done

  RUNTIME_ASSET_APPLIED=true
  for asset in "${assets[@]}"; do
    rel="${asset#"$RUNTIME_ASSET_STAGE"/}"
    target="$DATA_DIR/$rel"
    mkdir -p "$(dirname "$target")"
    if ! install -m 600 "$asset" "$target"; then
      rollback_runtime_assets
      return 1
    fi
  done
  log "Referenced legacy runtime SSL assets prepared and applied safely."
}

rollback_runtime_assets() {
  [ "$RUNTIME_ASSET_APPLIED" = true ] || return 0
  [ -d "$RUNTIME_ASSET_STAGE" ] || return 0
  local asset rel target backup_target
  while IFS= read -r -d '' asset; do
    rel="${asset#"$RUNTIME_ASSET_STAGE"/}"
    target="$DATA_DIR/$rel"
    if grep -F -x -q -- "$rel" "$RUNTIME_ASSET_PREVIOUS/.missing" 2>/dev/null; then
      rm -f -- "$target"
    else
      backup_target="$RUNTIME_ASSET_PREVIOUS/$rel"
      if [ -f "$backup_target" ]; then
        install -m 600 "$backup_target" "$target"
      fi
    fi
  done < <(find "$RUNTIME_ASSET_STAGE" -type f -print0 2>/dev/null)
  RUNTIME_ASSET_APPLIED=false
  log "Runtime assets rolled back to pre-migration state."
}

verify_compose_integrity() {
  [ -n "$COMPOSE_SHA256" ] || die "Compose integrity fingerprint is missing."
  [ -f "$COMPOSE_FILE" ] || die "CRITICAL: ManubisGuard compose file disappeared."
  local current
  current="$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')"
  if [ "$current" != "$COMPOSE_SHA256" ]; then
    printf '%s  %s\n' "$current" "$COMPOSE_FILE" >"$WORKDIR/compose-changed.sha256"
    die "CRITICAL: migration attempted to change docker-compose.yml. Production deployment was not trusted."
  fi
}

compose_integrity_ok() {
  [ -n "$COMPOSE_SHA256" ] || return 1
  [ -f "$COMPOSE_FILE" ] || return 1
  local current
  current="$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')"
  if [ "$current" != "$COMPOSE_SHA256" ]; then
    printf '%s  %s\n' "$current" "$COMPOSE_FILE" >"$WORKDIR/compose-changed.sha256"
    return 1
  fi
  return 0
}


copy_backup_to_workspace() {
  [ -f "$BACKUP_SOURCE" ] || die "Backup not found: $BACKUP_SOURCE"
  PANEL_BACKUP="$INPUTDIR/$(basename -- "$BACKUP_SOURCE")"
  if [ "$(readlink -f -- "$BACKUP_SOURCE")" != "$(readlink -f -- "$PANEL_BACKUP")" ]; then
    cp --reflink=auto --preserve=mode,timestamps -- "$BACKUP_SOURCE" "$PANEL_BACKUP"
  fi
  chmod 600 "$PANEL_BACKUP"
  sha256sum "$PANEL_BACKUP" >"$WORKDIR/backup.sha256"
}

analyze_backup() {
  log "Analyzing backup without touching production..."
  local output
  if ! output="$(docker exec "$PANEL_CONTAINER"       manubisguard-cli migrate-inspect "$PANEL_BACKUP"       --live-timescale "$PROD_TS_VERSION"       ${MANUBISGUARD_SOURCE_TIMESCALE:+--source-timescale "$MANUBISGUARD_SOURCE_TIMESCALE"}       --json 2>&1)"; then
    printf '%s\n' "$output" >"$WORKDIR/analysis.error"
    die "Backup analysis was blocked. See $WORKDIR/analysis.error"
  fi
  printf '%s\n' "$output" >"$WORKDIR/analysis.json"

  local ok
  ok="$(json_get "$output" ".preflight.ok")"
  if [ "$ok" != "True" ] && [ "$ok" != "true" ]; then
    printf '%s\n' "$output"
    die "Backup preflight failed."
  fi

  local ts_error
  ts_error="$(json_get "$output" ".staging_timescale_error")"
  [ -z "$ts_error" ] || die "$ts_error"

  SOURCE_PG_MAJOR="$(json_get "$output" ".detection.source_postgres_major")"
  if [ -n "$SOURCE_PG_MAJOR" ] && ! [[ "$SOURCE_PG_MAJOR" =~ ^[0-9]+$ ]]; then
    die "Backup reported an unsafe source PostgreSQL major: $SOURCE_PG_MAJOR"
  fi
  SOURCE_TS_VERSION="$(json_get "$output" ".timescale.source_version")"
  if [ -n "$SOURCE_TS_VERSION" ] && ! [[ "$SOURCE_TS_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]]; then
    die "Backup reported an unsafe source TimescaleDB version: $SOURCE_TS_VERSION"
  fi
  log "Accepted source=$(json_get "$output" ".detection.source_product") format=$(json_get "$output" ".detection.format") PostgreSQL=${SOURCE_PG_MAJOR:-unknown} TimescaleDB=${SOURCE_TS_VERSION:-unknown}"
  if printf "%s\n" "$output" | grep -q "detected MariaDB/MySQL logical dump"; then
    log "MariaDB/MySQL logical dump detected; enabling isolated MariaDB -> PostgreSQL bridge."
  fi
  if [ "$(json_get "$output" ".uses_timescaledb")" = "True" ] || [ "$(json_get "$output" ".uses_timescaledb")" = "true" ]; then
    log "Backup contains TimescaleDB objects."
  fi
}

start_temp_mariadb() {
  [ -n "$PANEL_CONTAINER" ] || die "Panel container is required for the isolated MariaDB bridge."
  MARIADB_CONTAINER="manubisguard-migration-mariadb-$ID"
  MARIADB_VOLUME="manubisguard-migration-mariadb-$ID"
  MARIADB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  local network
  network="$(docker inspect -f '{{range $name, $value := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$PANEL_CONTAINER" | head -n1)"
  [ -n "$network" ] || die "Could not determine the Panel Docker network for MariaDB bridge."
  log "Starting isolated MariaDB 12.3.3 source runtime..."
  docker volume create --label "manubisguard.migration=$ID" "$MARIADB_VOLUME" >/dev/null
  docker run -d --name "$MARIADB_CONTAINER" --restart=no --label "manubisguard.migration=$ID" --network "$network" -e MARIADB_ROOT_PASSWORD="$MARIADB_PASSWORD" -e MARIADB_DATABASE=pasarguard -v "$MARIADB_VOLUME:/var/lib/mysql" mariadb:12.3.3 >/dev/null
  local i
  for i in $(seq 1 90); do
    if docker exec "$MARIADB_CONTAINER" mariadb-admin -uroot ping >/dev/null 2>&1; then break; fi
    if [ "$(docker inspect -f '{{.State.Status}}' "$MARIADB_CONTAINER" 2>/dev/null || true)" = "exited" ]; then docker logs "$MARIADB_CONTAINER" >"$WORKDIR/mariadb-container.log" 2>&1 || true; die "Temporary MariaDB exited. See $WORKDIR/mariadb-container.log"; fi
    sleep 2
    [ "$i" -eq 90 ] && die "Temporary MariaDB did not become ready."
  done
  local sql_member
  sql_member="$(unzip -Z1 "$PANEL_BACKUP" | grep -E '(^|/)(db_backup|database|backup)[^/]*\.sql$' | head -n1 || true)"
  [ -n "$sql_member" ] || sql_member="$(unzip -Z1 "$PANEL_BACKUP" | grep -E '\.sql$' | head -n1 || true)"
  [ -n "$sql_member" ] || die "MariaDB backup ZIP contains no SQL dump."
  log "Importing MariaDB source dump into isolated runtime: $sql_member"
  if ! unzip -p "$PANEL_BACKUP" "$sql_member" | docker exec -i "$MARIADB_CONTAINER" mariadb -uroot; then
    docker logs "$MARIADB_CONTAINER" >"$WORKDIR/mariadb-import.error" 2>&1 || true
    die "MariaDB source dump import failed. See $WORKDIR/mariadb-import.error"
  fi
  docker exec "$MARIADB_CONTAINER" mariadb -uroot -e "CREATE USER IF NOT EXISTS 'manubisguard_bridge'@'%' IDENTIFIED BY '$MARIADB_PASSWORD'; GRANT ALL PRIVILEGES ON *.* TO 'manubisguard_bridge'@'%'; FLUSH PRIVILEGES;"
  MARIADB_SOURCE_URL="$(python3 - "$MARIADB_PASSWORD" "$MARIADB_CONTAINER" <<'PY'
import sys
from urllib.parse import quote
password, host = sys.argv[1:]
print("mysql+asyncmy://manubisguard_bridge:%s@%s:3306/pasarguard" % (quote(password, safe=""), host))
PY
)"
  log "MariaDB source runtime is ready; credentials remain isolated to this migration process."
}

psql_prod() {
  docker exec -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER"     psql -X -v ON_ERROR_STOP=1 -U "$ADMIN_USER" "$@"
}

psql_temp() {
  docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER"     psql -X -v ON_ERROR_STOP=1 -U "$DB_USER" "$@"
}

start_temp_timescale() {
  local version="$1"
  [ -n "$version" ] || die "No TimescaleDB version selected for staging."
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]] || die "Unsafe TimescaleDB version: $version"

  if [ -n "$TEMP_CONTAINER" ]; then
    docker rm -f "$TEMP_CONTAINER" >/dev/null 2>&1 || true
    TEMP_CONTAINER=""
  fi
  if [ -z "$TEMP_VOLUME" ]; then
    TEMP_VOLUME="manubisguard-migration-ts-$ID"
    docker volume create --label "manubisguard.migration=$ID" "$TEMP_VOLUME" >/dev/null
  fi

  TEMP_CONTAINER="manubisguard-migration-ts-$ID"
  [ -n "$SOURCE_PG_MAJOR" ] || die "Backup source PostgreSQL major is unknown; exact compatibility runtime cannot be selected safely."
  [[ "$SOURCE_PG_MAJOR" =~ ^(10|11|12|13|14|15|16|17|18)$ ]] || die "Unsupported source PostgreSQL major: $SOURCE_PG_MAJOR"
  local image="timescale/timescaledb:${version}-pg${SOURCE_PG_MAJOR}-oss"
  log "Starting isolated source-compatible runtime: $image"
  docker pull "$image" >/dev/null
  docker run -d --name "$TEMP_CONTAINER" --restart=no \
    --label "manubisguard.migration=$ID" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASS" \
    -e POSTGRES_DB=postgres \
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -p 127.0.0.1::5432 \
    -v "$TEMP_VOLUME:/var/lib/postgresql/data" \
    "$image" >/dev/null
  TEMP_PORT="$(docker port "$TEMP_CONTAINER" 5432/tcp | sed -nE 's/.*:([0-9]+)$/\1/p' | head -n1)"
  [[ "$TEMP_PORT" =~ ^[0-9]+$ ]] || die "Could not determine temporary TimescaleDB port."

  local i
  for i in $(seq 1 90); do
    if docker exec "$TEMP_CONTAINER" pg_isready -q -U "$DB_USER" -d postgres >/dev/null 2>&1 &&        docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER"        psql -X -U "$DB_USER" -d postgres -Atc 'SELECT 1;' >/dev/null 2>&1; then
      sleep 2
      break
    fi
    if [ "$(docker inspect -f '{{.State.Status}}' "$TEMP_CONTAINER" 2>/dev/null || true)" = "exited" ]; then
      docker logs "$TEMP_CONTAINER" >"$WORKDIR/timescale-container.log" 2>&1 || true
      die "Temporary TimescaleDB exited. See $WORKDIR/timescale-container.log"
    fi
    sleep 2
    [ "$i" -eq 90 ] && die "Temporary TimescaleDB did not become ready."
  done

  local live
  live="$(docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER"     psql -X -U "$DB_USER" -d postgres -Atc     "SELECT COALESCE((SELECT default_version FROM pg_available_extensions WHERE name='timescaledb'), '');"     2>/dev/null || true)"
  log "Temporary TimescaleDB on localhost:$TEMP_PORT extension=${live:-unknown}"

  if [ -n "$PROD_TS_VERSION" ] && [ "$version" != "$PROD_TS_VERSION" ]; then
    local available
    available="$(docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
      psql -X -U "$DB_USER" -d postgres -Atc \
      "SELECT count(*) FROM pg_available_extension_versions WHERE name='timescaledb' AND version='$version';" \
      2>/dev/null || true)"
    [ "$available" = "1" ] || die "Compatibility image does not contain TimescaleDB source version $version."
  fi
}

build_temp_url() {
  STAGING_URL="$(python3 - "$DB_USER" "$DB_PASS" "$TEMP_PORT" "$STAGING_DB" <<'PY'
import sys
from urllib.parse import quote
user, password, port, db = sys.argv[1:]
print("postgresql+asyncpg://%s:%s@127.0.0.1:%s/%s" % (
    quote(user, safe=""), quote(password, safe=""), port, quote(db, safe="")
))
PY
)"
}

create_staging_database() {
  STAGING_DB="manubisguard_migration_$ID"
  psql_temp -d postgres -c "CREATE DATABASE \"$STAGING_DB\" TEMPLATE template0 OWNER \"$DB_USER\";" >/dev/null
  build_temp_url
}

run_staging() {
  log "Restoring -> staging -> Alembic HEAD -> legacy adapter -> validation..."
  local output
  local stderr_file="$WORKDIR/staging.stderr"
  local -a env_args=(-e "MANUBISGUARD_MIGRATION_STAGING_URL=$STAGING_URL" -e "MANUBISGUARD_MIGRATION_PRODUCTION_URL=$PROD_URL")
  if [ -n "$MARIADB_SOURCE_URL" ]; then env_args+=(-e "MANUBISGUARD_MARIADB_SOURCE_URL=$MARIADB_SOURCE_URL"); fi
  if output="$(docker exec "${env_args[@]}" "$PANEL_CONTAINER" manubisguard-cli migrate-staging "$PANEL_BACKUP" --external-staging ${MANUBISGUARD_SOURCE_TIMESCALE:+--source-timescale "$MANUBISGUARD_SOURCE_TIMESCALE"} --json 2>"$stderr_file")"; then
    local json_output
    if ! json_output="$(extract_json_object "$output")"; then
      printf '%s\n' "$output" >"$WORKDIR/staging.error"
      [ -s "$stderr_file" ] && cat "$stderr_file" >>"$WORKDIR/staging.error"
      cat "$WORKDIR/staging.error" >&2
      return 1
    fi
    printf '%s\n' "$json_output" >"$WORKDIR/staging.json"
    if [ -s "$stderr_file" ]; then
      cat "$stderr_file" >&2
    fi
    return 0
  fi
  {
    printf '%s\n' "$output"
    [ -s "$stderr_file" ] && cat "$stderr_file"
  } >"$WORKDIR/staging.error"
  cat "$WORKDIR/staging.error" >&2
  return 1
}

validate_staging_result() {
  [ -s "$WORKDIR/staging.json" ] || die "Staging result JSON is missing."
  local ok
  ok="$(json_get "$(cat "$WORKDIR/staging.json")" ".valid")"
  if [ "$ok" != "True" ] && [ "$ok" != "true" ]; then
    cat "$WORKDIR/staging.json"
    die "Staging validation failed."
  fi
  log "Staging validation passed."
}

upgrade_temp_timescale_to_target() {
  [ "$PROD_HAS_TIMESCALE" = true ] || return 0
  [ -n "$PROD_TS_VERSION" ] || die "Production TimescaleDB version is unavailable."

  local source_version
  source_version="$(docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
    psql -X -U "$DB_USER" -d "$STAGING_DB" -Atc \
    "SELECT COALESCE((SELECT extversion FROM pg_extension WHERE extname='timescaledb'), '');" \
    2>/dev/null || true)"
  source_version="${source_version:-$PROD_TS_VERSION}"

  if [ "$source_version" = "$PROD_TS_VERSION" ]; then
    log "Staging TimescaleDB already matches production: $PROD_TS_VERSION."
    return 0
  fi

  # Timescale documents Docker upgrades as: stop/remove the old image,
  # launch the new image against the same data volume, then ALTER EXTENSION.
  # Do not issue ALTER EXTENSION before the destination extension files exist.
  local target_image="timescale/timescaledb:${PROD_TS_VERSION}-pg${SOURCE_PG_MAJOR}-oss"
  log "Switching isolated staging runtime to destination TimescaleDB image: $target_image"
  docker pull "$target_image" >/dev/null

  docker rm -f "$TEMP_CONTAINER" >/dev/null
  docker run -d --name "$TEMP_CONTAINER" --restart=no \
    --label "manubisguard.migration=$ID" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASS" \
    -e POSTGRES_DB=postgres \
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -p 127.0.0.1::5432 \
    -v "$TEMP_VOLUME:/var/lib/postgresql/data" \
    "$target_image" >/dev/null
  TEMP_PORT="$(docker port "$TEMP_CONTAINER" 5432/tcp | sed -nE 's/.*:([0-9]+)$/\1/p' | head -n1)"
  [[ "$TEMP_PORT" =~ ^[0-9]+$ ]] || die "Could not determine upgraded temporary TimescaleDB port."
  build_temp_url

  local i
  for i in $(seq 1 90); do
    if docker exec "$TEMP_CONTAINER" pg_isready -q -U "$DB_USER" -d postgres >/dev/null 2>&1 && \
       docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
       psql -X -U "$DB_USER" -d postgres -Atc 'SELECT 1;' >/dev/null 2>&1; then
      break
    fi
    if [ "$(docker inspect -f '{{.State.Status}}' "$TEMP_CONTAINER" 2>/dev/null || true)" = "exited" ]; then
      docker logs "$TEMP_CONTAINER" >"$WORKDIR/timescale-upgrade-container.log" 2>&1 || true
      die "Destination TimescaleDB runtime exited during isolated upgrade."
    fi
    sleep 2
    [ "$i" -eq 90 ] && die "Destination TimescaleDB runtime did not become ready."
  done

  local target_available
  target_available="$(docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
    psql -X -U "$DB_USER" -d postgres -Atc \
    "SELECT count(*) FROM pg_available_extension_versions WHERE name='timescaledb' AND version='$PROD_TS_VERSION';" \
    2>/dev/null || true)"
  [ "$target_available" = "1" ] || die "Destination TimescaleDB $PROD_TS_VERSION is not available for source PostgreSQL $SOURCE_PG_MAJOR."

  log "Upgrading isolated staging TimescaleDB $source_version -> $PROD_TS_VERSION."
  docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$STAGING_DB" \
    -c "ALTER EXTENSION timescaledb UPDATE TO '$PROD_TS_VERSION';" >/dev/null

  local ext_version
  ext_version="$(docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" \
    psql -X -U "$DB_USER" -d "$STAGING_DB" -Atc \
    "SELECT COALESCE((SELECT extversion FROM pg_extension WHERE extname='timescaledb'), '');" \
    2>/dev/null || true)"
  [ "$ext_version" = "$PROD_TS_VERSION" ] || \
    die "TimescaleDB staging extension did not reach destination version $PROD_TS_VERSION."

  psql_temp -d "$STAGING_DB" -c "SELECT timescaledb_post_restore();" >/dev/null 2>&1 || true
  log "Staging TimescaleDB extension aligned to $PROD_TS_VERSION."
}

validate_after_timescale_upgrade() {
  local output
  if ! output="$(docker exec       -e MANUBISGUARD_MIGRATION_DATABASE_URL="$STAGING_URL"       -e MANUBISGUARD_MIGRATION_PRODUCTION_URL="$PROD_URL"       "$PANEL_CONTAINER" manubisguard-cli migrate-validate --database-url "$STAGING_URL" --production-url "$PROD_URL" --external-staging --json 2>&1)"; then
    printf '%s\n' "$output" >"$WORKDIR/staging-post-upgrade.error"
    printf '%s\n' "$output" >&2
    die "Validation failed after TimescaleDB version alignment."
  fi
  printf '%s\n' "$output" >"$WORKDIR/staging-post-upgrade.json"
  local ok
  ok="$(json_get "$output" ".valid")"
  [ "$ok" = "True" ] || [ "$ok" = "true" ] || die "Post-upgrade staging validation failed."
}

timescale_version_gt() {
  docker exec "$PANEL_CONTAINER" python -c 'import sys; from app.migration.compatibility import version_tuple; left=version_tuple(sys.argv[1]); right=version_tuple(sys.argv[2]); raise SystemExit(2 if left is None or right is None else (0 if left > right else 1))' "$1" "$2"
}

portable_bridge_required() {
  [ "$PROD_HAS_TIMESCALE" = true ] || return 1
  if grep -q "detected MariaDB/MySQL logical dump" "$WORKDIR/analysis.json"; then return 1; fi
  [ -n "$SOURCE_TS_VERSION" ] || die "Portable Timescale bridge requires an exact source TimescaleDB version."
  [ -n "$PROD_TS_VERSION" ] || die "Portable Timescale bridge requires the destination TimescaleDB version."
  timescale_version_gt "$SOURCE_TS_VERSION" "$PROD_TS_VERSION"
}

PORTABLE_BRIDGE_DIR=""
PORTABLE_PRE_DATA_DUMP=""
PORTABLE_DATA_DUMP=""
PORTABLE_POST_DATA_DUMP=""
PORTABLE_HYPERTABLE_SQL=""
PORTABLE_POST_DATA_SQL=""
PORTABLE_EXCLUDE_TABLES=""

prepare_portable_bridge() {
  portable_bridge_required || return 1
  PORTABLE_BRIDGE_DIR="$WORKDIR/portable-bridge"
  mkdir -p "$PORTABLE_BRIDGE_DIR"
  local container_dir="/tmp/manubisguard-portable-$ID"
  docker exec "$PANEL_CONTAINER" rm -rf "$container_dir"
  docker exec "$PANEL_CONTAINER" mkdir -p "$container_dir"

  log "Extracting portable Timescale metadata from source-compatible staging runtime..."
  local bridge_database_url="${STAGING_URL/postgresql+asyncpg/postgresql}"
  docker exec \
    -e MANUBISGUARD_BRIDGE_DATABASE_URL="$bridge_database_url" \
    "$PANEL_CONTAINER" \
    python -m app.migration.portable_bridge \
    --database-url-env MANUBISGUARD_BRIDGE_DATABASE_URL \
    --source-version "$SOURCE_TS_VERSION" \
    --target-version "$PROD_TS_VERSION" \
    --output-dir "$container_dir" \
    >"$WORKDIR/portable-bridge.json"

  docker cp "$PANEL_CONTAINER:$container_dir/portable-plan.json" \
    "$PORTABLE_BRIDGE_DIR/portable-plan.json"
  docker cp "$PANEL_CONTAINER:$container_dir/portable-hypertables.sql" \
    "$PORTABLE_BRIDGE_DIR/portable-hypertables.sql"
  docker cp "$PANEL_CONTAINER:$container_dir/portable-post-data.sql" \
    "$PORTABLE_BRIDGE_DIR/portable-post-data.sql"
  docker cp "$PANEL_CONTAINER:$container_dir/portable-exclude-tables.txt" \
    "$PORTABLE_BRIDGE_DIR/portable-exclude-tables.txt"

  PORTABLE_HYPERTABLE_SQL="$PORTABLE_BRIDGE_DIR/portable-hypertables.sql"
  PORTABLE_POST_DATA_SQL="$PORTABLE_BRIDGE_DIR/portable-post-data.sql"
  PORTABLE_EXCLUDE_TABLES="$PORTABLE_BRIDGE_DIR/portable-exclude-tables.txt"

  log "Portable bridge metadata prepared: $(cat "$WORKDIR/portable-bridge.json")"
}

portable_pg_dump() {
  local section="$1"
  local output="$2"
  local extra_args=()
  local table
  if [ -s "$PORTABLE_EXCLUDE_TABLES" ]; then
    while IFS= read -r table; do
      [ -n "$table" ] || continue
      extra_args+=("--exclude-table=$table")
    done <"$PORTABLE_EXCLUDE_TABLES"
  fi

  local args=(
    pg_dump
    -U "$DB_USER"
    -d "$STAGING_DB"
    --format=plain
    --quote-all-identifiers
    --no-owner
    --no-privileges
    --no-tablespaces
    "--section=$section"
    "--exclude-extension=timescaledb"
    "--exclude-schema=_timescaledb_internal"
    "--exclude-schema=_timescaledb_catalog"
    "--exclude-schema=_timescaledb_config"
  )
  args+=("${extra_args[@]}")

  if ! docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" "${args[@]}" >"$output"; then
    rm -f "$output"
    die "Portable $section pg_dump failed. Production was not modified."
  fi
  [ -s "$output" ] || die "Portable $section dump is empty."
  chmod 600 "$output"
}

filter_portable_dump_for_target() {
  local source="$1"
  local target="$2"
  cat "$source" | docker exec -i "$PANEL_CONTAINER" python -c '
import sys
from app.migration.timescale import filter_postgresql_compatibility_line, filter_timescaledb_ddl_line
for raw in sys.stdin:
    line = raw.rstrip("\r\n")
    if filter_postgresql_compatibility_line(line, target_pg_major=int("'$PG_MAJOR'")):
        continue
    if filter_timescaledb_ddl_line(line):
        continue
    sys.stdout.write(line + "\n")
' >"$target"
  [ -s "$target" ] || die "Filtered portable dump became empty."
}

restore_portable_bridge_to_cutover() {
  [ -n "$CUTOVER_DB" ] || die "Portable bridge requires a cutover database."
  [ -s "$PORTABLE_HYPERTABLE_SQL" ] || die "Portable hypertable SQL is missing."
  [ -s "$PORTABLE_POST_DATA_SQL" ] || die "Portable post-data SQL is missing."

  PORTABLE_PRE_DATA_DUMP="$PORTABLE_BRIDGE_DIR/pre-data.sql"
  PORTABLE_DATA_DUMP="$PORTABLE_BRIDGE_DIR/data.sql"
  PORTABLE_POST_DATA_DUMP="$PORTABLE_BRIDGE_DIR/post-data.sql"

  log "Building portable PostgreSQL pre-data/schema transfer..."
  portable_pg_dump pre-data "$PORTABLE_PRE_DATA_DUMP.raw"
  filter_portable_dump_for_target "$PORTABLE_PRE_DATA_DUMP.raw" "$PORTABLE_PRE_DATA_DUMP"

  log "Restoring portable pre-data schema into cutover database..."
  cat "$PORTABLE_PRE_DATA_DUMP" | psql_prod -d "$CUTOVER_DB"

  log "Recreating Timescale hypertables and dimensions before data load..."
  cat "$PORTABLE_HYPERTABLE_SQL" | psql_prod -d "$CUTOVER_DB"

  log "Building portable user-table data transfer..."
  portable_pg_dump data "$PORTABLE_DATA_DUMP.raw"
  filter_portable_dump_for_target "$PORTABLE_DATA_DUMP.raw" "$PORTABLE_DATA_DUMP"

  log "Restoring portable user-table data..."
  cat "$PORTABLE_DATA_DUMP" | psql_prod -d "$CUTOVER_DB"

  log "Building portable post-data/index/constraint transfer..."
  portable_pg_dump post-data "$PORTABLE_POST_DATA_DUMP.raw"
  filter_portable_dump_for_target "$PORTABLE_POST_DATA_DUMP.raw" "$PORTABLE_POST_DATA_DUMP"

  log "Restoring portable post-data objects..."
  cat "$PORTABLE_POST_DATA_DUMP" | psql_prod -d "$CUTOVER_DB"

  log "Recreating continuous aggregates, policies and statistics..."
  cat "$PORTABLE_POST_DATA_SQL" | psql_prod -d "$CUTOVER_DB"
  rm -f "$PORTABLE_PRE_DATA_DUMP.raw" "$PORTABLE_DATA_DUMP.raw" "$PORTABLE_POST_DATA_DUMP.raw"
}

dump_staging() {
  PANEL_DUMP="$WORKDIR/manubisguard-staging.sql"
  log "Creating cross-major logical SQL dump with staging pg_dump..."
  if ! docker exec -e PGPASSWORD="$DB_PASS" "$TEMP_CONTAINER" pg_dump -U "$DB_USER" -d "$STAGING_DB" --format=plain --quote-all-identifiers --no-owner --no-privileges --no-tablespaces >"$PANEL_DUMP"; then
    rm -f "$PANEL_DUMP"
    die "Source-compatible pg_dump failed. Production database is unchanged."
  fi
  [ -s "$PANEL_DUMP" ] || die "Staging SQL dump is empty."
  grep -q -- "-- PostgreSQL database dump complete" "$PANEL_DUMP" || die "Staging SQL dump is incomplete."
  chmod 600 "$PANEL_DUMP"
  log "Validated logical staging dump: $PANEL_DUMP"
}


create_cutover_database() {
  CUTOVER_DB="manubisguard_migration_$ID"
  [ "$CUTOVER_DB" != "$DB_NAME" ] || die "Generated cutover database equals production."
  local exists
  exists="$(psql_prod -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$CUTOVER_DB';")"
  [ "$exists" != "1" ] || die "Cutover database already exists: $CUTOVER_DB"
  psql_prod -d postgres -c "CREATE DATABASE \"$CUTOVER_DB\" TEMPLATE template0 OWNER \"$DB_USER\";" >/dev/null

  CUTOVER_URL="$(docker exec "$PANEL_CONTAINER" python -c 'import sys; from sqlalchemy.engine import make_url; print(make_url(sys.argv[1]).set(database=sys.argv[2]).render_as_string(hide_password=False))' "$PROD_URL" "$CUTOVER_DB")"
}

timescale_prepare_cutover() {
  [ "$PROD_HAS_TIMESCALE" = true ] || return 0
  psql_prod -d "$CUTOVER_DB" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null
  psql_prod -d "$CUTOVER_DB" -c "SELECT timescaledb_pre_restore();" >/dev/null
  docker exec "$PANEL_CONTAINER" python -c \
    'from app.migration.timescale import TIMESCALEDB_CATALOG_SEED_CLEAR_SQL; print(TIMESCALEDB_CATALOG_SEED_CLEAR_SQL)' |
    docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U "$ADMIN_USER" -d "$CUTOVER_DB" >/dev/null
}

restore_dump_to_cutover() {
  [ -n "$CUTOVER_DB" ] || die "No cutover database exists."
  log "Restoring validated logical dump into isolated cutover database on the production PostgreSQL server."
  local rc=0
  if [ "$PROD_HAS_TIMESCALE" = true ]; then
    if portable_bridge_required; then
      cat "$PANEL_DUMP" | docker exec -i "$PANEL_CONTAINER" python -c '
import sys
from app.migration.timescale import filter_postgresql_compatibility_line, filter_timescaledb_ddl_line
for raw in sys.stdin:
    line = raw.rstrip("\r\n")
    if filter_postgresql_compatibility_line(line, target_pg_major=int("'$PG_MAJOR'")):
        continue
    if filter_timescaledb_ddl_line(line):
        continue
    sys.stdout.write(line + "\n")
' | docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$ADMIN_USER" -d "$CUTOVER_DB" || rc=$?
    else
      cat "$PANEL_DUMP" | docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$ADMIN_USER" -d "$CUTOVER_DB" || rc=$?
    fi
  else
    cat "$PANEL_DUMP" | docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$ADMIN_USER" -d "$CUTOVER_DB" || rc=$?
  fi
  psql_prod -d "$CUTOVER_DB" -c "SELECT timescaledb_post_restore();" >/dev/null 2>&1 || true
  [ "$rc" -eq 0 ] || die "Cutover restore failed. Production database is unchanged."
}

validate_cutover() {
  log "Validating cutover database before stopping the live panel..."
  local output
  if ! output="$(docker exec       -e MANUBISGUARD_MIGRATION_DATABASE_URL="$CUTOVER_URL"       -e MANUBISGUARD_MIGRATION_PRODUCTION_URL="$PROD_URL"       "$PANEL_CONTAINER" manubisguard-cli migrate-validate --database-url "$CUTOVER_URL" --production-url "$PROD_URL" --json 2>&1)"; then
    printf '%s\n' "$output" >"$WORKDIR/cutover-validation.error"
    printf '%s\n' "$output" >&2
    die "Cutover validation command failed. Production database is unchanged."
  fi
  printf '%s\n' "$output" >"$WORKDIR/cutover-validation.json"
  local ok
  ok="$(json_get "$output" ".valid")"
  [ "$ok" = "True" ] || [ "$ok" = "true" ] || {
    cat "$WORKDIR/cutover-validation.json"
    die "Cutover validation failed. Production database is unchanged."
  }
}

compare_cutover_counts() {
  python3 - "$WORKDIR/staging.json" "$WORKDIR/cutover-validation.json" <<'PY'
import json,sys
src=json.load(open(sys.argv[1],encoding="utf-8"))
dst=json.load(open(sys.argv[2],encoding="utf-8"))
source=src.get("post_upgrade_counts") or {}
target=((dst.get("snapshot") or {}).get("row_counts") or {})
critical=("admins","users","nodes","hosts","core_configs","inbounds","groups","user_templates")
losses=[]
for table in critical:
    if table in source and int(target.get(table,0)) < int(source[table]):
        losses.append("%s %s→%s" % (table,source[table],target.get(table,0)))
if losses:
    raise SystemExit("CRITICAL durable row-count loss: " + ", ".join(losses))
print("critical durable row counts preserved")
PY
}

production_safety_backup() {
  local out="$WORKDIR/production-safety.dump"
  log "Creating and verifying production safety backup before rename..."
  if ! docker exec -e PGPASSWORD="$DB_PASS" "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-privileges >"$out"; then
    rm -f "$out"
    die "Production safety backup creation failed; cutover aborted."
  fi
  [ -s "$out" ] || die "Production safety backup is empty; cutover aborted."
  if ! docker exec -i "$DB_CONTAINER" pg_restore --list >/dev/null <"$out"; then
    die "Production safety backup verification failed; cutover aborted."
  fi
  chmod 600 "$out"
  log "Safety backup verified: $out"
}
stop_panel() {
  log "Stopping panel for final cutover..."
  docker compose -f "$COMPOSE_FILE" stop "$COMPOSE_SERVICE" >/dev/null
}

start_panel() {
  docker compose -f "$COMPOSE_FILE" up -d "$COMPOSE_SERVICE" >/dev/null
}

terminate_database_connections() {
  local database="$1"
  psql_prod -d postgres -c     "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$database' AND pid <> pg_backend_pid();"     >/dev/null
}

rename_database() {
  PREVIOUS_DB="$DB_NAME"_"pre_migration_"$ID
  local exists
  exists="$(psql_prod -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$PREVIOUS_DB';")"
  [ "$exists" != "1" ] || die "Pre-migration database already exists: $PREVIOUS_DB"

  psql_prod -d postgres -c "ALTER DATABASE \"$DB_NAME\" WITH ALLOW_CONNECTIONS false;" >/dev/null
  terminate_database_connections "$DB_NAME"
  psql_prod -d postgres -c "ALTER DATABASE \"$DB_NAME\" RENAME TO \"$PREVIOUS_DB\";" >/dev/null
  psql_prod -d postgres -c "ALTER DATABASE \"$CUTOVER_DB\" WITH ALLOW_CONNECTIONS true;" >/dev/null
  if ! psql_prod -d postgres -c "ALTER DATABASE \"$CUTOVER_DB\" RENAME TO \"$DB_NAME\";" >/dev/null; then
    warn "Cutover rename failed; restoring the production database name."
    psql_prod -d postgres -c "ALTER DATABASE \"$PREVIOUS_DB\" WITH ALLOW_CONNECTIONS true;" >/dev/null 2>&1 || true
    if ! psql_prod -d postgres -c "ALTER DATABASE \"$PREVIOUS_DB\" RENAME TO \"$DB_NAME\";" >/dev/null; then
      die "CRITICAL: automatic rollback of database rename failed."
    fi
    rollback_runtime_env
    rollback_runtime_assets
    start_panel || true
    die "Cutover rename failed; production database name restored."
  fi
}

health_check() {
  log "Checking ManubisGuard container health after production cutover..."
  PANEL_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q "$COMPOSE_SERVICE" 2>/dev/null || true)"
  [ -n "$PANEL_CONTAINER" ] || return 1
  local i state
  for i in $(seq 1 60); do
    state="$(docker inspect --format='{{.State.Health.Status}}' "$PANEL_CONTAINER" 2>/dev/null || true)"
    if [ "$state" = "healthy" ]; then
      log "Panel container reports healthy."
      return 0
    fi
    if [ "$state" = "unhealthy" ] || [ "$state" = "dead" ]; then
      docker compose -f "$COMPOSE_FILE" logs --no-color --tail 120 "$COMPOSE_SERVICE" >"$WORKDIR/panel-health-failure.log" 2>&1 || true
      return 1
    fi
    sleep 2
  done
  docker compose -f "$COMPOSE_FILE" logs --no-color --tail 120 "$COMPOSE_SERVICE" >"$WORKDIR/panel-health-failure.log" 2>&1 || true
  return 1
}
rollback_after_failed_health() {
  FAILED_DB="$DB_NAME"_"failed_"$ID
  warn "Panel did not become healthy; rolling the database back."
  rollback_runtime_env
  rollback_runtime_assets
  docker compose -f "$COMPOSE_FILE" stop "$COMPOSE_SERVICE" >/dev/null 2>&1 || true
  psql_prod -d postgres -c "ALTER DATABASE \"$DB_NAME\" WITH ALLOW_CONNECTIONS false;" >/dev/null 2>&1 || true
  terminate_database_connections "$DB_NAME" || true
  psql_prod -d postgres -c "ALTER DATABASE \"$DB_NAME\" RENAME TO \"$FAILED_DB\";" >/dev/null 2>&1 || true
  terminate_database_connections "$PREVIOUS_DB" || true
  psql_prod -d postgres -c "ALTER DATABASE \"$PREVIOUS_DB\" WITH ALLOW_CONNECTIONS true;" >/dev/null 2>&1 || true
  psql_prod -d postgres -c "ALTER DATABASE \"$PREVIOUS_DB\" RENAME TO \"$DB_NAME\";" >/dev/null 2>&1 ||     die "CRITICAL: rollback failed; old database remains $PREVIOUS_DB."
  start_panel || true
  die "Panel health failed. Production was rolled back. Failed database kept as $FAILED_DB."
}

final_cutover() {
  stop_panel
  if ! production_safety_backup; then
    start_panel || true
    die "Production safety backup failed; panel was restarted and cutover was aborted."
  fi
  verify_compose_integrity

  if ! apply_runtime_assets; then
    rollback_runtime_env
    rollback_runtime_assets
    start_panel || true
    die "Runtime asset application failed; production database was not changed."
  fi

  if ! apply_runtime_env; then
    rollback_runtime_env
    rollback_runtime_assets
    start_panel || true
    die "Runtime environment application failed; production database was not changed."
  fi

  verify_compose_integrity
  rename_database

  if ! compose_integrity_ok; then
    rollback_after_failed_health
  fi

  start_panel
  if ! compose_integrity_ok; then
    rollback_after_failed_health
  fi

  health_check || rollback_after_failed_health

  if ! compose_integrity_ok; then
    rollback_after_failed_health
  fi

  log "Production cutover completed."
  log "Previous production DB: $PREVIOUS_DB"
  log "Safety backup: $WORKDIR/production-safety.dump"
}

parse_args() {
  [ "$#" -gt 0 ] || { usage; exit 2; }
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --apply) APPLY=true; shift ;;
      --keep) KEEP_WORKDIR=true; shift ;;
      --clean) KEEP_WORKDIR=false; shift ;;
      --check)
        CHECK_ONLY=true
        shift
        [ "$#" -eq 1 ] || die "--check requires exactly one backup path."
        BACKUP_SOURCE="$1"
        shift
        ;;
      --help|-h) usage; exit 0 ;;
      -*)
        die "Unknown option: $1"
        ;;
      *)
        [ -z "$BACKUP_SOURCE" ] || die "Only one backup path is allowed."
        BACKUP_SOURCE="$1"
        shift
        ;;
    esac
  done
  [ -n "$BACKUP_SOURCE" ] || die "Backup path is required."
}

main() {
  parse_args "$@"
  require_root
  find_services
  load_database_identity
  copy_backup_to_workspace
  capture_compose_integrity
  log "Workspace: $WORKDIR"

  analyze_backup
  verify_compose_integrity

  prepare_runtime_env
  verify_compose_integrity

  if [ "$CHECK_ONLY" = true ]; then
    log "CHECK-ONLY COMPLETE. No staging database or production database was modified."
    return 0
  fi

  local uses_ts stage_version
  uses_ts="$(json_get "$(cat "$WORKDIR/analysis.json")" ".uses_timescaledb")"
  if [ "$PROD_HAS_TIMESCALE" = true ]; then
    local is_mariadb
    is_mariadb="$(grep -q "detected MariaDB/MySQL logical dump" "$WORKDIR/analysis.json" && echo true || echo false)"
    if [ "$is_mariadb" = "True" ] || [ "$is_mariadb" = "true" ]; then
      SOURCE_PG_MAJOR="$PG_MAJOR"
      stage_version="$PROD_TS_VERSION"
      log "MariaDB source has no PostgreSQL/Timescale compatibility runtime; using an isolated destination-compatible PostgreSQL/Timescale staging runtime."
      start_temp_timescale "$stage_version"
      create_staging_database
      start_temp_mariadb
    elif portable_bridge_required; then
      stage_version="$SOURCE_TS_VERSION"
      log "Source TimescaleDB $SOURCE_TS_VERSION is newer than destination $PROD_TS_VERSION; enabling Portable Timescale Bridge."
      [ -n "$stage_version" ] || die "No compatible TimescaleDB staging version was selected."
      start_temp_timescale "$stage_version"
      create_staging_database
    else
      stage_version="$(json_get "$(cat "$WORKDIR/analysis.json")" ".staging_timescale_version")"
      stage_version="${stage_version:-$PROD_TS_VERSION}"
      [ -n "$stage_version" ] || die "No compatible TimescaleDB staging version was selected."
      start_temp_timescale "$stage_version"
      create_staging_database
    fi
  elif [ "$uses_ts" = "True" ] || [ "$uses_ts" = "true" ]; then
    die "TimescaleDB backup cannot be automatically restored into a plain PostgreSQL production database."
  else
    die "This migration helper currently supports the PostgreSQL/TimescaleDB production path only."
  fi

  verify_compose_integrity
  if ! run_staging; then
    die "Staging restore failed. Production was not modified."
  fi
  validate_staging_result
  verify_compose_integrity

  if portable_bridge_required; then
    prepare_portable_bridge
    verify_compose_integrity

    if [ "$APPLY" != true ]; then
      log "STAGING-ONLY PORTABLE BRIDGE PREPARED. Production was not modified."
      log "Portable artifacts: $PORTABLE_BRIDGE_DIR"
      log "Use --apply to restore the portable bridge into an isolated cutover database."
      return 0
    fi

    verify_compose_integrity
    create_cutover_database
    timescale_prepare_cutover
    restore_portable_bridge_to_cutover
    validate_cutover
    compare_cutover_counts
    final_cutover
    verify_compose_integrity
    return 0
  fi

  upgrade_temp_timescale_to_target
  validate_after_timescale_upgrade
  dump_staging
  verify_compose_integrity

  if [ "$APPLY" != true ]; then
    log "STAGING-ONLY COMPLETE. Production was not modified."
    log "Validated migration dump: $PANEL_DUMP"
    log "Use --apply to perform the validated cutover."
    return 0
  fi

  verify_compose_integrity
  create_cutover_database
  timescale_prepare_cutover
  restore_dump_to_cutover
  validate_cutover
  compare_cutover_counts
  final_cutover
  verify_compose_integrity
}

main "$@"
