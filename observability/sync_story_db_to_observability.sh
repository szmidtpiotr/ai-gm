#!/usr/bin/env bash
# Copy the live game DB to the observability VM so Grafana "Campaign Story Reader"
# and MCP campaign_story() see a recent snapshot. Re-run after gameplay as needed.
#
# ENV: OBS_HOST OBS_USER OBS_KEY REMOTE_DB_DIR BACKEND_CTR BACKEND_DB_PATH
#      SYNC_SOURCE=docker|host  HOST_DB_PATH (required when SYNC_SOURCE=host)
#
# Examples:
#   ./observability/sync_story_db_to_observability.sh
#   SYNC_SOURCE=host HOST_DB_PATH=/ai-gm/data/ai_gm.db ./observability/sync_story_db_to_observability.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OBS_HOST="${OBS_HOST:-192.168.1.19}"
OBS_USER="${OBS_USER:-root}"
OBS_KEY="${OBS_KEY:-${REPO_ROOT}/.secrets/ai_gm_debug_key}"
REMOTE_DB_DIR="${REMOTE_DB_DIR:-/var/lib/ai-gm-db}"
SYNC_SOURCE="${SYNC_SOURCE:-docker}"
BACKEND_CTR="${BACKEND_CTR:-ai-gm-backend-1}"
BACKEND_DB_PATH="${BACKEND_DB_PATH:-/data/ai_gm.db}"
HOST_DB_PATH="${HOST_DB_PATH:-}"

TMP_DB="/tmp/ai_gm_story_sync.db"

echo "[1/4] Export DB (${SYNC_SOURCE})"
case "${SYNC_SOURCE}" in
    host)
        if [[ -z "${HOST_DB_PATH}" ]]; then
            echo "ERROR: SYNC_SOURCE=host requires HOST_DB_PATH"
            exit 1
        fi
        cp -f "${HOST_DB_PATH}" "${TMP_DB}"
        ;;
    docker)
        docker cp "${BACKEND_CTR}:${BACKEND_DB_PATH}" "${TMP_DB}"
        ;;
    *)
        echo "ERROR: SYNC_SOURCE must be docker or host"
        exit 1
        ;;
esac

echo "[2/4] Prepare remote directory ${REMOTE_DB_DIR}"
ssh -i "${OBS_KEY}" "${OBS_USER}@${OBS_HOST}" "mkdir -p ${REMOTE_DB_DIR}"

echo "[3/4] Upload DB snapshot to observability VM"
scp -i "${OBS_KEY}" "${TMP_DB}" "${OBS_USER}@${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"

echo "[4/4] Set safe permissions"
ssh -i "${OBS_KEY}" "${OBS_USER}@${OBS_HOST}" "chmod 644 ${REMOTE_DB_DIR}/ai_gm.db"

rm -f "${TMP_DB}"
echo "DONE: SQLite snapshot synced to ${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"
