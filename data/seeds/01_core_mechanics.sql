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

-- ── S8 (#603) FAZA S — batch kondycji z prymitywów (dot/static_stat_modifier/periodic_save).
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('on_fire', 'Podpalony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"dot","value":"2d6","damage_type":"fire","tick":"start_turn"},{"type":"static_stat_modifier","stat":"STR","value":-2},{"type":"static_stat_modifier","stat":"DEX","value":-2},{"type":"periodic_save","stat":"DEX","value":12,"tick":"start_turn","expires":"save_success"}]}',
     'Postać płonie — 2k6 obrażeń od ognia na początku tury, STR i DEX -2. Udany rzut DEX DC 12 gasi ogień.',
     1, 0, NULL),
    ('frozen', 'Zmrożony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"DEX","value":-4},{"type":"periodic_save","stat":"CON","value":14,"tick":"start_turn","expires":"save_success"}]}',
     'Postać pokryta lodem — DEX -4. Udany rzut CON DC 14 lub kontakt z ciepłem zdejmuje stan.',
     1, 0, NULL),
    ('confused', 'Zdezorientowany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"INT","value":-3},{"type":"static_stat_modifier","stat":"WIS","value":-3},{"type":"behavior_override","behavior":"random_table_k4"},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}',
     'Postać nie rozumie otoczenia — INT i WIS -3. Na początku tury k4: 1 stoi / 2 atak losowego celu / 3 ucieczka / 4 normalnie. Udany rzut WIS DC 14 (zebranie myśli) kończy stan. (S18: pełne zachowanie behavior_override.)',
     1, 0, NULL),
    ('insane', 'Obłąkany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-5}]}',
     'Postać straciła kontakt z rzeczywistością — testy społeczne -5. Wersja lite.',
     1, 0, NULL),
    ('panicked', 'Spanikowany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-4},{"type":"static_stat_modifier","stat":"WIS","value":-4},{"type":"behavior_override","behavior":"flee"},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}',
     'Postać ogarnięta paniką — CHA i WIS -4. Wymuszona ucieczka (zmiana strefy na dystans). Udany rzut WIS DC 14 na początku tury przezwycięża panikę. (S18: pełne zachowanie behavior_override.)',
     1, 0, NULL),
    ('charmed', 'Zaczarowany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"WIS","value":-3},{"type":"periodic_save","stat":"WIS","value":16,"tick":"start_turn","expires":"save_success"}]}',
     'Postać oczarowana — WIS -3 wobec źródła. Udany rzut WIS DC 16 zrywa czar. Wersja lite.',
     1, 0, NULL),
    ('cursed', 'Przeklęty',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":-2},{"type":"static_stat_modifier","stat":"DEX","value":-2},{"type":"static_stat_modifier","stat":"CON","value":-2},{"type":"static_stat_modifier","stat":"INT","value":-2},{"type":"static_stat_modifier","stat":"WIS","value":-2},{"type":"static_stat_modifier","stat":"CHA","value":-2},{"type":"reroll","mode":"forced_keep_worst","scope":"skill_test"}]}',
     'Postać nosi klątwę — -2 do wszystkich testów. Zły omen: raz na scenę los przerzuca udany test na gorszy wynik (S11). Zdjęcie: rytuał theology/arcana.',
     1, 0, NULL);

-- ── S11 (#606) FAZA S — prymityw reroll + kondycja inspired (player_keep_best).
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('inspired', 'Zainspirowany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":2},{"type":"static_stat_modifier","stat":"WIS","value":2},{"type":"reroll","mode":"player_keep_best","uses":1,"scope":"skill_test"}]}',
     'Postać działa pewniej — CHA i WIS +2. Raz może przerzucić nieudany test umiejętności i zachować lepszy wynik. Znika po wykorzystaniu przerzutu lub po 3 turach.',
     1, 0, NULL);

-- ── S9 (#604) FAZA S — prymityw stacking_levels + kondycja exhausted (stackable=1).
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('exhausted', 'Wyczerpany',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"stacking_levels","max_level":2,"per_level_effects":[{"type":"static_stat_modifier","stat":"STR","value":-3},{"type":"static_stat_modifier","stat":"DEX","value":-3},{"type":"static_stat_modifier","stat":"CON","value":-3}],"threshold_effects":{"2":{"type":"block_action"}}}]}',
     'Postać skrajnie zmęczona — STR/DEX/CON -3 na poziom (poziom 2 = omdlenie/utrata tury). Ponowne nałożenie podbija poziom (max 2). Zdejmowanie: 1h odpoczynku = -1 poziom, pełny sen = wszystkie.',
     1, 1, NULL);

