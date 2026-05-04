-- Czyści wszystkie tabele katalogu importowane przez
-- POST /api/admin/config/catalog-snapshot/import
-- (ta sama kolejność co admin_config_transfer: od liści do korzenia).
--
-- Domyślna ścieżka w kodzie backendu to /data/ai_gm.db (volume w kontenerze).
-- NIE używaj dosłownie „/ścieżka/do/ai_gm.db” — to był tylko placeholder w dokumentacji.
--
-- Na hoście (jeśli masz lokalny plik SQLite, np. skopiowany z kontenera):
--   cd ~/ai-gm && sqlite3 ./chemin/vers/ai_gm.db < scripts/sql/wipe_game_catalog.sql
--
-- W środku kontenera backendu (typowo tam jest /data/ai_gm.db):
--   docker compose exec backend sqlite3 /data/ai_gm.db < /app/scripts/sql/wipe_game_catalog.sql
--   (dostosuj nazwę serwisu i ścieżkę do repo w kontenerze — często trzeba skopiować .sql lub użyć stdin)
--
-- Najprościej z hosta, jeśli znasz nazwę serwisu z docker-compose.yml:
--   docker compose exec -T backend sqlite3 /data/ai_gm.db < scripts/sql/wipe_game_catalog.sql
--
-- Potem sprawdź liczby:
--   SELECT 'stats', COUNT(*) FROM game_config_stats UNION ALL
--   SELECT 'skills', COUNT(*) FROM game_config_skills UNION ALL
--   SELECT 'dc', COUNT(*) FROM game_config_dc UNION ALL
--   SELECT 'weapons', COUNT(*) FROM game_config_weapons UNION ALL
--   SELECT 'conditions', COUNT(*) FROM game_config_conditions UNION ALL
--   SELECT 'items', COUNT(*) FROM game_config_items UNION ALL
--   SELECT 'consumables', COUNT(*) FROM game_config_consumables UNION ALL
--   SELECT 'loot_tables', COUNT(*) FROM game_config_loot_tables UNION ALL
--   SELECT 'enemies', COUNT(*) FROM game_config_enemies UNION ALL
--   SELECT 'loot_entries', COUNT(*) FROM game_config_loot_entries;

PRAGMA foreign_keys = OFF;

DELETE FROM game_config_loot_entries;
DELETE FROM game_config_enemies;
DELETE FROM game_config_loot_tables;
DELETE FROM game_config_consumables;
DELETE FROM game_config_items;
DELETE FROM game_config_conditions;
DELETE FROM game_config_weapons;
DELETE FROM game_config_dc;
DELETE FROM game_config_skills;
DELETE FROM game_config_stats;

PRAGMA foreign_keys = ON;
