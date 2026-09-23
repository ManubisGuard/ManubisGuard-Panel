#!/usr/bin/env bash
set -Eeuo pipefail

NODE_REPO="${PASARGUARD_NODE_REPO:-https://github.com/arsamnikzaad/ManubisGuard-Node.git}"
NODE_BRANCH="${PASARGUARD_NODE_BRANCH:-feature/amnezia-wg}"
APP_NAME="${PASARGUARD_NODE_NAME:-manubisguard-node}"
APP_DIR="${PASARGUARD_NODE_DIR:-/opt/$APP_NAME}"
DATA_DIR="${PASARGUARD_NODE_DATA:-/var/lib/$APP_NAME}"
ENV_FILE="$APP_DIR/.env"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"
SERVICE_PORT=62050
SERVICE_PROTOCOL=grpc
API_KEY=""
SSL_MODE="self-signed"
SSL_CERT_FILE="$DATA_DIR/certs/ssl_cert.pem"
SSL_KEY_FILE="$DATA_DIR/certs/ssl_key.pem"
ASSUME_YES=false
OVERRIDE=false

[[ $EUID -eq 0 ]] || { echo "ERROR: run as root."; exit 1; }

log(){ echo "[ManubisGuard Node] $*"; }
die(){ echo "ERROR: $*" >&2; exit 1; }

ask_yes_no(){
  local p="$1" d="${2:-N}" a
  [[ "$ASSUME_YES" == true ]] && return 0
  read -r -p "$p [$( [[ "$d" == Y ]] && echo Y/n || echo y/N )]: " a || true
  a="${a:-$d}"
  [[ "${a,,}" == y || "${a,,}" == yes ]]
}

valid_name(){ [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$ ]]; }
valid_port(){ [[ "$1" =~ ^[0-9]+$ ]] && (( $1 >= 1024 && $1 <= 65535 )); }

usage(){
  echo "Usage: $0 install [--name NAME] [--service-port PORT] [--api-key UUID] [--yes] [--override]"
  echo
  echo "Installer stages:"
  echo "  1) Detect existing node installation"
  echo "  2) Choose reuse / override / cancel"
  echo "  3) Configure service port and protocol"
  echo "  4) Configure TLS certificate"
  echo "  5) Install and health-check node"
}

parse_args(){
  [[ "${1:-}" == @ ]] && shift
  local cmd="${1:-}"
  [[ "$cmd" == install ]] || { usage; exit 0; }
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) APP_NAME="$2"; shift 2;;
      --name=*) APP_NAME="${1#*=}"; shift;;
      --service-port) SERVICE_PORT="$2"; shift 2;;
      --service-port=*) SERVICE_PORT="${1#*=}"; shift;;
      --api-key) API_KEY="$2"; shift 2;;
      --api-key=*) API_KEY="${1#*=}"; shift;;
      --yes|-y) ASSUME_YES=true; shift;;
      --override) OVERRIDE=true; shift;;
      *) die "Unknown option: $1";;
    esac
  done
  valid_name "$APP_NAME" || die "Invalid node name."
  valid_port "$SERVICE_PORT" || die "Invalid service port: $SERVICE_PORT"
}

ensure_dependencies(){
  command -v curl >/dev/null || { apt-get update && apt-get install -y curl; }
  command -v git >/dev/null || { apt-get update && apt-get install -y git; }
  command -v openssl >/dev/null || { apt-get update && apt-get install -y openssl; }
  command -v ss >/dev/null || { apt-get update && apt-get install -y iproute2; }

  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker detected and healthy."
  else
    log "Docker/Compose not ready; installing with official Docker installer."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    docker info >/dev/null 2>&1 || die "Docker failed to start."
    docker compose version >/dev/null 2>&1 || die "Docker Compose v2 unavailable."
  fi
}

detect_existing(){
  EXISTING=false
  [[ -f "$ENV_FILE" || -f "$COMPOSE_FILE" || -d "$APP_DIR/.git" ]] && EXISTING=true
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Fxq "$APP_NAME" && EXISTING=true || true

  if [[ "$EXISTING" == true ]]; then
    echo
    echo "========== Existing Node =========="
    echo "Node: $APP_NAME"
    echo "Directory: $APP_DIR"
    echo "Data: $DATA_DIR"
    echo "  1) Reuse/update existing node (preserve data)"
    echo "  2) Override application/config (preserve certificates/data)"
    echo "  3) Cancel"
    if [[ "$ASSUME_YES" == true ]]; then
      ACTION=reuse
    else
      read -r -p "Select [1-3]: " ACTION
      case "$ACTION" in
        1) ACTION=reuse;;
        2) ACTION=override; OVERRIDE=true;;
        3|"") die "Installation cancelled. Existing node was not modified.";;
        *) die "Invalid selection.";;
      esac
    fi
  fi
}

