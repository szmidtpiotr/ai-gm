-- S4: Weapons seed (#492)
-- Depends on S1 (archetypes for allowed_classes).
-- Depends on backend startup running RAW_MIGRATIONS (adds durability_base column).
-- Safe to re-run: INSERT OR IGNORE + UPDATE WHERE key=... pattern.
-- allowed_classes uses ALLOWED_CLASSES values: warrior / ranger / scholar
-- (ranger = the rogue archetype key in admin_config.py; archetype table uses 'rogue')

-- ── Helpers ──────────────────────────────────────────────────────────────────

-- Ensure effect_json is populated on shields and any future update by clearing
-- existing NULL-or-wrong values before UPSERTing below.
-- (UPDATE WHERE key=... at bottom handles this idempotently.)

-- ── New weapons — INSERT OR IGNORE ────────────────────────────────────────────

INSERT OR IGNORE INTO game_config_weapons
    (key, label, damage_die, weapon_type, linked_stat, allowed_classes,
     two_handed, finesse, range_m, targeting, weapon_slot,
     rarity, value_gp, durability_base, weight_kg, description,
     effect_json, is_active, approved, review_status)
VALUES
    -- ── Tier 1 melee ─────────────────────────────────────────────────────────
    ('dagger',
     'Sztylet', 'd4', 'melee', 'DEX', '["warrior","ranger"]',
     0, 1, NULL, 'single', 'main_hand',
     1, 10, 80, 0.5,
     'Lekki sztylet — zwinny, cichy. Oburęczna finezja.',
     NULL, 1, 1, 'permanent'),

    ('mace',
     'Buława', 'd6', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'main_hand',
     1, 18, 100, 2.5,
     'Żelazna buława — prosty, niezawodny oręż.',
     NULL, 1, 1, 'permanent'),

    ('spear',
     'Włócznia', 'd6', 'melee', 'STR', '["warrior"]',
     1, 0, NULL, 'single', 'two_handed',
     1, 20, 100, 2.0,
     'Długa włócznia — zasięg i siła w jednym.',
     NULL, 1, 1, 'permanent'),

    -- ── Tier 2 melee ─────────────────────────────────────────────────────────
    ('longsword',
     'Długi Miecz', 'd8', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'either',
     2, 40, 150, 1.5,
     'Wszechstronny długi miecz — można go trzymać jedną lub obiema rękami.',
     NULL, 1, 1, 'permanent'),

    ('rapier',
     'Rapier', 'd6', 'melee', 'DEX', '["warrior","ranger"]',
     0, 1, NULL, 'single', 'main_hand',
     2, 35, 120, 1.0,
     'Smukła szpada finezji — precyzja ponad siłę.',
     NULL, 1, 1, 'permanent'),

    ('warhammer',
     'Bojowy Młot', 'd8', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'main_hand',
     2, 35, 150, 3.0,
     'Ciężki młot bojowy — kruszy zbroje.',
     NULL, 1, 1, 'permanent'),

    ('battleaxe',
     'Topór Bojowy', 'd10', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'main_hand',
     2, 40, 150, 2.5,
     'Topór o szerokim ostrzu — maksymalne obrażenia.',
     NULL, 1, 1, 'permanent'),

    ('greatsword',
     'Wielki Miecz', '2d6', 'melee', 'STR', '["warrior"]',
     1, 0, NULL, 'single', 'two_handed',
     2, 60, 150, 3.0,
     'Potężny dwuręcznik — władają nim tylko najsilniejsi.',
     NULL, 1, 1, 'permanent'),

    ('greataxe',
     'Wielki Topór', '2d6', 'melee', 'STR', '["warrior"]',
     1, 0, NULL, 'single', 'two_handed',
     2, 55, 150, 3.5,
     'Ogromny topór wojenny — brutalna siła.',
     NULL, 1, 1, 'permanent'),

    -- ── Tier 2 ranged ────────────────────────────────────────────────────────
    ('longbow',
     'Długi Łuk', 'd8', 'ranged', 'DEX', '["ranger"]',
     1, 0, 60, 'single', 'two_handed',
     2, 45, 100, 1.0,
     'Długi łuk łowcy — duży zasięg, celność na dystansie.',
     NULL, 1, 1, 'permanent'),

    ('crossbow',
     'Kusza', 'd8', 'ranged', 'DEX', '["warrior","ranger"]',
     1, 0, 40, 'single', 'two_handed',
     2, 50, 150, 3.0,
     'Kusza mechaniczna — siłę wymagającą szkolenia zastępuje mechanizm.',
     NULL, 1, 1, 'permanent'),

    -- ── Tier 2 scholar ───────────────────────────────────────────────────────
    ('wand',
     'Różdżka', 'd4', 'spell', 'INT', '["scholar"]',
     0, 0, NULL, 'single', 'main_hand',
     2, 30, 80, 0.3,
     'Lekka różdżka — kanalizuje moc zaklęć, zwalnia jedną rękę.',
     NULL, 1, 1, 'permanent'),

    -- ── Tier 2 shield — ac_bonus ─────────────────────────────────────────────
    ('tower_shield',
     'Tarcza Wieżowa', 'd4', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'off_hand_only',
     2, 45, 150, 7.0,
     'Wielka tarcza wieżowa — niemal pełna osłona ciała.',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":2}]}',
     1, 1, 'permanent'),

    -- ── Tier 3 special — effect_json ─────────────────────────────────────────
    ('silver_sword',
     'Srebrny Miecz', 'd8', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'main_hand',
     3, 120, 200, 1.5,
     'Miecz ze srebra — boleśnie skuteczny przeciw nieumarłym i duchom.',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":1}]}',
     1, 1, 'permanent'),

    ('cursed_grimoire',
     'Przeklęte Grimuarium', 'd6', 'spell', 'INT', '["scholar"]',
     0, 0, NULL, 'single', 'off_hand_only',
     3, 150, 60, 0.8,
     'Czarny tom przeklętej wiedzy — trafienia zatruwają wrogów.',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"apply_condition","condition_key":"poisoned","duration_rounds":3}]}',
     1, 1, 'permanent'),

    ('healing_staff',
     'Laska Uzdrawiającego', 'd4', 'spell', 'INT', '["scholar"]',
     1, 0, NULL, 'single', 'two_handed',
     3, 200, 150, 1.5,
     'Laska naznaczona arkaną leczenia — każde trafienie przywraca moc życiową.',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"heal_on_hit","value":3}]}',
     1, 1, 'permanent'),

    ('burning_blade',
     'Płonące Ostrze', 'd8', 'melee', 'STR', '["warrior"]',
     0, 0, NULL, 'single', 'main_hand',
     3, 180, 150, 1.5,
     'Zaczarowany miecz owinięty płomieniami — trafienia podpalają wrogów.',
     '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"apply_condition","condition_key":"burning","duration_rounds":2}]}',
     1, 1, 'permanent');

