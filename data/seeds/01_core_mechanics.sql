-- S1: Core mechanics seed (#489)
-- Run after S0 (users + LLM preset) and backend startup (which runs ADMIN_MIGRATIONS).
-- Safe to re-run: INSERT OR IGNORE + UPDATE WHERE key=... pattern.

-- ── Stats ────────────────────────────────────────────────────────────────────
-- 6 base stats seeded by ADMIN_MIGRATIONS; LCK is the missing 7th.
INSERT OR IGNORE INTO game_config_stats (key, label, description, sort_order) VALUES
    ('LCK', 'Szczęście', 'Rzuty losowe, jakość łupów, szanse ucieczki i zdarzenia losowe.', 7);

-- Ensure labels are Polish
UPDATE game_config_stats SET label = 'Siła'         WHERE key = 'STR';
UPDATE game_config_stats SET label = 'Zręczność'    WHERE key = 'DEX';
UPDATE game_config_stats SET label = 'Kondycja'     WHERE key = 'CON';
UPDATE game_config_stats SET label = 'Inteligencja' WHERE key = 'INT';
UPDATE game_config_stats SET label = 'Mądrość'      WHERE key = 'WIS';
UPDATE game_config_stats SET label = 'Charyzma'     WHERE key = 'CHA';

-- ── Archetypes ────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO game_config_archetypes
    (key, label, description, starter_items_json, starter_gold_gp, is_active, hp_base)
VALUES
    ('warrior', 'Wojownik',
     'Frontowy wojownik w ciężkiej zbroi. Wysoki HP, silne ciosy, mistrz broni wręcz.',
     '["shortsword"]', 15, 1, 12),
    ('rogue', 'Łotrzyk',
     'Zwinny cień: snajper z ukrycia lub złodziej w ciemnościach. Skradanie, łuk, inteligentna walka.',
     '["shortbow"]', 10, 1, 8),
    ('scholar', 'Uczony',
     'Tkacz arkanów: kruchy, ale niszczycielski dzięki zaklęciom. Zarządza maną i ryzykiem Omylenia.',
     '["staff"]', 10, 1, 6);

-- Update hp_base for existing archetypes (migration may have used defaults)
UPDATE game_config_archetypes SET hp_base = 12 WHERE key = 'warrior';
UPDATE game_config_archetypes SET hp_base = 8  WHERE key = 'rogue';
UPDATE game_config_archetypes SET hp_base = 6  WHERE key = 'scholar';

-- starting_stats_json: base 10 for all stats, then archetype bonuses applied at character creation
-- warrior: +2 STR, +1 CON  |  rogue: +2 DEX, +1 LCK  |  scholar: +2 INT, +1 WIS
UPDATE game_config_archetypes
    SET starting_stats_json = '{"STR":12,"DEX":10,"CON":11,"INT":10,"WIS":10,"CHA":10,"LCK":10}'
    WHERE key = 'warrior';
UPDATE game_config_archetypes
    SET starting_stats_json = '{"STR":10,"DEX":12,"CON":10,"INT":10,"WIS":10,"CHA":10,"LCK":11}'
    WHERE key = 'rogue';
UPDATE game_config_archetypes
    SET starting_stats_json = '{"STR":10,"DEX":10,"CON":10,"INT":12,"WIS":11,"CHA":10,"LCK":10}'
    WHERE key = 'scholar';

-- ── Conditions ────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('stunned', 'Ogłuszony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"skip_turn","duration_rounds":1}],"clear_on":"duration"}',
     'Cel pomija swoją następną turę. Znika po 1 rundzie.',
     1, 0, 'on_turn_start'),
    ('burning', 'Płonący',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"dot","damage":"1d4","stat":null,"duration_rounds":3}],"clear_on":"duration"}',
     'Cel otrzymuje 1k4 obrażeń od ognia na początku każdej tury przez 3 rundy.',
     1, 0, 'on_duration'),
    ('bleeding', 'Krwawienie',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"dot","damage":"1d3","stat":null,"duration_rounds":3}],"clear_on":"duration"}',
     'Cel otrzymuje 1k3 obrażeń na początku każdej tury przez 3 rundy.',
     1, 0, 'on_duration'),
    ('blinded', 'Oślepiony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"attack_penalty","value":-4,"duration_rounds":2}],"clear_on":"duration"}',
     'Cel ma -4 do ataków przez 2 rundy.',
     1, 0, 'on_duration'),
    ('weakened', 'Osłabiony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":-3,"expires":"duration_rounds:2"}]}',
     'Cel traci 3 do SIŁ przez 2 rundy.',
     1, 0, 'on_duration'),
    ('frightened', 'Przerażony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-2,"expires":"duration_rounds:2"}],"clear_on":"duration"}',
     'Cel traci 2 do CHA przez 2 rundy (ucieka lub jest sparaliżowany strachem).',
     1, 0, 'on_duration'),
    ('slowed', 'Spowolniony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"skip_turn","chance":0.5,"duration_rounds":2}],"clear_on":"duration"}',
     '50% szansa na pominięcie tury przez 2 rundy.',
     1, 0, 'on_duration');

-- ── DC tiers (ensure correct values) ─────────────────────────────────────────
INSERT OR IGNORE INTO game_config_dc (key, label, value, sort_order, description) VALUES
    ('easy',      'Łatwe',       8,  1, 'Proste działania. Większość postaci z moderowaną biegłością sobie poradzi.'),
    ('medium',    'Średnie',     12, 2, 'Wymaga skupienia i pewnej biegłości.'),
    ('hard',      'Trudne',      16, 3, 'Niepewne i wymagające. Ryzyko nawet przy dobrym przygotowaniu.'),
    ('extreme',   'Ekstremalne', 20, 4, 'Granica możliwości. Wyjątkowe przygotowanie lub talent.'),
    ('legendary', 'Legendarne',  24, 5, 'Działanie na poziomie legend.');
