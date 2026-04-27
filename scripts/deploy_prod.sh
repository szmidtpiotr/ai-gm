#!/usr/bin/env bash
# =============================================================
# deploy_prod.sh — Deployment PRODUKCJA (port 3001 / 8000)
# Wywołaj TYLKO po zmergowaniu develop → main
# =============================================================
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "🔍 [1/5] Sprawdzanie gałęzi..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "❌ BŁĄD: Jesteś na , a nie main."
  echo "   Wykonaj: git checkout main && git pull origin main"
  exit 1
fi

echo "📦 [2/5] Backup bazy danych..."
BACKUP_FILE="backups/ai_gm_pre_deploy_$(date +%Y%m%d_%H%M%S).db"
mkdir -p backups
cp data/ai_gm.db "$BACKUP_FILE"
echo "   Backup: $BACKUP_FILE"

echo "⬇️  [3/5] Pull z main..."
git fetch origin
git pull origin main

echo "🐳 [4/5] Restart kontenerów prod..."
docker compose -f docker-compose.yml up -d --build --remove-orphans

echo "⏳ [5/5] Healthcheck (max 60s)..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8000/api/healthz > /dev/null; then
    echo "✅ Deployment zakończony sukcesem!"
    echo "   Prod: http://localhost:3001"
    exit 0
  fi
  echo "   Próba $i/12 — czekam 5s..."
  sleep 5
done
echo "❌ Backend nie odpowiada po 60s."
echo "   docker compose logs backend --tail=50"
exit 1
