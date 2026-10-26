#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/root/usr/local/bin" "$TMP/root/usr/local/lib"

cat > "$TMP/bin/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
out=""
url=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
[ -n "$out" ] && [ -n "$url" ] || exit 2
case "$url" in
  */pasarguard) source_file="$TEST_SOURCE/pasarguard" ;;
  */manubisguard-native-backup.sh) source_file="$TEST_SOURCE/scripts/manubisguard-native-backup.sh" ;;
  */manubisguard-native-restore-safety.py) source_file="$TEST_SOURCE/scripts/manubisguard-native-restore-safety.py" ;;
  */manubisguard-migrate.sh) source_file="$TEST_SOURCE/scripts/manubisguard-migrate.sh" ;;
  */lib/*.sh) source_file="$TEST_SOURCE/lib/${url##*/}" ;;
  *) echo "unexpected mocked URL: $url" >&2; exit 3 ;;
esac
cp "$source_file" "$out"
MOCK_CURL

cat > "$TMP/bin/install" <<'MOCK_INSTALL'
#!/usr/bin/env bash
set -Eeuo pipefail
args=()
for arg in "$@"; do
  if [[ "$arg" == /usr/local/* ]]; then arg="$MOCK_ROOT$arg"; fi
  args+=("$arg")
done
exec /usr/bin/install "${args[@]}"
MOCK_INSTALL

cat > "$TMP/bin/ln" <<'MOCK_LN'
#!/usr/bin/env bash
set -Eeuo pipefail
args=()
for arg in "$@"; do
  if [[ "$arg" == /usr/local/* ]]; then arg="$MOCK_ROOT$arg"; fi
  args+=("$arg")
done
exec /bin/ln "${args[@]}"
MOCK_LN

chmod +x "$TMP/bin/curl" "$TMP/bin/install" "$TMP/bin/ln"
export TEST_SOURCE="$ROOT" MOCK_ROOT="$TMP/root" PYTHONPYCACHEPREFIX="$TMP/pycache"
bash -n "$ROOT/install-pasarguard.sh" "$ROOT/install-manubisguard.sh"
TERM=xterm bash "$ROOT/pasarguard" help >/dev/null
PATH="$TMP/bin:$PATH" bash "$ROOT/pasarguard" install-script

test -x "$TMP/root/usr/local/bin/pasarguard"
test -L "$TMP/root/usr/local/bin/manubis"
test -L "$TMP/root/usr/local/bin/manubisguard"
test -x "$TMP/root/usr/local/bin/pasarguard-native-backup"
test -L "$TMP/root/usr/local/bin/manubisguard-native-backup"
test -s "$TMP/root/usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py"
test -x "$TMP/root/usr/local/bin/pasarguard-migrate"
for lib in common.sh system.sh docker.sh github.sh env.sh pasarguard-backup.sh pasarguard-restore.sh; do
  test -s "$TMP/root/usr/local/lib/pasarguard-scripts/lib/$lib"
done

echo "pasarguard official CLI/shared-library bootstrap: PASS"
