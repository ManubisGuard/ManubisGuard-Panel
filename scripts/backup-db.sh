#!/usr/bin/env bash
set -Eeuo pipefail

# Create a compressed PostgreSQL custom-format backup from the Compose database.
# Usage: scripts/backup-db.sh [output-dir]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="${1:-${BACKUP_DIR:-/opt/pasarguard/backup/database}}"
mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-timescaledb}"
DB_NAME="${POSTGRES_DB:-pasarguard}"
DB_USER="${POSTGRES_USER:-pasarguard}"

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

STAMP="$(date -u +%Y%m%dT%H%M%S%NZ)"
TARGET="$OUTPUT_DIR/${DB_NAME}_${STAMP}.dump"
META="$TARGET.sha256"
TEMP_DUMP="$(mktemp "$OUTPUT_DIR/.${DB_NAME}.XXXXXX.dump.tmp")"
TEMP_META="${TEMP_DUMP}.sha256"
cleanup() { rm -f -- "$TEMP_DUMP" "$TEMP_META"; }
trap cleanup EXIT

if [[ -e "$TARGET" || -e "$META" ]]; then
  echo "ERROR: refusing to overwrite an existing backup: $TARGET" >&2
  exit 1
fi

# pg_dump reads the database but writes only to a private temporary file.
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl > "$TEMP_DUMP"

if [[ ! -s "$TEMP_DUMP" ]]; then
  echo "ERROR: backup file is empty" >&2
  exit 1
fi
chmod 600 "$TEMP_DUMP"

# Validate using a disposable offline container, never by exec'ing into the live DB container.
docker run --rm -i --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --entrypoint pg_restore timescale/timescaledb:latest-pg16 --list \
  < "$TEMP_DUMP" >/dev/null

sha256sum "$TEMP_DUMP" > "$TEMP_META"
chmod 600 "$TEMP_META"
# Atomic hard-link publication: never clobber an existing archive or checksum.
ln -- "$TEMP_DUMP" "$TARGET"
if ! ln -- "$TEMP_META" "$META"; then
  # The archive was created by this invocation; remove only that just-published path.
  rm -f -- "$TARGET"
  echo "ERROR: could not publish checksum sidecar; incomplete backup removed" >&2
  exit 1
fi
SIZE="$(du -h "$TARGET" | cut -f1)"
echo "BACKUP OK"
echo "file=$TARGET"
echo "size=$SIZE"
echo "sha256=$(cut -d' ' -f1 "$META")"
