-- S13: Encounter templates + adventure hooks seed (#501)
-- Tables: gameconfig_encounter_templates, adventure_hooks
-- Depends on S9 (enemies), S10 (locations).
-- adventure_hooks table created by migration (migrations_admin.py S13/S14 block).
-- Safe to re-run: INSERT OR IGNORE.

-- ── Encounter templates — fill missing biomes ─────────────────────────────────
-- Existing: tavern, dungeon, city, road/wilderness
-- Missing:  forest, mountain, swamp, plains (higher tiers), cave, ruins

INSERT OR IGNORE INTO gameconfig_encounter_templates
    (key, label, difficulty, min_level, max_level, location_tags, enemies_json, threat_total)
VALUES
    -- Forest encounters
    ('enc_forest_wolves',
     'Wataha wilków',
     'easy', 1, 4, 'forest,wilderness',
     '[{"enemy_key":"wolf","count":3}]',
     36),

    ('enc_forest_spider',
     'Gniazdo pająków',
     'medium', 2, 5, 'forest,cave',
     '[{"enemy_key":"giant_spider","count":2},{"enemy_key":"giant_spider","count":1}]',
     54),

    ('enc_forest_bandits',
     'Leśni zbójcy',
     'medium', 3, 7, 'forest,road',
     '[{"enemy_key":"bandit","count":2},{"enemy_key":"bandit_chief","count":1}]',
     65),

    ('enc_forest_witch',
     'Czarownica z puszczy',
     'hard', 5, 9, 'forest,ruins',
     '[{"enemy_key":"witch","count":1},{"enemy_key":"wolf","count":2}]',
     90),

    -- Mountain encounters
    ('enc_mountain_orcs',
     'Orcki patrol',
     'medium', 3, 6, 'mountain,hills',
     '[{"enemy_key":"orc","count":2},{"enemy_key":"orc_warrior","count":1}]',
     72),

    ('enc_mountain_harpy',
     'Harpie ze skał',
     'medium', 4, 7, 'mountain,ruins',
     '[{"enemy_key":"harpy","count":2}]',
     60),

    ('enc_mountain_troll',
     'Troll ze szczelin',
     'hard', 5, 9, 'mountain,cave',
     '[{"enemy_key":"troll","count":1}]',
     120),

    ('enc_mountain_warlord',
     'Wódz klanowy',
     'deadly', 7, 12, 'mountain',
     '[{"enemy_key":"orc_warchief","count":1},{"enemy_key":"orc_warrior","count":3}]',
     320),

    -- Swamp encounters
    ('enc_swamp_undead',
     'Topielcy z moczarów',
     'easy', 1, 4, 'swamp',
     '[{"enemy_key":"zombie","count":2}]',
     40),

    ('enc_swamp_lizardmen',
     'Jaszczuroludzie',
     'medium', 3, 6, 'swamp,river',
     '[{"enemy_key":"lizardman","count":2},{"enemy_key":"lizardman","count":1}]',
     63),

    ('enc_swamp_wraiths',
     'Zjawa bagien',
     'hard', 5, 9, 'swamp,ruins',
     '[{"enemy_key":"wraith","count":1},{"enemy_key":"ghost","count":2}]',
     110),

    -- Plains/road higher tier
    ('enc_plains_mercenaries',
     'Najemnicy',
     'medium', 4, 8, 'plains,road',
     '[{"enemy_key":"mercenary","count":2},{"enemy_key":"bandit_thug","count":1}]',
     78),

    ('enc_plains_ogre',
     'Ogr na szlaku',
     'hard', 5, 8, 'plains,road',
     '[{"enemy_key":"ogre","count":1}]',
     130),

    -- High-level encounters (10+)
    ('enc_elite_assassin',
     'Gildiowy zabójca',
     'deadly', 8, 15, 'city,dungeon',
     '[{"enemy_key":"assassin","count":1},{"enemy_key":"shadow_stalker","count":1}]',
     280),

    ('enc_elite_dragon',
     'Młody smok',
     'deadly', 10, 20, 'mountain,ruins',
     '[{"enemy_key":"dragon_young","count":1}]',
     500),

    ('enc_elite_vampire',
     'Wampirzy Lord',
     'deadly', 9, 15, 'dungeon,ruins',
     '[{"enemy_key":"vampire_master","count":1},{"enemy_key":"vampire","count":2}]',
     420),

    ('enc_elite_iron_golem',
     'Żelazny Strażnik',
     'deadly', 8, 14, 'dungeon,castle',
     '[{"enemy_key":"iron_golem","count":1}]',
     380),

    ('enc_elite_demon_lord',
     'Pomniejszy Demon',
     'deadly', 12, 20, 'dungeon,ruins',
     '[{"enemy_key":"demon_lord","count":1},{"enemy_key":"imp","count":3}]',
     600);

-- ── Adventure hooks — generic encounter pool ──────────────────────────────────
-- Format mirrors encounter_seed_service.py GENERIC_ENCOUNTERS.
-- adventure_idea_id=NULL: standalone hooks not tied to a specific story.
-- draft_data.__generic_encounter__=true: marker for encounter injection engine.

INSERT OR IGNORE INTO adventure_hooks
    (adventure_idea_id, hook_type, title, description, significance, draft_data, status)
VALUES
    -- Level 1-5 hooks
    (NULL, 'encounter', 'Zasadzka na trakcie',
     'Bandyci blokują drogę, żądając opłaty przejazdu.',
     'minor',
     '{"__generic_encounter__":true,"key":"hook_road_toll","biomes":["road","plains"],"trigger_types":["hex_enter","n_turns"],"level_min":1,"level_max":5,"trigger_probability":0.20,"enemies":[{"enemy_key":"bandit","name":"bandyta","count":2}]}',
     'approved'),

    (NULL, 'encounter', 'Ślad krwi',
     'Na ziemi widać ślad krwi prowadzący w głąb lasu. Niedługo przybędzie sprawca.',
     'minor',
     '{"__generic_encounter__":true,"key":"hook_blood_trail","biomes":["forest","wilderness"],"trigger_types":["n_turns"],"level_min":1,"level_max":4,"trigger_probability":0.18,"enemies":[{"enemy_key":"wolf","name":"wilk","count":2}]}',
     'approved'),

    (NULL, 'encounter', 'Stary grób',
     'Przy drodze stoi rozwalony nagrobek. W nocy coś wychodzi z ziemi.',
     'minor',
     '{"__generic_encounter__":true,"key":"hook_old_grave","biomes":["road","ruins","plains"],"trigger_types":["n_turns"],"level_min":2,"level_max":5,"trigger_probability":0.15,"enemies":[{"enemy_key":"skeleton","name":"szkielet","count":2},{"enemy_key":"zombie","name":"zombie","count":1}]}',
     'approved'),

    -- Level 5-10 hooks
    (NULL, 'encounter', 'Kultowy rytuał',
     'Odgłosy śpiewu dobiegają z ruin. Cultists przeprowadzają mroczny rytuał.',
     'moderate',
     '{"__generic_encounter__":true,"key":"hook_cult_ritual","biomes":["ruins","dungeon","forest"],"trigger_types":["hex_enter","n_turns"],"level_min":5,"level_max":10,"trigger_probability":0.20,"enemies":[{"enemy_key":"cultist","name":"kultista","count":3},{"enemy_key":"dark_priest","name":"mroczny kapłan","count":1}]}',
     'approved'),

    (NULL, 'encounter', 'Leśna wiedźma',
     'Stara wiedźma wysyła pomiot do ochrony swojego terytorium.',
     'moderate',
     '{"__generic_encounter__":true,"key":"hook_forest_witch","biomes":["forest","swamp"],"trigger_types":["hex_enter"],"level_min":4,"level_max":8,"trigger_probability":0.15,"enemies":[{"enemy_key":"witch","name":"wiedźma","count":1},{"enemy_key":"wolf","name":"wilk","count":2}]}',
     'approved'),

    (NULL, 'encounter', 'Orcki patrol',
     'Uzbrojonemu oddziałowi orków nie podoba się obecność bohaterów.',
     'moderate',
     '{"__generic_encounter__":true,"key":"hook_orc_patrol","biomes":["mountain","hills","plains"],"trigger_types":["hex_enter","n_turns"],"level_min":4,"level_max":9,"trigger_probability":0.22,"enemies":[{"enemy_key":"orc","name":"ork","count":2},{"enemy_key":"orc_warrior","name":"wojownik orków","count":2}]}',
     'approved'),

    -- Level 10+ hooks
    (NULL, 'encounter', 'Starożytna zjawa',
     'Duch pradawnego rycerza pilnuje zapomnianego grobowca.',
     'major',
     '{"__generic_encounter__":true,"key":"hook_ancient_wraith","biomes":["ruins","dungeon","cave"],"trigger_types":["hex_enter"],"level_min":8,"level_max":15,"trigger_probability":0.18,"enemies":[{"enemy_key":"wraith","name":"zjawa","count":1},{"enemy_key":"shadow_stalker","name":"cień","count":2}]}',
     'approved'),

    (NULL, 'encounter', 'Smocze terytorium',
     'Wlatujący w teren smoka bohaterowie muszą albo walczyć, albo uciekać.',
     'major',
     '{"__generic_encounter__":true,"key":"hook_dragon_territory","biomes":["mountain","ruins"],"trigger_types":["hex_enter"],"level_min":10,"level_max":20,"trigger_probability":0.12,"enemies":[{"enemy_key":"dragon_young","name":"młody smok","count":1}]}',
     'approved');
