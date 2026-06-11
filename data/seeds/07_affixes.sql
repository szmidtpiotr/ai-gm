-- S7: Affixes seed (#495)
-- Depends on S1 (core mechanics — game_config_affixes table must exist).
-- Safe to re-run: INSERT OR IGNORE + UPDATE WHERE key=... pattern.
-- effect_json uses F1 schema: {"schema_version":1,"effect_category":"gear_bonus","effects":[...]}
--
-- T1: basic enchantments (damage, defense, stat tune, condition)
-- T2: mid-tier power (lifesteal, empowered stats, guardianship)
-- T3: legendary dual-effects

-- ── T1 affixes ────────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json, is_active)
VALUES
    ('sharp',
     'Ostry', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":2}]}',
     1),

    ('light_edge',
     'Lekkie Ostrze', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":1}]}',
     1),

    ('warding',
     'Ochronny', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":1}]}',
     1),

    ('sturdy_grip',
     'Pewny Chwyt', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"STR","value":1}]}',
     1),

    ('swift_hand',
     'Szybka Ręka', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"DEX","value":1}]}',
     1),

    ('numbing',
     'Odrętwiający', 1, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"apply_condition","condition_key":"slowed","duration_rounds":2}]}',
     1);

-- ── T2 affixes ────────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json, is_active)
VALUES
    ('keen',
     'Wyostrzony', 2, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":4}]}',
     1),

    ('lifesteal',
     'Krwiopijca', 2, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"heal_on_hit","value":2}]}',
     1),

    ('empowered',
     'Wzmocniony', 2, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"STR","value":2}]}',
     1),

    ('guardian',
     'Strażniczy', 2, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":2}]}',
     1);

-- ── T3 affixes ────────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json, is_active)
VALUES
    ('brutal',
     'Brutalny', 3, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":6}]}',
     1),

    ('vampiric',
     'Wampiryczny', 3, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":4},{"type":"heal_on_hit","value":3}]}',
     1),

    ('conquering',
     'Zdobywczy', 3, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":4},{"type":"static_stat_modifier","stat":"STR","value":3}]}',
     1),

    ('runic_edge',
     'Runiczny', 3, 'weapon',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":3},{"type":"apply_condition","condition_key":"weakened","duration_rounds":3}]}',
     1);

-- ── Idempotent updates (sync name/tier/effect if rows already exist) ──────────

UPDATE game_config_affixes SET
    name = 'Ostry', tier = 1,
    effect_json = '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":2}]}'
WHERE key = 'sharp';

UPDATE game_config_affixes SET
    name = 'Wyostrzony', tier = 2,
    effect_json = '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":4}]}'
WHERE key = 'keen';

UPDATE game_config_affixes SET
    name = 'Brutalny', tier = 3,
    effect_json = '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":6}]}'
WHERE key = 'brutal';
