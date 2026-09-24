#!/usr/bin/env bash
set -Eeuo pipefail

# Verify checksum and PostgreSQL custom-format readability without modifying the DB.
# Usage: scripts/verify-backup.sh /path/to/file.dump

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/file.dump" >&2
  exit 2
fi

BACKUP="$1"
CHECKSUM="${BACKUP}.sha256"

[[ -s "$BACKUP" ]] || { echo "ERROR: backup does not exist or is empty: $BACKUP" >&2; exit 1; }

if [[ -f "$CHECKSUM" ]]; then
  sha256sum -c "$CHECKSUM"
else
  echo "WARNING: checksum file not found: $CHECKSUM" >&2
fi

# Prefer a local pg_restore if available; otherwise use the Compose DB container.
if command -v pg_restore >/dev/null 2>&1; then
  pg_restore --list "$BACKUP" >/dev/null
else
  COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
  DB_SERVICE="${DB_SERVICE:-timescaledb}"
  docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" pg_restore --list < "$BACKUP" >/dev/null
fi

echo "BACKUP VERIFY OK"
