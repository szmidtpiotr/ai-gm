#!/bin/bash
# Import game_config seed into running container DB

set -e

SEED_FILE="data/game_config_seed.sql"
ENVIRONMENT=${1:-dev}  # dev or prod
FORCE=${2:-}  # --force to skip confirmation

if [ ! -f "$SEED_FILE" ]; then
    echo "❌ Seed file not found: $SEED_FILE"
    echo "   Run: bash scripts/export_game_config.sh (from DEV)"
    exit 1
fi

# Determine target container
if [ "$ENVIRONMENT" = "prod" ]; then
    CONTAINER="ai-gm-backend-1"
    DB="/data/ai_gm.db"
    echo "🔴 TARGET: PRODUCTION"
elif [ "$ENVIRONMENT" = "dev" ]; then
    CONTAINER="ai-gm-dev-backend-1"
    DB="/data/ai_gm_dev.db"
    echo "🟢 TARGET: DEV"
else
    echo "❌ Unknown environment: $ENVIRONMENT (use 'dev' or 'prod')"
    exit 1
fi

# Confirmation (unless --force)
if [ "$FORCE" != "--force" ]; then
    echo "📋 This will import $(grep -c '^INSERT INTO' "$SEED_FILE") rows into $ENVIRONMENT"
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "⏳ Importing seed into $ENVIRONMENT..."

# Read seed file and execute in container
docker exec -i "$CONTAINER" sqlite3 "$DB" < "$SEED_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Seed imported successfully!"
    echo "   Verify: docker logs $CONTAINER | tail -20"
else
    echo "❌ Import failed"
    exit 1
fi
