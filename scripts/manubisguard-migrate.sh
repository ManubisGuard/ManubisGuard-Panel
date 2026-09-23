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
DATA_DIR="${MANUBISGUARD_DATA_DIR:-/var/lib/pasarguard}"
MIGRATION_ROOT="$DATA_DIR/migration"
ID="$(LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 12 || true)"
WORKDIR="$MIGRATION_ROOT/$ID"
INPUTDIR="$WORKDIR/input"

APPLY=false
KEEP_WORKDIR=true
BACKUP_SOURCE=""
MANUBISGUARD_SOURCE_TIMESCALE="${MANUBISGUARD_MIGRATION_SOURCE_TIMESCALE:-}"
PANEL_CONTAINER=""
DB_CONTAINER=""
COMPOSE_SERVICE="pasarguard"
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

TEMP_CONTAINER=""
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

The backup is copied under /var/lib/pasarguard/migration before the panel reads it.
EOF
}

cleanup() {
  set +e
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

find_services() {
  local services
  services="$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || true)"
  printf '%s\n' "$services" | grep -qx 'pasarguard' && COMPOSE_SERVICE="pasarguard"
  if ! printf '%s\n' "$services" | grep -qx "$COMPOSE_SERVICE"; then
    printf '%s\n' "$services" | grep -qx 'panel' && COMPOSE_SERVICE="panel"
  fi
  printf '%s\n' "$services" | grep -qx "$COMPOSE_SERVICE" || die "Panel service not found in compose."

  if printf '%s\n' "$services" | grep -qx 'timescaledb'; then
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
  printf '%s  %s\\n' "$COMPOSE_SHA256" "$COMPOSE_FILE" >"$WORKDIR/compose.sha256"
  log "Compose integrity captured: $COMPOSE_SHA256"
}

verify_compose_integrity() {
  [ -n "$COMPOSE_SHA256" ] || die "Compose integrity fingerprint is missing."
  [ -f "$COMPOSE_FILE" ] || die "CRITICAL: ManubisGuard compose file disappeared."
  local current
  current="$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')"
  if [ "$current" != "$COMPOSE_SHA256" ]; then
    printf '%s  %s\\n' "$current" "$COMPOSE_FILE" >"$WORKDIR/compose-changed.sha256"
    die "CRITICAL: migration attempted to change docker-compose.yml. Production deployment was not trusted."
  fi
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
  if ! output="$(docker exec "$PANEL_CONTAINER"       pasarguard-cli migrate-inspect "$PANEL_BACKUP"       --live-timescale "$PROD_TS_VERSION"       ${MANUBISGUARD_SOURCE_TIMESCALE:+--source-timescale "$MANUBISGUARD_SOURCE_TIMESCALE"}       --json 2>&1)"; then
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

  log "Accepted source=$(json_get "$output" ".detection.source_product") format=$(json_get "$output" ".detection.format")"
  if [ "$(json_get "$output" ".uses_timescaledb")" = "True" ] || [ "$(json_get "$output" ".uses_timescaledb")" = "true" ]; then
    log "Backup contains TimescaleDB objects."
  fi
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
  local image
  local source_series
  source_series="${version%.*}"

  if [ -n "$PROD_TS_VERSION" ] && [ "$version" != "$PROD_TS_VERSION" ]; then
    # The compatibility image must contain the SOURCE extension version, not
    # merely the destination series. A 2.28.2 backup must first run with
    # 2.28 extension files and only then be upgraded to the destination.
    image="timescale/timescaledb-ha:pg${PG_MAJOR}-ts${source_series}-all"
    log "Starting isolated source-compatible TimescaleDB image: $image"
    if ! docker pull "$image" >/dev/null 2>&1; then
      image="timescale/timescaledb-ha:pg${PG_MAJOR}-all"
      log "Source-series image unavailable; trying multi-version image: $image"
      docker pull "$image" >/dev/null || die "Could not pull a TimescaleDB image containing source version $version."
    fi
  else
    image="timescale/timescaledb:$version-pg$PG_MAJOR"
    log "Starting isolated TimescaleDB image: $image"
    docker pull "$image" >/dev/null
  fi
  docker run -d --name "$TEMP_CONTAINER" --restart=no     --label "manubisguard.migration=$ID"     -e POSTGRES_USER="$DB_USER"     -e POSTGRES_PASSWORD="$DB_PASS"     -e POSTGRES_DB=postgres     -e POSTGRES_HOST_AUTH_METHOD=trust     -p 127.0.0.1::5432     -v "$TEMP_VOLUME:/var/lib/postgresql/data"     "$image" >/dev/null

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
    quote(user, safe=""), quote(password, safe=""), port, db
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
  if output="$(docker exec       -e MANUBISGUARD_MIGRATION_STAGING_URL="$STAGING_URL"       -e MANUBISGUARD_MIGRATION_PRODUCTION_URL="$PROD_URL"       "$PANEL_CONTAINER"       pasarguard-cli migrate-staging "$PANEL_BACKUP"       --external-staging       ${MANUBISGUARD_SOURCE_TIMESCALE:+--source-timescale "$MANUBISGUARD_SOURCE_TIMESCALE"}       --json 2>&1)"; then
    printf '%s\n' "$output" >"$WORKDIR/staging.json"
    return 0
  fi
  printf '%s\n' "$output" >"$WORKDIR/staging.error"
  printf '%s\n' "$output" >&2
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
  if ! output="$(docker exec       -e MANUBISGUARD_MIGRATION_DATABASE_URL="$STAGING_URL"       -e MANUBISGUARD_MIGRATION_PRODUCTION_URL="$PROD_URL"       "$PANEL_CONTAINER" pasarguard-cli migrate-validate --external-staging --json 2>&1)"; then
    printf '%s\n' "$output" >"$WORKDIR/staging-post-upgrade.error"
    printf '%s\n' "$output" >&2
    die "Validation failed after TimescaleDB version alignment."
  fi
  printf '%s\n' "$output" >"$WORKDIR/staging-post-upgrade.json"
  local ok
  ok="$(json_get "$output" ".valid")"
  [ "$ok" = "True" ] || [ "$ok" = "true" ] || die "Post-upgrade staging validation failed."
}

dump_staging() {
  PANEL_DUMP="$WORKDIR/manubisguard-staging.dump"
  log "Creating custom-format dump from validated staging database..."
  docker exec -e PGPASSWORD="$DB_PASS" "$PANEL_CONTAINER"     pg_dump -h 127.0.0.1 -p "$TEMP_PORT" -U "$DB_USER" -d "$STAGING_DB"     -Fc --no-owner --no-privileges -f "$PANEL_DUMP"
  [ -s "$PANEL_DUMP" ] || die "Staging dump is empty."
  docker exec "$PANEL_CONTAINER" pg_restore --list "$PANEL_DUMP" >/dev/null
  chmod 600 "$PANEL_DUMP"
  log "Validated staging dump: $PANEL_DUMP"
}

create_cutover_database() {
  CUTOVER_DB="manubisguard_migration_$ID"
  [ "$CUTOVER_DB" != "$DB_NAME" ] || die "Generated cutover database equals production."
  local exists
  exists="$(psql_prod -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$CUTOVER_DB';")"
  [ "$exists" != "1" ] || die "Cutover database already exists: $CUTOVER_DB"
  psql_prod -d postgres -c "CREATE DATABASE \"$CUTOVER_DB\" TEMPLATE template0 OWNER \"$DB_USER\";" >/dev/null

  CUTOVER_URL="$(python3 - "$PROD_URL" "$CUTOVER_DB" <<'PY'
import sys
from sqlalchemy.engine import make_url
url = make_url(sys.argv[1]).set(database=sys.argv[2])
print(url.render_as_string(hide_password=False))
PY
)"
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
  log "Restoring validated dump into isolated cutover database on the production PostgreSQL server."
  local listfile="$WORKDIR/cutover.list"
  docker exec "$PANEL_CONTAINER" pg_restore --list "$PANEL_DUMP" |
    grep -viE 'EXTENSION.*timescaledb(_toolkit)?' >"$listfile"

  docker exec -i "$DB_CONTAINER" sh -c "cat > /tmp/manubisguard-$ID.list" <"$listfile"

  local rc=0
  if [ "$PROD_HAS_TIMESCALE" = true ]; then
    cat "$PANEL_DUMP" | docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER"       pg_restore --exit-on-error --no-owner --no-privileges       --use-list="/tmp/manubisguard-$ID.list" -d "$CUTOVER_DB" - || rc=$?
  else
    cat "$PANEL_DUMP" | docker exec -i -e PGPASSWORD="$ADMIN_PASS" "$DB_CONTAINER"       pg_restore --exit-on-error --no-owner --no-privileges       -d "$CUTOVER_DB" - || rc=$?
  fi

  psql_prod -d "$CUTOVER_DB" -c "SELECT timescaledb_post_restore();" >/dev/null 2>&1 || true
  docker exec "$DB_CONTAINER" rm -f "/tmp/manubisguard-$ID.list" >/dev/null 2>&1 || true
  [ "$rc" -eq 0 ] || die "Cutover restore failed. Production database is unchanged."
}

