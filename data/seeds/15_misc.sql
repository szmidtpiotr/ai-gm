-- S15: Knowledge book + riddles + hex config seed (#503)
-- Tables: knowledge_book, game_config_riddles, hex_type_config
-- Depends on S10 (locations for hex context).
-- Safe to re-run: INSERT OR IGNORE.

-- ── Hex type config — add missing terrain types ───────────────────────────────
-- Existing: road, plains, forest, hills, mountains, swamp, river, town,
--           dungeon, ruins, castle, cave
-- Adding: water, desert, tundra

INSERT OR IGNORE INTO hex_type_config
    (hex_type, label, travel_hours, encounter_base_chance,
     map_color, map_icon, is_active, is_passable, spawn_weight, has_submap)
VALUES
    ('water',   'Woda',    0.0, 0.05, '#1a4a7a', '≈', 1, 0, 5,  0),
    ('desert',  'Pustynia',1.5, 0.20, '#c8a43a', '☀', 1, 1, 8,  0),
    ('tundra',  'Tundra',  1.5, 0.25, '#8aadad', '❄', 1, 1, 6,  0),
    ('coast',   'Wybrzeże',1.0, 0.15, '#5a9aaa', '⛵', 1, 1, 12, 0),
    ('volcanic','Wulkan',  2.0, 0.40, '#8a2a1a', '🌋', 1, 1, 2,  0);

-- ── Knowledge book — world lore + mechanic hints ──────────────────────────────
-- Existing: combat (2), exploration (1), magic (2), mechanics (2)
-- Adding: lore, exploration, combat, magic, mechanics

INSERT OR IGNORE INTO knowledge_book
    (tip_key, category, title, body, is_active, sort_order)
VALUES
    -- World lore
    ('lore_vilnograd',
     'lore',
     'Vilnograd — stolica regionu',
     'Vilnograd to największe miasto w regionie. Siedziba króla i centrum handlu. Gildie kupieckie, świątynia Światła i dzielnica złodziei tworzą trzy nieformalnie rządzące siły. Mówi się, że prawdziwa władza leży w rękach Rady Czterech — anonimowych mecenasów.',
     1, 10),

    ('lore_ancient_ruins',
     'lore',
     'Pradawne ruiny',
     'Przed setkami lat kontynent zamieszkiwała zaawansowana cywilizacja. Ich ruiny rozsiane są po całym regionie. Większość zawiera pułapki i nieumarłe. Nieliczni uczeni twierdzą, że pradawni opanowali moc rdzenia i to zniszczyło ich cywilizację.',
     1, 11),

    ('lore_currency',
     'lore',
     'System monetarny',
     'W świecie obowiązuje jeden system monet: złote dukaty (gp). Miedź i srebro istnieją ale nie są modelem ekonomicznym gry. 1 gp to wartość dobrego posiłku. Ekwipunek bojowy kosztuje dziesiątki do setek gp. Magiczne przedmioty — tysiące.',
     1, 12),

    -- Exploration
    ('explore_fog_of_war',
     'exploration',
     'Mgła wojny — odkrywanie świata',
     'Mapa świata jest zakryta dopóki bohater nie odwiedzi danego heksa. Każda eksploracja może ujawnić nowe lokacje, skarbce lub zagrożenia. Niektóre heksy mają zakryte sub-lokacje — potrzeba odwiedzin kilku razy lub specjalnych umiejętności.',
     1, 20),

    ('explore_travel',
     'exploration',
     'Podróż i czas',
     'Podróż między heksami zajmuje określony czas zależny od terenu: droga — 1h, równiny — 1h, las/góry — 2h+. Bagno spowalnia najbardziej. Nocna podróż zwiększa ryzyko spotkań losowych. Odpoczynek w karczmie regeneruje HP i manę.',
     1, 21),

    -- Combat hints
    ('combat_positioning',
     'combat',
     'Pozycjonowanie w walce',
     'Walka dzieli się na dwie strefy: ZWARCIE (melee) i DYSTANS (ranged). Broń biała działa tylko w zwarciu, dystansowa tylko z odległości. Przełączanie strefy kosztuje turę. Wrogowie melee zbliżają się, zanim zaatakują — zyskujesz dodatkowy ruch.',
     1, 30),

    ('combat_conditions',
     'combat',
     'Stany bojowe',
     'Efekty stanu modyfikują rzuty kośćmi. OGŁUSZENIE: -2 do wszystkich rzutów. ZATRUCIE: -2 do STR/DEX. PARALIŻ: nie można się poruszać. BLEEDING: 1d4 obrażeń co turę. BURNING: 1d6 obrażeń, gaszone przez akcję. Stan znika po sukcesie rzutu obrony lub po walce.',
     1, 31),

    ('combat_crits',
     'combat',
     'Krytyki i fumble',
     'Naturalne 20 na kości (bez modyfikatorów) to krytyk: automatyczny sukces i podwójne obrażenia. Naturalne 1 to fumble: automatyczna porażka i komplikacja (GM może zaimprowizować). Krytykiem i fumble nie można zmienić via zdolności — to wola kości.',
     1, 32),

    -- Magic hints
    ('magic_spells_learning',
     'magic',
     'Nauka zaklęć (Scholar)',
     'Scholar (Uczony) zaczyna z dwoma zaklęciami: Magiczna Strzała i Leczenie. Nowe zaklęcia odblokowuje się wydając Punkty Arkaniczne (zdobywane co poziom). Każde zaklęcie ma 3 rangi — wyższa ranga = silniejszy efekt, wyższy koszt many.',
     1, 40),

    ('magic_miscast',
     'magic',
     'Magiczne fiasko (Miscast)',
     'Naturalna 1 przy rzucaniu zaklęcia to miscast. Na poziomach 1-2 tylko ogłuszenie. Poziom 3-4: 1d4 obrażeń własnych. Poziom 5-7: 1d6 + ogłuszenie. Poziom 8+: 1d8 + ogłuszenie + efekt wtórny (losowy). Wysoka INT zmniejsza ryzyko powikłań.',
     1, 41),

    -- Mechanics
    ('mech_leveling',
     'mechanics',
     'Awansowanie i XP',
     'Punkty doświadczenia (XP) zdobywa się za: pokonanie wrogów, odkrywanie lokacji, rozwiązywanie zagadek, kluczowe decyzje fabularne. Każdy poziom wymaga coraz więcej XP. Awans daje: +max HP (CON mod), nowe zdolności, punkt arcanski (Scholar), +proficiency co 3 poziomy.',
     1, 50),

    ('mech_death',
     'mechanics',
     'Śmierć i resurrekcja',
     'Gdy HP spadnie do 0 — bohater ginie. Kampania kończy się (bohater przechodzi w tryb "poległy"). Jeśli admin ma włączoną resurrekcję: za koszt (złoto lub XP) bohater może wrócić do życia z HP = 1 i bez part buffs. Historia kampanii jest zachowana.',
     1, 51),

    ('mech_skills',
     'mechanics',
     'Umiejętności i rangi',
     'Każda umiejętność ma rangę 1-5. Ranga 1-2: podstawowa biegłość. Ranga 3-4: zaawansowana (daje bonus proficiency +2 do rzutów). Ranga 5: mistrzostwo (bonus +2 i specjalny efekt). Umiejętności rozwijają się przez użycie — GM może przyznawać rangi za istotne działania.',
     1, 52);

-- ── Riddles — 7 new riddles to extend the pool ───────────────────────────────
-- Existing 12: shadow, echo, fire, time, key, death, river, mirror,
--              book, night (hole), bones (ship), sword (wind)
-- Adding: nature, dungeon, magic, logic themes

INSERT OR IGNORE INTO game_config_riddles
    (key, text, answer, answer_alts, hints, difficulty, theme, is_active)
VALUES
    ('riddle_stone',
     'Stoję tysiące lat, wicher mnie nie przewróci. Woda mnie rzeźbi, lecz ja jej nie czuję. Czym jestem?',
     'kamień',
     '["skała","głaz","kamień"]',
     '["Znajdziesz mnie w górach i na drogach","Można mnie ciosać dłutem","Nie jestem żywy, ale mogę być zimny lub gorący"]',
     1, 'nature', 1),

    ('riddle_silence',
     'Im więcej masz, tym mniej mówisz. Czym jestem?',
     'mądrość',
     '["mądrość","wiedza"]',
     '["Starcy mają tego więcej niż młodzi","Milczenie bywa jej wyrazem","Nie można jej kupić, tylko zdobyć"]',
     3, 'magic', 1),

    ('riddle_chain',
     'Mocniejszy gdy jestem wolny, słabszy gdy mnie trzymają. Czym jestem?',
     'ogień',
     '["ogień","płomień","pożar"]',
     '["Daję ciepło i światło","Woda jest moim wrogiem","W kominku jestem oswojony"]',
     2, 'dungeon', 1),

    ('riddle_staircase',
     'Mam wiele stopni, ale nie jestem schodami. Mam dno, ale nie jestem studnią. Czym jestem?',
     'piwnicy',
     '["piwnica","loch","katakumby"]',
     '["Słońce mnie nie lubi","Dobre wino dojrzewa we mnie","Strach często przebywa na moich korytarzach"]',
     2, 'dungeon', 1),

    ('riddle_map',
     'Pokazuję drogi, których nie przeszedłem. Znam krainy, których nie widziałem. Czym jestem?',
     'mapa',
     '["mapa","pergamin","plan"]',
     '["Można mnie złożyć","Podróżnicy mnie szukają","Na mnie są zaznaczone miejsca"]',
     1, 'general', 1),

    ('riddle_name',
     'Każdy mi coś zawdzięcza, nikt mnie nie prosił. Noszą mnie przez całe życie, ale nie ważę nic. Czym jestem?',
     'imię',
     '["imię","nazwa"]',
     '["Rodzice dają to dzieciom","Wrogowie mogą je splamić","Bohaterowie walczą o jego sławę"]',
     2, 'general', 1),

    ('riddle_blood',
     'Płynę w żyłach dzielnych i tchórzów. Gdy wychodzę na zewnątrz, coś idzie nie tak. Czym jestem?',
     'krew',
     '["krew"]',
     '["Czerwona jak rubiny","Lekarze dobrze mnie znają","Wojownicy widzą mnie za dużo"]',
     1, 'death', 1);
