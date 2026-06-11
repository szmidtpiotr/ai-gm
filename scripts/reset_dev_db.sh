#!/bin/bash
# Full DEV DB wipe + schema reinit
# Run from repo root on Claude VM (.19) or directly on .61
# After wipe: follow DB-RESET GitHub issue subtask order (S0 first)

set -e

DEV_HOST="claude@192.168.1.61"
REPO="/home/piotrszmidt/ai-gm"
DB_PATH="$REPO/data-dev/ai_gm.db"

echo "=== DEV DB RESET ==="
echo ""

echo "[1/5] Backing up current DB..."
ssh "$DEV_HOST" "cd $REPO && ./scripts/backup_dev.sh 2>/dev/null || echo 'Backup skipped (DB may be empty)'"

echo "[2/5] Stopping backend container..."
ssh "$DEV_HOST" "cd $REPO && docker compose -f docker-compose.dev.yml stop backend"

echo "[3/5] Wiping DB..."
ssh "$DEV_HOST" "rm -f $DB_PATH && echo 'DB deleted'"

echo "[4/5] Starting backend (migrations recreate schema)..."
ssh "$DEV_HOST" "cd $REPO && docker compose -f docker-compose.dev.yml up -d backend"

echo "[5/5] Waiting for health check..."
for i in $(seq 1 30); do
  if ssh "$DEV_HOST" "curl -sf http://localhost:8100/health" > /dev/null 2>&1; then
    echo "Backend healthy after ${i}×2s"
    break
  fi
  echo "  ... waiting ($i/30)"
  sleep 2
done

echo ""
echo "=== WIPE COMPLETE ==="
echo ""
echo "Schema recreated. Next steps (follow GitHub DB-RESET issue):"
echo ""
echo "  S0 — Manual: create users + LLM preset"
echo "       1. POST /api/auth/register — create 'demo' user (is_admin=1)"
echo "       2. Admin → System → LLM presets → add OpenAI preset, set active"
echo "       3. Verify: https://aigm-dev.studio-colorbox.com/admin/"
echo ""
echo "  S1+ — Run seed files from data/seeds/ in order"
echo "         sqlite3 /data/ai_gm.db < data/seeds/00_core.sql"
echo ""
echo "See: https://github.com/szmidtpiotr/ai-gm/issues (DB-RESET issue)"
