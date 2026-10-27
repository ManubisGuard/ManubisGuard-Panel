#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

log() { printf '[test-installer-source-fetch] %s\n' "$*"; }
die() { printf '[test-installer-source-fetch] ERROR: %s\n' "$*" >&2; exit 1; }

# Exercise the actual prepare_source() function from the installer, not a copy.
source <(awk '/^prepare_source\(\) \{/ {copy=1} copy {print} copy && /^}$/ {exit}' "$ROOT/install-pasarguard.sh")

git init --bare "$TMP/remote.git" >/dev/null
git init -b feature/amnezia-wg "$TMP/seed" >/dev/null
git -C "$TMP/seed" config user.name Test
git -C "$TMP/seed" config user.email test@example.invalid
printf 'installer-source-fetch-test\n' > "$TMP/seed/marker.txt"
git -C "$TMP/seed" add marker.txt
git -C "$TMP/seed" commit -m 'seed feature branch' >/dev/null
git -C "$TMP/seed" remote add origin "$TMP/remote.git"
git -C "$TMP/seed" push -u origin feature/amnezia-wg >/dev/null

# Simulate an existing checkout whose fetch refspec only tracks a different branch.
git clone -b feature/amnezia-wg "$TMP/remote.git" "$TMP/existing" >/dev/null
git -C "$TMP/existing" checkout -b test-install >/dev/null
git -C "$TMP/existing" config remote.origin.fetch '+refs/heads/test-install:refs/remotes/origin/test-install'
INSTALL_DIR="$TMP/existing"
UPDATE_MODE=false
REPO="$TMP/remote.git"
BRANCH=feature/amnezia-wg
prepare_source

test "$(git -C "$INSTALL_DIR" branch --show-current)" = feature/amnezia-wg
test "$(git -C "$INSTALL_DIR" rev-parse HEAD)" = "$(git --git-dir="$TMP/remote.git" rev-parse refs/heads/feature/amnezia-wg)"
test -s "$INSTALL_DIR/marker.txt"
printf '%s\n' 'installer existing-checkout explicit branch fetch: PASS'
