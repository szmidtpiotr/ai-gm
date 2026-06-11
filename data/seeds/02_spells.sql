-- S2: Spells seed (#490)
-- Table: game_config_spells
-- 9 scholar spells (tiers 1–5) + magic_light utility cantrip.
-- Depends on S1 (scholar archetype). Idempotent: INSERT OR IGNORE.
-- Schema note: rank2_json / rank3_json hold per-rank overrides (mana_cost, dice, bonuses).

INSERT OR IGNORE INTO game_config_spells
    (key, label, tier, mana_cost, spell_type, damage_die, heal_die, effect_stat,
     effect_type, effect_duration, target_zone, aoe, description, rank2_json, rank3_json, is_active)
VALUES
    ('magic_bolt', 'Błysk Magiczny', 1, 2, 'attack', '2d6', NULL, NULL, NULL, 1, 'any', 0,
     'Strumień magicznej energii uderzający wroga.',
     '{"mana_cost":2,"damage_die":"2d8"}', '{"mana_cost":1,"damage_die":"3d6"}', 1),

    ('mend_wounds', 'Rana Uleczona', 1, 2, 'heal', NULL, '2d6', NULL, NULL, 1, 'self', 0,
     'Magiczne leczenie ran bohatera.',
     '{"mana_cost":2,"heal_die":"2d8"}', '{"mana_cost":1,"heal_die":"3d6"}', 1),

    ('arcane_shield', 'Tarcza Arkan', 1, 2, 'defense', NULL, NULL, NULL, NULL, 1, 'self', 0,
     'Magiczna tarcza zwiększająca pancerz.',
     '{"mana_cost":2,"ac_bonus":4,"duration":1}', '{"mana_cost":1,"ac_bonus":4,"duration":2}', 1),

    ('sleep', 'Sen', 2, 3, 'effect', NULL, NULL, 'WIS', 'sleeping', 1, 'any', 0,
     'Wpędza wroga w magiczny sen.',
     '{"mana_cost":3,"effect_duration":2}', '{"mana_cost":2,"effect_duration":3}', 1),

    ('burning_arc', 'Pałająca Ścieżka', 2, 4, 'attack_aoe', '1d6', NULL, NULL, NULL, 1, 'any', 1,
     'Łuk ognia trafia wszystkich wrogów.',
     '{"mana_cost":4,"damage_die":"1d8"}', '{"mana_cost":3,"damage_die":"2d6"}', 1),

    ('drain_life', 'Wysysanie Życia', 3, 3, 'attack', '2d8', NULL, NULL, NULL, 1, 'engaged', 0,
     'Wysysa życie wroga, lecząc rzucającego.',
     '{"mana_cost":3,"damage_die":"2d10"}', '{"mana_cost":2,"damage_die":"3d6","heal_pct":100}', 1),

    ('chain_lightning', 'Łańcuch Błyskawic', 4, 5, 'attack_aoe', '2d6', NULL, NULL, NULL, 1, 'any', 0,
     'Błyskawica skacząca przez do 3 wrogów.',
     NULL, NULL, 1),

    ('stone_skin', 'Kamienna Skóra', 4, 4, 'defense', NULL, NULL, NULL, NULL, 3, 'self', 0,
     'Skóra twardnieje jak kamień.',
     '{"mana_cost":4,"ac_bonus":5,"duration":4}', '{"mana_cost":2,"ac_bonus":6,"duration":4}', 1),

    ('fireball', 'Kula Ognia', 5, 6, 'attack_aoe', '3d6', NULL, NULL, NULL, 1, 'any', 1,
     'Ognista eksplozja niszczy wszystkich wrogów.',
     NULL, NULL, 1),

    ('magic_light', 'Magiczne Światło', 1, 0, 'narrative', NULL, NULL, NULL, NULL, 0, 'self', 0,
     'Uczony przywołuje unoszącą się kulę świetlną oświetlającą obszar w promieniu kilku metrów. Działa jak pochodnia — rozjaśnia ciemność, lecz nie ma wartości ofensywnej.',
     NULL, NULL, 1);
