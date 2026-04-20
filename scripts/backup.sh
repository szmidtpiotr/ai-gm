#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_SOURCE="$ROOT_DIR/data/ai_gm.db"
BACKUP_DIR="$ROOT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/ai_gm_${DATE}.db"

if [ ! -f "$DB_SOURCE" ]; then
  echo "ERROR: Database not found at $DB_SOURCE"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp "$DB_SOURCE" "$DEST"
echo "✅ Backup saved: $DEST"
echo "   Size: $(du -h "$DEST" | cut -f1)"
