#!/usr/bin/env bash
set -Eeuo pipefail

# Restore a PostgreSQL custom-format dump only into a disposable offline container.
# No Compose service, production database, host DB volume, or live panel is used.
# Usage: scripts/restore-db.sh /path/to/file.dump [restore-db-name]

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /path/to/file.dump [restore-db-name]" >&2
  exit 2
fi

BACKUP="$1"
RESTORE_DB="${2:-manubisguard_restore}"
IMAGE="${RESTORE_IMAGE:-timescale/timescaledb:latest-pg16}"
NAME="manubisguard-db-restore-test-$$-${RANDOM}"

[[ -s "$BACKUP" ]] || { echo "ERROR: backup does not exist or is empty: $BACKUP" >&2; exit 1; }
[[ "$RESTORE_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "ERROR: invalid restore database name" >&2; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
  echo "ERROR: required local test image is missing: $IMAGE (no pull attempted)" >&2
  exit 3
}

CONTAINER_CREATED=0
cleanup() {
  if [[ "$CONTAINER_CREATED" -eq 1 ]]; then
    docker rm -f "$NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "ERROR: disposable test container name collision: $NAME" >&2
  exit 1
fi
docker run -d --rm --name "$NAME" --network none \
  --tmpfs /var/lib/postgresql/data:rw,size=768m,mode=0700 \
  -e POSTGRES_USER=restoretest -e POSTGRES_DB=postgres \
  -e POSTGRES_PASSWORD=temporary-not-production \
  "$IMAGE" >/dev/null
CONTAINER_CREATED=1

ready=0
for _ in $(seq 1 90); do
  logs="$(docker logs "$NAME" 2>&1 || true)"
  if grep -q 'PostgreSQL init process complete; ready for start up.' <<<"$logs" \
      && docker exec "$NAME" pg_isready -U restoretest -d postgres >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "ERROR: disposable PostgreSQL did not become ready" >&2
  docker logs "$NAME" 2>&1 | tail -n 60 >&2
  exit 1
fi

docker exec "$NAME" createdb -U restoretest "$RESTORE_DB"
docker exec -i "$NAME" pg_restore -U restoretest -d "$RESTORE_DB" \
  --no-owner --no-acl --exit-on-error < "$BACKUP"

readout="$(docker exec "$NAME" psql -U restoretest -d "$RESTORE_DB" -Atqc \
  "SELECT (SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema'))::text || ' ' || (SELECT count(*) FROM pg_extension);")"
read -r tables extensions <<<"$readout"
[[ "${tables:-0}" =~ ^[0-9]+$ && "$tables" -gt 0 ]] || {
  echo "ERROR: isolated restore did not produce user tables" >&2
  exit 1
}
[[ "${extensions:-0}" =~ ^[0-9]+$ && "$extensions" -gt 0 ]] || {
  echo "ERROR: isolated restore did not produce database extensions" >&2
  exit 1
}

echo "ISOLATED RESTORE OK"
echo "temporary_database=$RESTORE_DB"
echo "user_tables=$tables"
echo "extensions=$extensions"
echo "network=none"
echo "storage=tmpfs-only"
echo "temporary_container_will_be_removed=yes"