-- ── S10 (#605) FAZA S — prymityw escalating_dot + kondycja hemorrhage (narastający DOT).
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    Top-level `cure` = deklaratywne zdjęcie udanym SKILL_TEST:medicine (DC z zamka {8,12,16,20,24}).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('hemorrhage', 'Krwotok',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"escalating_dot","value":"1d4","escalate_every_rounds":3,"escalate_dice":"1d4","damage_type":"physical","tick":"start_turn"}],"cure":{"skill":"medicine","dc":16}}',
     'Krwotok — 1k4 obrażeń na początku tury, +1k4 co 3 tury bez leczenia (narastający). Zdjęcie: test medicine DC 16 (bandaże/narzędzia) lub leczenie magiczne (remove_condition).',
     1, 0, NULL);

-- ── S12 (#607) FAZA S — prymitywy extra_action + on_expire_apply + kondycja hasted.
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    duration: design doc „k4+1 tur"; schemat U10 nie dopuszcza kości w duration → stała 3 (≈ śr. k4+1).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('hasted', 'Przyśpieszony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"DEX","value":2},{"type":"extra_action","action_kind":"move_only","expires":"duration_rounds:3"},{"type":"on_expire_apply","condition_key":"exhausted","value":1}]}',
     'Postać przyśpieszona — DEX +2 i dodatkowa akcja ruchu (zmiana strefy bez utraty tury). Trwa 3 rundy; po wygaśnięciu postać dostaje 1 poziom wyczerpania (exhausted). Niestackowalna.',
     1, 0, NULL);

-- S13 (#608) FAZA S — prymityw `on_zero_hp_save` + kondycja `blessed`.
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    +2 defensywny przez derived stat 'save'. Brak `expires` → trwa do końca walki/sceny
--    (design doc: „1 scena/spotkanie"). uses=1 → raz na scenę. Niekumulowalna.
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('blessed', 'Pobłogosławiony',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"save","value":2},{"type":"on_zero_hp_save","stat":"CON","value":12,"result":"stay_at_1hp","uses":1}]}',
     'Postać pod opieką bóstwa — +2 do testów obronnych i przeciw kondycjom negatywnym. Raz na scenę, gdy cios miałby ją powalić, silnik rzuca CON DC 12 i przy sukcesie zostawia 1 HP zamiast nieprzytomności. Trwa do końca walki/sceny. Niekumulowalna.',
     1, 0, NULL);

-- S14 (#609) FAZA S — prymityw `condition_immunity` + klucz `broken_by` + kondycja `rage`.
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    immune_to[slowed,weakened] = odporność; broken_by[stunned,confused] = nałożenie przerywa furię;
--    on_expire_apply exhausted 1 = koszt furii; duration: design doc „k6+2" → stała 6 (schemat U10
--    nie dopuszcza kości w duration; wzorzec S12 hasted ≈ śr. k6+2 = 5,5). damage_bonus +3 = wręcz.
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('rage', 'Furia',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":2},{"type":"static_stat_modifier","stat":"damage_bonus","value":3},{"type":"condition_immunity","immune_to":["slowed","weakened"],"expires":"duration_rounds:6"},{"type":"on_expire_apply","condition_key":"exhausted","value":1}],"broken_by":["stunned","confused"]}',
     'Kontrolowana furia bojowa — +2 SIŁY, +3 obrażeń wręcz, odporność na spowolnienie i osłabienie. Trwa 6 rund; ogłuszenie lub dezorientacja natychmiast ją przerywają. Po wygaśnięciu postać dostaje 1 poziom wyczerpania (exhausted). Niekumulowalna.',
     1, 0, NULL);

