#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"
DATA_DIR="/var/lib/pasarguard"

[[ "$EUID" -eq 0 ]] || { echo "ERROR: run as root"; exit 1; }

install_base() {
  command -v git >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 && command -v docker >/dev/null 2>&1 && return
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
  else
    echo "ERROR: this installer currently requires Debian/Ubuntu (apt-get)."
    exit 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi
}

install_base
mkdir -p "$DATA_DIR"
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
p.write_text(s)
PY

docker compose build --pull=false
docker compose up -d

echo "Panel source: $REPO"
echo "Panel branch: $BRANCH"\necho "Initial admin username: admin"\necho "Initial admin password: $ADMIN_PASSWORD"
docker compose ps
