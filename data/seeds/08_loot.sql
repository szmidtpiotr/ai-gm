-- S8: Loot tables seed (#496)
-- Depends on S4 (weapons), S5 (items), S6 (consumables).
-- item_key references game_config_items (includes consumables, item_type='consumable').
-- consumable_key is legacy (game_config_consumables) — NOT used here.
-- weight = per-entry drop % (1–100). Unique constraint: one entry per (table, key).
-- Safe to re-run: INSERT OR IGNORE + UPDATE pattern.

-- ── Base loot tables — INSERT OR IGNORE ──────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_tables (key, label, description, is_active, gold_min, gold_max)
VALUES
    ('loot_poor',     'Biedny łup',       'Podstawowe łupy biednego przeciwnika.',              1, 1, 5),
    ('loot_standard', 'Standardowy łup',  'Typowe łupy przeciętnego przeciwnika.',              1, 3, 12),
    ('loot_rich',     'Bogaty łup',       'Łupy zamożnego lub dobrze wyposażonego wroga.',      1, 8, 25),
    ('loot_treasure', 'Skarb',            'Cenne łupy — boss lub specjalny cel.',               1, 20, 60);

-- ── Update gold on existing enemy tables ─────────────────────────────────────

UPDATE game_config_loot_tables SET gold_min = 0,  gold_max = 5  WHERE key = 'loot_goblin';
UPDATE game_config_loot_tables SET gold_min = 2,  gold_max = 12 WHERE key = 'loot_bandit';
UPDATE game_config_loot_tables SET gold_min = 2,  gold_max = 15 WHERE key = 'loot_orc';
UPDATE game_config_loot_tables SET gold_min = 0,  gold_max = 3  WHERE key = 'loot_skeleton';
UPDATE game_config_loot_tables SET gold_min = 5,  gold_max = 20 WHERE key = 'loot_troll';
UPDATE game_config_loot_tables SET gold_min = 0,  gold_max = 2  WHERE key = 'loot_wolf';
UPDATE game_config_loot_tables SET gold_min = 5,  gold_max = 15 WHERE key = 'loot_guard';
UPDATE game_config_loot_tables SET gold_min = 1,  gold_max = 8  WHERE key = 'loot_enemy';
UPDATE game_config_loot_tables SET gold_min = 0,  gold_max = 5  WHERE key = 'loot_old_man';
UPDATE game_config_loot_tables SET gold_min = 1,  gold_max = 10 WHERE key = 'loot_unknown_attacker';

-- ── Entries: loot_poor ────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_poor', 'healing_herb',  60, 1, 2),
    ('loot_poor', 'bandage',       50, 1, 2),
    ('loot_poor', 'torch',         70, 1, 3),
    ('loot_poor', 'leather_cap',   12, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_poor', 'dagger', 8, 1, 1);

-- ── Entries: loot_standard ────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_standard', 'potion_healing_minor', 35, 1, 1),
    ('loot_standard', 'bandage',              50, 1, 2),
    ('loot_standard', 'rope_hemp',            25, 1, 1),
    ('loot_standard', 'leather_armor',        15, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_standard', 'shortsword', 10, 1, 1);

-- ── Entries: loot_rich ────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_rich', 'potion_healing_standard', 40, 1, 1),
    ('loot_rich', 'chainmail_shirt',          20, 1, 1),
    ('loot_rich', 'antidote',                 30, 1, 2),
    ('loot_rich', 'oil_flask',                40, 1, 2);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_rich', 'longsword', 12, 1, 1);

-- ── Entries: loot_treasure ────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_treasure', 'potion_healing_major',  50, 1, 1),
    ('loot_treasure', 'scale_mail',            25, 1, 1),
    ('loot_treasure', 'scroll_fireball',       20, 1, 1),
    ('loot_treasure', 'potion_mana_standard',  35, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_treasure', 'greatsword', 15, 1, 1);

-- ── Entries: loot_goblin ──────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_goblin', 'healing_herb', 30, 1, 1),
    ('loot_goblin', 'torch',        40, 1, 2);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_goblin', 'dagger', 25, 1, 1);

-- ── Entries: loot_bandit ──────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_bandit', 'potion_healing_minor', 25, 1, 1),
    ('loot_bandit', 'rope_hemp',            35, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_bandit', 'shortsword', 20, 1, 1);

-- ── Entries: loot_orc ────────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_orc', 'potion_healing_minor', 30, 1, 1),
    ('loot_orc', 'hide_armor',           20, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_orc', 'mace', 15, 1, 1);

-- ── Entries: loot_skeleton ────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_skeleton', 'bone_dust',  50, 1, 2),
    ('loot_skeleton', 'holy_water', 10, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_skeleton', 'dagger', 15, 1, 1);

-- ── Entries: loot_troll ──────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_troll', 'potion_healing_standard', 35, 1, 1),
    ('loot_troll', 'leather_armor',           20, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_troll', 'warhammer', 10, 1, 1);

-- ── Entries: loot_wolf ───────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_wolf', 'wolf_pelt',    70, 1, 1),
    ('loot_wolf', 'healing_herb', 30, 1, 1);

-- ── Entries: loot_guard ──────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_guard', 'potion_healing_minor', 30, 1, 1),
    ('loot_guard', 'chainmail_shirt',      15, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_guard', 'sword', 20, 1, 1);

-- ── Entries: loot_enemy ──────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_enemy', 'bandage', 50, 1, 2),
    ('loot_enemy', 'torch',   40, 1, 2);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_enemy', 'dagger', 15, 1, 1);

-- ── Entries: loot_old_man ────────────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_old_man', 'healing_herb',      40, 1, 1),
    ('loot_old_man', 'parchment_sheets',  30, 1, 1),
    ('loot_old_man', 'waterskin',         30, 1, 1);

-- ── Entries: loot_unknown_attacker ───────────────────────────────────────────

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
VALUES
    ('loot_unknown_attacker', 'potion_healing_minor', 20, 1, 1),
    ('loot_unknown_attacker', 'smoke_bomb',           30, 1, 1),
    ('loot_unknown_attacker', 'antidote',             20, 1, 1);

INSERT OR IGNORE INTO game_config_loot_entries (loot_table_key, weapon_key, weight, qty_min, qty_max)
VALUES
    ('loot_unknown_attacker', 'dagger', 20, 1, 1);
