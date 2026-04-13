#!/bin/bash
set -e

echo "=========================================="
echo "🚀 AI GM Install Script"
echo "=========================================="
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "❌ Docker Compose is not available"
  exit 1
fi

echo "✅ Docker and Docker Compose found"
echo ""

echo "🛑 Stopping existing containers..."
docker compose down 2>/dev/null || true
echo ""

echo "🧹 Removing old database volume contents..."
docker volume rm ai-gm_ai_gm_data 2>/dev/null || true
echo "✅ Fresh volume will be created"
echo ""

echo "🔨 Building containers..."
docker compose build backend frontend
echo ""

echo "🚀 Starting backend only..."
docker compose up -d backend
echo ""

echo "⏳ Waiting for backend container..."
sleep 5

echo "🗃️ Initializing database..."
docker compose exec -T backend sh -lc '
  rm -f /data/ai_gm.db &&
  sqlite3 /data/ai_gm.db < /app/sql/schema.sql &&
  sqlite3 /data/ai_gm.db < /app/sql/002_turn_engine.sql &&
  sqlite3 /data/ai_gm.db < /app/sql/004_campaign_turns.sql &&
  sqlite3 /data/ai_gm.db < /app/sql/seed.sql
'
echo "✅ Database initialized"
echo ""

echo "🚀 Starting frontend..."
docker compose up -d frontend
echo ""

echo "⏳ Waiting for API health..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -s --max-time 3 http://localhost:8000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

echo ""
echo "=========================================="
echo "📊 Installation Summary"
echo "=========================================="

curl -s http://localhost:8000/api/health || true
echo ""
echo ""
echo "🌐 Frontend: http://localhost:3001"
echo "👤 Demo user: demo / demo"