#!/usr/bin/env python3
"""CB-6 — zawartość bojowa i „żywa" Czarnoboru: wrogowie + spotkania + plotki + loch.

Źródło prawdy: docs/world/regions/czarnobor.md §1–§8 + charakter pul ustalony w
zadaniu CB-6. Wzorzec 1:1: scripts/seed_siwe_granie_bestia.py (SG-6b #1481).

CO CZYTA SILNIK (żeby treść nie była martwym wpisem w adminie):
  * `game_config_enemies` → `encounter_service.eligible_enemy_pool()` (kompozytor,
    ~50% spotkań) — filtry: world_scope, review_status, is_active, pasmo poziomów,
    `terrain_tags` vs teren hexa oraz `region_tag` vs kraina hexa,
  * `game_config_encounters` → `encounter_catalog_service.draw_combat()` (drugie ~50%)
    — filtry: kind/biome/poziom oraz `region_tag`,
  * `world_rumors` → `world_rumor_service.draw_for_region()` w `rumor_service` —
    pula regionu ma pierwszeństwo przed plotką generowaną per bohater,
  * `game_dungeons` → farmowalny loch (Utopiona Wieś).

TERENY (CB-1 #Czarnobór): `biome` w katalogu spotkań = WPROST `world_hexes.hex_type`
(forest / czarny_las / trzesawisko / swamp / step / heath / road). Wrogowie mają
uboższy słownik `terrain_tags`, na który hex_type jest mapowany w encounter_service
`_HEX_TYPE_TO_TERRAIN`: czarny_las→forest, trzesawisko→swamp, step→plains. Dlatego
wrogom nadajemy tagi ze starego słownika (forest/swamp/plains), a scenom — realne
hex_type krainy.

SMACZEK WARDÓW (§6): działający ward = spokój. Silnik podróży (#1390) traktuje jawne
`encounter_chance = 0` na hexie jako świadomą STREFĘ BEZPIECZNĄ (teren nie nadpisuje
zera). Nastrajany Szept Koron (hub elfów, Aerlin pielęgnuje wardy) dostaje wokół
siebie pierścień spokoju. Milczące Drzewa (wygasłe wardy) NIE są bezpieczne —
zostają groźne, bo to one są zagrożeniem.

WARTOŚCI STARTOWE (Numbers Policy): staty wrogów, `weight`/`level_*` scen, promień
strefy wardów, chance — wszystko strojlne w Sandboxie. Pasma pod bohatera 1–8 bez
inwersji tierów (#1376): weak < standard < elite < boss w wartości zagrożenia.

Idempotentny: INSERT OR IGNORE po kluczu; plotki po treści; strefa wardów nadpisuje
tylko wskazany pierścień. Seed jest źródłem prawdy pól „strojlnych" (content-as-code
#1202) — przy powtórce dociąga je do wartości z pliku.

    docker cp scripts/seed_czarnobor_bestia.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_bestia.py
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_bestia.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "czarnobor"

# ── 1. WROGOWIE ───────────────────────────────────────────────────────────────
# region_tag='czarnobor' → pojawiają się WYŁĄCZNIE w Czarnoborze (tożsamość krainy);
# globalni wrogowie (wolf, bandit, dark_elf, bagienny_topielec, wraith…) i tak
# dochodzą na pasującym terenie, więc te wpisy UZUPEŁNIAJĄ braki i dają smak.
# world_scope: 'global' = kompozytor bierze na pasującym terenie; 'pool' = tylko tam,
# gdzie autor wpisał klucz do world_hexes.encounter_pool / boss lochu.
ENEMIES: list[dict] = [
    # ── las / czarny_las (nawiedzony bór) ───────────────────────────────────
    dict(
        key="cien_boru", label="Cień Boru", tier="weak",
        hp=10, ac=12, atk=3, die="1d6", dmg=0, apt=1, xp=55,
        lvl=(1, 3), terrain="forest", scope="global", dmg_type="necrotic",
        desc="Wygasłe stróżowe drzewo nie umiera do końca — zostaje z niego cień, "
             "który sunie między pniami pod prąd światła. Nie goni. Czeka, aż "
             "sam podejdziesz bliżej, niż trzeba.",
        loot=[("bone_dust", 60, 1, 2), ("alchemical_reagent", 25, 1, 1)], gold=(0, 3),
    ),
    dict(
        key="dzik_borowy", label="Dzik Borowy", tier="weak",
        hp=13, ac=12, atk=3, die="1d6", dmg=1, apt=1, xp=60,
        lvl=(1, 3), terrain="forest", scope="global", dmg_type="physical",
        desc="Stary odyniec o kłach żółtych jak próchno. W borze, gdzie zwierzyny "
             "coraz mniej, dziki zeszły do jednego szlaku — i bronią go jak stada.",
        loot=[("bear_hide", 55, 1, 1), ("healing_herb", 30, 1, 1)], gold=(0, 4),
    ),
    dict(
        key="mroczny_elf_lowca", label="Mroczny Elf Łowca", tier="standard",
        hp=22, ac=14, atk=6, die="1d8", dmg=1, apt=1, xp=150,
        lvl=(4, 7), terrain="forest", scope="global", dmg_type="physical",
        desc="Elf, który zamiast stroić pęknięcia, zaczął z nich brać wprost. Strzela "
             "z łuku z ciemności i cofa się, zanim opadnie cięciwa — poluje na "
             "tych, co weszli za głęboko w bór.",
        loot=[("silk_thread", 40, 1, 2), ("alchemical_reagent", 35, 1, 1),
              ("wolf_hide_cloak", 8, 1, 1)], gold=(3, 16),
    ),
    dict(
        key="mara_czarnodrzewna", label="Mara Czarnodrzewna", tier="elite",
        hp=31, ac=13, atk=6, die="1d8", dmg=1, apt=1, xp=190,
        lvl=(5, 8), terrain="forest", scope="global", dmg_type="necrotic",
        desc="Tam, gdzie sczerniał cały okrąg drzew, cienie zlewają się w jeden — "
             "wysoki jak korona, gęsty jak smoła. Idzie za tobą tak długo, jak "
             "długo pamiętasz, że idzie.",
        loot=[("bone_dust", 60, 1, 3), ("alchemical_reagent", 30, 1, 1)], gold=(2, 12),
    ),
    # ── trzęsawisko / bagno (utopce, błotne bestie) ─────────────────────────
    dict(
        key="topielec_mielizny", label="Topielec z Mielizny", tier="standard",
        hp=16, ac=11, atk=4, die="1d6", dmg=0, apt=1, xp=92,
        lvl=(2, 5), terrain="swamp", scope="global", dmg_type="physical",
        desc="Ten, kto utonął w trzęsawisku, nie zawsze schodzi na dno. Wraca po "
             "mieliźnie, sino nabrzmiały, i wyciąga rękę do każdego, kto brnie "
             "brzegiem — nie po pomoc.",
        loot=[("healing_herb", 40, 1, 1), ("bone_dust", 35, 1, 2)], gold=(0, 8),
    ),
    dict(
        key="blotnik", label="Błotnik", tier="standard",
        hp=24, ac=12, atk=5, die="1d8", dmg=1, apt=1, xp=135,
        lvl=(3, 6), terrain="swamp", scope="global", dmg_type="physical",
        desc="Kupa mułu, korzeni i mgły, która wstaje z oczka wodnego, gdy staniesz "
             "za blisko. W mgle nie widać, gdzie się kończy — i to jest gorsze "
             "niż jego ciężar.",
        loot=[("alchemical_reagent", 50, 1, 2), ("antidote", 30, 1, 1)], gold=(1, 10),
    ),
    # ── step (watahy wilków, harpie) ────────────────────────────────────────
    dict(
        key="harpia_stepowa", label="Harpia Stepowa", tier="standard",
        hp=18, ac=13, atk=5, die="1d6", dmg=1, apt=1, xp=120,
        lvl=(3, 6), terrain="plains", scope="global", dmg_type="physical",
        desc="Nad stepem nie ma się gdzie schować przed cieniem, który zatacza koła. "
             "Harpie gnieżdżą się w kurhanach i spadają na to, co zostało samo "
             "z dala od ogniska.",
        loot=[("silk_thread", 45, 1, 2), ("bandage", 25, 1, 1)], gold=(2, 14),
    ),
    dict(
        key="wilk_stepowy_herszt", label="Wilk Stepowy Herszt", tier="elite",
        hp=28, ac=13, atk=5, die="1d8", dmg=2, apt=1, xp=170,
        lvl=(3, 6), terrain="plains", scope="global", dmg_type="physical",
        desc="Największy samiec wataszy, siwy na grzbiecie, z blizną przez pysk. To "
             "on decyduje, kiedy wataha przestaje kluczyć i zachodzi z trzech "
             "stron naraz. Kurhan Wilczego Króla okrąża, ale nigdy nie wchodzi.",
        loot=[("wolf_pelt", 75, 1, 2), ("fur_mantle", 20, 1, 1)], gold=(4, 22),
    ),
    # ── boss lochu (Utopiona Wieś) — pool: nie wychodzi na podróż ────────────
    dict(
        key="utopiony_wojt", label="Utopiony Wójt", tier="boss",
        hp=60, ac=14, atk=7, die="1d10", dmg=2, apt=1, xp=340,
        lvl=(5, None), terrain="swamp", scope="pool", dmg_type="necrotic",
        desc="Ostatni, który kazał wsi zostać, gdy woda już podchodziła pod progi. "
             "Została z nim — i on z nią. Dzierży wciąż pieczęć sołectwa, "
             "obrośniętą pijawkami, i wciąż zwołuje zmarłych na wiec.",
        loot=[("alchemical_reagent", 55, 1, 2), ("bone_dust", 40, 1, 3),
              ("wolf_hide_cloak", 10, 1, 1)], gold=(15, 55),
    ),
]

# ── 2. SPOTKANIA ──────────────────────────────────────────────────────────────
# (klucz, biome=hex_type, poziomy, waga, wrogowie[(key,nazwa,ile)], tytuł, scena)
# WAGI startowe: dzicz/bór/trzęsawisko/step 22–30, przedpola (heath) 22–25,
# TRAKT (road) 10–12 — droga ma być bezpieczniejsza od dziczy.
ENCOUNTERS: list[dict] = [
    # ── forest (1185 hexów) — zwykły bór: wilki, dziki, bandyci rzadcy ────────
    dict(key="cb_forest_wilki", biome="forest", lvl=(1, 4), w=30,
         enemies=[("wolf", "wilk", 2), ("dzik_borowy", "dzik borowy", 1)],
         title="Szlak zwierzyny",
         scene="Ścieżka zwierza schodzi się z twoją dokładnie tam, gdzie las gęstnieje. "
               "Coś już na niej stało — i wciąż stoi, tyle że teraz patrzy na ciebie."),
    dict(key="cb_forest_cienie", biome="forest", lvl=(2, 5), w=24,
         enemies=[("cien_boru", "cień boru", 2)],
         title="Światło, które nie dochodzi",
         scene="Między pniami robi się ciemniej, choć słońce nie zaszło. Dwa cienie "
               "suną pod prąd tej ciemności, prosto ku tobie."),
    dict(key="cb_forest_bandyci", biome="forest", lvl=(2, 5), w=20,
         enemies=[("bandit", "leśny rzezimieszek", 2)],
         title="Ognisko za wykrotem",
         scene="Dym idzie nisko między drzewami — ktoś, kto nie chce być widziany "
               "z daleka. Przy ogniu dwóch, i obaj już wiedzą, że nadchodzisz."),
    dict(key="cb_forest_elfy", biome="forest", lvl=(4, 7), w=20,
         enemies=[("mroczny_elf_lowca", "mroczny elf łowca", 1), ("dark_elf", "mroczny elf", 1)],
         title="Cięciwa w ciemności",
         scene="Pierwsza strzała mija cię o dłoń i wbija się w pień. Nie zobaczysz, "
               "skąd padła — mroczne elfy strzelają i cofają się, zanim opadnie łuk."),
    # ── czarny_las (243 hexy) — wygasły okrąg, nieumarli i mroczne elfy ───────
    dict(key="cb_czarnylas_cienie", biome="czarny_las", lvl=(2, 5), w=28,
         enemies=[("cien_boru", "cień boru", 2)],
         title="Smoliste pnie",
         scene="Pnie są tu czarne jak po pożarze, którego nie było. Z każdego zsuwa "
               "się cień i żaden nie rzuca go na ziemię — bo są cieniem same."),
    dict(key="cb_czarnylas_mara", biome="czarny_las", lvl=(5, 8), w=24,
         enemies=[("mara_czarnodrzewna", "mara czarnodrzewna", 1), ("cien_boru", "cień boru", 1)],
         title="Cień wysoki jak korona",
         scene="Ciemność przed tobą ma kształt — wysoki, gęsty, rosnący. Kiedy "
               "przystajesz, ona rośnie dalej, jakby karmiła się tym, że ją widzisz."),
    dict(key="cb_czarnylas_nieumarli", biome="czarny_las", lvl=(3, 6), w=22,
         enemies=[("wraith", "widmo boru", 1), ("skeleton", "kość spod korzeni", 2)],
         title="Coś się wygrzebuje spod korzeni",
         scene="Ziemia między czarnymi pniami rusza się w kilku miejscach naraz. "
               "Najpierw dłonie, potem reszta — bór oddaje to, co przyjął."),
    dict(key="cb_czarnylas_elfy", biome="czarny_las", lvl=(4, 7), w=22,
         enemies=[("mroczny_elf_lowca", "mroczny elf łowca", 1), ("dark_elf", "mroczny elf", 1)],
         title="Straż wygnańców",
         scene="Tu, w głębi wygasłego okręgu, mroczne elfy czują się jak u siebie. "
               "Nie ostrzegają. Pierwsze, co usłyszysz, to świst cięciwy."),
    # ── swamp (256 hexów) — bagno przy trzęsawiskach ────────────────────────
    dict(key="cb_swamp_topielce", biome="swamp", lvl=(2, 5), w=28,
         enemies=[("topielec_mielizny", "topielec z mielizny", 2)],
         title="Ręce z mielizny",
         scene="Brzeg jest grząski, a woda zbyt spokojna. Z płycizny podnoszą się "
               "dwie sylwetki, sine i nabrzmiałe, i wyciągają ku tobie ręce."),
    dict(key="cb_swamp_blotniki", biome="swamp", lvl=(3, 6), w=25,
         enemies=[("blotnik", "błotnik", 1), ("slime", "kożuch bagienny", 1)],
         title="Oczko, które wstaje",
         scene="Mijasz oczko wodne i muł na jego brzegu zaczyna się unosić. Nie wiatr "
               "— to on wstaje, ociekając korzeniami i wodą."),
    # ── trzesawisko (201 hexów) — utopce, błotne bestie, mgła ────────────────
    dict(key="cb_trzesawisko_topielce", biome="trzesawisko", lvl=(3, 6), w=28,
         enemies=[("topielec_mielizny", "topielec", 2), ("blotnik", "błotnik", 1)],
         title="Mgła zna twoje imię",
         scene="Mgła kładzie się do pasa i tłumi każdy dźwięk oprócz jednego: chlupotu, "
               "który idzie za tobą. Kiedy przystajesz, chlupot też przystaje — "
               "o krok za blisko."),
    dict(key="cb_trzesawisko_mgla", biome="trzesawisko", lvl=(2, 5), w=24,
         enemies=[("blotnik", "błotnik", 1), ("pijawczy_roj", "pijawczy rój", 1)],
         title="Coś się rusza pod powierzchnią",
         scene="Woda przy twoich stopach mętnieje i wrze drobnymi bąbelkami. Z mgły "
               "przed tobą wyłania się kształt, a spod niej — druga rzecz, mniejsza "
               "i głodniejsza."),
    dict(key="cb_trzesawisko_utopiec", biome="trzesawisko", lvl=(6, 9), w=22,
         enemies=[("bagienny_topielec", "bagienny topielec", 1)],
         title="To nie kłoda",
         scene="Kłoda dryfująca w mgle jest za duża i płynie pod prąd. Prostuje się, "
               "gdy jesteś w połowie brodu, i okazuje się, że ma twarz."),
    # ── step (351 hexów) — watahy wilków, harpie ────────────────────────────
    dict(key="cb_step_wataha", biome="step", lvl=(2, 5), w=30,
         enemies=[("wilk_stepowy", "wilk stepowy", 2), ("wilk_stepowy_herszt", "herszt wataszy", 1)],
         title="Wataha na horyzoncie",
         scene="Na stepie widać daleko — dlatego widzisz je od dawna. Szły równolegle "
               "do ciebie, a teraz siwy na grzbiecie skręca watahę wprost na ciebie."),
    dict(key="cb_step_watahaduza", biome="step", lvl=(4, 7), w=22,
         enemies=[("wilk_stepowy", "wilk stepowy", 3), ("wilk_stepowy_herszt", "herszt wataszy", 1)],
         title="Zejście z trzech stron",
         scene="Nie liczyłeś ich dobrze. Za pierwszą linią jest druga, a herszt "
               "trzyma się z tyłu i czeka, aż złamie się twój krąg."),
    dict(key="cb_step_harpie", biome="step", lvl=(3, 6), w=25,
         enemies=[("harpia_stepowa", "harpia stepowa", 2)],
         title="Cień, który zatacza koła",
         scene="Cień przechodzi po trawie trzeci raz i za każdym razem niżej. "
               "Kurhan po lewej roi się od piór — to stamtąd spadają."),
    # ── heath (147 hexów) — przedpola, wrzosowiska ──────────────────────────
    dict(key="cb_heath_wilki", biome="heath", lvl=(1, 4), w=25,
         enemies=[("wolf", "wilk", 2)],
         title="Ślad we wrzosie",
         scene="Wrzos jest wysoki i głuszy kroki — twoje i ich. Dlatego usłyszysz "
               "je dopiero wtedy, gdy będą tuż-tuż."),
    dict(key="cb_heath_dziki", biome="heath", lvl=(1, 4), w=22,
         enemies=[("dzik_borowy", "dzik borowy", 2)],
         title="Ryja w zaroślach",
         scene="Zarośla po prawej pękają z chrzęstem. Dwa odyńce wypadają na ścieżkę "
               "i staje ci na drodze coś, co nie zamierza ustąpić."),
    # ── road (101 hexów) — trakt: najniższe wagi, bezpieczniej ───────────────
    dict(key="cb_road_wilk", biome="road", lvl=(1, 4), w=12,
         enemies=[("wolf", "wilk", 1)],
         title="Wilk przy trakcie",
         scene="Pojedynczy wilk siedzi na pniaku przy drodze i patrzy, jak przechodzisz. "
               "Gdy mijasz go o dziesięć kroków, rusza za tobą."),
    dict(key="cb_road_bandyci", biome="road", lvl=(3, 6), w=12,
         enemies=[("brigand", "rozbójnik z traktu", 2)],
         title="Myto na Zarośniętym Trakcie",
         scene="Na trakcie leży zwalone drzewo, za dobrze ułożone, żeby padło samo. "
               "Zza niego wychodzi dwóch i pyta uprzejmie, ile masz przy sobie."),
    dict(key="cb_road_topielec", biome="road", lvl=(2, 5), w=10,
         enemies=[("topielec_mielizny", "topielec", 1)],
         title="Trakt idzie przez bród",
         scene="Stary imperialny trakt nurza się tu w rozlewisku. W miejscu, gdzie "
               "woda sięga po kolana, coś czeka, żebyś wszedł."),
]

# ── 3. PLOTKI ─────────────────────────────────────────────────────────────────
# truth_flag=1 → plotka prawdziwa (kanon). Tajemnice krainy zostają PYTANIAMI:
# DLACZEGO gasną stróżowe drzewa i co wyrosło pod Pradrzewem — bez odpowiedzi.
RUMORS: list[tuple[str, int, str | None, str | None]] = [
    ("Kolejne stróżowe drzewo zgasło tej wiosny — pień sczerniał jak smoła w jedną "
     "noc. Aerlin ze Strojni mówi, że gasną coraz szybciej, i nikt nie umie "
     "powiedzieć, czemu.", 1, "location", "milczace_drzewo_1"),
    ("Drwale z zachodniego skraju ścięli w zeszłym roku trzy drzewa, o których elfy "
     "mówią, że były żywe. Starosta Hagen powiada: dla nas to belki, dla nich "
     "świętość — a rodziny trzeba wykarmić.", 1, "location", "oboz_drwali"),
    ("Wilki okrążają Kurhan Wilczego Króla całymi watahami, ale żaden zwierz nie "
     "wejdzie na sam kopiec. Coś tam leży od czasów przed elfami i nawet herszt "
     "trzyma się z daleka.", 1, "location", "kurhan_wilczego_krola"),
    ("Stary imperialny trakt na południe zjadł las tak, że po dwóch dniach marszu "
     "gubisz go pod korzeniami. Pytanie nie brzmi, dokąd wiódł — tylko czemu "
     "Imperium go porzuciło.", 1, "location", "zarosniety_trakt"),
    ("Mówią, że wszystkie ścieżki w głąb boru w końcu zawracają w stronę jednego "
     "miejsca — i że tam strach robi się tak gęsty, że nogi same skręcają w bok. "
     "Nikt, kto tam doszedł, nie umie powiedzieć, co widział.", 1, "location", "czarne_serce"),
    ("W Utopionej Wsi za trzęsawiskiem woda podeszła pod progi jednej jesieni i już "
     "nie odeszła. Ludzie zostali. Podobno wójt do dziś zwołuje ich na wiec — "
     "tyle że wszyscy dawno na dnie.", 1, "dungeon", "utopiona_wies"),
    ("Część elfów uznała strojenie pęknięć za niewolę i zaczęła brać moc wprost. "
     "Odeszli w głąb boru i na południe — to dzisiejsze mroczne elfy. Strzelają "
     "z ciemności i nie ostrzegają.", 1, None, None),
    ("Na Polanie Schizmy, gdzie doszło do rozłamu, trawa rośnie czarna, a elfy tam "
     "nie chodzą. Powiadają, że ziemia pamięta, kto pierwszy rozdarł ward.",
     1, "location", "polana_schizmy"),
    ("Stare Gniazdo, pierwsza osada elfów, stoi opuszczone w sercu Boru Zmarłych — "
     "porzucili je, gdy drzewa wokół sczerniały. Kto tam dziś zajdzie, wraca "
     "z niczym albo nie wraca.", 1, "location", "stare_gniazdo"),
    ("Bór Zmarłych rośnie z roku na rok ku Kresom — czarne pnie podchodzą pod samą "
     "granicę. Po tamtej stronie siedzi Birkenwald i patrzy, jak las czernieje "
     "w jego stronę.", 1, "location", "bor_zmarlych"),
    ("Smolarze ze Smolarni na Palach warzą dziegieć czarnodrzewny — smarowidło, co "
     "maskuje zapach. Łowcy powiadają, że posmarowany nim przejdziesz przez bór, "
     "a żadna bestia cię nie zwietrzy.", 1, None, None),
    ("Każde z Milczących Drzew ma swoją historię i żadna nie kończy się dobrze. "
     "Elfy podchodzą do nich pojedynczo, kładą dłoń na czarnej korze i długo "
     "milczą, jakby czegoś słuchały.", 1, "location", "milczace_drzewo_2"),
    ("W Szepcie Koron obcych puszczają tylko do Gościnnego Drzewa — jednego miejsca, "
     "gdzie wolno przenocować. Dalej w koronach elfy nie wpuszczają nikogo, "
     "a nazwy swoich miejsc trzymają dla siebie.", 1, "location", "szept_koron"),
]

# ── 4. LOCH: Utopiona Wieś ────────────────────────────────────────────────────
# Farmowalny loch kafelkowy (§4, #1507 lochy krain). Wejście = enter_dungeon_tiles
# WYMAGA `tile_category_key` (inaczej 409) — dlatego loch dostaje DEDYKOWANĄ kategorię
# kafli `utopiona_wies` z własnymi kaflami niosącymi wrogów z puli krainy (topielce,
# błotniki, bagienna fauna) i bossem `utopiony_wojt`. Kafle bez obrazków (jak
# smoke_engine — działają, UI pokaże placeholder); grafiki FLUX .170 = osobny follow-up.
DUNGEON = dict(
    key="utopiona_wies", label="Utopiona Wieś", location_key="utopiona_wies",
    rooms=6, tile_category_key="utopiona_wies", tile_count=6, boss_tile_id=None,
    enemy_pool=["topielec_mielizny", "blotnik", "slime", "pijawczy_roj", "zombie"],
    boss_enemy="utopiony_wojt", loot_tier="rich", cooldown_hours=48, min_level=3,
    atmosphere=("Chaty po dachy w brunatnej wodzie, mgła gęsta jak mleko, chlupot "
                "kroków, których nie stawiasz ty. Gdzieś z głębi wsi bije stłumiony "
                "dzwon — ktoś wciąż zwołuje na wiec."),
    room_types_json='{"combat":55,"chest":15,"trap":10,"riddle":10,"rest":10}',
    dungeon_difficulty=2, room_loot_chance=0.15, rest_heal_pct=20, rest_charges=2,
)

# Kategoria kafli lochu — base_prompt/system_prompt gotowe pod przyszłą generację
# grafik (FLUX .170), teraz kafle idą bez obrazków.
TILE_CATEGORY = dict(
    key="utopiona_wies", label="Utopiona Wieś", sort_order=70,
    description="Ludzka wieś pochłonięta przez trzęsawisko — chaty po dachy w wodzie, "
                "mgła nad rozlewiskiem, utopce wśród zatopionych zabudowań.",
    style_modifier=("flooded drowned village, half-submerged wooden cottages, brown "
                    "stagnant swamp water, thick low fog, rotting fences and jetties, "
                    "reeds and duckweed, waterlogged bog aesthetic, murky and desolate"),
    system_prompt=("Opisujesz pomieszczenie w Utopionej Wsi — ludzkiej osadzie "
                   "pochłoniętej przez trzęsawisko. Skup się na brunatnej wodzie po "
                   "kolana, zatopionych chatach, gnijących płotach i pomostach, mgle, "
                   "trzcinie, chlupocie i zapachu mułu. Opis po polsku, 2-3 zdania "
                   "klimatyczne, zmysłowe."),
    base_prompt=("flooded drowned swamp village chamber seen from directly straight "
                 "above, half-submerged rotting wooden cottage walls forming the "
                 "irregular boundary of the room, brown stagnant water covering the "
                 "floor, sunken planks and broken furniture, reeds and duckweed, "
                 "rotting jetty boards, 2-3 open water channels leading off the edges "
                 "as passages, thick low fog, murky green-brown lighting, painted "
                 "tabletop RPG battlemap art style, high detail, strict top-down "
                 "orthographic overhead view, square map tile, 2D game art, NO "
                 "perspective, NO side view, flat overhead, no text, no UI"),
)

# Kafle: wszystkie z 4 drzwiami (trywialna spójność grafu). combat → enemies_cleared.
# (label, enemies[(key,count)], is_boss, items[(item_key,chance)], room_desc)
TILES: list[dict] = [
    dict(label="Zatopiona Grobla", enemies=[], boss=0, items=[],
         desc="Grobla znika pod brunatną wodą po kilku krokach. Dalej wieś stoi po "
              "dachy w rozlewisku, a mgła połyka jej krańce."),
    dict(label="Rozlane Podwórze", enemies=[("topielec_mielizny", 1)], boss=0, items=[],
         desc="Podwórze zamieniło się w staw. Coś sinego prostuje się z płycizny."),
    dict(label="Chata pod Wodą", enemies=[("topielec_mielizny", 2)], boss=0, items=[],
         desc="Przez okno zatopionej chaty widać ruch. Wychodzą tą samą drogą, "
              "którą kiedyś wchodzili do domu."),
    dict(label="Zapadła Stodoła", enemies=[("blotnik", 1)], boss=0, items=[],
         desc="Belki stodoły osunęły się w muł. Muł wstaje razem z nimi."),
    dict(label="Kożuch na Stawie", enemies=[("slime", 1), ("pijawczy_roj", 1)], boss=0, items=[],
         desc="Zielony kożuch na wodzie faluje, choć nie ma wiatru. Pod nim coś się rusza."),
    dict(label="Zalana Piwnica", enemies=[("zombie", 2)], boss=0, items=[],
         desc="Woda w piwnicy sięga pasa i śmierdzi. Z ciemności pod schodami "
              "wychlupują dwie sylwetki."),
    dict(label="Cmentarzyk na Kępie", enemies=[("topielec_mielizny", 1), ("zombie", 1)], boss=0, items=[],
         desc="Ostatnia sucha kępa to wiejski cmentarzyk. Krzyże przechylone, "
              "a ziemia między nimi rozgrzebana od środka."),
    dict(label="Mielizna Utopców", enemies=[("topielec_mielizny", 2), ("blotnik", 1)], boss=0, items=[],
         desc="Mielizna roi się od sinych rąk. Nie wiadomo, gdzie kończy się muł, "
              "a zaczyna topielec."),
    dict(label="Studnia Wiecu", enemies=[("blotnik", 1), ("topielec_mielizny", 1)], boss=0, items=[],
         desc="Wokół studni na rynku ktoś ustawił ławy. Woda w studni jest czarna "
              "i sięga po sam okap."),
    dict(label="Skrzynia Sołtysa", enemies=[], boss=0,
         items=[("alchemical_reagent", 1.0), ("bandage", 0.5)],
         desc="W izbie sołtysa stoi okuta skrzynia, wpół zanurzona, ale wciąż "
              "zamknięta. Ktoś jej pilnował do końca."),
    dict(label="Sucha Kępa", enemies=[], boss=0, items=[],
         desc="Skrawek twardego gruntu nad wodą, osłonięty trzciną. Można tu "
              "złapać oddech, zanim mgła znów cię znajdzie."),
    dict(label="Izba Wójta", enemies=[("utopiony_wojt", 1)], boss=1, items=[],
         desc="Największa chata we wsi, wciąż z resztką dachu. W progu stoi wójt — "
              "obrośnięty pijawkami, z pieczęcią sołectwa w spuchniętej dłoni."),
    dict(label="Wiec Utopionych", enemies=[("utopiony_wojt", 1), ("topielec_mielizny", 2)],
         boss=1, items=[],
         desc="Na zalanym rynku zebrała się cała wieś. Stoją w wodzie twarzami do "
              "chaty wójta i czekają, aż zabierze głos."),
    # Zaślepki (dead-end, 1 drzwi) — zamykają otwarte drzwi grafu (v2 grapher).
    dict(label="Ślepe Rozlewisko (N)", enemies=[], boss=0, items=[], doors=["N"],
         desc="Woda rozlewa się szeroko i nigdzie nie prowadzi. Ślepy zaułek wsi."),
    dict(label="Ślepe Rozlewisko (S)", enemies=[], boss=0, items=[], doors=["S"],
         desc="Trzcina zamyka drogę ścianą. Dalej tylko mgła i stojąca woda."),
    dict(label="Ślepe Rozlewisko (E)", enemies=[], boss=0, items=[], doors=["E"],
         desc="Zapadła chata blokuje przejście. Kąt, z którego nie ma wyjścia."),
    dict(label="Ślepe Rozlewisko (W)", enemies=[], boss=0, items=[], doors=["W"],
         desc="Grobla urywa się w toń. Krok dalej to już samo dno."),
]

# Prompt EN do generacji grafiki (interior; ściany/drzwi dokłada compositor).
TILE_IMAGE_PROMPTS: dict[str, str] = {
    "Zatopiona Grobla": "a submerged earthen causeway leading into the drowned village, water lapping over the muddy track, broken fence posts",
    "Rozlane Podwórze": "a flooded farmyard turned into a stagnant pond, a half-sunken wooden cart, floating planks",
    "Chata pod Wodą": "the interior of a half-submerged peasant cottage, brown water pouring through a broken shutter, floating debris and a drowned table",
    "Zapadła Stodoła": "a collapsed barn sunk into the mud, broken timber beams half-buried in bog water, scattered rotten hay",
    "Kożuch na Stawie": "a stagnant pond thickly covered in green duckweed scum, slow bubbles rising, tangled reeds",
    "Zalana Piwnica": "a flooded stone cellar, waist-deep murky black water, submerged wooden stairs and floating barrels",
    "Cmentarzyk na Kępie": "a tiny village graveyard on a dry hummock, tilted wooden crosses, freshly disturbed muddy graves, ringed by swamp water",
    "Mielizna Utopców": "a wide muddy bog shallows, clumps of reeds and dark sinkholes, pale drowned hands breaking the surface",
    "Studnia Wiecu": "a flooded village square with an old stone well at the center, wooden benches arranged around it, black still water",
    "Skrzynia Sołtysa": "a flooded village-elder's chamber, an iron-bound wooden chest sitting half-submerged, waterlogged shelves",
    "Sucha Kępa": "a small patch of dry raised ground amid the swamp, sheltered by tall reeds, a smoldering safe campfire spot",
    "Izba Wójta": "the largest village cottage with a partial remnant roof, a murky mud-caked seat of honor, ceremonial candles guttering on black water",
    "Wiec Utopionych": "a flooded village square meeting ground, water knee-deep, rows of empty wooden benches facing a headman's cottage, low fog",
    "Ślepe Rozlewisko (N)": "a wide dead-end backwater of stagnant swamp water, tall reeds closing off the far side, no exit",
    "Ślepe Rozlewisko (S)": "a dead-end swamp channel choked with reeds and duckweed, still black water, no way through",
    "Ślepe Rozlewisko (E)": "a sunken collapsed cottage blocking the way, dead-end pool of murky bog water",
    "Ślepe Rozlewisko (W)": "a causeway breaking off into deep dark open water, a dead-end drop into the mire",
}

# Wygenerowane grafiki (FLUX .170, kafle skompozytowane ze ścianami+drzwiami) —
# PNG zacommitowane w frontend/images/tiles/. Mapa label→URL relinkuje obrazki po
# reseedzie na czystej DB (image_url to string, niezależny od nowego id kafla).
TILE_IMAGE_FILES: dict[str, str] = {
    "Zatopiona Grobla": "/images/tiles/dungeon_tile_348_1784903367.png",
    "Rozlane Podwórze": "/images/tiles/dungeon_tile_349_1784903393.png",
    "Chata pod Wodą": "/images/tiles/dungeon_tile_350_1784903417.png",
    "Zapadła Stodoła": "/images/tiles/dungeon_tile_351_1784903442.png",
    "Kożuch na Stawie": "/images/tiles/dungeon_tile_352_1784903467.png",
    "Zalana Piwnica": "/images/tiles/dungeon_tile_353_1784903492.png",
    "Cmentarzyk na Kępie": "/images/tiles/dungeon_tile_354_1784903517.png",
    "Mielizna Utopców": "/images/tiles/dungeon_tile_355_1784903542.png",
    "Studnia Wiecu": "/images/tiles/dungeon_tile_356_1784903567.png",
    "Skrzynia Sołtysa": "/images/tiles/dungeon_tile_357_1784903591.png",
    "Sucha Kępa": "/images/tiles/dungeon_tile_358_1784903617.png",
    "Izba Wójta": "/images/tiles/dungeon_tile_359_1784903641.png",
    "Wiec Utopionych": "/images/tiles/dungeon_tile_360_1784903666.png",
    "Ślepe Rozlewisko (N)": "/images/tiles/dungeon_tile_361_1784903690.png",
    "Ślepe Rozlewisko (S)": "/images/tiles/dungeon_tile_362_1784903715.png",
    "Ślepe Rozlewisko (E)": "/images/tiles/dungeon_tile_363_1784903739.png",
    "Ślepe Rozlewisko (W)": "/images/tiles/dungeon_tile_364_1784903764.png",
}

# ── 5. STREFA WARDÓW: pierścień spokoju wokół Szeptu Koron ─────────────────────
# §6 smaczek: działający ward = spokój. Silnik (#1390) czyta jawne encounter_chance=0
# jako świadomą strefę bezpieczną. Szept Koron = hub, wardy nastrajane; pierścień
# promienia WARD_SAFE_RADIUS wokół (74,-12) dostaje chance=0. Milczące Drzewa
# (wygasłe wardy) NIE — zostają groźne.
WARD_HUB_HEX = (74, -12)     # szept_koron
WARD_SAFE_RADIUS = 2
_HEX_NEIGHBOURS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _hex_ring(center: tuple[int, int], radius: int = 1) -> list[tuple[int, int]]:
    out = {center}
    frontier = {center}
    for _ in range(radius):
        nxt = set()
        for q, r in frontier:
            for dq, dr in _HEX_NEIGHBOURS:
                nxt.add((q + dq, r + dr))
        out |= nxt
        frontier = nxt
    return sorted(out)


def seed_enemies(conn: sqlite3.Connection) -> dict:
    res = {"enemies": 0, "loot_tables": 0, "loot_entries": 0}
    for e in ENEMIES:
        lt_key = f"loot_{e['key']}"
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_loot_tables (key, label, description, "
            "gold_min, gold_max, is_active) VALUES (?, ?, '', ?, ?, 1)",
            (lt_key, f"Łupy: {e['label']}", int(e["gold"][0]), int(e["gold"][1])),
        )
        res["loot_tables"] += cur.rowcount
        for item_key, weight, qmin, qmax in e["loot"]:
            exists = conn.execute(
                "SELECT 1 FROM game_config_loot_entries WHERE loot_table_key = ? "
                "AND item_key = ?", (lt_key, item_key),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, "
                "qty_min, qty_max) VALUES (?, ?, ?, ?, ?)",
                (lt_key, item_key, int(weight), int(qmin), int(qmax)),
            )
            res["loot_entries"] += 1
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO game_config_enemies
                (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                 tier, attacks_per_turn, damage_bonus, damage_type, xp_award,
                 description, lore_text, terrain_tags, min_level, max_level,
                 world_scope, region_tag, loot_table_key, drop_chance,
                 review_status, created_by, is_active)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0,
                    'permanent', 'seed', 1)
            """,
            (e["key"], e["label"], e["hp"], e["ac"], e["atk"], e["die"], e["tier"],
             e["apt"], e["dmg"], e["dmg_type"], e["xp"], e["desc"], e["desc"],
             e["terrain"], e["lvl"][0], e["lvl"][1], e["scope"], REGION, lt_key),
        )
        res["enemies"] += cur.rowcount
        # Seed = źródło prawdy pól strojlnych (content-as-code #1202): przy powtórce
        # dociągamy je do wartości z pliku, nie zostawiając rozjazdu DB ↔ repo.
        conn.execute(
            "UPDATE game_config_enemies SET terrain_tags = ?, min_level = ?, max_level = ?, "
            "world_scope = ?, region_tag = ?, tier = ?, updated_at = datetime('now') "
            "WHERE key = ? AND created_by = 'seed'",
            (e["terrain"], e["lvl"][0], e["lvl"][1], e["scope"], REGION, e["tier"], e["key"]),
        )
    return res


