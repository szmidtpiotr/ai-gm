-- Loot table balance pass: boost item/weapon drop weights + fill empty tables
-- Idempotent: UPDATEs are safe to re-run; INSERTs use OR IGNORE on unique rows.

-- loot_poor (weak enemies: goblin variants, cultists, slimes, zombies, imps, kobolds)
UPDATE game_config_loot_entries SET weight=75 WHERE loot_table_key='loot_poor' AND item_key='healing_herb';
UPDATE game_config_loot_entries SET weight=65 WHERE loot_table_key='loot_poor' AND item_key='bandage';
UPDATE game_config_loot_entries SET weight=78 WHERE loot_table_key='loot_poor' AND item_key='torch';
UPDATE game_config_loot_entries SET weight=22 WHERE loot_table_key='loot_poor' AND item_key='leather_cap';
UPDATE game_config_loot_entries SET weight=18 WHERE loot_table_key='loot_poor' AND weapon_key='dagger';

-- loot_standard (most standard enemies: assassins, brigands, dark elves, etc.)
UPDATE game_config_loot_entries SET weight=52 WHERE loot_table_key='loot_standard' AND item_key='potion_healing_minor';
UPDATE game_config_loot_entries SET weight=65 WHERE loot_table_key='loot_standard' AND item_key='bandage';
UPDATE game_config_loot_entries SET weight=38 WHERE loot_table_key='loot_standard' AND item_key='rope_hemp';
UPDATE game_config_loot_entries SET weight=25 WHERE loot_table_key='loot_standard' AND item_key='leather_armor';
UPDATE game_config_loot_entries SET weight=22 WHERE loot_table_key='loot_standard' AND weapon_key='shortsword';

-- loot_rich (elite enemies: bandit chief, ogre, wyvern, etc.)
UPDATE game_config_loot_entries SET weight=55 WHERE loot_table_key='loot_rich' AND item_key='potion_healing_standard';
UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_rich' AND item_key='chainmail_shirt';
UPDATE game_config_loot_entries SET weight=45 WHERE loot_table_key='loot_rich' AND item_key='antidote';
UPDATE game_config_loot_entries SET weight=52 WHERE loot_table_key='loot_rich' AND item_key='oil_flask';
UPDATE game_config_loot_entries SET weight=25 WHERE loot_table_key='loot_rich' AND weapon_key='longsword';

-- loot_treasure (boss enemies: lich, dragon, iron golem, etc.)
UPDATE game_config_loot_entries SET weight=70 WHERE loot_table_key='loot_treasure' AND item_key='potion_healing_major';
UPDATE game_config_loot_entries SET weight=40 WHERE loot_table_key='loot_treasure' AND item_key='scale_mail';
UPDATE game_config_loot_entries SET weight=35 WHERE loot_table_key='loot_treasure' AND item_key='scroll_fireball';
UPDATE game_config_loot_entries SET weight=55 WHERE loot_table_key='loot_treasure' AND item_key='potion_mana_standard';
UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_treasure' AND weapon_key='greatsword';

-- Individual enemy tables
UPDATE game_config_loot_entries SET weight=45 WHERE loot_table_key='loot_bandit' AND item_key='potion_healing_minor';
UPDATE game_config_loot_entries SET weight=50 WHERE loot_table_key='loot_bandit' AND item_key='rope_hemp';
UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_bandit' AND weapon_key='shortsword';

UPDATE game_config_loot_entries SET weight=55 WHERE loot_table_key='loot_goblin' AND item_key='healing_herb';
UPDATE game_config_loot_entries SET weight=60 WHERE loot_table_key='loot_goblin' AND item_key='torch';
UPDATE game_config_loot_entries SET weight=35 WHERE loot_table_key='loot_goblin' AND weapon_key='dagger';

UPDATE game_config_loot_entries SET weight=50 WHERE loot_table_key='loot_orc' AND item_key='potion_healing_minor';
UPDATE game_config_loot_entries SET weight=35 WHERE loot_table_key='loot_orc' AND item_key='hide_armor';
UPDATE game_config_loot_entries SET weight=25 WHERE loot_table_key='loot_orc' AND weapon_key='mace';

UPDATE game_config_loot_entries SET weight=45 WHERE loot_table_key='loot_guard' AND item_key='potion_healing_minor';
UPDATE game_config_loot_entries SET weight=25 WHERE loot_table_key='loot_guard' AND item_key='chainmail_shirt';
UPDATE game_config_loot_entries SET weight=28 WHERE loot_table_key='loot_guard' AND weapon_key='sword';

UPDATE game_config_loot_entries SET weight=55 WHERE loot_table_key='loot_enemy' AND item_key='bandage';
UPDATE game_config_loot_entries SET weight=45 WHERE loot_table_key='loot_enemy' AND item_key='torch';
UPDATE game_config_loot_entries SET weight=18 WHERE loot_table_key='loot_enemy' AND weapon_key='dagger';

UPDATE game_config_loot_entries SET weight=55 WHERE loot_table_key='loot_skeleton' AND item_key='bone_dust';
UPDATE game_config_loot_entries SET weight=18 WHERE loot_table_key='loot_skeleton' AND item_key='holy_water';
UPDATE game_config_loot_entries SET weight=20 WHERE loot_table_key='loot_skeleton' AND weapon_key='dagger';

UPDATE game_config_loot_entries SET weight=40 WHERE loot_table_key='loot_troll' AND item_key='potion_healing_standard';
UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_troll' AND item_key='leather_armor';
UPDATE game_config_loot_entries SET weight=20 WHERE loot_table_key='loot_troll' AND weapon_key='warhammer';

UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_unknown_attacker' AND item_key='potion_healing_minor';
UPDATE game_config_loot_entries SET weight=40 WHERE loot_table_key='loot_unknown_attacker' AND item_key='smoke_bomb';
UPDATE game_config_loot_entries SET weight=30 WHERE loot_table_key='loot_unknown_attacker' AND item_key='antidote';
UPDATE game_config_loot_entries SET weight=25 WHERE loot_table_key='loot_unknown_attacker' AND weapon_key='dagger';

UPDATE game_config_loot_entries SET weight=75 WHERE loot_table_key='loot_wolf' AND item_key='wolf_pelt';
UPDATE game_config_loot_entries SET weight=40 WHERE loot_table_key='loot_wolf' AND item_key='healing_herb';

-- Fill empty loot_goblin_u31 table (goblin_u31 enemy was dropping only gold)
UPDATE game_config_loot_tables SET gold_min=1, gold_max=6 WHERE key='loot_goblin_u31' AND gold_max=0;
INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weapon_key, consumable_key, weight, qty_min, qty_max)
    SELECT 'loot_goblin_u31', 'healing_herb', NULL, NULL, 55, 1, 2
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND item_key='healing_herb');
INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weapon_key, consumable_key, weight, qty_min, qty_max)
    SELECT 'loot_goblin_u31', 'torch', NULL, NULL, 60, 1, 2
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND item_key='torch');
INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weapon_key, consumable_key, weight, qty_min, qty_max)
    SELECT 'loot_goblin_u31', NULL, 'dagger', NULL, 30, 1, 1
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND weapon_key='dagger');

-- Fix krypta_opiekun (boss) — had no loot table assigned
UPDATE game_config_enemies SET loot_table_key='loot_treasure', drop_chance=1.0
    WHERE key='krypta_opiekun' AND (loot_table_key IS NULL OR loot_table_key='');
