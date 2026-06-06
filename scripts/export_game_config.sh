#!/bin/bash
# Export game_config seed from DEV database — commit to git

set -e

SEED_FILE="data/game_config_seed.sql"
DB_PATH="/data/ai_gm.db"  # actual DB location (mounted from data-dev/)
CONTAINER="ai-gm-dev-backend-1"

echo "🔄 Exporting game config seed from DEV..."
echo "   Database: $DB_PATH"

# Simply use sqlite3 dump command on entire DB, then filter to static tables only
docker exec $CONTAINER sqlite3 $DB_PATH .dump | grep -E "^(CREATE TABLE|INSERT INTO) (game_config_|dungeon_|gameconfig_|adventure_|enemy_behavior_|hex_type_|knowledge_|ui_texts|campaign_templates)" > "$SEED_FILE.tmp" 2>/dev/null || true

# If that didn't work, try simpler .dump of all tables, then post-filter
if [ ! -s "$SEED_FILE.tmp" ]; then
    docker exec $CONTAINER sqlite3 $DB_PATH .dump > "$SEED_FILE.tmp.all"
    grep -E "^(CREATE TABLE|INSERT INTO) (game_config_|dungeon_|gameconfig_|adventure_|enemy_behavior_|hex_type_|knowledge_|ui_texts|campaign_templates)" "$SEED_FILE.tmp.all" > "$SEED_FILE.tmp" 2>/dev/null || true
    rm -f "$SEED_FILE.tmp.all"
fi

if [ -f "$SEED_FILE.tmp" ]; then
    mv "$SEED_FILE.tmp" "$SEED_FILE"
    SIZE=$(du -h "$SEED_FILE" | cut -f1)
    ROWS=$(grep -c "^INSERT INTO" "$SEED_FILE" || echo "0")
    echo "✅ Seed exported: $SEED_FILE ($SIZE, ~$ROWS rows)"
    echo "📝 Next: git add $SEED_FILE && git commit -m 'chore: update game config seed'"
else
    echo "❌ Failed to export seed file"
    exit 1
fi
