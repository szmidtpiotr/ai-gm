-- S12: Dungeon seeds (#500)
-- Tables: game_dungeons
-- Depends on S8 (loot_poor/standard/rich), S9 (enemies), S10 (locations).
-- 5 canonical dungeons with correct enemy keys from S9.
-- Safe to re-run: INSERT OR REPLACE.

INSERT OR REPLACE INTO game_dungeons
    (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier,
     atmosphere, cooldown_hours, min_level, is_active, dungeon_difficulty,
     room_loot_chance, riddle_source, riddle_max_hints)
VALUES
    -- Tier 1 (level 1-2): goblin warrens inside mine tunnels
    ('goblin_warren',
     'Nora Goblinów',
     'kopalnia_wejscie_glowne',
     5,
     '["goblin","goblin_archer","kobold"]',
     'orc_shaman',
     'standard',
     'Ciasne, cuchnące tunele wydrążone przez pokolenia goblinów. Pobrzękiwanie oręża i skrzeczące głosy dobiegają z ciemności. Ściany znaczone żółtymi pazurami.',
     48, 1, 1, 1,
     0.15, 'database', 2),

    -- Tier 1 (level 1): city sewers — fast cooldown, poor loot
    ('rat_tunnels',
     'Kanały pod Miastem',
     'czarnogrod_nabrzeze',
     4,
     '["giant_rat","slime"]',
     NULL,
     'poor',
     'Zawilgocone kanały ściekowe biegnące pod miastem. Fetor, ciemność i plusk wody. Coś tu zamieszkało i nie lubi gości.',
     24, 1, 1, 1,
     0.10, 'database', 1),

    -- Tier 2 (level 2-3): ancient crypt — undead, rich loot
    ('crypt_of_bones',
     'Krypta Kości',
     'krypta_grobowiec_hrabiego',
     6,
     '["skeleton","zombie","ghoul"]',
     'lich',
     'rich',
     'Wilgotne katakumby wykute w litej skale. Fosforyzujące kości, echo kroków odbija się od kamiennych ścian, lodowate zimno przeszywające do szpiku.',
     72, 2, 1, 2,
     0.15, 'database', 2),

    -- Tier 2 (level 3): swamp ruins — wraiths and drowned dead
    ('swamp_ruins',
     'Zatopione Ruiny',
     'trzesawiska_mgiel',
     5,
     '["zombie","ghost","wraith"]',
     'undead_champion',
     'rich',
     'Półzatopione ruiny pradawnej świątyni ukryte w bagnie. Mgła unosi się nad ciemną wodą. Widma snują się między porośniętymi mchem kolumnami.',
     72, 3, 1, 2,
     0.15, 'database', 2),

    -- Tier 3 (level 4+): black fortress dungeons — orcs + dark magic
    ('dark_fortress',
     'Lochy Czarnej Twierdzy',
     'twierdza_lochy',
     7,
     '["orc_warrior","orc","dark_mage","skeleton"]',
     'orc_warchief',
     'rich',
     'Mroczne lochy pod starą twierdzą zdobytą przez orcich najeźdźców. Kamienne ściany pokryte runami, kratowane cele, echo kroków straży w korytarzach.',
     96, 4, 1, 3,
     0.20, 'database', 2);
