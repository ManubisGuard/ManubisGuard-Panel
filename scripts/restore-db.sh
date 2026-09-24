#!/usr/bin/env bash
set -Eeuo pipefail

# Restore a backup into a separate PostgreSQL database for validation.
# This script deliberately refuses to overwrite the configured production DB.
# Usage: scripts/restore-db.sh /path/to/file.dump [restore-db-name]

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /path/to/file.dump [restore-db-name]" >&2
  exit 2
fi

BACKUP="$1"
RESTORE_DB="${2:-manubisguard_restore}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-timescaledb}"
DB_USER="${POSTGRES_USER:-manubisguard}"
PROD_DB="${POSTGRES_DB:-manubisguard}"

[[ -s "$BACKUP" ]] || { echo "ERROR: backup does not exist or is empty" >&2; exit 1; }
[[ "$RESTORE_DB" != "$PROD_DB" ]] || { echo "ERROR: refusing to restore over production database '$PROD_DB'" >&2; exit 1; }
[[ "$RESTORE_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "ERROR: invalid restore database name" >&2; exit 1; }

set -a
# shellcheck disable=SC1091
source .env
set +a
DB_USER="${POSTGRES_USER:-$DB_USER}"
PROD_DB="${POSTGRES_DB:-$PROD_DB}"

# Re-check after loading .env.
[[ "$RESTORE_DB" != "$PROD_DB" ]] || { echo "ERROR: refusing to restore over production database '$PROD_DB'" >&2; exit 1; }

# Create a clean validation database. No production tables are touched.
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$RESTORE_DB' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"$RESTORE_DB\";" \
  -c "CREATE DATABASE \"$RESTORE_DB\" OWNER \"$DB_USER\";"

docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_restore -U "$DB_USER" -d "$RESTORE_DB" --no-owner --no-acl --exit-on-error < "$BACKUP"

echo "RESTORE OK"
echo "database=$RESTORE_DB"
echo "production_database=$PROD_DB"
