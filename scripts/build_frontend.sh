#!/usr/bin/env bash
# =============================================================
# build_frontend.sh — build the ŻAR (front-v2) SPA into
# frontend/front-v2/dist via a pinned node container.
#
# WHY: front-v2 is the primary player frontend (#1314). Its dist/ is
# gitignored (base=/graj/ baked from vite.config.ts) and PROD (.62) has
# no node/npm. Building in a container makes the dist reproducible and
# fresh on every deploy on ANY host with docker — no host toolchain.
# Called by deploy_prod.sh and deploy_dev.sh before the nginx container
# is (re)created, so /graj/ always serves a build matching deployed source.
#
# The build is hermetic: node_modules lives in a named docker volume (not
# the host tree), and npm's download cache is a second named volume so
# repeat builds are fast. Fails loudly — a broken ŻAR must abort the deploy.
# =============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FV2="$REPO_DIR/frontend/front-v2"
NODE_IMAGE="${FRONT_V2_NODE_IMAGE:-node:18}"

_docker() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    sudo docker "$@"
  else
    echo "❌ Docker niedostępny — nie mogę zbudować front-v2." >&2
    exit 1
  fi
}

if [[ ! -f "$FV2/package.json" || ! -f "$FV2/package-lock.json" ]]; then
  echo "❌ Brak $FV2/package.json lub package-lock.json — nie ma czego budować." >&2
  exit 1
fi

echo "🛠  Budowa ŻAR (front-v2) w kontenerze ${NODE_IMAGE} (npm ci + vite build)..."
_docker run --rm \
  -v "$FV2":/app \
  -v ai-gm-fv2-node-modules:/app/node_modules \
  -v ai-gm-npm-cache:/root/.npm \
  -w /app \
  "$NODE_IMAGE" \
  sh -c "npm ci --no-audit --no-fund && npm run build"

if [[ ! -f "$FV2/dist/index.html" ]]; then
  echo "❌ Build nie wyprodukował dist/index.html — przerywam." >&2
  exit 1
fi

echo "✅ ŻAR zbudowany: $(find "$FV2/dist" -type f | wc -l) plików → frontend/front-v2/dist/"
