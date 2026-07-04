#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# #1166 — resolve the DB the running backend actually uses.
# DEV mounts ./data-dev:/data (compose.dev), PROD mounts ./data:/data. The backend
# always opens /data/ai_gm.db inside the container, so on the host that is either
# data-dev/ai_gm.db (DEV) or data/ai_gm.db (PROD). Backing up the wrong dir (the
# old hardcoded data/ai_gm.db) silently snapshotted a file the DEV backend never
# writes. Override with AIGM_DB_FILE=<host path> when auto-detection is not enough.
if [ -n "${AIGM_DB_FILE:-}" ]; then
  DB_SOURCE="$AIGM_DB_FILE"
elif [ -f "$ROOT_DIR/data-dev/ai_gm.db" ]; then
  DB_SOURCE="$ROOT_DIR/data-dev/ai_gm.db"   # DEV
else
  DB_SOURCE="$ROOT_DIR/data/ai_gm.db"       # PROD
fi

BACKUP_DIR="$ROOT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/ai_gm_${DATE}.db"

if [ ! -f "$DB_SOURCE" ]; then
  echo "ERROR: Database not found at $DB_SOURCE" >&2
  echo "       (set AIGM_DB_FILE=<path> to override)" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# Use sqlite3 .backup for a consistent online snapshot — a plain cp of a live DB
# ignores the -wal / -shm sidecars and can produce a torn copy. Fall back to cp
# only if sqlite3 is unavailable on the host.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_SOURCE" ".backup '$DEST'"
else
  echo "⚠️  sqlite3 not found — falling back to cp (may be torn if backend is writing)" >&2
  cp "$DB_SOURCE" "$DEST"
fi

echo "✅ Backup saved: $DEST"
echo "   Source: $DB_SOURCE"
echo "   Size: $(du -h "$DEST" | cut -f1)"
