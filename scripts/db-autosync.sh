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
#   OBS_KEY        path to SSH private key      (default: REPO_ROOT/.secrets/ai_gm_debug_key)
#   REMOTE_DB_DIR  target dir on obs. host      (default: /var/lib/ai-gm-db)
#                  e.g. /home/you/ai-gm/observability-data/story-db when using AI_GM_STORY_DB_DIR
#   SYNC_SOURCE    "docker" (default) or "host" — where to read the DB before scp
#   BACKEND_CTR    backend Docker container name (default: ai-gm-backend-1)
#   BACKEND_DB_PATH path inside container for docker cp (default: /data/ai_gm.db)
#   HOST_DB_PATH   host filesystem path when SYNC_SOURCE=host (e.g. /ai-gm/data/ai_gm.db)
#   SYNC_INTERVAL  seconds between syncs (--loop)(default: 300)
#   SYNC_TRANSPORT "ssh" (default) or "local" — local = copy to REMOTE_DB_DIR on this machine (no SSH)
#   CRON_SCHEDULE  cron time spec for --install-cron (default: */5 * * * *)
#   LOG_FILE       log file for cron mode       (default: /tmp/ai-gm-db-sync.log)
# ============================================================
set -euo pipefail

# ---- config ----
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OBS_HOST="${OBS_HOST:-192.168.1.19}"
OBS_USER="${OBS_USER:-root}"
OBS_KEY="${OBS_KEY:-${REPO_ROOT}/.secrets/ai_gm_debug_key}"
REMOTE_DB_DIR="${REMOTE_DB_DIR:-/var/lib/ai-gm-db}"
SYNC_SOURCE="${SYNC_SOURCE:-docker}"
BACKEND_CTR="${BACKEND_CTR:-ai-gm-backend-1}"
BACKEND_DB_PATH="${BACKEND_DB_PATH:-/data/ai_gm.db}"
HOST_DB_PATH="${HOST_DB_PATH:-}"
SYNC_INTERVAL="${SYNC_INTERVAL:-300}"
SYNC_TRANSPORT="${SYNC_TRANSPORT:-ssh}"
CRON_SCHEDULE="${CRON_SCHEDULE:-*/5 * * * *}"
LOG_FILE="${LOG_FILE:-/tmp/ai-gm-db-sync.log}"
TMP_DB="/tmp/ai_gm_autosync_$$.db"

SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
CRON_MARKER="# ai-gm-db-autosync"
CRON_WRAPPER="${REPO_ROOT}/scripts/.db-autosync-cron-wrap.sh"

# ---- helpers ----
ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(ts)] $*"; }

