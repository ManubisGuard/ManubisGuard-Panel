#!/usr/bin/env bash
set -u -o pipefail

PROJECT="manubisguard-test"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
SOURCE_URL="${MANUBISGUARD_BRIDGE_SOURCE_URL:-postgresql://postgres:integration@127.0.0.1:55432/source_db}"
DESTINATION_URL="${MANUBISGUARD_BRIDGE_DESTINATION_URL:-postgresql://postgres:integration@127.0.0.1:55433/destination_db}"
SOURCE_SERVICE="timescaledb-source"
DESTINATION_SERVICE="timescaledb-destination"
RESULT=0

stage() {
  local name="$1"
  echo "==> $name"
  shift
  "$@" && echo "OK: $name" || {
    echo "FAILED: $name"
    RESULT=1
  }
}

compose_exec() {
  docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T "$@"
}

cleanup() {
  docker compose -p "$PROJECT" -f "$COMPOSE_FILE" down -v --remove-orphans --rmi local >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_postgres() {
  local service="$1"
  local database="$2"
  local attempt
  for attempt in $(seq 1 30); do
    if compose_exec "$service" pg_isready -U postgres -d "$database" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  compose_exec "$service" pg_isready -U postgres -d "$database"
}

verify_databases() {
  PGPASSWORD=integration compose_exec "$SOURCE_SERVICE" psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='source_db'" | grep -qx 1
  PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='destination_db'" | grep -qx 1
}

seed_source() {
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE TABLE public.devices (id integer PRIMARY KEY, name text NOT NULL)"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE TABLE public.usage (time timestamptz NOT NULL, device_id integer NOT NULL REFERENCES public.devices(id), bytes bigint NOT NULL)"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "SELECT create_hypertable('public.usage', by_range('time', INTERVAL '1 day'))"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "INSERT INTO public.devices SELECT g, 'device-' || g FROM generate_series(1,3) g"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "INSERT INTO public.usage SELECT TIMESTAMPTZ '2026-01-01' + g * INTERVAL '1 day', ((g-1)%3)+1, g*100 FROM generate_series(1,48) g"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CREATE MATERIALIZED VIEW public.daily_usage WITH (timescaledb.continuous) AS SELECT time_bucket('1 day',time) bucket,min(device_id) device_id,sum(bytes) bytes FROM public.usage GROUP BY bucket WITH NO DATA"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "CALL refresh_continuous_aggregate('public.daily_usage',NULL,NULL)"
  compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -v ON_ERROR_STOP=1 -c "ANALYZE"
}

verify_seed() {
  test "$(PGPASSWORD=integration compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.devices")" = 3
  test "$(PGPASSWORD=integration compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.usage")" = 48
  test "$(PGPASSWORD=integration compose_exec "$SOURCE_SERVICE" psql -U postgres -d source_db -Atc "SELECT count(*) FROM public.daily_usage")" = 48
}

build_bridge() {
  rm -rf .local-bridge-test
  MANUBISGUARD_BRIDGE_DATABASE_URL="$SOURCE_URL" uv run python -m app.migration.portable_bridge --database-url-env MANUBISGUARD_BRIDGE_DATABASE_URL --source-version 2.30.0 --target-version 2.29.2 --output-dir .local-bridge-test
  test -s .local-bridge-test/portable-plan.json
  test -s .local-bridge-test/portable-hypertables.sql
  test -s .local-bridge-test/portable-post-data.sql
}

dump_source() {
  rm -rf .local-migration-dumps
  mkdir -p .local-migration-dumps
  local section
  for section in pre-data data post-data; do
    compose_exec -e PGPASSWORD=integration "$SOURCE_SERVICE" pg_dump -U postgres -d source_db --format=plain --quote-all-identifiers --no-owner --no-privileges --no-tablespaces --section="$section" --exclude-extension=timescaledb --exclude-schema=_timescaledb_internal --exclude-schema=_timescaledb_catalog --exclude-schema=_timescaledb_config --exclude-table=public.daily_usage > ".local-migration-dumps/$section.sql"
    test -s ".local-migration-dumps/$section.sql"
    uv run python -c "from pathlib import Path; from app.migration.timescale import prepare_timescale_sql_file; p=Path('.local-migration-dumps/$section.sql'); prepare_timescale_sql_file(p, p.with_suffix('.prepared.sql'), target_pg_major=16)"
    test -s ".local-migration-dumps/$section.prepared.sql"
  done
}

restore_destination() {
  PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb"
  cat .local-migration-dumps/pre-data.prepared.sql | PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1
  cat .local-bridge-test/portable-hypertables.sql | PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1
  cat .local-migration-dumps/data.prepared.sql | PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1
  cat .local-migration-dumps/post-data.prepared.sql | PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1
  cat .local-bridge-test/portable-post-data.sql | PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -v ON_ERROR_STOP=1
}

verify_cagg() {
  test "$(PGPASSWORD=integration compose_exec "$DESTINATION_SERVICE" psql -U postgres -d destination_db -Atc "SELECT count(*) FROM public.daily_usage")" = 48
}

echo "==> Validate compose configuration"
if ! docker compose -p "$PROJECT" -f "$COMPOSE_FILE" config -q; then
  echo "FAILED: Validate compose configuration"
  exit 1
fi
echo "OK: Validate compose configuration"

stage "Start isolated Timescale services" docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --wait
stage "Verify source and destination databases" verify_databases
stage "Verify PostgreSQL readiness before seed" wait_for_postgres "$SOURCE_SERVICE" source_db
stage "Seed source database" seed_source
stage "Verify seeded data and 48-row continuous aggregate" verify_seed
stage "Build portable bridge artifacts" build_bridge
stage "Dump pre-data, data, and post-data from source service" dump_source
stage "Restore source schema and data on destination" restore_destination
stage "Verify migration counts" uv run python scripts/verify-migration-counts.py --source-url "$SOURCE_URL" --destination-url "$DESTINATION_URL"
stage "Verify migrated continuous aggregate has 48 rows" verify_cagg
stage "Ruff lint (feature scope)" uv run ruff check app/core/domain_intelligence.py app/migration/portable_bridge.py app/migration/timescale.py tests/migration/test_portable_bridge.py --no-fix
stage "Ruff format check (feature scope)" uv run ruff format --check app/core/domain_intelligence.py app/migration/portable_bridge.py app/migration/timescale.py tests/migration/test_portable_bridge.py
stage "Migration unit tests" uv run pytest tests/migration -q

if [ "$RESULT" -eq 0 ]; then
  echo "ALL TESTS PASSED"
else
  echo "TESTS FAILED"
fi
exit "$RESULT"
