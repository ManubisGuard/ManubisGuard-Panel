#!/usr/bin/env bash
set -Eeuo pipefail

# Validate an isolated restored database without changing production data.
# Usage: scripts/validate-restore.sh [restore-db-name]

RESTORE_DB="${1:-manubisguard_restore}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-timescaledb}"

set -a
# shellcheck disable=SC1091
source .env
set +a
DB_USER="${POSTGRES_USER:-manubisguard}"
PROD_DB="${POSTGRES_DB:-manubisguard}"

[[ "$RESTORE_DB" != "$PROD_DB" ]] || { echo "ERROR: validation DB must not be production DB" >&2; exit 1; }

psql_exec() {
  local db="$1"; shift
  docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    psql -U "$DB_USER" -d "$db" -Atqc "$*"
}

exists="$(psql_exec postgres "SELECT 1 FROM pg_database WHERE datname='$RESTORE_DB';")"
[[ "$exists" == "1" ]] || { echo "ERROR: restore database '$RESTORE_DB' does not exist" >&2; exit 1; }

prod_tables="$(psql_exec "$PROD_DB" "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
restore_tables="$(psql_exec "$RESTORE_DB" "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
prod_migrations="$(psql_exec "$PROD_DB" "SELECT COALESCE((SELECT version_num FROM alembic_version LIMIT 1),'missing');")"
restore_migrations="$(psql_exec "$RESTORE_DB" "SELECT COALESCE((SELECT version_num FROM alembic_version LIMIT 1),'missing');")"

printf 'production_tables=%s\n' "$prod_tables"
printf 'restore_tables=%s\n' "$restore_tables"
printf 'production_alembic=%s\n' "$prod_migrations"
printf 'restore_alembic=%s\n' "$restore_migrations"

if [[ "$prod_tables" != "$restore_tables" ]]; then
  echo "ERROR: public table count mismatch" >&2
  exit 1
fi

if [[ "$prod_migrations" != "$restore_migrations" ]]; then
  echo "ERROR: Alembic revision mismatch" >&2
  exit 1
fi

# Check TimescaleDB extension and hypertable count where available.
prod_hypertables="$(psql_exec "$PROD_DB" "SELECT count(*) FROM timescaledb_information.hypertables;" 2>/dev/null || echo 0)"
restore_hypertables="$(psql_exec "$RESTORE_DB" "SELECT count(*) FROM timescaledb_information.hypertables;" 2>/dev/null || echo 0)"
printf 'production_hypertables=%s\n' "$prod_hypertables"
printf 'restore_hypertables=%s\n' "$restore_hypertables"

if [[ "$prod_hypertables" != "$restore_hypertables" ]]; then
  echo "ERROR: Timescale hypertable count mismatch" >&2
  exit 1
fi

echo "RESTORE VALIDATION OK"
