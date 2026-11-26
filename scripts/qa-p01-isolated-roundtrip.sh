#!/usr/bin/env bash
set -Eeuo pipefail

# Synthetic-only backup/restore acceptance drill. Never mounts production paths,
# connects to live nodes, or exposes PostgreSQL to any network.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d /tmp/manubis-p01-synthetic.XXXXXXXX)"
chmod 700 "$TEST_ROOT"
CONTAINER=""
cleanup() {
  if [[ -n "$CONTAINER" ]]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$TEST_ROOT"
}
trap cleanup EXIT

for MAJOR in 16 17; do
  IMAGE="timescale/timescaledb:latest-pg${MAJOR}"
  docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "Missing locally cached image $IMAGE; no automatic download" >&2
    exit 3
  }
  CONTAINER="manubis-p01-fixture-${MAJOR}-$$"
  docker run -d --rm --name "$CONTAINER" --network none \
    --tmpfs /var/lib/postgresql/data:rw,size=768m,mode=0700 \
    -e POSTGRES_USER=fixture -e POSTGRES_PASSWORD=synthetic-fixture-only \
    -e POSTGRES_DB=fixture_src "$IMAGE" >/dev/null
  ready=0
  for _ in $(seq 1 60); do
    if docker exec "$CONTAINER" pg_isready -U fixture -d fixture_src >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" != 1 ]]; then
    echo "Synthetic PG${MAJOR} database failed to start" >&2
    exit 1
  fi
  docker exec "$CONTAINER" psql -v ON_ERROR_STOP=1 -U fixture -d fixture_src \
    -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;' \
    -c 'CREATE TABLE p01_fixture (id integer primary key, payload text not null);' \
    -c "INSERT INTO p01_fixture VALUES (1, 'sample-alpha'), (2, 'sample-beta');" >/dev/null

  DUMP="$TEST_ROOT/fixture-pg${MAJOR}.dump"
  SQL="$TEST_ROOT/fixture-pg${MAJOR}.sql"
  docker exec "$CONTAINER" pg_dump -U fixture -d fixture_src --format=custom --no-owner --no-acl > "$DUMP"
  docker exec "$CONTAINER" pg_dump -U fixture -d fixture_src --format=plain --no-owner --no-acl > "$SQL"
  [[ -s "$DUMP" && -s "$SQL" ]] || { echo "Empty fixture dump" >&2; exit 1; }
  docker exec "$CONTAINER" createdb -U fixture fixture_copy
  docker exec -i "$CONTAINER" pg_restore -U fixture -d fixture_copy \
    --no-owner --no-acl --exit-on-error < "$DUMP"
  SOURCE="$(docker exec "$CONTAINER" psql -U fixture -d fixture_src -Atqc 'SELECT string_agg(id::text || payload, $$|$$ ORDER BY id) FROM p01_fixture')"
  COPIED="$(docker exec "$CONTAINER" psql -U fixture -d fixture_copy -Atqc 'SELECT string_agg(id::text || payload, $$|$$ ORDER BY id) FROM p01_fixture')"
  [[ "$SOURCE" == '1sample-alpha|2sample-beta' && "$COPIED" == "$SOURCE" ]] || {
    echo "Synthetic PG${MAJOR} data did not survive restore" >&2; exit 1;
  }
  RESTORE_IMAGE="$IMAGE" bash "$ROOT/scripts/restore-db.sh" "$DUMP" "p01_drill_${MAJOR}" >/dev/null
  echo "PG${MAJOR}: isolated dump and restore OK; 2 fixture rows preserved; TimescaleDB extension verified"
  docker rm -f "$CONTAINER" >/dev/null
  CONTAINER=""
done

echo 'P01 SYNTHETIC ISOLATED ROUNDTRIP PASSED'
