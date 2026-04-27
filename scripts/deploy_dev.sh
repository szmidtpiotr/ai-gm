#!/usr/bin/env bash
# =============================================================
# deploy_dev.sh — Deployment DEV (port 3002 / 8100)
# =============================================================
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "⬇️  [1/3] Pull z develop..."
git fetch origin
git checkout develop
git pull origin develop

echo "🐳 [2/3] Restart kontenerów dev..."
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans

echo "⏳ [3/3] Healthcheck dev (max 60s)..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8100/api/healthz > /dev/null; then
    echo "✅ Dev deployment zakończony!"
    echo "   Dev: http://localhost:3002"
    exit 0
  fi
  echo "   Próba $i/12 — czekam 5s..."
  sleep 5
done
echo "❌ Dev backend nie odpowiada."
echo "   docker compose -f docker-compose.dev.yml logs backend --tail=50"
exit 1
