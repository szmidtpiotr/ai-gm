-- S5: Items seed (#493)
-- Depends on S1 (core mechanics baseline).
-- Table: game_config_items
-- Safe to re-run: INSERT OR IGNORE pattern.
-- Types: armor, gear, tool, misc, quest, material
-- allowed_classes uses: warrior / ranger / scholar
-- (ranger = rogue archetype in DB, ranger in ALLOWED_CLASSES in admin_config.py)

-- ── ARMOR (item_type = 'armor') ────────────────────────────────────────────
-- armor_coverage: torso | head | hands | feet | back | shield

INSERT OR IGNORE INTO game_config_items
    (key, label, item_type, description, value_gp, weight_kg,
     ac_bonus, armor_coverage, allowed_classes, charges,
     rarity, is_active, approved, ai_generated, review_status)
VALUES
    -- ── light armor ───────────────────────────────────────────────────────
    ('padded_armor',
     'Pikowana zbroja', 'armor',
     'Warstwa grubo pikowanej tkaniny z konopnym wypełnieniem. Tłumi cios maczugi, ale przed mieczem nie obroni.',
     5, 4.0, 1, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('leather_armor',
     'Skórzana zbroja', 'armor',
     'Garbowana skóra wołowa naszywana na lnianą podkładkę. Cicha i wygodna — ulubiona zbroja zwiadowców i łowców.',
     10, 5.0, 1, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('studded_leather',
     'Skóra ćwiekowana', 'armor',
     'Skórzana zbroja wzmocniona setkami żelaznych ćwieków. Brzęczy ledwo słyszalnie i chroni przed cięciami.',
     45, 6.0, 2, 'torso', '["warrior","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('hide_armor',
     'Zbroja ze skór', 'armor',
     'Surowe skóry zwierzęce zszyte i wzmocnione kośćmi. Cuchnie dziką zwierzyną, ale potrafi pochłonąć cios topora.',
     10, 6.5, 2, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('cloth_robes',
     'Szaty Uczonego', 'armor',
     'Luźne szaty z grubej wełny ze srebrnymi haftami runicznymi. Nie chronią ciała, ale pomagają skupić ducha podczas rzucania zaklęć.',
     8, 1.5, 0, 'torso', '["scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('wizard_robe',
     'Szata Maga', 'armor',
     'Ciężka jedwabna szata z wszytymi srebrnymi runami. Nie zatrzymuje miecza, ale pochłania część obrażeń magicznych.',
     75, 2.0, 1, 'torso', '["scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    -- ── medium armor ─────────────────────────────────────────────────────
    ('chainmail_shirt',
     'Koszulka kolcza', 'armor',
     'Krótka kolczuga sięgająca pasa, z rozcięciem do jazdy konnej. Zatrzymuje cięcia i większość pchnięć.',
     50, 9.0, 3, 'torso', '["warrior","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('scale_mail',
     'Łuskowa zbroja', 'armor',
     'Setki metalowych łusek naszytych na skórzaną podkładkę. Brzęczy przy każdym ruchu jak żmija.',
     70, 11.0, 3, 'torso', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('breastplate',
     'Napierśnik', 'armor',
     'Stalowa płyta chroniąca tors i brzuch, mocowana paskami. Nie ogranicza ruchów rąk.',
     80, 8.0, 3, 'torso', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('brigandine',
     'Brygantyna', 'armor',
     'Płócienna kamizelka z wszytymi w środku stalowymi płytkami. Wygląda zwyczajnie, chroni jak średnia zbroja.',
     90, 10.0, 3, 'torso', '["warrior","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    -- ── heavy armor ──────────────────────────────────────────────────────
    ('chain_hauberk',
     'Kolczuga długa', 'armor',
     'Pełna kolczuga sięgająca kolan z kapturem. Standardowa zbroja zawodowych zbrojnych — ciężka, ale niezawodna.',
     150, 16.0, 4, 'torso', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('half_plate',
     'Półpłytowa zbroja', 'armor',
     'Pełen pancerz z płyt stalowych chroniących tors, ramiona i uda. Brak ochrony nóg pozwala szybko biegać.',
     400, 18.0, 4, 'torso', '["warrior"]', 1,
     3, 1, 1, 0, 'permanent'),

    ('full_plate',
     'Pełna zbroja płytowa', 'armor',
     'Kompletna zbroja rycerska z setkami precyzyjnie dopasowanych płyt. Wymaga giermka do założenia i miesięcy treningu, by walczyć w niej zręcznie.',
     1500, 25.0, 5, 'torso', '["warrior"]', 1,
     3, 1, 1, 0, 'permanent'),

    -- ── helmets ───────────────────────────────────────────────────────────
    ('leather_cap',
     'Skórzany hełm', 'armor',
     'Prosty kaptur ze sztywnej skóry. Chroni przed wilgocią i lekkimi obrażeniami głowy.',
     3, 0.5, 0, 'head', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('iron_helm',
     'Hełm żelazny', 'armor',
     'Stożkowaty hełm z nosalem. Odbija ciosy z góry, choć ogranicza pole widzenia.',
     12, 1.8, 1, 'head', '["warrior"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('great_helm',
     'Hełm garnczkowy', 'armor',
     'Stalowy hełm zamknięty z wąskimi otworami na oczy. Chroni głowę całkowicie, ale tłumi słuch i głosy.',
     35, 3.5, 2, 'head', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('hooded_cloak',
     'Płaszcz z kapturem', 'armor',
     'Wełniany płaszcz z głębokim kapturem. Pomaga ukryć twarz w mieście i osłania przed deszczem.',
     5, 1.0, 0, 'head', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('silver_circlet',
     'Srebrny diadem', 'armor',
     'Cienki diadem ze srebra ozdobiony niewielkim turkusem. Skupia myśli kastującego, choć nie chroni głowy.',
     80, 0.2, 0, 'head', '["scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    -- ── gloves & boots ────────────────────────────────────────────────────
    ('leather_gloves',
     'Skórzane rękawice', 'armor',
     'Miękkie rękawiczki dobrze chroniące skórę dłoni. Pozwalają trzymać miecz bez ślizgania się rękojeści.',
     2, 0.3, 0, 'hands', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('plate_gauntlets',
     'Stalowe rękawice płytowe', 'armor',
     'Rękawice z metalowych płytek na skórzanej podkładce. Można w nich zacisnąć pięść i przyjąć cios mieczem na grzbiet dłoni.',
     40, 1.2, 1, 'hands', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('leather_boots',
     'Skórzane buty', 'armor',
     'Wysokie buty ze sznurowaniem. Wytrzymują dni marszu w błocie i kamienistych ścieżkach.',
     4, 1.0, 0, 'feet', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('soft_slippers',
     'Miękkie pantofle', 'armor',
     'Miękkie pantofle z owczej skóry. Pozwalają poruszać się bezgłośnie po deskach albo kamiennych korytarzach.',
     6, 0.3, 0, 'feet', '["ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('plate_sabatons',
     'Płytowe sabatony', 'armor',
     'Stalowe buty rycerskie z ostrymi noskami. Ciężkie, ale można nimi kopnąć tak, że pęka kolano.',
     50, 2.5, 1, 'feet', '["warrior"]', 1,
     2, 1, 1, 0, 'permanent'),

    -- ── mantles/cloaks ────────────────────────────────────────────────────
    ('travelers_cloak',
     'Płaszcz podróżnika', 'armor',
     'Wełniany płaszcz nasycony oliwą — chroni przed deszczem i wiatrem podczas długiej drogi.',
     3, 1.5, 0, 'back', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('fur_mantle',
     'Mantia z futra', 'armor',
     'Gruba mantia uszyta z futra wilka. Niezbędna podczas zimowych wypraw na północ.',
     25, 2.5, 0, 'back', '["warrior","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

-- ── GEAR (item_type = 'gear') ───────────────────────────────────────────────

    ('rope_hemp',
     'Lina konopna 15m', 'gear',
     'Pleciona lina z konopi, długości piętnastu metrów. Niezbędna przy wspinaczce, krępowaniu więźniów i tysiącu innych zastosowań.',
     1, 4.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('grappling_hook',
     'Hak z linką', 'gear',
     'Żelazny hak z trzema zębami na pięciometrowej lince. Zarzucony na mur z trzeciej próby — zazwyczaj się trzyma.',
     2, 1.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('climbing_kit',
     'Zestaw wspinaczkowy', 'gear',
     'Hak, kliny, młotek i kawałek liny w skórzanej torbie. Pozwala wejść tam, gdzie mury wyglądają na nie do zdobycia.',
     25, 5.5, 0, 'torso', '["warrior","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('torch',
     'Pochodnia', 'gear',
     'Pakuł nasycony smołą na drewnianym kiju. Płonie godzinę silnym, dymiącym płomieniem.',
     1, 0.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('lantern_hooded',
     'Latarnia z zasłoną', 'gear',
     'Mosiążna latarnia ze szklanymi ścianami i metalową zasłoną. Pozwala kontrolować, gdzie pada światło.',
     7, 1.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('oil_flask',
     'Bańka oleju', 'gear',
     'Gliniana bańka pełna lampowego oleju. Zasili latarnię na sześć godzin, albo zapali wroga, jeśli rozbije się o niego.',
     1, 0.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('mirror_small',
     'Małe lusterko', 'gear',
     'Polerowane stalowe lusterko w drewnianej oprawie. Można sprawdzić, co czai się za rogiem, nie wystawiając głowy.',
     5, 0.1, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('tinderbox',
     'Hubka z krzesiwem', 'gear',
     'Mały skórzany etui z krzesiwem, hubką i suchą podpałką. Pozwala rozpalić ogień — nawet w deszczu, jeśli ma się wprawę.',
     1, 0.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('bedroll',
     'Posłanie', 'gear',
     'Skręcony siennik i koc. Wystarczy znaleźć kawałek równej ziemi, by przespać nawet w lesie.',
     1, 3.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('caltrops_bag',
     'Woreczek kolczastek', 'gear',
     'Woreczek żelaznych kolców rozsypanych na ścieżce — kaleczy stopy ścigających. Wystarczy na trzy użycia.',
     5, 1.0, 0, 'torso', '["warrior","ranger"]', 3,
     1, 1, 1, 0, 'permanent'),

    ('manacles',
     'Kajdany', 'gear',
     'Ciężkie żelazne kajdany z kluczykiem. Krępują nadgarstki dorosłego człowieka — z byle wprawnym łotrzykiem mają większy kłopot.',
     2, 2.5, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('parchment_sheets',
     'Arkusze pergaminu 10szt', 'gear',
     'Dziesięć starannie wygładzonych arkuszy pergaminu. Na każdym można narysować mapę albo zapisać list.',
     5, 0.3, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('spyglass',
     'Luneta', 'gear',
     'Mosiężna luneta z trzema soczewkami. Pozwala dostrzec sztandar wroga z połowy mili.',
     1000, 1.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     3, 1, 1, 0, 'permanent'),

    ('hourglass',
     'Klepsydra', 'gear',
     'Szklana klepsydra w drewnianej oprawie. Piasek przesypuje się dokładnie godzinę — w pewnych miejscach szybciej lub wolniej.',
     25, 1.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('noble_garb',
     'Strój szlachecki', 'gear',
     'Ubranie z bogatego sukna z futrzanym kołnierzem. Pozwala wejść tam, gdzie miecz by tylko sprowokował straże.',
     75, 2.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('merchant_garb',
     'Strój kupiecki', 'gear',
     'Solidne, dyskretne ubranie z dobrego sukna. Idealny przebranie dla zwiadu w mieście.',
     15, 2.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('iron_spikes_10',
     'Żelazne kliny 10szt', 'gear',
     'Dziesięć żelaznych klinów do podpierania drzwi, blokowania zamków i wbijania w skałę przy wspinaczce.',
     1, 2.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('hunting_horn',
     'Róg myśliwski', 'gear',
     'Polerowany róg bydlęcy z mosiężnym ustnikiem. Słychać go na pół godziny marszu — zbiera kompanów albo zwołuje wroga.',
     15, 0.8, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('lute',
     'Lutnia', 'gear',
     'Drewniana lutnia z sześcioma strunami. W rękach barda potrafi otworzyć drzwi, na które miecz nie ma rady.',
     35, 2.0, 0, 'torso', '["scholar","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

-- ── TOOLS (item_type = 'tool') ───────────────────────────────────────────────

    ('lockpicks',
     'Wytrychy', 'tool',
     'Zestaw cienkich, hartowanych haczyków w skórzanym etui. W rękach łotrzyka otwierają drzwi szybciej niż prawdziwy klucz.',
     25, 0.1, 0, 'torso', '["ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('crowbar',
     'Łom', 'tool',
     'Stalowy pręt z rozdwojonym końcem. Otworzy zamknięte drzwi, podważy kamień grobowy albo rozłupie czaszkę.',
     2, 2.5, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('shovel',
     'Łopata', 'tool',
     'Solidna łopata z drewnianym trzonkiem. Wykopie schron, grób, albo zakopany skarb.',
     2, 2.5, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('whetstone',
     'Osełka', 'tool',
     'Szary kamień do ostrzenia ostrzy. Tępy miecz to martwy miecz — każdy zawodowiec o tym wie.',
     1, 0.5, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('hammer_small',
     'Mały młotek', 'tool',
     'Stalowy młotek z drewnianym trzonkiem. Wbije gwóźdź, klin lub piszczel.',
     1, 1.0, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('chisel',
     'Dłuto', 'tool',
     'Ostre stalowe dłuto. Przydatne kamieniarzowi, włamywaczowi i każdemu, kto chce zostawić znak na ścianie.',
     1, 0.3, 0, 'torso', '["ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('fishing_rod',
     'Wędka', 'tool',
     'Prosta wędka z włókna lnianego. Cierpliwy rybak zdoła nią wyciągnąć kolację z byle strumienia.',
     2, 1.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('ink_quill_set',
     'Atrament z piórem', 'tool',
     'Buteleczka czarnego atramentu i trzy zaostrzone pióra. Niezbędne, by spisać kontrakt, list albo proroctwo.',
     3, 0.2, 0, 'torso', '["scholar","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('fishing_net',
     'Sieć rybacka', 'tool',
     'Pleciona sieć z węzłami co dłoń. Łapie ryby, ale w razie potrzeby unieruchomi też zaskoczonego przeciwnika.',
     4, 2.0, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

-- ── MISC (item_type = 'misc') ────────────────────────────────────────────────

    ('backpack',
     'Plecak', 'misc',
     'Pojemny skórzany plecak na ramiączkach. Mieści zapas żywności na tydzień, koc i drobny ekwipunek.',
     2, 2.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('belt_pouch',
     'Sakiewka przy pasie', 'misc',
     'Skórzana sakiewka mocowana do pasa. Mieści garść monet i parę drobiazgów.',
     1, 0.3, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('waterskin',
     'Bukłak', 'misc',
     'Skórzany bukłak na cztery litry wody albo wina. Nieoceniony na pustkowiu.',
     1, 2.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('small_chest',
     'Mała szkatuła', 'misc',
     'Drewniana szkatuła okuta żelazem, zamykana na zameczek. Mieści sto sztuk złota lub kilka cennych precjozów.',
     5, 6.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('satchel',
     'Torba listonosza', 'misc',
     'Skórzana torba na ramię z kilkoma przegródkami. Dobra na zwoje, mapy i drobny ekwipunek alchemika.',
     3, 1.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('dice_set',
     'Komplet kości', 'misc',
     'Cztery kostki rzeźbione z kości. Mogą wciągnąć w grę przy każdym ognisku — a niektórzy mówią, że są obciążone.',
     1, 0.1, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('incense_bundle',
     'Pęczek kadzideł', 'misc',
     'Wiązka pachnących mirry i żywicy paliw. Spalone w komnacie odpędzają smród trupów — i czasem zwabiają duchy.',
     3, 0.2, 0, 'torso', '["scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

-- ── QUEST items (item_type = 'quest') ───────────────────────────────────────

    ('ancient_scroll',
     'Starożytny zwój', 'quest',
     'Pergamin pociemniały od wieków, zapisany pismem, którego dawno nikt nie używa. Może opisuje skarb, klątwę albo proroctwo.',
     50, 0.2, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('family_locket',
     'Rodzinny medalion', 'quest',
     'Srebrny medalion z miniaturą kobiety i dziecka. Po wewnętrznej stronie wygrawerowano dwie litery, których właściciel nie pamięta.',
     30, 0.05, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('signet_ring',
     'Pierścień herbowy', 'quest',
     'Złoty pierścień z grawerowanym wizerunkiem trzymającego miecz gryfa. Pozwala podszyć się pod członka rodu — albo ściągnąć jego wrogów.',
     60, 0.05, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('treasure_map',
     'Mapa skarbu', 'quest',
     'Wytarta mapa narysowana na skrawku skóry. X zaznaczono w głębi lasu, ale ścieżki dawno zarosły mchem.',
     25, 0.1, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('holy_symbol',
     'Symbol święty', 'quest',
     'Drewniany lub srebrny symbol bóstwa zawieszony na łańcuszku. Daje pocieszenie w mroku i — czasami — odpędza złe rzeczy.',
     5, 0.3, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('golden_idol',
     'Złoty bożek', 'quest',
     'Mały złoty posążek bezimiennego bóstwa z dziwnymi oczyma. Im dłużej się go niesie, tym cięższy się wydaje.',
     500, 1.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     3, 1, 1, 0, 'permanent'),

    ('demon_skull',
     'Czaszka demona', 'quest',
     'Czarna jak smoła czaszka z trzema oczodołami i parą zakrzywionych rogów. Cuchnie siarką, choć minęły lata, odkąd jej właściciel zginął.',
     200, 2.5, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     3, 1, 1, 0, 'permanent'),

-- ── MATERIALS (item_type = 'material') ───────────────────────────────────────

    ('iron_ore',
     'Ruda żelaza', 'material',
     'Ciężki kamień z żyłkami metalu. Kowal przetopi go na kilogram żelaza — surowiec do broni, zbroi i narzędzi.',
     3, 2.0, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('wolf_pelt',
     'Skóra wilka', 'material',
     'Surowa skóra czarnego wilka z głową i pazurami. Można ją sprzedać kupcom albo udowodnić nią zabicie bestii.',
     8, 3.0, 0, 'torso', '["warrior","ranger"]', 1,
     1, 1, 1, 0, 'permanent'),

    ('bear_hide',
     'Skóra niedźwiedzia', 'material',
     'Gruba, kudłata skóra brunatnego niedźwiedzia. Z ośmiu kilogramów futra można uszyć zbroję ze skór lub ciepłą mantię.',
     20, 8.0, 0, 'torso', '["warrior","ranger"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('alchemical_reagent',
     'Odczynnik alchemiczny', 'material',
     'Skórzana torba z precyzyjnie odmierzonymi proszkami i olejkami. Niezbędny do warzenia mikstury lub trwałego napisu runami.',
     15, 0.5, 0, 'torso', '["scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('dragon_scale_shard',
     'Łuska smocza', 'material',
     'Jeden z pancernych łusek zdobytych ze skóry małego smoka. Niemal niezniszczalna — poszukiwana przez kowali i alchemików.',
     250, 0.3, 0, 'torso', '["warrior","ranger","scholar"]', 1,
     3, 1, 1, 0, 'permanent'),

    ('bone_dust',
     'Proch z kości', 'material',
     'Drobny proszek starych kości, zbierany na polach bitew lub cmentarzyskach. Składnik czarnej magii i pewnych eliksirów.',
     10, 0.2, 0, 'torso', '["scholar"]', 1,
     2, 1, 1, 0, 'permanent'),

    ('silk_thread',
     'Nić jedwabna', 'material',
     'Rolka cienkiej jedwabnej nici z południa. Szewc uszyje z niej niewidzialny szew; alchemik użyje jako składnika filtru.',
     5, 0.1, 0, 'torso', '["ranger","scholar"]', 1,
     1, 1, 1, 0, 'permanent');