run_sync() {
    if [[ "${SYNC_TRANSPORT}" == "local" ]]; then
        log "START sync  (${SYNC_SOURCE}, transport=local) → ${REMOTE_DB_DIR}/ai_gm.db"
    else
        log "START sync  (${SYNC_SOURCE}, transport=ssh) → ${OBS_USER}@${OBS_HOST}:${REMOTE_DB_DIR}/ai_gm.db"
    fi

    case "${SYNC_SOURCE}" in
        host)
            if [[ -z "${HOST_DB_PATH}" ]]; then
                log "ERROR SYNC_SOURCE=host requires HOST_DB_PATH (e.g. /ai-gm/data/ai_gm.db)"
                return 1
            fi
            if [[ ! -f "${HOST_DB_PATH}" ]]; then
                log "ERROR HOST_DB_PATH not a file: ${HOST_DB_PATH}"
                return 1
            fi
            cp -f "${HOST_DB_PATH}" "${TMP_DB}" || {
                log "ERROR cp from host failed"
                rm -f "${TMP_DB}"
                return 1
            }
            ;;
        docker)
            if ! docker inspect "${BACKEND_CTR}" > /dev/null 2>&1; then
                log "ERROR container '${BACKEND_CTR}' not found — is the game stack running?"
                return 1
            fi
            docker cp "${BACKEND_CTR}:${BACKEND_DB_PATH}" "${TMP_DB}" 2>/dev/null || {
                log "ERROR docker cp ${BACKEND_CTR}:${BACKEND_DB_PATH} failed"
                rm -f "${TMP_DB}"
                return 1
            }
            ;;
        *)
            log "ERROR unknown SYNC_SOURCE='${SYNC_SOURCE}' (use docker or host)"
            return 1
            ;;
    esac

    if [[ "${SYNC_TRANSPORT}" == "local" ]]; then
        mkdir -p "${REMOTE_DB_DIR}" || {
            log "ERROR cannot mkdir ${REMOTE_DB_DIR}"
            rm -f "${TMP_DB}"
            return 1
        }
        # Atomic replace so Grafana's SQLite plugin picks up a new inode/file.
        PARTIAL="${REMOTE_DB_DIR}/ai_gm.db.partial.$$"
        cp -f "${TMP_DB}" "${PARTIAL}" || {
            log "ERROR cp to ${PARTIAL} failed"
            rm -f "${TMP_DB}" "${PARTIAL}"
            return 1
        }
        chmod 644 "${PARTIAL}" 2>/dev/null || true
        mv -f "${PARTIAL}" "${REMOTE_DB_DIR}/ai_gm.db" || {
            log "ERROR mv to ${REMOTE_DB_DIR}/ai_gm.db failed"
            rm -f "${TMP_DB}" "${PARTIAL}"
            return 1
        }
        rm -f "${TMP_DB}"
        log "DONE  synced (local) → ${REMOTE_DB_DIR}/ai_gm.db"
        return 0
    fi

    if [[ ! -f "${OBS_KEY}" ]]; then
        log "ERROR missing SSH key: ${OBS_KEY} (set OBS_KEY or use SYNC_TRANSPORT=local)"
        rm -f "${TMP_DB}"
        return 1
    fi

    ssh -i "${OBS_KEY}" -o BatchMode=yes -o ConnectTimeout=8 \
        "${OBS_USER}@${OBS_HOST}" "mkdir -p ${REMOTE_DB_DIR}" 2>/dev/null || {
        log "ERROR SSH to ${OBS_HOST} failed"
        rm -f "${TMP_DB}"
        return 1
    }

    REMOTE_PARTIAL="${REMOTE_DB_DIR}/ai_gm.db.partial.${RANDOM}"
    scp -i "${OBS_KEY}" -o BatchMode=yes -o ConnectTimeout=8 \
        "${TMP_DB}" "${OBS_USER}@${OBS_HOST}:${REMOTE_PARTIAL}" 2>/dev/null || {
        log "ERROR scp upload failed"
        rm -f "${TMP_DB}"
        return 1
    }

    ssh -i "${OBS_KEY}" -o BatchMode=yes "${OBS_USER}@${OBS_HOST}" \
        "mv -f '${REMOTE_PARTIAL}' '${REMOTE_DB_DIR}/ai_gm.db' && chmod 644 '${REMOTE_DB_DIR}/ai_gm.db'" 2>/dev/null || {
        log "ERROR remote mv/chmod failed"
        rm -f "${TMP_DB}"
        return 1
    }

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
        cat > "${CRON_WRAPPER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export SYNC_TRANSPORT="${SYNC_TRANSPORT}"
export SYNC_SOURCE="${SYNC_SOURCE}"
export REMOTE_DB_DIR="${REMOTE_DB_DIR}"
export OBS_HOST="${OBS_HOST}"
export OBS_USER="${OBS_USER}"
export OBS_KEY="${OBS_KEY}"
export BACKEND_CTR="${BACKEND_CTR}"
export BACKEND_DB_PATH="${BACKEND_DB_PATH}"
export HOST_DB_PATH="${HOST_DB_PATH}"
exec "${SCRIPT_ABS}"
EOF
        chmod 700 "${CRON_WRAPPER}"
        CRON_LINE="${CRON_SCHEDULE} \"${CRON_WRAPPER}\" >> \"${LOG_FILE}\" 2>&1 ${CRON_MARKER}"
        (crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" || true; echo "${CRON_LINE}") | crontab -
        echo "Cron job installed:"
        echo "  schedule: ${CRON_SCHEDULE}"
        echo "  wrapper:  ${CRON_WRAPPER}"
        crontab -l | grep "${CRON_MARKER}"
        echo ""
        echo "Logs: ${LOG_FILE}"
        echo "To remove: $0 --uninstall-cron"
        ;;

    --uninstall-cron)
        crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" | crontab - || true
        rm -f "${CRON_WRAPPER}" 2>/dev/null || true
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
