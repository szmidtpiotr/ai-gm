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

# #1179 — env.test MUST be a file, not a directory. Docker bind-mount
# (./env.test:/app/env.test) silently creates an empty DIRECTORY on the host
# if the path is missing → bootstrap_env.py:_load_one_file() skips it
# (is_file() == False) and AI_TEST_MODE / AI_TEST_STUB_LLM never load.
# env.test is gitignored, so seed it from env.test.example on every deploy.
if [ -d env.test ]; then
  echo "⚠️  env.test is a directory (docker artifact) — replacing with file..."
  rmdir env.test 2>/dev/null || rm -rf env.test
fi
if [ ! -f env.test ]; then
  echo "🌱 Seeding env.test from env.test.example..."
  cp env.test.example env.test
fi

echo "🛠  [2a/3] Budowa ŻAR (front-v2) — dist gitignored, budujemy w kontenerze node..."
"$REPO_DIR/scripts/build_frontend.sh"

echo "🐳 [2b/3] Restart kontenerów dev..."
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
# nginx.conf/dist są bind-mountem → wymuś recreate frontendu by załadować zmiany.
docker compose -f docker-compose.dev.yml up -d --force-recreate frontend

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
    python3 scripts/seed_world_map.py
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