def seed_encounters(conn: sqlite3.Connection) -> int:
    n = 0
    for enc in ENCOUNTERS:
        payload = {
            "title": enc["title"],
            "scene_setup": enc["scene"],
            "enemies": [
                {"enemy_key": k, "name": name, "count": cnt}
                for k, name, cnt in enc["enemies"]
            ],
        }
        cur = conn.execute(
            """INSERT OR IGNORE INTO game_config_encounters
               (key, kind, biome, level_min, level_max, weight, trigger_types,
                region_tag, payload_json, is_active, source, quality_rating, times_used)
               VALUES (?, 'combat', ?, ?, ?, ?, ?, ?, ?, 1, 'seed', 3, 0)""",
            (enc["key"], enc["biome"], enc["lvl"][0], enc["lvl"][1], float(enc["w"]),
             json.dumps(["hex_enter", "n_turns"]), REGION,
             json.dumps(payload, ensure_ascii=False)),
        )
        n += cur.rowcount
    return n


def seed_rumors(conn: sqlite3.Connection) -> int:
    n = 0
    for text, truth, ttype, tkey in RUMORS:
        exists = conn.execute(
            "SELECT 1 FROM world_rumors WHERE region = ? AND rumor_text = ?",
            (REGION, text),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO world_rumors (region, rumor_text, truth_flag, target_type, "
            "target_key, created_by, is_active) VALUES (?, ?, ?, ?, ?, 'seed', 1)",
            (REGION, text, int(truth), ttype, tkey),
        )
        n += 1
    return n


def seed_dungeon(conn: sqlite3.Connection) -> int:
    d = DUNGEON
    cur = conn.execute(
        """INSERT OR IGNORE INTO game_dungeons
           (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier,
            atmosphere, cooldown_hours, min_level, is_active, room_loot_chance,
            room_types_json, riddle_source, riddle_max_hints, dungeon_difficulty,
            rest_heal_pct, rest_charges, tile_category_key, tile_count, boss_tile_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'database', 2, ?, ?, ?, ?, ?, ?)""",
        (d["key"], d["label"], d["location_key"], d["rooms"],
         json.dumps(d["enemy_pool"]), d["boss_enemy"], d["loot_tier"],
         d["atmosphere"], d["cooldown_hours"], d["min_level"], d["room_loot_chance"],
         d["room_types_json"], d["dungeon_difficulty"], d["rest_heal_pct"],
         d["rest_charges"], d["tile_category_key"], d["tile_count"], d["boss_tile_id"]),
    )
    # Dociągnij pola strojlne przy powtórce (content-as-code).
    conn.execute(
        "UPDATE game_dungeons SET enemy_pool = ?, boss_enemy = ?, atmosphere = ?, "
        "min_level = ?, is_active = 1, tile_category_key = ?, tile_count = ? WHERE key = ?",
        (json.dumps(d["enemy_pool"]), d["boss_enemy"], d["atmosphere"],
         d["min_level"], d["tile_category_key"], d["tile_count"], d["key"]),
    )
    return cur.rowcount


def seed_dungeon_tiles(conn: sqlite3.Connection) -> dict:
    """Dedykowana kategoria kafli + kafle lochu Utopionej Wsi. Kafle bez obrazków
    (jak smoke_engine) — loch jest w pełni grywalny, grafiki = osobny follow-up.
    Idempotentny: kategoria INSERT OR IGNORE po kluczu, kafle po (category_key,label)."""
    res = {"category": 0, "tiles": 0}
    tc = TILE_CATEGORY
    cur = conn.execute(
        "INSERT OR IGNORE INTO dungeon_tile_categories (key, label, description, "
        "style_modifier, system_prompt, base_prompt, sort_order, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (tc["key"], tc["label"], tc["description"], tc["style_modifier"],
         tc["system_prompt"], tc["base_prompt"], tc["sort_order"]),
    )
    res["category"] += cur.rowcount
    for t in TILES:
        img_prompt = TILE_IMAGE_PROMPTS.get(t["label"], "")
        img_url = TILE_IMAGE_FILES.get(t["label"])
        exists = conn.execute(
            "SELECT 1 FROM dungeon_tiles WHERE category_key = ? AND label = ?",
            (tc["key"], t["label"]),
        ).fetchone()
        if exists:
            # Dociągnij prompt+obraz przy powtórce (content-as-code) — nie kasuj
            # istniejącego image_url, gdy nie mamy nowego.
            conn.execute(
                "UPDATE dungeon_tiles SET image_gen_prompt = ?, "
                "image_url = COALESCE(?, image_url) WHERE category_key = ? AND label = ?",
                (img_prompt, img_url, tc["key"], t["label"]),
            )
            continue
        enemies_json = json.dumps(
            [{"enemy_key": k, "count": n} for k, n in t["enemies"]]
        )
        items_json = json.dumps(
            [{"item_key": k, "chance": ch} for k, ch in t["items"]]
        )
        exit_cond = (
            json.dumps([{"type": "enemies_cleared"}]) if t["enemies"] else "[]"
        )
        doors_json = json.dumps(t.get("doors", ["N", "S", "E", "W"]))
        conn.execute(
            "INSERT INTO dungeon_tiles (category_key, label, doors_json, enemies_json, "
            "items_json, active_states_json, exit_conditions_json, room_description, "
            "image_gen_prompt, image_url, is_boss_tile, is_active) "
            "VALUES (?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?, 1)",
            (tc["key"], t["label"], doors_json, enemies_json,
             items_json, exit_cond, t["desc"], img_prompt, img_url, int(t["boss"])),
        )
        res["tiles"] += 1
    return res


