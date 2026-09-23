#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/arsamnikzaad/pasarguard-panel-awg.git"
BRANCH="${PASARGUARD_PANEL_BRANCH:-feature/amnezia-wg}"
INSTALL_DIR="${PASARGUARD_PANEL_DIR:-/opt/pasarguard-panel-awg}"

[[ "$EUID" -eq 0 ]] || { echo "Run as root."; exit 1; }
command -v git >/dev/null 2>&1 || { apt-get update && apt-get install -y git; }
command -v docker >/dev/null 2>&1 || { curl -fsSL https://get.docker.com | sh; }

rm -rf "$INSTALL_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"

cd "$INSTALL_DIR"
docker compose build --pull=false
docker compose up -d

echo "PasarGuard Panel AWG installed from: $REPO ($BRANCH)"
docker compose ps