-- ── Patch existing weapons — durability_base + effect_json ───────────────────

-- unarmed: no durability (bare hands)
UPDATE game_config_weapons
SET durability_base = NULL,
    rarity          = 1,
    value_gp        = 0,
    weapon_slot     = 'either',
    description     = CASE WHEN description = '' THEN 'Pięści — ostatnia linia obrony.' ELSE description END
WHERE key = 'unarmed';

-- shortsword: standard light blade
UPDATE game_config_weapons
SET durability_base = 100,
    rarity          = 1,
    value_gp        = 15,
    weapon_slot     = 'main_hand',
    description     = CASE WHEN description = '' THEN 'Lekki krótki miecz — szybki i niezawodny.' ELSE description END
WHERE key = 'shortsword';

-- sword: reliable mid-tier weapon
UPDATE game_config_weapons
SET durability_base = 100,
    rarity          = 1,
    value_gp        = 25,
    weapon_slot     = 'main_hand',
    description     = CASE WHEN description = '' THEN 'Standardowy miecz bojowy — balans siły i szybkości.' ELSE description END
WHERE key = 'sword';

-- shield: basic metal shield with ac bonus
UPDATE game_config_weapons
SET durability_base = 100,
    rarity          = 1,
    value_gp        = 12,
    weapon_slot     = 'off_hand_only',
    effect_json     = '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"ac_bonus","value":1}]}',
    description     = CASE WHEN description = '' THEN 'Metalowa tarcza — premia do obrony.' ELSE description END
WHERE key = 'shield';

-- wooden_shield: cheap but fragile
UPDATE game_config_weapons
SET durability_base = 60,
    rarity          = 1,
    value_gp        = 8,
    weapon_slot     = 'off_hand_only',
    description     = CASE WHEN description = '' THEN 'Drewniana tarcza — tania ochrona, łatwo się kruszy.' ELSE description END
WHERE key = 'wooden_shield';

-- shortbow: fragile ranged weapon
UPDATE game_config_weapons
SET durability_base = 80,
    rarity          = 1,
    value_gp        = 25,
    weapon_slot     = 'two_handed',
    range_m         = 30,
    description     = CASE WHEN description = '' THEN 'Krótki łuk — szybki w boju, dobre rzemiosło.' ELSE description END
WHERE key = 'shortbow';

-- staff: scholar arcane focus
UPDATE game_config_weapons
SET durability_base = 80,
    rarity          = 1,
    value_gp        = 6,
    weapon_slot     = 'two_handed',
    description     = CASE WHEN description = '' THEN 'Laska Uczonego — kanalizuje zaklęcia, chroni w walce.' ELSE description END
WHERE key = 'staff';

-- quarterstaff: versatile melee reach weapon
UPDATE game_config_weapons
SET durability_base = 100,
    rarity          = 1,
    value_gp        = 7,
    weapon_slot     = 'two_handed',
    description     = CASE WHEN description = '' THEN 'Solidny kij bojowy — zasięg bez ostrza.' ELSE description END
WHERE key = 'quarterstaff';
