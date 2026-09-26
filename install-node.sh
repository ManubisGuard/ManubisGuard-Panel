#!/usr/bin/env bash
set -Eeuo pipefail

NODE_INSTALLER_URL="${MANUBISGUARD_NODE_INSTALLER_URL:-https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Node/feature/amnezia-wg/install-manubisguard-node.sh}"

[[ $EUID -eq 0 ]] || { echo "ERROR: run as root." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required." >&2; exit 1; }

exec bash <(curl -fsSL "$NODE_INSTALLER_URL") "$@"
