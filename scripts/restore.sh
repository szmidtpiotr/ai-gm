#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# #1166 — restore into the DB the running backend actually uses (DEV: data-dev,
# PROD: data). The old hardcoded data/ai_gm.db restored a file the DEV backend
# never reads, so the restore appeared to succeed but changed nothing live.
# Override with AIGM_DB_FILE=<host path>.
if [ -n "${AIGM_DB_FILE:-}" ]; then
  DB_TARGET="$AIGM_DB_FILE"
elif [ -f "$ROOT_DIR/data-dev/ai_gm.db" ]; then
  DB_TARGET="$ROOT_DIR/data-dev/ai_gm.db"   # DEV
else
  DB_TARGET="$ROOT_DIR/data/ai_gm.db"       # PROD
fi

BACKUP_DIR="$ROOT_DIR/backups"

if [ -z "${1:-}" ]; then
  echo "Usage: ./scripts/restore.sh <filename>"
  echo ""
  echo "Available backups:"
  ls -lht "$BACKUP_DIR"/*.db 2>/dev/null | awk '{print "  " $NF}' || echo "  (none)"
  exit 1
fi

# Accept either a full path or just a filename (looks in backups/ if no path)
if [[ "$1" == /* ]] || [[ "$1" == ./* ]]; then
  SOURCE="$1"
else
  SOURCE="$BACKUP_DIR/$1"
fi

if [ ! -f "$SOURCE" ]; then
  echo "ERROR: File not found: $SOURCE"
  exit 1
fi

# Auto-backup current DB before restore
if [ -f "$DB_TARGET" ]; then
  PRE="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).db"
  cp "$DB_TARGET" "$PRE"
  echo "📦 Current DB backed up to: $PRE"
fi

cp "$SOURCE" "$DB_TARGET"
echo "✅ Restored: $SOURCE → $DB_TARGET"
echo "   Restart the backend to reload: docker compose restart backend"
