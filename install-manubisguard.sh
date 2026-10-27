#!/usr/bin/env bash
# Legacy compatibility entry point; the canonical installer is install-pasarguard.sh.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$HERE/install-pasarguard.sh" ]; then
  exec bash "$HERE/install-pasarguard.sh" "$@"
fi
tmp="$(mktemp)"
if ! curl -fsSL "https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/install-pasarguard.sh" -o "$tmp"; then
  rm -f -- "$tmp"
  echo "Could not download the canonical PasarGuard installer." >&2
  exit 1
fi
if bash "$tmp" "$@"; then rc=0; else rc=$?; fi
rm -f -- "$tmp"
exit "$rc"