validate_cutover() {
  log "Validating cutover database before stopping the live panel..."
  local output
  if ! output="$(docker exec       -e MANUBISGUARD_MIGRATION_DATABASE_URL="$CUTOVER_URL"       -e MANUBISGUARD_MIGRATION_PRODUCTION_URL="$PROD_URL"       "$PANEL_CONTAINER" pasarguard-cli migrate-validate --json 2>&1)"; then
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
  docker exec -e PGPASSWORD="$DB_PASS" "$DB_CONTAINER"     pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-privileges >"$out"
  [ -s "$out" ] || die "Production safety backup is empty; cutover aborted."
  docker exec -i "$DB_CONTAINER" pg_restore --list - >/dev/null <"$out"
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
    start_panel || true
    die "Cutover rename failed; production database name restored."
  fi
}

health_check() {
  log "Checking ManubisGuard HTTP health..."
  local i
  for i in $(seq 1 45); do
    if curl -kfsS --max-time 5 "https://127.0.0.1:8000/health" >/dev/null 2>&1 ||
       curl -kfsS --max-time 5 "https://127.0.0.1:8000/" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

rollback_after_failed_health() {
  FAILED_DB="$DB_NAME"_"failed_"$ID
  warn "Panel did not become healthy; rolling the database back."
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
  rename_database
  start_panel
  health_check || rollback_after_failed_health
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

  local uses_ts stage_version
  uses_ts="$(json_get "$(cat "$WORKDIR/analysis.json")" ".uses_timescaledb")"
  if [ "$PROD_HAS_TIMESCALE" = true ]; then
    stage_version="$(json_get "$(cat "$WORKDIR/analysis.json")" ".staging_timescale_version")"
    stage_version="${stage_version:-$PROD_TS_VERSION}"
    [ -n "$stage_version" ] || die "No compatible TimescaleDB staging version was selected."
    start_temp_timescale "$stage_version"
    create_staging_database
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
