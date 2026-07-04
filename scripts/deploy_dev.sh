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

echo "🔍 [3/4] DB Lint — audyt integralności (informacyjny, nie blokujący)..."
docker compose -f docker-compose.dev.yml exec -T backend python scripts/db_lint.py || true

echo "🌱 [3b/4] Seed Lint (U13) — walidacja seedów 01–15 (informacyjny, nie blokujący)..."
docker compose -f docker-compose.dev.yml cp data/seeds backend:/tmp/seeds 2>/dev/null \
  || docker cp data/seeds ai-gm-dev-backend-1:/tmp/seeds 2>/dev/null || true
docker compose -f docker-compose.dev.yml exec -T backend python scripts/lint_seeds.py --seeds-dir /tmp/seeds || true

echo "⏳ [4/4] Healthcheck dev (max 60s)..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8100/api/healthz > /dev/null; then
    echo "✅ Dev deployment zakończony!"
    echo "🗺  Seed mapy świata (Kresy) — odtworzy z docs/world/world_map_seed.json jeśli world_hexes puste..."
    python3 scripts/seed_world_map.py || true
    echo "📚 Seed treści gry (#1202) — git seedy -> DB (kanon; wiersze kampanijne nietknięte)..."
    cp data-dev/ai_gm.db "backups/ai_gm_dev_pre_seed_$(date +%Y%m%d_%H%M%S).db" 2>/dev/null || true
    python3 scripts/seed_content.py --apply --db data-dev/ai_gm.db --seeds data/seeds/content || true
    echo "   Dev: http://localhost:3002"
    exit 0
  fi
  echo "   Próba $i/12 — czekam 5s..."
  sleep 5
done
echo "❌ Dev backend nie odpowiada."
echo "   docker compose -f docker-compose.dev.yml logs backend --tail=50"
exit 1
