#!/bin/sh
# Bootstrap empty E2E volume with base schema before FastAPI migrations run.
set -eu
DB="${DATABASE_URL#sqlite:///}"
if [ -z "$DB" ]; then
  DB="/data/ai_gm.db"
fi
mkdir -p "$(dirname "$DB")"
if [ ! -f "$DB" ]; then
  echo "[e2e] Initializing $DB from sql/schema.sql"
  sqlite3 "$DB" < /app/sql/schema.sql
  if [ -f /app/sql/002_turn_engine.sql ]; then
    sqlite3 "$DB" < /app/sql/002_turn_engine.sql || true
  fi
  if [ -f /app/sql/004_campaign_turns.sql ]; then
    sqlite3 "$DB" < /app/sql/004_campaign_turns.sql || true
  fi
  if [ -f /app/sql/e2e_bootstrap.sql ]; then
    sqlite3 "$DB" < /app/sql/e2e_bootstrap.sql || true
  fi
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
