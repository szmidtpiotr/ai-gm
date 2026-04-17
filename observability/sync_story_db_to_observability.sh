#!/usr/bin/env bash
# Copy the live game DB from the backend container to the observability VM so
# Grafana "Campaign Story Reader" (SQLite datasource) matches a recent snapshot.
# Re-run after gameplay whenever you need the dashboard to reflect new turns.
set -euo pipefail

OBS_HOST="${OBS_HOST:-192.168.1.19}"
OBS_USER="${OBS_USER:-root}"
OBS_KEY="${OBS_KEY:-.secrets/ai_gm_debug_key}"
REMOTE_DB_DIR="${REMOTE_DB_DIR:-/var/lib/ai-gm-db}"

TMP_DB="/tmp/ai_gm_story_sync.db"

echo "[1/4] Export DB from backend container"
docker cp ai-gm-backend-1:/data/ai_gm.db "${TMP_DB}"

echo "[2/4] Prepare remote directory ${REMOTE_DB_DIR}"
ssh -i "${OBS_KEY}" "${OBS_USER}@${OBS_HOST}" "mkdir -p ${REMOTE_DB_DIR}"

echo "[3/4] Upload DB snapshot to observability VM"
scp -i "${OBS_KEY}" "${TMP_DB}" "${OBS_USER}@${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"

echo "[4/4] Set safe permissions"
ssh -i "${OBS_KEY}" "${OBS_USER}@${OBS_HOST}" "chmod 644 ${REMOTE_DB_DIR}/ai_gm.db"

rm -f "${TMP_DB}"
echo "DONE: SQLite snapshot synced to ${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"
