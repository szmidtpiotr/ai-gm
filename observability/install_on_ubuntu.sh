#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/ai-gm-observability}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-}"

if [[ -z "${GRAFANA_ADMIN_PASSWORD}" ]]; then
  echo "ERROR: set GRAFANA_ADMIN_PASSWORD env var before running."
  echo "Example: GRAFANA_ADMIN_PASSWORD='StrongPass123!' bash observability/install_on_ubuntu.sh"
  exit 1
fi

echo "[1/7] Installing base packages"
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release ufw jq

echo "[2/7] Installing Docker if missing"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "[3/7] Preparing firewall"
ufw allow OpenSSH || true
ufw allow 3000/tcp || true
ufw --force enable || true

echo "[4/7] Preparing target directory ${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
cp -R ./observability/* "${TARGET_DIR}/"

echo "[5/7] Starting observability stack"
cd "${TARGET_DIR}"
export GRAFANA_ADMIN_PASSWORD
docker compose pull
docker compose up -d

echo "[6/7] Checking service status"
docker compose ps

echo "[7/7] Basic health checks"
sleep 3
curl -fsS http://127.0.0.1:3100/ready && echo
curl -fsS http://127.0.0.1:3000/api/health | jq .

echo "DONE. Grafana: http://<server-ip>:3000 (user: admin)"
