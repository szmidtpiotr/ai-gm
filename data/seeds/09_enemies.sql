-- S9: Enemies seed (#497)
-- ~50 canonical enemies. Depends on S8 (loot_poor/standard/rich/treasure must exist).
-- Existing 10 enemies updated with loot_tier + behavior_profile_key.
-- New enemies reference base tier loot tables (per-enemy tables created by admin panel on approve).
-- Safe to re-run: INSERT OR IGNORE + UPDATE pattern.

-- ── Behavior profiles — INSERT OR IGNORE ─────────────────────────────────────
-- (8 already exist; fill gaps needed by new enemies)

INSERT OR IGNORE INTO enemy_behavior_profiles
    (enemy_key, default_action, hp_threshold_flee, special_ability_key,
     special_ability_cooldown_turns, dialogue_on_aggro, dialogue_on_death,
     fear_aura, fear_dc)
VALUES
    ('goblin',         'attack_player',  25, 'throw_rock', 3,
     'Goblin warczy i atakuje!', 'Goblin pada z cichym świstem.', 0, 0),
    ('goblin_archer',  'attack_player',  20, NULL, 0,
     'Goblin łucznik naciąga cięciwę!', 'Goblin pada.', 0, 0),
    ('bandit',         'attack_weakest', 20, NULL, 0,
     'Bandyta atakuje!', 'Bandyta osunął się na ziemię.', 0, 0),
    ('wolf',           'attack_player',  15, NULL, 0,
     'Wilk warczy z nisko opuszczoną głową.', 'Wilk pada.', 0, 0),
    ('skeleton',       'attack_player',  0,  NULL, 0,
     'Szkielet zgrzyta kośćmi.', 'Kości rozsypują się.', 0, 0),
    ('orc',            'attack_weakest', 10, NULL, 0,
     'Ork ryczy i szarżuje!', 'Ork pada z głuchym łoskotem.', 0, 0),
    ('troll',          'attack_player',  5,  'regenerate', 2,
     'Troll ryczy — sam widok budzi grozę!', 'Troll pada.', 1, 12),
    ('vampire_master', 'attack_player',  0,  'drain_life', 3,
     'Wampir uśmiecha się. Zimno.', 'Wampir rozpływa się w mroku.', 1, 16),
    -- new profiles
    ('zombie',         'attack_player',  0,  NULL, 0,
     'Zombie pełznie ku tobie z martwymi oczami.', 'Zombie pada po raz ostatni.', 0, 0),
    ('orc_shaman',     'attack_player',  20, NULL, 0,
     'Szaman orków rytualnymi słowami przywołuje mrok!', 'Szaman upada, zaklęcia milkną.', 0, 0),
    ('vampire',        'attack_player',  5,  'drain_life', 3,
     'Wampir ukazuje kły w zimnym uśmiechu.', 'Wampir obraca się w pył.', 0, 0),
    ('ogre',           'attack_player',  10, NULL, 0,
     'Ogr ryczy i unosi maczugę!', 'Ogr wali o ziemię z hukiem.', 0, 0),
    ('lich',           'attack_player',  0,  'drain_life', 3,
     'Lich spogląda na ciebie pustymi oczodołami. Zimno — bardzo zimno.', 'Lich rozpada się w proch starożytnych kości.', 1, 14),
    ('dragon_young',   'attack_player',  0,  NULL, 0,
     'Młody smok ryczy — powietrze parzy od jego oddechu!', 'Smok pada — jego łuski twardnieją w kamień.', 1, 16);

-- ── Patch existing enemies — loot_tier + behavior_profile_key ────────────────

UPDATE game_config_enemies SET
    loot_tier            = 'poor',
    drop_chance          = 0.7,
    behavior_profile_key = 'goblin',
    xp_award             = 35
WHERE key = 'goblin';

UPDATE game_config_enemies SET
    loot_tier            = 'standard',
    drop_chance          = 0.9,
    behavior_profile_key = 'bandit',
    xp_award             = 100
WHERE key = 'bandit';

UPDATE game_config_enemies SET
    loot_tier            = 'standard',
    drop_chance          = 0.8,
    behavior_profile_key = NULL,
    xp_award             = 75
WHERE key = 'enemy';

UPDATE game_config_enemies SET
    loot_tier            = 'standard',
    drop_chance          = 0.85,
    behavior_profile_key = NULL,
    xp_award             = 90
WHERE key = 'guard';

UPDATE game_config_enemies SET
    loot_tier            = 'poor',
    drop_chance          = 0.4,
    behavior_profile_key = NULL,
    xp_award             = 20
WHERE key = 'old_man';

UPDATE game_config_enemies SET
    loot_tier            = 'standard',
    drop_chance          = 0.9,
    behavior_profile_key = 'orc',
    xp_award             = 110
WHERE key = 'orc';

UPDATE game_config_enemies SET
    loot_tier            = 'poor',
    drop_chance          = 0.6,
    behavior_profile_key = 'skeleton',
    xp_award             = 60,
    conditions_immune    = '["poisoned"]'
WHERE key = 'skeleton';

UPDATE game_config_enemies SET
    tier                 = 'elite',
    loot_tier            = 'rich',
    drop_chance          = 1.0,
    behavior_profile_key = 'troll',
    xp_award             = 350
WHERE key = 'troll';

UPDATE game_config_enemies SET
    loot_tier            = 'standard',
    drop_chance          = 0.8,
    behavior_profile_key = 'bandit',
    xp_award             = 85
WHERE key = 'unknown_attacker';

UPDATE game_config_enemies SET
    loot_tier            = 'poor',
    drop_chance          = 0.7,
    behavior_profile_key = 'wolf',
    xp_award             = 55
WHERE key = 'wolf';

-- ── New enemies — INSERT OR IGNORE ───────────────────────────────────────────
-- Columns: key, label, hp_base, ac_base, attack_bonus, dex_modifier,
--          damage_die, tier, attacks_per_turn, damage_bonus, damage_type,
--          xp_award, conditions_immune, loot_table_key, loot_tier, drop_chance,
--          behavior_profile_key, description, note, review_status, is_active

INSERT OR IGNORE INTO game_config_enemies
    (key, label, hp_base, ac_base, attack_bonus, dex_modifier,
     damage_die, tier, attacks_per_turn, damage_bonus, damage_type,
     xp_award, conditions_immune, loot_table_key, loot_tier, drop_chance,
     behavior_profile_key, description, note, review_status, is_active)
VALUES

-- ── WEAK ─────────────────────────────────────────────────────────────────────

('goblin_archer',
 'Goblin Łucznik', 8, 11, 2, 2,
 '1d6', 'weak', 1, 0, 'physical',
 35, NULL, 'loot_poor', 'poor', 0.7,
 'goblin_archer',
 'Goblin uzbrojony w krótki łuk. Trzyma się na dystansie i zasypuje wrogów strzałami.',
 'Atak z dystansu — trzyma się w tylnym rzędzie.', 'permanent', 1),

('kobold',
 'Kobold', 6, 11, 1, 2,
 '1d4', 'weak', 1, 0, 'physical',
 20, NULL, 'loot_poor', 'poor', 0.6,
 NULL,
 'Mały jaszczuroludek o łuskowatej skórze i przebiegłych oczkach. Słaby, ale atakuje w grupach.',
 NULL, 'permanent', 1),

('giant_rat',
 'Olbrzymi Szczur', 6, 10, 1, 1,
 '1d4', 'weak', 1, 0, 'physical',
 15, NULL, 'loot_poor', 'poor', 0.5,
 NULL,
 'Szczur wielkości psa. Zęby jak sztylet — i odpowiednio jadowity.',
 NULL, 'permanent', 1),

('zombie',
 'Zombie', 15, 9, 1, -1,
 '1d6', 'weak', 1, 0, 'physical',
 30, '["poisoned"]', 'loot_poor', 'poor', 0.5,
 'zombie',
 'Ożywiony trup poruszający się powoli, ale niepowstrzymanie. Głodne mięsa żywych.',
 'Nieumarły — odporny na truciznę.', 'permanent', 1),

('cultist',
 'Kultista', 8, 10, 2, 1,
 '1d4', 'weak', 1, 0, 'physical',
 25, NULL, 'loot_poor', 'poor', 0.65,
 NULL,
 'Fanatyczny wyznawca mrocznego bóstwa. Walczy z zapałem, choć bez umiejętności.',
 NULL, 'permanent', 1),

('imp',
 'Imp', 8, 12, 2, 3,
 '1d4', 'weak', 1, 0, 'magical',
 30, '["poisoned"]', 'loot_poor', 'poor', 0.6,
 NULL,
 'Mały demon o czerwonawej skórze i złośliwym temperamencie. Szybki i denerwujący.',
 'Magiczne obrażenia.', 'permanent', 1),

('bandit_thug',
 'Bandyta Oprych', 10, 11, 2, 1,
 '1d6', 'weak', 1, 0, 'physical',
 40, NULL, 'loot_poor', 'poor', 0.7,
 'bandit',
 'Nieokrzesany zbój na usługach bandy. Mięcho bez strategii.',
 NULL, 'permanent', 1),

('slime',
 'Szlam', 12, 8, 1, -2,
 '1d4', 'weak', 1, 0, 'physical',
 25, '["stunned","frightened"]', 'loot_poor', 'poor', 0.3,
 NULL,
 'Bezpostaciowa masa kwaśnej substancji. Powolna, ale kwas drąży zbroję.',
 'Odporny na ogłuszenie i strach.', 'permanent', 1),

-- ── STANDARD ─────────────────────────────────────────────────────────────────

('orc_warrior',
 'Wojownik Orków', 22, 14, 5, 0,
 '1d8', 'standard', 1, 1, 'physical',
 100, NULL, 'loot_standard', 'standard', 0.9,
 'orc',
 'Orc w zbroi z łupów. Szybszy i bardziej doświadczony niż zwykły ork.',
 NULL, 'permanent', 1),

('orc_shaman',
 'Szaman Orków', 16, 11, 4, 1,
 '1d6', 'standard', 1, 0, 'magical',
 120, NULL, 'loot_standard', 'standard', 0.85,
 'orc_shaman',
 'Ork z wiedzą rytualną i grubą warstwą malowidła na twarzy. Rzuca zaklęcia obok ciosów.',
 'Zadaje magiczne obrażenia.', 'permanent', 1),

('ghoul',
 'Ghul', 20, 12, 3, 1,
 '1d6', 'standard', 1, 0, 'physical',
 100, '["poisoned"]', 'loot_standard', 'standard', 0.7,
 'zombie',
 'Szybki nieumarły polujący na żywych. Pazury paraliżują skórę.',
 'Nieumarły — odporny na truciznę.', 'permanent', 1),

('werewolf',
 'Wilkołak', 24, 13, 5, 2,
 '1d8', 'standard', 1, 1, 'physical',
 150, NULL, 'loot_standard', 'standard', 0.8,
 'wolf',
 'Człowiek przeklęty wilczą naturą. W pełni księżyca szału nie opanuje.',
 'Zranienie srebrną bronią zadaje obrażenia kości wyżej.', 'permanent', 1),

('assassin',
 'Skrytobójca', 18, 13, 6, 3,
 '1d6', 'standard', 1, 2, 'physical',
 130, NULL, 'loot_standard', 'standard', 0.85,
 'bandit',
 'Profesjonalny zabójca na zlecenie. Celuje w słabe punkty i uderza pierwsze.',
 'Wysoka premia do ataku z zaskoczenia.', 'permanent', 1),

('mercenary',
 'Najemnik', 20, 14, 5, 0,
 '1d8', 'standard', 1, 0, 'physical',
 110, NULL, 'loot_standard', 'standard', 0.9,
 'bandit',
 'Żołnierz za pieniądze. Dobrze wyposażony, bez skrupułów.',
 NULL, 'permanent', 1),

('cave_bear',
 'Niedźwiedź Jaskiniowy', 28, 12, 5, 0,
 '1d8', 'standard', 2, 1, 'physical',
 140, NULL, 'loot_standard', 'standard', 0.8,
 NULL,
 'Ogromny niedźwiedź zamieszkujący ciemne jaskinie. Uderza dwukrotnie za każdym razem.',
 '2 ataki na turę.', 'permanent', 1),

('giant_spider',
 'Olbrzymi Pająk', 16, 12, 4, 2,
 '1d6', 'standard', 1, 0, 'physical',
 90, NULL, 'loot_standard', 'standard', 0.65,
 NULL,
 'Pająk wielkości psa. Jad paraliżuje, sieć unieruchamia.',
 'Ukąszenie może nałożyć stan zatrucia.', 'permanent', 1),

('dark_mage',
 'Mroczny Czarodziej', 14, 11, 5, 1,
 '1d6', 'standard', 1, 0, 'magical',
 140, NULL, 'loot_standard', 'standard', 0.85,
 'orc_shaman',
 'Człowiek lub elf opanowany przez mroczną magię. Rzuca zaklęcia z bezpiecznej odległości.',
 'Magiczne obrażenia.', 'permanent', 1),

('lizardman',
 'Jaszczuroludek', 18, 13, 4, 1,
 '1d6', 'standard', 1, 0, 'physical',
 95, NULL, 'loot_standard', 'standard', 0.8,
 NULL,
 'Humanoid o łuskowatej skórze zamieszkujący bagna i ruiny. Walczy kłami i toporem.',
 NULL, 'permanent', 1),

('ghost',
 'Duch', 16, 11, 3, 3,
 '1d6', 'standard', 1, 0, 'magical',
 120, '["poisoned","stunned"]', 'loot_standard', 'standard', 0.5,
 'skeleton',
 'Niespokojny duch przywiązany do miejsca śmierci. Ataki fizyczne mają obniżoną skuteczność.',
 'Odporny na truciznę i ogłuszenie. Magiczne obrażenia.', 'permanent', 1),

('brigand',
 'Rozbójnik', 16, 12, 4, 1,
 '1d6', 'standard', 1, 0, 'physical',
 85, NULL, 'loot_standard', 'standard', 0.85,
 'bandit',
 'Uliczny złodziej lub grasant leśny. Szybki, podły, liczy na rozbój bez walki.',
 NULL, 'permanent', 1),

('dark_elf',
 'Mroczny Elf', 16, 13, 5, 3,
 '1d6', 'standard', 1, 1, 'physical',
 130, NULL, 'loot_standard', 'standard', 0.85,
 NULL,
 'Elf podziemny wygnany lub z własnej woli służący mroku. Szybki i precyzyjny.',
 NULL, 'permanent', 1),

('harpy',
 'Harpja', 14, 12, 4, 3,
 '1d6', 'standard', 1, 0, 'physical',
 95, NULL, 'loot_standard', 'standard', 0.65,
 NULL,
 'Skrzydlata bestia o kobiecej głowie i szponach ptaka. Śpiewa, by dezorientować wrogów.',
 'Śpiew może nałożyć stan dezorientacji.', 'permanent', 1),

('wraith',
 'Widmo', 18, 12, 3, 3,
 '1d6', 'standard', 1, 0, 'necrotic',
 130, '["poisoned","stunned"]', 'loot_standard', 'standard', 0.5,
 'skeleton',
 'Czarna sylwetka przemykająca w cieniu. Dotyk wysysa siły życiowe.',
 'Nekrotyczne obrażenia. Odporny na truciznę i ogłuszenie.', 'permanent', 1),

-- ── ELITE ────────────────────────────────────────────────────────────────────

('vampire',
 'Wampir', 45, 15, 7, 3,
 '1d8', 'elite', 1, 1, 'physical',
 300, '["poisoned"]', 'loot_rich', 'rich', 0.95,
 'vampire',
 'Nieumarły arystokrata zasilający się krwią żywych. Szybki, silny i trudny do zabicia.',
 'Odporny na truciznę. Uzdrawia się z obrażeń zadanych wrogom.', 'permanent', 1),

('ogre',
 'Ogr', 50, 13, 6, -1,
 '2d6', 'elite', 1, 2, 'physical',
 280, NULL, 'loot_rich', 'rich', 0.9,
 'ogre',
 'Olbrzym o tępym umyśle i brutalnej sile. Każde trafienie może powali na ziemię.',
 '2d6 obrażeń, szansa na knockdown.', 'permanent', 1),

('golem_stone',
 'Golem Kamienny', 55, 17, 6, -2,
 '2d6', 'elite', 1, 2, 'physical',
 320, '["poisoned","stunned","frightened"]', 'loot_rich', 'rich', 0.8,
 NULL,
 'Animowany posąg z kamienia. Powolny, ale prawie niezniszczalny. Służy swojemu twórcy wiernie.',
 'Odporny na truciznę, ogłuszenie i strach.', 'permanent', 1),

('witch',
 'Wiedźma', 35, 12, 7, 2,
 '1d8', 'elite', 1, 0, 'magical',
 350, NULL, 'loot_rich', 'rich', 0.9,
 'orc_shaman',
 'Potężna czarodziejka korzystająca z mrocznych mocy. Rzuca zaklęcia kontroli i zniszczenia.',
 'Magiczne obrażenia. Może nakładać klątwy.', 'permanent', 1),

('undead_champion',
 'Nieumarły Mistrz', 45, 16, 7, 0,
 '1d8', 'elite', 1, 1, 'physical',
 300, '["poisoned"]', 'loot_rich', 'rich', 0.9,
 'skeleton',
 'Były rycerz lub wojownik podniesiony z martwych czarną magią. Zachował bojowe umiejętności.',
 'Odporny na truciznę.', 'permanent', 1),

('bandit_chief',
 'Herszt Bandy', 40, 14, 7, 2,
 '1d8', 'elite', 1, 1, 'physical',
 280, NULL, 'loot_rich', 'rich', 0.95,
 'bandit',
 'Przywódca bandy rozbójników. Doświadczony i bezlitosny — z bandą za plecami.',
 'Może wezwać posiłki.', 'permanent', 1),

('orc_warchief',
 'Wódz Orków', 48, 15, 7, 0,
 '1d10', 'elite', 1, 2, 'physical',
 350, NULL, 'loot_rich', 'rich', 0.95,
 'orc',
 'Wódz klanu orków w pełnej zbroi wojennej. Rzdzi przez siłę i strach.',
 'Wysoka obrona i siła ataku.', 'permanent', 1),

('dark_priest',
 'Mroczny Kapłan', 35, 13, 6, 1,
 '1d6', 'elite', 1, 0, 'necrotic',
 320, NULL, 'loot_rich', 'rich', 0.9,
 'orc_shaman',
 'Kapłan mrocznego bóstwa kanalizujący nekrotyczną moc przez symbol swego boga.',
 'Nekrotyczne obrażenia. Leczy się w pobliżu nieumarłych.', 'permanent', 1),

('shadow_stalker',
 'Cień', 35, 14, 7, 4,
 '1d6', 'elite', 1, 2, 'necrotic',
 300, '["poisoned","frightened"]', 'loot_rich', 'rich', 0.85,
 NULL,
 'Żywy cień przywołany przez starożytne zło. Niemal niewidoczny w ciemności.',
 'Nekrotyczne obrażenia. Odporny na truciznę i strach.', 'permanent', 1),

('wyvern',
 'Wiwerna', 60, 15, 8, 1,
 '2d6', 'elite', 1, 2, 'physical',
 400, NULL, 'loot_rich', 'rich', 0.95,
 NULL,
 'Mniejszy kuzyn smoka — bez oddechu ognia, ale za to z trującym kolcem w ogonie.',
 'Ogon może nałożyć truciznę.', 'permanent', 1),

('vampire_master',
 'Mistrz Wampirów', 75, 17, 9, 4,
 '1d10', 'elite', 1, 2, 'necrotic',
 600, '["poisoned","stunned"]', 'loot_rich', 'rich', 1.0,
 'vampire_master',
 'Pradawny wampir rządzący klinem innych nieumarłych. Jego spojrzenie paraliżuje.',
 'Strach, wysysanie życia, odporność na truciznę i ogłuszenie.', 'permanent', 1),

-- ── BOSS ─────────────────────────────────────────────────────────────────────

('lich',
 'Lisz', 90, 17, 9, 2,
 '2d8', 'boss', 1, 2, 'necrotic',
 1000, '["poisoned","stunned","frightened"]', 'loot_treasure', 'treasure', 1.0,
 'lich',
 'Potężny nekromanta który przekroczył śmierć by żyć wiecznie. Jedna z najtrudniejszych walk.',
 'Nekrotyczne obrażenia, strach, odporność na truciznę/ogłuszenie/strach.', 'permanent', 1),

('dragon_young',
 'Młody Smok', 120, 17, 10, 2,
 '2d8', 'boss', 1, 3, 'fire',
 1500, '["poisoned","frightened"]', 'loot_treasure', 'treasure', 1.0,
 'dragon_young',
 'Młody smok — wciąż groźniejszy niż cokolwiek, z czym większość bohaterów się spotkała.',
 'Oddech ognia, strach. Obrażenia od ognia.', 'permanent', 1),

('demon_lord',
 'Pan Demonów', 100, 18, 11, 3,
 '2d10', 'boss', 1, 3, 'magical',
 1800, '["poisoned","stunned","frightened"]', 'loot_treasure', 'treasure', 1.0,
 'lich',
 'Wielki demon przyzwany przez szalony kult. Ucieleśnienie destrukcji.',
 'Magiczne obrażenia, odporność na wiele stanów.', 'permanent', 1),

('iron_golem',
 'Golem Żelazny', 110, 19, 9, -2,
 '2d8', 'boss', 1, 3, 'physical',
 1200, '["poisoned","stunned","frightened","burning"]', 'loot_treasure', 'treasure', 1.0,
 NULL,
 'Golem z kutego żelaza — absurdalna obrona i niszczycielska siła. Powolny, ale niemal niezniszczalny.',
 'Odporny na truciznę, ogłuszenie, strach i podpalenie.', 'permanent', 1),

('ancient_troll',
 'Pradawny Troll', 80, 16, 9, 0,
 '2d6', 'boss', 1, 2, 'physical',
 900, '["poisoned"]', 'loot_treasure', 'treasure', 1.0,
 'troll',
 'Troll żyjący od stuleci — jego ciało rośnie i regeneruje się szybciej niż można je uszkodzić.',
 'Szybka regeneracja HP co turę. Odporny na truciznę.', 'permanent', 1);