configure(){
  echo
  echo "========== Node configuration =========="
  if [[ "$ASSUME_YES" != true ]]; then
    read -r -p "Service port [$SERVICE_PORT]: " x
    [[ -n "$x" ]] && SERVICE_PORT="$x"
    valid_port "$SERVICE_PORT" || die "Invalid service port."
  fi

  echo
  echo "========== TLS configuration =========="
  echo "1) Self-signed certificate (recommended for node)"
  echo "2) Custom certificate + key"
  echo "3) Existing certificate in node data directory"
  if [[ "$ASSUME_YES" == true ]]; then
    SSL_MODE=self-signed
  else
    read -r -p "Select TLS option [1-3] (default: 1): " c
    c="${c:-1}"
    case "$c" in
      1) SSL_MODE=self-signed;;
      2) SSL_MODE=custom;;
      3) SSL_MODE=existing;;
      *) die "Invalid TLS selection.";;
    esac
  fi

  mkdir -p "$DATA_DIR/certs"
  case "$SSL_MODE" in
    self-signed)
      if [[ ! -s "$SSL_CERT_FILE" || ! -s "$SSL_KEY_FILE" ]]; then
        openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
          -keyout "$SSL_KEY_FILE" -out "$SSL_CERT_FILE" -days 3650 \
          -subj "/CN=$(hostname -f 2>/dev/null || hostname)" \
          -addext "subjectAltName=IP:$(curl -4fsS --max-time 8 https://api4.ipify.org || hostname -I | awk '{print \$1}'),IP:127.0.0.1,DNS:localhost" >/dev/null 2>&1 \
          || die "Failed to generate self-signed certificate."
      else
        log "Existing node certificate found; reusing it."
      fi
      ;;
    custom)
      read -r -p "Full certificate path: " src_cert
      read -r -p "Full private key path: " src_key
      [[ -s "$src_cert" && -r "$src_cert" ]] || die "Certificate is not readable."
      [[ -s "$src_key" && -r "$src_key" ]] || die "Private key is not readable."
      cp -f "$src_cert" "$SSL_CERT_FILE"
      cp -f "$src_key" "$SSL_KEY_FILE"
      chmod 644 "$SSL_CERT_FILE"; chmod 600 "$SSL_KEY_FILE"
      ;;
    existing)
      [[ -s "$SSL_CERT_FILE" && -s "$SSL_KEY_FILE" ]] || die "Existing certificate/key not found."
      ;;
  esac
}

prepare_source(){
  mkdir -p "$APP_DIR" "$DATA_DIR"
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch --depth 1 origin "$NODE_BRANCH"
    git -C "$APP_DIR" checkout -B "$NODE_BRANCH" "origin/$NODE_BRANCH"
    git -C "$APP_DIR" reset --hard "origin/$NODE_BRANCH"
  else
    if [[ -e "$APP_DIR" && "$OVERRIDE" != true && "$EXISTING" != true ]]; then
      die "Directory $APP_DIR already exists. Use --override."
    fi
    if [[ ! -d "$APP_DIR/.git" ]]; then
      rm -rf "$APP_DIR"
      git clone --depth 1 --branch "$NODE_BRANCH" "$NODE_REPO" "$APP_DIR"
    fi
  fi
  [[ -f "$APP_DIR/docker-compose.yml" ]] || die "Node docker-compose.yml not found."
}

prepare_config(){
  if [[ -z "$API_KEY" && -s "$DATA_DIR/.api_key" ]]; then
    API_KEY="$(cat "$DATA_DIR/.api_key")"
  fi
  if [[ -z "$API_KEY" ]]; then
    API_KEY="$(cat /proc/sys/kernel/random/uuid)"
    printf '%s' "$API_KEY" > "$DATA_DIR/.api_key"
    chmod 600 "$DATA_DIR/.api_key"
  fi

  cat > "$ENV_FILE" <<EOF
SERVICE_PORT=$SERVICE_PORT
SERVICE_PROTOCOL=$SERVICE_PROTOCOL
API_KEY=$API_KEY
SSL_CERT_FILE=/var/lib/pg-node/certs/ssl_cert.pem
SSL_KEY_FILE=/var/lib/pg-node/certs/ssl_key.pem
GENERATED_CONFIG_PATH=/var/lib/pg-node/generated
PG_NODE_WG_HOST_ROUTING=1
EOF
  chmod 600 "$ENV_FILE"

  cat > "$APP_DIR/docker-compose.yml" <<EOF
services:
  node:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    network_mode: host
    cap_add:
      - NET_ADMIN
    env_file:
      - .env
    volumes:
      - $DATA_DIR:/var/lib/pg-node
EOF
}

start_node(){
  cd "$APP_DIR"
  docker compose build --pull node
  docker compose up -d
  sleep 3
  if ! docker compose ps --status running --services 2>/dev/null | grep -Fxq "node"; then
    docker compose ps
    docker compose logs --tail 100
    die "Node container did not start."
  fi
  log "Node container is running."
  echo
  echo "Node name: $APP_NAME"
  echo "Service port: $SERVICE_PORT"
  echo "Protocol: $SERVICE_PROTOCOL"
  echo "API key: $API_KEY"
  echo "Certificate: $SSL_CERT_FILE"
  echo "Key: $SSL_KEY_FILE"
  echo
  echo "Add this node in ManubisGuard Panel using the service port and API key."
}

main(){
  parse_args "$@"
  detect_existing
  ensure_dependencies
  configure
  prepare_source
  prepare_config
  start_node
}

main "$@"