def seed_ward_safe_zone(conn: sqlite3.Connection) -> int:
    """§6 — pierścień spokoju wokół nastrajanego huba wardów (Szept Koron).
    Jawne encounter_chance=0 = strefa bezpieczna (#1390 nie nadpisuje zera terenem)."""
    n = 0
    for q, r in _hex_ring(WARD_HUB_HEX, radius=WARD_SAFE_RADIUS):
        cur = conn.execute(
            "UPDATE world_hexes SET encounter_chance = 0 "
            "WHERE q=? AND r=? AND map_level=0 AND region=? AND encounter_chance != 0",
            (q, r, REGION),
        )
        n += cur.rowcount
    return n


def verify(conn: sqlite3.Connection) -> list[str]:
    problems: list[str] = []
    valid_enemies = {r[0] for r in conn.execute("SELECT key FROM game_config_enemies")}
    for enc in ENCOUNTERS:
        for k, _, _ in enc["enemies"]:
            if k not in valid_enemies:
                problems.append(f"{enc['key']}: nieistniejący enemy_key {k}")
    for e in ENEMIES:
        row = conn.execute(
            "SELECT region_tag, world_scope, terrain_tags, loot_table_key, review_status, "
            "created_by FROM game_config_enemies WHERE key = ?", (e["key"],),
        ).fetchone()
        if not row:
            problems.append(f"{e['key']}: brak w bazie")
            continue
        if row["region_tag"] != REGION:
            problems.append(f"{e['key']}: region_tag={row['region_tag']}")
        if row["review_status"] != "permanent" or row["created_by"] != "seed":
            problems.append(f"{e['key']}: zły review_status/created_by")
        if not row["loot_table_key"]:
            problems.append(f"{e['key']}: brak tabeli łupów")
    # Loot musi wskazywać istniejące itemy — inaczej pusty drop.
    item_keys = {r[0] for r in conn.execute("SELECT key FROM game_config_items")}
    cons_keys = {r[0] for r in conn.execute("SELECT key FROM game_config_consumables")}
    for e in ENEMIES:
        for item_key, *_ in e["loot"]:
            if item_key not in item_keys and item_key not in cons_keys:
                problems.append(f"{e['key']}: loot → brak itemu {item_key}")
    # Boss lochu + pula muszą istnieć.
    if DUNGEON["boss_enemy"] not in valid_enemies:
        problems.append(f"loch: brak bossa {DUNGEON['boss_enemy']}")
    for k in DUNGEON["enemy_pool"]:
        if k not in valid_enemies:
            problems.append(f"loch: pula → brak wroga {k}")
    # Kafle lochu: kategoria istnieje, ≥1 kafel bossa, wszyscy wrogowie kafli w bazie.
    tile_enemy_keys = {k for t in TILES for k, _ in t["enemies"]}
    for k in tile_enemy_keys:
        if k not in valid_enemies:
            problems.append(f"kafel lochu → brak wroga {k}")
    if not any(t["boss"] for t in TILES):
        problems.append("loch: brak kafla bossa (is_boss_tile)")
    cat_rows = {r[0] for r in conn.execute(
        "SELECT category_key FROM dungeon_tiles WHERE category_key = ? AND is_boss_tile = 1",
        (DUNGEON["tile_category_key"],))}
    if DUNGEON["tile_category_key"] not in cat_rows:
        problems.append(f"loch: kategoria kafli {DUNGEON['tile_category_key']} bez kafla bossa w DB")
    # Cele plotek muszą istnieć — inaczej plotka prowadzi donikąd.
    locs = {r[0] for r in conn.execute("SELECT key FROM game_locations")}
    dungs = {r[0] for r in conn.execute("SELECT key FROM game_dungeons")}
    for text, _, ttype, tkey in RUMORS:
        if ttype == "location" and tkey not in locs:
            problems.append(f"plotka → brak lokacji {tkey}")
        if ttype == "dungeon" and tkey not in dungs:
            problems.append(f"plotka → brak lochu {tkey}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    res = seed_enemies(conn)
    enc_n = seed_encounters(conn)
    rum_n = seed_rumors(conn)
    dun_n = seed_dungeon(conn)
    tile_res = seed_dungeon_tiles(conn)
    ward_n = seed_ward_safe_zone(conn)
    conn.commit()

    print(f"  wrogowie nowi:            {res['enemies']} (z {len(ENEMIES)})")
    print(f"  tabele łupów nowe:        {res['loot_tables']}")
    print(f"  wpisy łupów nowe:         {res['loot_entries']}")
    print(f"  spotkania nowe:           {enc_n} (z {len(ENCOUNTERS)})")
    print(f"  plotki nowe:              {rum_n} (z {len(RUMORS)})")
    print(f"  loch nowy:                {dun_n} (Utopiona Wieś)")
    print(f"  kategoria kafli nowa:     {tile_res['category']}")
    print(f"  kafle lochu nowe:         {tile_res['tiles']} (z {len(TILES)})")
    print(f"  hexy strefy wardów (=0):  {ward_n}")

    print("\n  spotkania per teren krainy:")
    for row in conn.execute(
        "SELECT biome, COUNT(*) n, MIN(level_min) lo, MAX(level_max) hi, "
        "MIN(weight) wmin, MAX(weight) wmax FROM game_config_encounters "
        "WHERE region_tag = ? GROUP BY biome ORDER BY n DESC, biome", (REGION,),
    ):
        print(f"    {row['biome']:14s} {row['n']} scen | poziomy {row['lo']}–{row['hi']} "
              f"| wagi {row['wmin']:.0f}–{row['wmax']:.0f}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
