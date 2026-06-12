-- S6: Consumables seed (#494) — CORRECTED
-- Consumables live in game_config_items with item_type='consumable' (migration 8H).
-- game_config_consumables is the LEGACY table; admin panel reads game_config_items.
-- Effects stored in effect_json (schema_version=1, effect_category=consumable_immediate).
-- Supported effect types: heal_hp | restore_mana | remove_condition | apply_condition | narrative_only
-- Safe to re-run: INSERT OR IGNORE + UPDATE for pre-existing stubs.

-- ── Patch pre-existing stubs in game_config_items ───────────────────────────

UPDATE game_config_items
SET description = 'Mała szklana ampułka czerwonej cieczy o cierpkim posmaku ziół. Wypita zalewa rany ciepłem.',
    effect_json = '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"2d4+2"}]}',
    value_gp    = 25,
    weight_kg   = 0.2,
    rarity      = 1,
    approved    = 1
WHERE key = 'health_potion_small' AND item_type = 'consumable';

UPDATE game_config_items
SET description = 'Lazurowa ciecz w okrągłej ampułce. Pachnie miętą i wapnem — przywraca część zużytej mocy magicznej.',
    effect_json = '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"restore_mana","value":"1d6+2"}]}',
    value_gp    = 30,
    weight_kg   = 0.2,
    rarity      = 1,
    approved    = 1
WHERE key = 'mana_potion' AND item_type = 'consumable';

-- ── New consumables — INSERT OR IGNORE into game_config_items ────────────────

INSERT OR IGNORE INTO game_config_items
    (key, label, item_type, description, effect_json,
     value_gp, weight_kg, charges, rarity,
     ac_bonus, armor_coverage, allowed_classes,
     is_active, approved, ai_generated, review_status)
VALUES
    -- ── HEALING — 3 tiers (mandatory) ────────────────────────────────────────
    ('potion_healing_minor',
     'Mała mikstura leczenia', 'consumable',
     'Mała szklana ampułka czerwonej cieczy o cierpkim posmaku ziół. Wypita zalewa rany ciepłem.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"2d4+2"}]}',
     25, 0.2, 1, 1, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('potion_healing_standard',
     'Mikstura leczenia', 'consumable',
     'Pełna fiolka rubinowej cieczy. Smakuje jak żelazo i kwiat lipy — goi nawet poważne rany.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"4d4+4"}]}',
     75, 0.3, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('potion_healing_major',
     'Wielka mikstura leczenia', 'consumable',
     'Duży flakon z mikstury alchemika. Przywróci do walki nawet człowieka konającego w kałuży krwi.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"8d4+8"}]}',
     250, 0.5, 1, 3, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    -- ── MANA — 3 tiers (mandatory) ───────────────────────────────────────────
    ('potion_mana_minor',
     'Mała mikstura many', 'consumable',
     'Lazurowa ciecz w okrągłej ampułce. Pachnie miętą i wapnem — przywraca część zużytej mocy magicznej.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"restore_mana","value":"1d6+2"}]}',
     30, 0.2, 1, 1, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent'),

    ('potion_mana_standard',
     'Mikstura many', 'consumable',
     'Granatowy eliksir o przyjemnym ziołowym posmaku. Odnawia więcej many niż mała mikstura.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"restore_mana","value":"2d6+4"}]}',
     90, 0.3, 1, 2, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent'),

    ('potion_mana_major',
     'Wielka mikstura many', 'consumable',
     'Wielki flakon ciemnogranatowej mikstury z migocącymi iskierkami. Niemal w pełni regeneruje arkany kastującego.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"restore_mana","value":"4d6+8"}]}',
     300, 0.5, 1, 3, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent'),

    -- ── ANTIDOTE (mandatory) ─────────────────────────────────────────────────
    ('antidote',
     'Antydot', 'consumable',
     'Mętna ciecz o gorzkim posmaku w małej fiolce. Neutralizuje truciznę — jeśli wypić w porę.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"remove_condition","condition_key":"poisoned"}]}',
     50, 0.1, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    -- ── STAMINA POTION (mandatory) ────────────────────────────────────────────
    ('potion_stamina',
     'Mikstura wytrzymałości', 'consumable',
     'Zielona ciecz pachnąca ziołami i chmielem. Wypita odpędza zmęczenie i pozwala walczyć dalej.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     70, 0.2, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    -- ── OTHER BUFFS / POTIONS ────────────────────────────────────────────────
    ('potion_strength',
     'Mikstura siły', 'consumable',
     'Mętna brunatna mikstura o zapachu byczej krwi. Wypita daje na chwilę siłę osiłka.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     60, 0.2, 1, 2, 0, 'torso', '["warrior"]', 1, 1, 0, 'permanent'),

    ('potion_haste',
     'Mikstura pośpiechu', 'consumable',
     'Bladozielona ciecz pulsująca delikatnym światłem. Wyostrza refleks i przyspiesza krok.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     80, 0.2, 1, 2, 0, 'torso', '["ranger"]', 1, 1, 0, 'permanent'),

    ('potion_resistance',
     'Mikstura odporności', 'consumable',
     'Mętna biaława mikstura. Po wypiciu skóra twardnieje, a ciosy ślizgają się po niej jakby były tępe.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     100, 0.2, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('potion_giant_strength',
     'Mikstura siły olbrzyma', 'consumable',
     'Gęsta brązowa mikstura w kamiennym dzbanuszku. Daje krótko siłę pozwalającą podnieść wóz albo wyrwać drzwi z zawiasów.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     250, 0.3, 1, 3, 0, 'torso', '["warrior"]', 1, 1, 0, 'permanent'),

    -- ── HERBS / NATURALS ─────────────────────────────────────────────────────
    ('healing_herb',
     'Lecznicze zioła', 'consumable',
     'Pęczek suszonych ziół owinięty w len. Przyłożone do rany przyspieszają gojenie.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"1d4+1"}]}',
     8, 0.1, 1, 1, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('bandage',
     'Bandaż', 'consumable',
     'Czysty zwój lnianego płótna. Pozwala opatrzyć ranę towarzysza w polu walki.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"1d6"}]}',
     2, 0.2, 1, 1, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('sobering_draught',
     'Trzeźwiący napar', 'consumable',
     'Gorzki ziołowy wywar. Neutralizuje efekty dezorientacji i strachu jednym łykiem.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"remove_condition","condition_key":"frightened"}]}',
     20, 0.2, 1, 1, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    -- ── COMBAT THROWABLES ────────────────────────────────────────────────────
    ('holy_water',
     'Woda święcona', 'consumable',
     'Mała ampułka z modlitwą wyrytą na korku. Wylana na nieumarłego spala go jak ogień.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     25, 0.2, 1, 1, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('alchemist_fire',
     'Ogień alchemika', 'consumable',
     'Gęsta oleista substancja w szklanym pojemniku. Rzucona na cel zapala go i pali przez kilka chwil.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"apply_condition","condition_key":"burning","duration_rounds":2}]}',
     50, 0.5, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    ('smoke_bomb',
     'Bomba dymna', 'consumable',
     'Mała gliniana kulka ze sproszkowanymi ziołami. Rzucona o podłogę wybucha kłębem dymu — idealna na ucieczkę.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     30, 0.3, 1, 2, 0, 'torso', '[]', 1, 1, 0, 'permanent'),

    -- ── SCROLLS ──────────────────────────────────────────────────────────────
    ('scroll_magic_bolt',
     'Zwój: Magiczna Strzała', 'consumable',
     'Zwitek pergaminu zapisany świetlistym inkaustem. Czytanie wyzwala pocisk mocy w wybrany cel.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     40, 0.1, 1, 2, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent'),

    ('scroll_mend',
     'Zwój: Zaszycie Ran', 'consumable',
     'Pergamin zapisany srebrnym pismem. Wypowiedzenie formuły zalecza ranę towarzysza.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"heal_hp","value":"2d4+2"}]}',
     35, 0.1, 1, 2, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent'),

    ('scroll_fireball',
     'Zwój: Kula Ognia', 'consumable',
     'Gruby zwój zapisany czerwonym pigmentem. Wyzwala kulę ognia, która eksploduje wśród wrogów.',
     '{"schema_version":1,"effect_category":"consumable_immediate","effects":[{"type":"narrative_only"}]}',
     350, 0.2, 1, 3, 0, 'torso', '["scholar"]', 1, 1, 0, 'permanent');
