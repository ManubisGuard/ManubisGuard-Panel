#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
SOURCE_URL="${MANUBISGUARD_BRIDGE_SOURCE_URL:-postgresql://postgres:integration@127.0.0.1:55432/source_db}"
DESTINATION_URL="${MANUBISGUARD_BRIDGE_DESTINATION_URL:-postgresql://postgres:integration@127.0.0.1:55433/destination_db}"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" up -d --wait
uv run ruff check app tests --no-fix
uv run ruff format --check app tests
uv run pytest tests/migration -q

MANUBISGUARD_BRIDGE_DATABASE_URL="$SOURCE_URL" uv run python -m app.migration.portable_bridge --database-url-env MANUBISGUARD_BRIDGE_DATABASE_URL --source-version 2.30.0 --target-version 2.29.2 --output-dir .local-bridge-test
