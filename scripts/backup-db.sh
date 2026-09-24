#!/usr/bin/env bash
set -Eeuo pipefail

# Create a compressed PostgreSQL custom-format backup from the Compose database.
# Usage: scripts/backup-db.sh [output-dir]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="${1:-${BACKUP_DIR:-/var/lib/manubisguard/backups}}"
mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-timescaledb}"
DB_NAME="${POSTGRES_DB:-manubisguard}"
DB_USER="${POSTGRES_USER:-manubisguard}"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $ROOT_DIR" >&2
  exit 1
fi

# Load only the variables needed by docker compose interpolation.
set -a
# shellcheck disable=SC1091
source .env
set +a
DB_NAME="${POSTGRES_DB:-$DB_NAME}"
DB_USER="${POSTGRES_USER:-$DB_USER}"

if ! docker compose -f "$COMPOSE_FILE" ps --status running "$DB_SERVICE" >/dev/null 2>&1; then
  echo "ERROR: database service '$DB_SERVICE' is not running" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$OUTPUT_DIR/${DB_NAME}_${STAMP}.dump"
META="$TARGET.sha256"

# pg_dump runs inside the database container, so the host does not need pg_dump installed.
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl > "$TARGET"

if [[ ! -s "$TARGET" ]]; then
  echo "ERROR: backup file is empty" >&2
  rm -f "$TARGET"
  exit 1
fi

sha256sum "$TARGET" > "$META"
chmod 600 "$TARGET" "$META"

# Basic archive integrity check before declaring success.
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_restore --list < "$TARGET" >/dev/null

SIZE="$(du -h "$TARGET" | cut -f1)"
echo "BACKUP OK"
echo "file=$TARGET"
echo "size=$SIZE"
echo "sha256=$(cut -d' ' -f1 "$META")"