-- ── S18 (#613) FAZA S — prymityw `behavior_override` + kondycja `berserk` (niekontrolowany szał).
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    attack_nearest = atak najbliższego niezależnie od frakcji (też sojusznika); +3 atak/+3 obrażenia,
--    -3 AC; WIS DC 14 odzyskuje kontrolę; duration k6 → stała 6 (schemat U10 bez kości w duration).
--    Różni się od `rage`: rage = kontrolowana (pozytywna), berserk = niekontrolowana (negatywna mentalna).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('berserk', 'Berserk',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"behavior_override","behavior":"attack_nearest","expires":"duration_rounds:6"},{"type":"static_stat_modifier","stat":"attack_bonus","value":3},{"type":"static_stat_modifier","stat":"damage_bonus","value":3},{"type":"static_stat_modifier","stat":"ac","value":-3},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}',
     'Niekontrolowany szał bojowy — postać atakuje najbliższy cel NIEZALEŻNIE od frakcji (też sojuszników). +3 do ataków i obrażeń, -3 AC. Na początku tury rzut WIS DC 14 odzyskuje kontrolę. Trwa do 6 rund lub brak wrogów w zasięgu. Różni się od kontrolowanej furii (rage).',
     1, 0, NULL);

-- ── S19 (#614) FAZA S — prymitywy `untargetable` + `ambush_bonus` + kondycja `hidden`.
--    Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
--    untargetable = wróg pomija ukrytego gracza przy wyborze celu; ambush_bonus 2k6 = pierwszy
--    atak z ukrycia (oddzielny add po mnożniku, zdejmuje kondycję). granted_by = ODWROTNOŚĆ cure:
--    udany SKILL_TEST stealth DC 14 NAKŁADA hidden. detect_dc 14 = WIS save wroga przy poszukiwaniu.
--    Nie zmienia strefy — ortogonalne (zasadzka możliwa też w zwarciu).
INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove)
VALUES
    ('hidden', 'Ukryty',
     '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"untargetable"},{"type":"ambush_bonus","value":"2d6"}],"granted_by":{"skill":"stealth","dc":14},"detect_dc":14}',
     'Postać skutecznie się ukryła — wrogowie nie mogą jej atakować, dopóki jej nie wykryją. Pierwszy atak z ukrycia zadaje +2k6 obrażeń (zasadzka) i zdejmuje ukrycie. Wejście: udany test skradania (stealth DC 14). Zejście: własny atak (demaskuje) lub wykrycie (wróg WIS DC 14 przy aktywnym poszukiwaniu). Nie zmienia strefy — możliwa zasadzka również w zwarciu.',
     1, 0, NULL);

-- ── DC tiers (ensure correct values) ─────────────────────────────────────────
INSERT OR IGNORE INTO game_config_dc (key, label, value, sort_order, description) VALUES
    ('easy',      'Łatwe',       8,  1, 'Proste działania. Większość postaci z moderowaną biegłością sobie poradzi.'),
    ('medium',    'Średnie',     12, 2, 'Wymaga skupienia i pewnej biegłości.'),
    ('hard',      'Trudne',      16, 3, 'Niepewne i wymagające. Ryzyko nawet przy dobrym przygotowaniu.'),
    ('extreme',   'Ekstremalne', 20, 4, 'Granica możliwości. Wyjątkowe przygotowanie lub talent.'),
    ('legendary', 'Legendarne',  24, 5, 'Działanie na poziomie legend.');
