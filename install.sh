#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"
DATA_DIR="/var/lib/pasarguard"

[[ "$EUID" -eq 0 ]] || { echo "ERROR: run as root"; exit 1; }

install_base() {
  command -v git >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 && command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && return
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates openssl python3 docker.io docker-compose-plugin
  else
    echo "ERROR: this installer currently requires Debian/Ubuntu (apt-get)."
    exit 1
  fi

}

install_base
mkdir -p "$DATA_DIR/timescaledb"
if [[ -s "$DATA_DIR/.postgres_password" ]]; then
  POSTGRES_PASSWORD="$(cat "$DATA_DIR/.postgres_password")"
else
  POSTGRES_PASSWORD="$(openssl rand -hex 32)"
  printf "%s" "$POSTGRES_PASSWORD" > "$DATA_DIR/.postgres_password"
  chmod 600 "$DATA_DIR/.postgres_password"
fi
export POSTGRES_PASSWORD
rm -rf "$INSTALL_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

ADMIN_PASSWORD="$(openssl rand -hex 18)"
python3 - "$ADMIN_PASSWORD" <<'PY'
from pathlib import Path
import sys
p=Path(".env")
password=sys.argv[1]
s=p.read_text()
s=s.replace('SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///db.sqlite3"',
            'SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:////var/lib/pasarguard/pasarguard.db"')
s=s.replace('# SUDO_USERNAME = "admin"', 'SUDO_USERNAME = "admin"')
s=s.replace('# SUDO_PASSWORD = "admin"', f'SUDO_PASSWORD = "{password}"')
s=s.replace('# SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://postgres:DB_PASSWORD@localhost:5432/pasarguard"', f'SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://pasarguard:{__import__("os").environ.get("POSTGRES_PASSWORD")}@127.0.0.1:5432/pasarguard"')
s=s.replace('SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:////var/lib/pasarguard/pasarguard.db"', f'SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://pasarguard:{__import__("os").environ.get("POSTGRES_PASSWORD")}@127.0.0.1:5432/pasarguard"')
p.write_text(s)
PY

printf '%s\n' "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
docker compose build --pull=false
docker compose up -d

echo "Panel source: $REPO"
echo "Panel branch: $BRANCH"\necho "Initial admin username: admin"\necho "Initial admin password: $ADMIN_PASSWORD"\necho "TimescaleDB: 127.0.0.1:5432 / database=pasarguard / user=pasarguard"
docker compose ps
