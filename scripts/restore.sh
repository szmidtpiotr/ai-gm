#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_TARGET="$ROOT_DIR/data/ai_gm.db"
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
