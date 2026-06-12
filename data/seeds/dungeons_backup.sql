PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE game_dungeons (
            key             TEXT PRIMARY KEY,
            label           TEXT NOT NULL,
            location_key    TEXT NOT NULL,
            rooms           INTEGER NOT NULL DEFAULT 5,
            enemy_pool      TEXT NOT NULL DEFAULT '[]',
            boss_enemy      TEXT,
            loot_tier       TEXT NOT NULL DEFAULT 'standard',
            atmosphere      TEXT,
            cooldown_hours  INTEGER NOT NULL DEFAULT 72,
            min_level       INTEGER NOT NULL DEFAULT 1,
            is_active       INTEGER NOT NULL DEFAULT 1
        , chest_loot_table_key TEXT, boss_loot_table_key TEXT, room_loot_chance REAL NOT NULL DEFAULT 0.15, room_types_json TEXT NOT NULL DEFAULT '{"combat":50,"chest":15,"trap":15,"riddle":10,"rest":10}', riddle_source TEXT NOT NULL DEFAULT 'database', riddle_max_hints INTEGER NOT NULL DEFAULT 2, tile_category_key TEXT, difficulty_config_json TEXT NOT NULL DEFAULT '{"1":{"tiles":4},"2":{"tiles":6},"3":{"tiles":8},"4":{"tiles":10}}', boss_tile_id INTEGER, tile_count INTEGER, dungeon_difficulty INTEGER NOT NULL DEFAULT 1);
INSERT INTO game_dungeons VALUES('loch_test2','Lochy Mlochy','loch_test2',5,'[]',NULL,'standard',NULL,72,1,1,NULL,NULL,0.149999999999999994,'{"combat":50,"chest":15,"trap":15,"riddle":10,"rest":10}','database',2,'dungeon','{"1":{"tiles":4},"2":{"tiles":6},"3":{"tiles":8},"4":{"tiles":10}}',NULL,4,1);
INSERT INTO game_dungeons VALUES('goblin_warren','Nora Goblinów','goblin_warren',5,'["goblin","goblin_archer"]','goblin_shaman','standard','Ciasne tunele, smród gnijącego mięsa, pobrzękiwanie oręża w ciemności.',48,1,1,NULL,NULL,0.149999999999999994,'{"combat":50,"chest":15,"trap":15,"riddle":10,"rest":10}','database',2,NULL,'{"1":{"tiles":4},"2":{"tiles":6},"3":{"tiles":8},"4":{"tiles":10}}',NULL,NULL,1);
INSERT INTO game_dungeons VALUES('crypt_of_bones','Krypta Kości','crypt_of_bones',6,'["skeleton","zombie"]','skeleton_lord','rich','Wilgotne katakumby, fosforyzujące kości, echo kroków odbija się od kamiennych ścian.',72,2,1,NULL,NULL,0.149999999999999994,'{"combat":50,"chest":15,"trap":15,"riddle":10,"rest":10}','database',2,NULL,'{"1":{"tiles":4},"2":{"tiles":6},"3":{"tiles":8},"4":{"tiles":10}}',NULL,NULL,1);
INSERT INTO game_dungeons VALUES('rat_tunnels','Kanały pod Miastem','rat_tunnels',4,'["giantrat"]',NULL,'poor','Ciemne, zawilgocone kanały. Coś tu mieszka i nie lubi gości.',24,1,1,NULL,NULL,0.149999999999999994,'{"combat":50,"chest":15,"trap":15,"riddle":10,"rest":10}','database',2,NULL,'{"1":{"tiles":4},"2":{"tiles":6},"3":{"tiles":8},"4":{"tiles":10}}',NULL,NULL,1);
COMMIT;
