#!/usr/bin/env bash
set -u -o pipefail
PROJECT="manubisguard-test"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
SOURCE_URL="${MANUBISGUARD_BRIDGE_SOURCE_URL:-postgresql://postgres:integration@127.0.0.1:55432/source_db}"
DESTINATION_URL="${MANUBISGUARD_BRIDGE_DESTINATION_URL:-postgresql://postgres:integration@127.0.0.1:55433/destination_db}"
RESULT=0
stage() { local name="$1"; echo "==> $name"; shift; "$@" && echo "OK: $name" || { echo "FAILED: $name"; RESULT=1; }; }
cleanup() { docker compose -p "$PROJECT" -f "$COMPOSE_FILE" down -v --remove-orphans --rmi local >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "==> Validate compose configuration"
if ! docker compose -p "$PROJECT" -f "$COMPOSE_FILE" config -q; then
  echo "FAILED: Validate compose configuration"
  exit 1
fi
echo "OK: Validate compose configuration"

stage "Start isolated Timescale services" docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --wait
SOURCE_CONTAINER="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" ps -q timescaledb-source)"
DESTINATION_CONTAINER="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" ps -q timescaledb-destination)"
stage "Resolve source and destination containers" bash -c 'set -e; test -n "$1"; test -n "$2"' _ "$SOURCE_CONTAINER" "$DESTINATION_CONTAINER"
stage "Create source and destination databases" bash -c 'set -e; PGPASSWORD=integration docker exec "$1" psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='\''source_db'\''" | grep -qx 1; PGPASSWORD=integration docker exec "$2" psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='\''destination_db'\''" | grep -qx 1' _ "$SOURCE_CONTAINER" "$DESTINATION_CONTAINER"
stage "Verify PostgreSQL readiness before seed" bash -c 'set -e; docker exec "$1" pg_isready -U postgres -d source_db' _ "$SOURCE_CONTAINER"
stage "Seed source database" bash -c 'set -e
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE TABLE public.devices (id integer PRIMARY KEY, name text NOT NULL)"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE TABLE public.usage (time timestamptz NOT NULL, device_id integer NOT NULL REFERENCES public.devices(id), bytes bigint NOT NULL)"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "SELECT create_hypertable('public.usage', by_range('time', INTERVAL '1 day'))"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "INSERT INTO public.devices SELECT g, 'device-' || g FROM generate_series(1,3) g"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "INSERT INTO public.usage SELECT TIMESTAMPTZ '2026-01-01' + g * INTERVAL '1 day', ((g-1)%3)+1, g*100 FROM generate_series(1,48) g"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE MATERIALIZED VIEW public.daily_usage WITH (timescaledb.continuous) AS SELECT time_bucket('1 day',time) bucket,min(device_id) device_id,sum(bytes) bytes FROM public.usage GROUP BY bucket WITH NO DATA"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CALL refresh_continuous_aggregate('public.daily_usage',NULL,NULL)"
docker exec "$1" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "ANALYZE"
' _ "$SOURCE_CONTAINER"
stage "Verify seeded data and 48-row continuous aggregate" bash -c 'set -e; test "$(PGPASSWORD=integration docker exec "$1" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.devices")" = 3; test "$(PGPASSWORD=integration docker exec "$1" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.usage")" = 48; test "$(PGPASSWORD=integration docker exec "$1" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.daily_usage")" = 48' _ "$SOURCE_CONTAINER"
stage "Build portable bridge artifacts" bash -c 'set -e; rm -rf .local-bridge-test; MANUBISGUARD_BRIDGE_DATABASE_URL="$1" uv run python -m app.migration.portable_bridge --database-url-env MANUBISGUARD_BRIDGE_DATABASE_URL --source-version 2.30.0 --target-version 2.29.2 --output-dir .local-bridge-test; test -s .local-bridge-test/portable-plan.json; test -s .local-bridge-test/portable-hypertables.sql; test -s .local-bridge-test/portable-post-data.sql' _ "$SOURCE_URL"
stage "Dump pre-data, data, and post-data from source container" bash -c 'set -e
rm -rf .local-migration-dumps
mkdir -p .local-migration-dumps
for section in pre-data data post-data; do
  docker exec -e PGPASSWORD=integration "$1" pg_dump -U postgres -d source_db --format=plain --quote-all-identifiers --no-owner --no-privileges --no-tablespaces --section="$section" --exclude-extension=timescaledb --exclude-schema=_timescaledb_internal --exclude-schema=_timescaledb_catalog --exclude-schema=_timescaledb_config --exclude-table=public.daily_usage > ".local-migration-dumps/\$section.sql"
  test -s ".local-migration-dumps/$section.sql"
  uv run python -c "from pathlib import Path; from app.migration.timescale import prepare_timescale_sql_file; p=Path('.local-migration-dumps/\$section.sql'); prepare_timescale_sql_file(p, p.with_suffix('.prepared.sql'), target_pg_major=16)"
  test -s ".local-migration-dumps/\$section.prepared.sql"
done
' _ "$SOURCE_CONTAINER"
stage "Restore source schema and data on destination" bash -c 'set -e; PGPASSWORD=integration docker exec "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb"; cat .local-migration-dumps/pre-data.prepared.sql | PGPASSWORD=integration docker exec -i "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1; cat .local-bridge-test/portable-hypertables.sql | PGPASSWORD=integration docker exec -i "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1; cat .local-migration-dumps/data.prepared.sql | PGPASSWORD=integration docker exec -i "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1; cat .local-migration-dumps/post-data.prepared.sql | PGPASSWORD=integration docker exec -i "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1; cat .local-bridge-test/portable-post-data.sql | PGPASSWORD=integration docker exec -i "$1" psql -U postgres -d destination_db -v ON_ERROR_STOP=1' _ "$DESTINATION_CONTAINER"
stage "Verify migration counts" uv run python scripts/verify-migration-counts.py --source-url "$SOURCE_URL" --destination-url "$DESTINATION_URL"
stage "Verify migrated continuous aggregate has 48 rows" bash -c 'set -e; test "$(PGPASSWORD=integration docker exec "$1" psql -U postgres -d destination_db -Atc "SELECT count(*) FROM public.daily_usage")" = 48' _ "$DESTINATION_CONTAINER"
stage "Ruff lint" uv run ruff check app tests --no-fix
stage "Ruff format check" uv run ruff format --check app tests
stage "Migration unit tests" uv run pytest tests/migration -q
if [ "$RESULT" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "TESTS FAILED"; fi
exit "$RESULT"
