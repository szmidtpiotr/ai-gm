#!/usr/bin/env bash
# Daily DEV DB backup. Runs from cron on .61 at 03:00.
# Retention: keep last 30 days + always-keep last 14, whichever is larger.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_SOURCE="$ROOT_DIR/data-dev/ai_gm.db"
BACKUP_DIR="$ROOT_DIR/backups/dev"
DATE=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/ai_gm_dev_${DATE}.db"

if [ ! -f "$DB_SOURCE" ]; then
  echo "ERROR: DEV database not found at $DB_SOURCE" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# Use sqlite3 .backup for a consistent online snapshot (safe while backend is
# writing); fall back to plain cp if sqlite3 is unavailable on the host.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_SOURCE" ".backup '$DEST'"
else
  cp "$DB_SOURCE" "$DEST"
fi

echo "✅ DEV backup saved: $DEST ($(du -h "$DEST" | cut -f1))"

# Retention: delete .db files older than 30 days, but always keep at least 14
# most-recent ones so a quiet period doesn't leave us empty-handed.
KEEP_MIN=14
TOTAL=$(ls -1 "$BACKUP_DIR"/ai_gm_dev_*.db 2>/dev/null | wc -l)
if [ "$TOTAL" -gt "$KEEP_MIN" ]; then
  # List old files (>30d), but skip the newest KEEP_MIN
  find "$BACKUP_DIR" -maxdepth 1 -name 'ai_gm_dev_*.db' -mtime +30 -printf '%T@ %p\n' 2>/dev/null \
    | sort -n \
    | head -n -"$KEEP_MIN" \
    | cut -d' ' -f2- \
    | xargs -r -n1 rm -v
fi
