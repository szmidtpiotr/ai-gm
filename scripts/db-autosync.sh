#!/usr/bin/env bash
# ============================================================
# db-autosync.sh — sync ai_gm.db from backend container to
# the observability VM so Grafana "Campaign Story Reader" stays
# current without manual intervention.
#
# MODES
#   one-shot (default):
#       ./scripts/db-autosync.sh
#
#   loop every N seconds (default 300 = 5 min):
#       ./scripts/db-autosync.sh --loop
#       SYNC_INTERVAL=60 ./scripts/db-autosync.sh --loop
#
#   install as cron job (every 5 min, current user):
#       ./scripts/db-autosync.sh --install-cron
#
#   uninstall cron job:
#       ./scripts/db-autosync.sh --uninstall-cron
#
#   show status of cron job:
#       ./scripts/db-autosync.sh --status
#
# ENV VARS (all have defaults)
#   OBS_HOST       observability VM IP/hostname (default: 192.168.1.19)
#   OBS_USER       SSH user                     (default: root)
#   OBS_KEY        path to SSH private key      (default: .secrets/ai_gm_debug_key)
#   REMOTE_DB_DIR  target dir on VM             (default: /var/lib/ai-gm-db)
#   BACKEND_CTR    backend Docker container name (default: ai-gm-backend-1)
#   SYNC_INTERVAL  seconds between syncs (--loop)(default: 300)
#   LOG_FILE       log file for cron mode       (default: /tmp/ai-gm-db-sync.log)
# ============================================================
set -euo pipefail

# ---- config ----
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OBS_HOST="${OBS_HOST:-192.168.1.19}"
OBS_USER="${OBS_USER:-root}"
OBS_KEY="${OBS_KEY:-${REPO_ROOT}/.secrets/ai_gm_debug_key}"
REMOTE_DB_DIR="${REMOTE_DB_DIR:-/var/lib/ai-gm-db}"
BACKEND_CTR="${BACKEND_CTR:-ai-gm-backend-1}"
SYNC_INTERVAL="${SYNC_INTERVAL:-300}"
LOG_FILE="${LOG_FILE:-/tmp/ai-gm-db-sync.log}"
TMP_DB="/tmp/ai_gm_autosync_$$.db"

SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
CRON_MARKER="# ai-gm-db-autosync"
CRON_LINE="*/5 * * * * /bin/bash \"${SCRIPT_ABS}\" >> \"${LOG_FILE}\" 2>&1 ${CRON_MARKER}"

# ---- helpers ----
ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(ts)] $*"; }

run_sync() {
    log "START sync  backend→${OBS_HOST}"

    if ! docker inspect "${BACKEND_CTR}" > /dev/null 2>&1; then
        log "ERROR container '${BACKEND_CTR}' not found — is the game stack running?"
        return 1
    fi

    docker cp "${BACKEND_CTR}:/data/ai_gm.db" "${TMP_DB}" 2>/dev/null || {
        log "ERROR docker cp failed"
        rm -f "${TMP_DB}"
        return 1
    }

    ssh -i "${OBS_KEY}" -o BatchMode=yes -o ConnectTimeout=8 \
        "${OBS_USER}@${OBS_HOST}" "mkdir -p ${REMOTE_DB_DIR}" 2>/dev/null || {
        log "ERROR SSH to ${OBS_HOST} failed"
        rm -f "${TMP_DB}"
        return 1
    }

    scp -i "${OBS_KEY}" -o BatchMode=yes -o ConnectTimeout=8 \
        "${TMP_DB}" "${OBS_USER}@${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db" 2>/dev/null || {
        log "ERROR scp upload failed"
        rm -f "${TMP_DB}"
        return 1
    }

    ssh -i "${OBS_KEY}" -o BatchMode=yes "${OBS_USER}@${OBS_HOST}" \
        "chmod 644 ${REMOTE_DB_DIR}/ai_gm.db" 2>/dev/null || true

    rm -f "${TMP_DB}"
    log "DONE  synced to ${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"
}

# ---- modes ----
case "${1:-}" in

    --loop)
        log "LOOP mode — syncing every ${SYNC_INTERVAL}s (Ctrl-C to stop)"
        while true; do
            run_sync || true
            log "Sleeping ${SYNC_INTERVAL}s…"
            sleep "${SYNC_INTERVAL}"
        done
        ;;

    --install-cron)
        # Remove old entry if present, then add fresh one
        (crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" || true; echo "${CRON_LINE}") | crontab -
        echo "Cron job installed (every 5 min):"
        crontab -l | grep "${CRON_MARKER}"
        echo ""
        echo "Logs: ${LOG_FILE}"
        echo "To remove: $0 --uninstall-cron"
        ;;

    --uninstall-cron)
        crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" | crontab - || true
        echo "Cron job removed."
        ;;

    --status)
        echo "=== cron job ==="
        crontab -l 2>/dev/null | grep "${CRON_MARKER}" && echo "INSTALLED" || echo "NOT installed"
        echo ""
        echo "=== last 20 log lines (${LOG_FILE}) ==="
        tail -n 20 "${LOG_FILE}" 2>/dev/null || echo "(no log yet)"
        ;;

    --help|-h)
        grep '^#' "${BASH_SOURCE[0]}" | grep -v '^#!/' | sed 's/^# \{0,2\}//'
        ;;

    "")
        run_sync
        ;;

    *)
        echo "Unknown option: $1  (use --help)"
        exit 1
        ;;
esac
