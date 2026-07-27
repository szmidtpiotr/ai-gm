#!/usr/bin/env python3
"""KN-7 — zawartość bojowa i „żywa" Koronnych Nizin: wrogowie + spotkania + plotki
+ loch (Katakumby Vilnogradu = miejski farm) + strojenie ryzyka terenu (trakty,
strefy patroli, pule miejsc zapomnianych).

Źródło prawdy: docs/world/regions/koronne_niziny.md §1–§8 + charakter zadania KN-7.
Wzorzec 1:1: scripts/seed_wybrzeze_lez_bestia.py (WL-7), seed_martwe_pustkowia_bestia.py
(MP-6), seed_czarnobor_bestia.py (CB-6).

CHARAKTER KRAINY (kanon §1, §3): CYWILIZACYJNY SUFIT gry — najbezpieczniejsza kraina,
i najwięcej noży w plecach. „Mrok tej krainy nie ma kłów — ma pieczęcie, weksle i
uśmiech." GRADIENT zagrożeń:
  * trakty (road) — NAJBEZPIECZNIEJ dniem (patrole Korony); ryzyko dopiero NOCĄ,
  * pola/wsie (pola_uprawne, village, town, city) — SPOKOJNE (spichlerz, patrole),
  * zaplecze (plains, heath, forest) — bandyci/rozbójnicy i kultyści w przebraniu,
  * wzgórza (hills) — teren MIEJSC ZAPOMNIANYCH: gęściej, wisielcze widma, kult ruin,
  * stawy/rzeka (lake, river) — utopce przy Zatopionym Opactwie,
  * Katakumby Vilnogradu — loch: szczury, ghule, strzygi, kościej.

DZIEŃ vs NOC (weryfikacja KN-7): różnicę robi SILNIK, nie ten skrypt —
`hex_travel_service.NIGHT_ENCOUNTER_MULT = 1.5` mnoży P(spotkanie) przy `night_march`.
Warunek: hex NIE może mieć twardego zera. Siatka KN-2 zaseedowała WSZYSTKIE 136
traktów z `encounter_chance = 0.0`, a silnik (#1390/#1128) traktuje jawne 0 jako
STREFĘ BEZPIECZNĄ i zeruje szansę nocą i dniem → trakty były MARTWE. `seed_road_risk`
odblokowuje trakty (0.0 → 0.05 = baza terenu road; #1390 i tak liczy z terenu), więc:
  trakt DZIEŃ  = 0.05,   trakt NOC (×1.5) = 0.075  → mierzalna różnica.
Patrole przy hubach (Vilnograd, Volhynia) chronimy JAWNYM zerem na pierścieniu
(`seed_ward_hubs`) — „pola/wsie spokojne", trakt ryzykowny dopiero z dala od miasta.

„MIEJSCA ZAPOMNIANE = GĘŚCIEJ": per-hex `encounter_chance` NIE potrafi PODNIEŚĆ
szansy powyżej bazy terenu (#1390 — teren nadpisuje; jedyny działający lewar w dół
to jawne 0). Dlatego „gęściej" realizujemy DWOJAKO: (1) miejsca zapomniane leżą na
`hills` (baza 0.2 = 4× trakt) i `lake` — teren sam jest gęstszy; (2) `encounter_pool`
na pierścieniu wokół nich ZAWĘŻA pulę do tematycznych elit (`herold_umarlych`,
`topielica_opactwa`, arcykultyści) — tam trafiasz wyłącznie na to, co pod ruiną.

CO CZYTA SILNIK:
  * `game_config_enemies` → `encounter_service.eligible_enemy_pool()` (~50% spotkań):
    world_scope, review_status, is_active, pasmo poziomów, `terrain_tags` vs teren
    hexa, `region_tag` vs kraina. hills→`hills`, pola_uprawne/heath→`plains`,
    lake→`river` (encounter_service._HEX_TYPE_TO_TERRAIN).
  * `game_config_encounters` → `encounter_catalog_service.draw_combat()` (~50%):
    kind/biome/poziom + `region_tag`. `biome` = WPROST `world_hexes.hex_type`.
  * `world_rumors` → `rumor_service.draw_for_region()`.
  * `game_dungeons` (+ dungeon_tiles/kategoria) → Katakumby Vilnogradu (farm kafelkowy,
    #1507). Wejście z KN-4 (`game_locations.katakumby_vilnogradu`). Dwór Czwartego
    NIE jest lochem — to fabularny endgame krainy (§4 hierarchia tajemnic).
  * `world_hexes.encounter_pool` → pule miejsc zapomnianych (elity scope='pool').
  * `world_hexes.encounter_chance` → 0.05 na traktach (odblok), 0 na pierścieniu hubów.

WARTOŚCI STARTOWE (Numbers Policy): staty wrogów, wagi/pasma scen, promienie pul
i wardów, cooldown lochu — wszystko strojlne w Sandboxie. Pasma pod bohatera 3–10
(kraina PÓŹNEJ FAZY) bez inwersji tierów (#1376): weak < standard < elite < boss.

Idempotentny: INSERT OR IGNORE po kluczu; plotki po treści; pule/wardy/trakty
nadpisują tylko wskazane hexy. game_config_encounters / world_rumors / dungeon_tiles
/ world_hexes NIE są w CONTENT_TABLES snapshotu treści — ten skrypt jest ich jedynym
źródłem prawdy (re-aplikuje po reseedzie mapy). game_config_enemies/loot_* SĄ w
CONTENT_TABLES → snapshot_content --tables po seedzie utrwala je w git (#1202).
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys

REGION = "koronne_niziny"

# ── 1. WROGOWIE ───────────────────────────────────────────────────────────────
# Pasma pod bohatera 3–10 (kraina późnej fazy). scope='global' = auto-losowanie po
# terenie+regionie (eligible_enemy_pool); scope='pool' = tylko tam, gdzie klucz jest
# w encounter_pool hexa albo w kaflu lochu (elity/unikaty się nie rozlewają).
ENEMIES: list[dict] = [
    # ── weak (hero 3-5) ──────────────────────────────────────────────────────
    dict(
        key="zbir_uliczny", label="Zbir Uliczny", tier="weak",
        hp=18, ac=12, atk=4, die="1d6", dmg=0, apt=1, xp=75,
        lvl=(3, 5), terrain="road,plains", scope="global", dmg_type="physical",
        desc="Drobny opryszek z bocznej uliczki albo z rogatki po zmroku: nóż, "
             "przekleństwo i pewność, że obcy z sakwą sam się prosi. Pojedynczo "
             "tchórz, w kupie zuchwały.",
        loot=[("bandage", 40, 1, 1), ("health_potion_small", 25, 1, 1)],
        gold=(3, 16),
    ),
    dict(
        key="szczur_kanalowy", label="Szczur Kanałowy", tier="weak",
        hp=16, ac=12, atk=4, die="1d6", dmg=0, apt=1, xp=65,
        lvl=(3, 5), terrain="", scope="pool", dmg_type="physical",
        desc="Wielkości psa, wyhodowany na odpadkach stolicy w ciemności Katakumb. "
             "Ślepy, ale węchem trafia w tętnicę. Rzadko chodzi sam.",
        loot=[("bone_dust", 50, 1, 2)], gold=(0, 3),
    ),
    # ── standard (hero 4-7) ──────────────────────────────────────────────────
    dict(
        key="rzezimieszek_gildyjny", label="Rzezimieszek Gildyjny", tier="standard",
        hp=30, ac=13, atk=6, die="1d8", dmg=1, apt=1, xp=160,
        lvl=(4, 7), terrain="road,plains", scope="global", dmg_type="physical",
        desc="Nie zwykły zbój — najęty przez gildię do brudnej roboty, z której "
             "nikt się nie przyzna. Ma pieczęć zlecenia w rękawie i cenę za twoje "
             "milczenie albo za twoje gardło. Woli po zmroku, z dala od patrolu.",
        loot=[("alchemical_reagent", 35, 1, 1), ("health_potion_small", 30, 1, 1),
              ("relikt_pradawnych", 10, 1, 1)], gold=(8, 30),
    ),
    # UWAGA: `rozbojnik_traktowy` istnieje już jako GLOBALNY generyk (created_by='seed',
    # region_tag pusty) — NIE definiujemy go tu, żeby UPDATE nie zawęził go do KN i nie
    # wyrwał go z pul innych krain. Sceny/pule KN odwołują się do istniejącego klucza.
    dict(
        key="kultysta_w_kaftanie", label="Kultysta w Kaftanie Kupca", tier="standard",
        hp=32, ac=12, atk=6, die="1d8", dmg=1, apt=1, xp=170,
        lvl=(4, 7), terrain="plains,forest", scope="global", dmg_type="necrotic",
        desc="Kult tej krainy nie siedzi w ruinach — nosi kaftan gildii i pierścień "
             "kantoru. Ten wymknął się z salonu na uboczne pola, by dokończyć obrzęd, "
             "którego Światło zakazało. Uśmiecha się jak kupiec i tnie jak fanatyk.",
        loot=[("relikt_pradawnych", 20, 1, 1), ("bone_dust", 35, 1, 2),
              ("alchemical_reagent", 30, 1, 1)], gold=(5, 22),
    ),
    dict(
        key="szczurzy_roj", label="Szczurzy Rój", tier="standard",
        hp=26, ac=12, atk=5, die="1d6", dmg=0, apt=2, xp=150,
        lvl=(4, 7), terrain="", scope="pool", dmg_type="physical",
        desc="Nie pojedyncze szczury — falująca, piszcząca masa, która wypełnia "
             "korytarz od ściany do ściany. Nie da się jej zabić, tylko przetrzebić; "
             "gryzie zewsząd naraz i cofa się dopiero z ogniem.",
        loot=[("bone_dust", 45, 1, 3)], gold=(0, 4),
    ),
    dict(
        key="ghul_katakumb", label="Ghul Katakumb", tier="standard",
        hp=34, ac=13, atk=6, die="1d8", dmg=1, apt=1, xp=175,
        lvl=(4, 7), terrain="", scope="pool", dmg_type="necrotic",
        desc="W kryptach pod miastem grzebano od zawsze — a nie wszystko leży cicho. "
             "Ghul żywi się tym, co złożono w niszach, i tym, co dość głupie, by zejść "
             "po skarby przemytników. Cuchnie grobem i głodem.",
        loot=[("bone_dust", 50, 1, 3), ("relikt_pradawnych", 15, 1, 1)],
        gold=(2, 14),
    ),
    dict(
        key="utopiec_stawowy", label="Utopiec ze Stawów", tier="standard",
        hp=30, ac=12, atk=6, die="1d8", dmg=1, apt=1, xp=165,
        lvl=(4, 7), terrain="river", scope="global", dmg_type="necrotic",
        desc="Przy stawach młyńskich Zatopionego Opactwa woda zabrała kogoś, kto nie "
             "odszedł. Zielonosina postać wygrzebuje się z mułu, gdy zmącisz taflę, i "
             "chce cię wciągnąć tam, gdzie sama leży.",
        loot=[("bone_dust", 40, 1, 2), ("relikt_pradawnych", 15, 1, 1),
              ("alchemical_reagent", 25, 1, 1)], gold=(4, 18),
    ),
    dict(
        key="widmo_wisielca", label="Widmo Wisielca", tier="standard",
        hp=28, ac=13, atk=6, die="1d8", dmg=1, apt=1, xp=170,
        lvl=(4, 7), terrain="hills", scope="global", dmg_type="necrotic",
        desc="Na wzgórzach krainy Korona wieszała od pokoleń. Nocą sylwetki kołyszą "
             "się nad Szubienicznym Wzgórzem, choć szubienic dawno nie ma. To, które "
             "zejdzie ku tobie, wciąż ma pętlę na szyi i pretensję do żywych.",
        loot=[("bone_dust", 40, 1, 2), ("relikt_pradawnych", 18, 1, 1)],
        gold=(3, 16),
    ),
    # ── elite (hero 6-9) ─────────────────────────────────────────────────────
    dict(
        key="herszt_rozbojnikow", label="Herszt Rozbójników", tier="elite",
        hp=50, ac=14, atk=8, die="1d10", dmg=2, apt=2, xp=275,
        lvl=(6, 9), terrain="road,plains,heath", scope="global", dmg_type="physical",
        desc="Dorobił się własnej bandy i własnej ceny za głowę, a rogatki wolą go "
             "nie zauważać, bo płaci. Zna każdy trakt i każdy skrót; przy pasie nosi "
             "weksle warte więcej niż wóz kupca, którego wczoraj obrał.",
        loot=[("relikt_pradawnych", 25, 1, 1), ("potion_healing_standard", 30, 1, 1),
              ("alchemical_reagent", 40, 1, 2)], gold=(25, 90),
    ),
    dict(
        key="arcykultysta_salonu", label="Arcykultysta Salonu", tier="elite",
        hp=48, ac=14, atk=8, die="1d10", dmg=2, apt=2, xp=285,
        lvl=(6, 9), terrain="plains,forest,hills", scope="global", dmg_type="necrotic",
        desc="Prowadzi obrzęd z tą samą pewnością, z jaką prowadzi rachunki gildii. "
             "Kult w tej krainie mieszka w skórze kupca i urzędnika, a ten wspiął się "
             "na sam szczyt hierarchii, o której Światło woli nie mówić głośno.",
        loot=[("relikt_pradawnych", 35, 1, 1), ("bone_dust", 40, 1, 3),
              ("mana_potion", 25, 1, 1)], gold=(18, 70),
    ),
    dict(
        key="herold_umarlych", label="Herold Umarłych", tier="elite",
        hp=52, ac=15, atk=8, die="1d10", dmg=2, apt=2, xp=290,
        lvl=(6, 9), terrain="", scope="pool", dmg_type="necrotic",
        desc="Nad miejscami straceń stoi ktoś, kto zwołuje powieszonych jak herold "
             "zwołuje dwór. Odczytuje wyroki dawno wykonane i wzywa skazańców na "
             "ostatnią rozprawę — a ty właśnie wszedłeś na salę.",
        loot=[("relikt_pradawnych", 35, 1, 1), ("bone_dust", 45, 1, 3),
              ("alchemical_reagent", 40, 1, 2)], gold=(15, 60),
    ),
    dict(
        key="topielica_opactwa", label="Topielica Opactwa", tier="elite",
        hp=50, ac=14, atk=8, die="1d10", dmg=2, apt=2, xp=280,
        lvl=(6, 9), terrain="", scope="pool", dmg_type="necrotic",
        desc="Gdy stawy młyńskie zalały opactwo, przeorysza nie zdążyła wyjść. Teraz "
             "unosi się nad taflą w zbutwiałym habicie i przyjmuje do swojego "
             "zatopionego chóru każdego, kto podejdzie za blisko wody.",
        loot=[("relikt_pradawnych", 35, 1, 1), ("bone_dust", 45, 1, 3),
              ("antidote", 30, 1, 1)], gold=(15, 60),
    ),
    dict(
        key="strzyga_katakumb", label="Strzyga Katakumb", tier="elite",
        hp=52, ac=15, atk=8, die="1d10", dmg=2, apt=2, xp=285,
        lvl=(6, 9), terrain="", scope="pool", dmg_type="necrotic",
        desc="Pochowano ją dwa razy i dwa razy wstała — o dwóch sercach i dwóch "
             "duszach, jak głosi stara wiara. W Katakumbach poluje na żywych, żeby "
             "domknąć to, czego jej przy śmierci odmówiono.",
        loot=[("relikt_pradawnych", 35, 1, 1), ("bone_dust", 45, 1, 3),
              ("potion_healing_standard", 25, 1, 1)], gold=(12, 55),
    ),
    # ── boss (hero 8+; loch) ─────────────────────────────────────────────────
    dict(
        key="kosciej_katakumb", label="Kościej Katakumb", tier="boss",
        hp=90, ac=16, atk=9, die="1d12", dmg=3, apt=2, xp=560,
        lvl=(8, None), terrain="", scope="pool", dmg_type="necrotic",
        desc="Na fundamentach starszych niż samo miasto siedzi ten, którego kości "
             "nikt nie zdołał rozsypać. Był tu, zanim wzniesiono Vilnograd, i będzie, "
             "gdy latarnia porządku zgaśnie. Pilnuje, by z Katakumb nie wyszło nic — "
             "łącznie z tobą.",
        loot=[("relikt_pradawnych", 50, 1, 2), ("bone_dust", 50, 1, 3),
              ("potion_healing_standard", 35, 1, 1), ("mana_potion", 30, 1, 1)],
        gold=(60, 180),
    ),
]

# ── 2. SPOTKANIA ──────────────────────────────────────────────────────────────
# biome = hex_type WPROST. WAGI = gradient tematyczny (nie zmienia P(spotkanie) —
# tę ustala teren; waga rządzi TYM, CO wypadnie na danym terenie): trakt/pola lekko
# (patrole, spichlerz), zaplecze średnio, hills/lake najcięższe (miejsca zapomniane).
ENCOUNTERS: list[dict] = [
    # ── road — trakt: najlżej, tylko nocą realnie grozi ──────────────────────
    dict(key="kn_road_rogatka_nocna", biome="road", lvl=(3, 6), w=10,
         enemies=[("zbir_uliczny", "zbir uliczny", 2)],
         title="Rogatka po zmroku",
         scene="Trakt pusty, patrol dawno przeszedł. Zza przewróconej beczki wychodzi "
               "dwóch opryszków — o tej porze myto pobiera się bez glejtu i bez "
               "świadków."),
    dict(key="kn_road_falszywy_celnik", biome="road", lvl=(4, 7), w=9,
         enemies=[("rozbojnik_traktowy", "rozbójnik traktowy", 1),
                  ("zbir_uliczny", "zbir", 1)],
         title="Fałszywa komora celna",
         scene="Na trakcie ktoś rozstawił stolik i wagę jak celnik, ale glejtu nie "
               "sprawdza — liczy twoją sakwę. Za plecami ma drugiego z pałką."),
    # ── pola_uprawne — spichlerz: spokojnie, drobni rzezimieszkowie ───────────
    dict(key="kn_pola_zbiry", biome="pola_uprawne", lvl=(3, 5), w=11,
         enemies=[("zbir_uliczny", "zbir uliczny", 2)],
         title="Miedzą od wsi",
         scene="Między łanami zboża idzie dwóch obszarpańców z workami przez ramię. "
               "Wracają z folwarku, gdzie brali nie swoje, i ty jesteś świadkiem za "
               "dużo."),
    dict(key="kn_pola_najem", biome="pola_uprawne", lvl=(4, 7), w=10,
         enemies=[("rzezimieszek_gildyjny", "rzezimieszek gildyjny", 1)],
         title="Zlecenie w polu",
         scene="Ktoś czekał na tym rozstaju konkretnie na ciebie. Wyjmuje z rękawa "
               "pieczęć, na którą nie zdążysz spojrzeć, i nóż, który zdążysz."),
    # ── plains — zaplecze: bandyci i kultyści ────────────────────────────────
    dict(key="kn_plains_zasadzka", biome="plains", lvl=(4, 7), w=14,
         enemies=[("rzezimieszek_gildyjny", "rzezimieszek gildyjny", 2)],
         title="Zasadzka na uboczu",
         scene="Z dala od traktu, gdzie żaden patrol nie dojdzie, czekają dwaj "
               "najęci. Nie chcą sakwy — chcą, żebyś przestał być kłopotem dla kogoś "
               "z miasta."),
    dict(key="kn_plains_kultysci", biome="plains", lvl=(4, 7), w=13,
         enemies=[("kultysta_w_kaftanie", "kultysta w kaftanie", 1)],
         title="Obrzęd na uboczu",
         scene="Za kępą krzaków klęczy postać w kupieckim kaftanie, mamrocząc nad "
               "wyrytym znakiem. Odwraca się do ciebie z uśmiechem gildyjnego "
               "urzędnika i ostrzem ofiarnym."),
    # ── heath — wrzosowiska: bandy ───────────────────────────────────────────
    dict(key="kn_heath_banda", biome="heath", lvl=(4, 7), w=15,
         enemies=[("rozbojnik_traktowy", "rozbójnik traktowy", 1),
                  ("zbir_uliczny", "zbir", 1)],
         title="Obóz na wrzosowisku",
         scene="Nad wrzosem snuje się dym z ogniska. Przy nim rozbójnik i jego "
               "pomagier dzielą łup — twoje nadejście traktują jak trzecią porcję do "
               "podziału."),
    dict(key="kn_heath_herszt", biome="heath", lvl=(6, 9), w=13,
         enemies=[("herszt_rozbojnikow", "herszt rozbójników", 1),
                  ("rzezimieszek_gildyjny", "rzezimieszek", 2)],
         title="Herszt z bandą",
         scene="Na wrzosowisku rozłożyła się cała banda, a rozkazy wydaje ktoś, kogo "
               "reszta słucha bez słowa. Herszt mierzy cię wzrokiem jak towar, a "
               "ludzie rozchodzą się, żeby odciąć ci drogę."),
    # ── forest — kępy lasu: rozbójnicy i kult ────────────────────────────────
    dict(key="kn_forest_rozbojnicy", biome="forest", lvl=(4, 7), w=16,
         enemies=[("rozbojnik_traktowy", "rozbójnik traktowy", 2)],
         title="Kryjówka w zagajniku",
         scene="Wśród drzew stoi szałas obwieszony zdobyczą. Dwóch ludzi wyskakuje "
               "spomiędzy pni — trafiłeś na skład, którego mieli nie znaleźć obcy."),
    dict(key="kn_forest_kult", biome="forest", lvl=(6, 9), w=14,
         enemies=[("arcykultysta_salonu", "arcykultysta", 1),
                  ("kultysta_w_kaftanie", "kultysta", 1)],
         title="Salon w lesie",
         scene="W leśnej polanie stoją powozy z herbami gildii, a między drzewami "
               "trwa obrzęd, na który zaproszono tylko wtajemniczonych. Prowadzący "
               "podnosi głowę — świadka trzeba dopisać do ofiary."),
    # ── river/lake — stawy: utopce (Zatopione Opactwo) ───────────────────────
    dict(key="kn_river_utopce", biome="river", lvl=(4, 7), w=15,
         enemies=[("utopiec_stawowy", "utopiec ze stawów", 2)],
         title="Coś w wodzie",
         scene="Rzeka leży gładka jak lustro, dopóki nie zmącisz jej krokiem. Spod "
               "tafli podnoszą się dwie zielonosine postaci, które czekały, aż ktoś "
               "podejdzie do brzegu."),
    dict(key="kn_lake_utopiec", biome="lake", lvl=(4, 7), w=16,
         enemies=[("utopiec_stawowy", "utopiec ze stawów", 2)],
         title="Stawy młyńskie",
         scene="Przy zarośniętych stawach Zatopionego Opactwa woda pachnie zgnilizną "
               "i kadzidłem. Z mułu wygrzebują się utopce w strzępach habitów — "
               "chór, który nigdy nie skończył nabożeństwa."),
    # ── hills — wzgórza miejsc zapomnianych: NAJCIĘŻEJ ────────────────────────
    dict(key="kn_hills_widma", biome="hills", lvl=(4, 7), w=20,
         enemies=[("widmo_wisielca", "widmo wisielca", 2)],
         title="Na Szubienicznym Wzgórzu",
         scene="Na grzbiecie wzgórza wiatr niesie skrzypienie, choć szubienic dawno "
               "nie ma. Dwie sylwetki z pętlami na szyjach schodzą ku tobie z "
               "pretensją do wszystkich, którzy jeszcze oddychają."),
    dict(key="kn_hills_kult_ruin", biome="hills", lvl=(6, 9), w=18,
         enemies=[("arcykultysta_salonu", "arcykultysta", 1),
                  ("kultysta_w_kaftanie", "kultysta", 1)],
         title="Obrzęd w ruinach",
         scene="Wśród kamieni miejsca, którego kroniki nie chcą pamiętać, płoną "
               "świece. Kult zszedł tu z salonów, by dokończyć to, czego w mieście "
               "nie wolno — i nie zostawia świadków."),
    dict(key="kn_hills_rozbojnicy", biome="hills", lvl=(3, 6), w=12,
         enemies=[("rzezimieszek_gildyjny", "rzezimieszek gildyjny", 2)],
         title="Zbiry pod ruiną",
         scene="Ktoś urządził sobie kryjówkę w cieniu zapomnianych murów, bo tu nikt "
               "nie zagląda. Dwóch najętych podnosi się od ogniska — obcy pod ruiną "
               "to albo łup, albo świadek."),
]

# ── 3. PLOTKI ─────────────────────────────────────────────────────────────────
# Z LORE §3/§7, BEZ spoilerów: Sekret Rady Czterech, Pierwszy Tron i Dwór Czwartego
# zostają PYTANIAMI (kanon §4 — kampania dotyka najwyżej JEDNEGO agenta, nigdy całej
# Rady/celu). Cele location = klucze game_locations; dungeon = klucz game_dungeons.
RUMORS: list[tuple[str, int, str | None, str | None]] = [
    ("Powiadają, że latarnia porządku świeci na kredyt. Żołd Strzegwachtu, długi "
     "twierdz granicznych, kupione rozkazy — ktoś to wszystko skupuje wekslami, "
     "ratami, i nikt nie wie, kiedy przyjdzie zapłata.", 1, None, None),
    ("Raz w tygodniu w bocznej kamienicy przyjmuje „Rachmistrzyni” — prowadzi rachunki "
     "kogoś, kogo się nie nazywa. Nikt nie zna jej imienia; ci, co próbowali poznać, "
     "przestali pytać.", 1, None, None),
    ("Dzielnicą Złodziei rządzi „Nocny Burmistrz”, choć nikt nie umie powiedzieć, kto "
     "nim jest. Starzy szepczą, że to nie człowiek, tylko urząd — przechodzi z rąk do "
     "rąk, a ostatni nosiciel zawsze znika bez śladu.", 1, "location",
     "vilnograd_dzielnica_zlodziei"),
    ("W kantorach enklawy krasnoludzkiej złoto zamienisz na weksel, a weksla nie "
     "zabierze ci ani nóż, ani śmierć — wymienisz go w każdym kantorze. Dlatego bogaci "
     "podróżują z papierem, a biedni ze stalą.", 1, "location",
     "vilnograd_enklawa_krasnoludzka"),
    ("Pierwszy Tron to ruiny pierwotnej siedziby Korony — dwór przeniesiono stamtąd "
     "nagle, a kroniki milczą, dlaczego. Kto pyta zbyt głośno, dowiaduje się, że "
     "niektóre archiwa spłonęły akurat na czas.", 1, "location", "pierwszy_tron"),
    ("Dwór Czwartego stoi spalony od pokoleń, a ziemi nikt nie kupuje, choćby za "
     "bezcen. Mówią, że rzekomy założyciel Rady sam kazał go podpalić — albo że ktoś "
     "podpalił jego razem z dworem.", 1, "location", "dwor_czwartego"),
    ("W Wieży Heroldów gnije archiwum rodowodów. Ten, kto je przeczyta do końca, "
     "podobno dowie się, kto NAPRAWDĘ ma prawo do tronu — dlatego wieża stoi "
     "zamknięta, a klucz zaginął „przypadkiem”.", 1, "location", "wieza_heroldow"),
    ("Spichlerz krainy biednieje, żeby stolica błyszczała. Po wsiach spichlerzowych "
     "coraz głośniej o buncie — a Korona woli ściągnąć Strzegwacht z granicy niż "
     "obniżyć podatek. Ktoś na tym zarobi.", 1, None, None),
    ("Pod Vilnogradem ciągną się Katakumby starsze niż samo miasto — krypty, tunele "
     "przemytników i fundamenty, których nikt nie kładł za pamięci żywych. Schodzą "
     "tam po skarby; wychodzi mniej, niż wchodzi.", 1, "dungeon",
     "katakumby_vilnogradu"),
    ("W Katakumbach przemytnicy mają szlaki, którymi towar wchodzi do miasta z "
     "pominięciem rogatek. Kto zna tunele, omija myto — o ile wcześniej ominie to, co "
     "mieszka w kryptach.", 1, "dungeon", "katakumby_vilnogradu"),
    ("Zatopione Opactwo zalano przy budowie stawów młyńskich, a Światło nie tłumaczy, "
     "czemu opuszczono je tak nagle. Rybacy nie zapuszczają się na tamte stawy po "
     "zmroku — mówią, że chór wciąż śpiewa pod wodą.", 1, "location",
     "zatopione_opactwo"),
    ("Na Szubienicznym Wzgórzu Korona wieszała skazańców od początku Ery Latarni. "
     "Szubienic dawno nie ma, ale nocą coś się nad grzbietem kołysze, a wiatr niesie "
     "skrzypienie sznura.", 1, "location", "szubieniczne_wzgorze"),
    ("Brat Tomasz Kronikarz w Klasztorze Iskry skupuje relikty z pustkowi i katakumb "
     "— płaci uczciwie i nie pyta, skąd. Powiadają, że spisuje coś, o czym reszta "
     "Światła woli nie wiedzieć.", 1, "location", "vilnograd_swiatynia_swiatla"),
    ("Kult w tej krainie nie mieszka w ruinach — nosi kaftan gildii i pierścień "
     "kantoru. Światło walczy z nim po SALONACH, nie po lochach; kto tnie fanatyka na "
     "uboczu, częściej trafia na kupca niż na obszarpańca.", 1, None, None),
    ("Glejt kupiecki i list żelazny otwierają rogatki bez pytań — a fałszywe papiery "
     "otwierają je z ryzykiem. Na Rogatce Wschodniej Berta Twarda Pieczęć rozpoznaje "
     "podróbkę z dziesięciu kroków; kto wpadnie, ten myta już nie zapłaci.", 1,
     "location", "vilnograd_rynek"),
]

# ── 4. LOCH — KATAKUMBY VILNOGRADU ────────────────────────────────────────────
# Miejski farm (§4: „miejski farmowalny dungeon", otwarty od seedu). Wejście z KN-4:
# game_locations.katakumby_vilnogradu. Silnik kafelkowy (#1507) — enter_dungeon_tiles
# WYMAGA `tile_category_key` (inaczej 409), więc dedykowana kategoria kafli z wrogami
# z puli krainy i kaflem bossa. Kafle bez obrazków (grywalne; grafiki FLUX = follow-up).
# Dwór Czwartego NIE jest lochem — fabularny endgame krainy (§4), poza zakresem KN-7.
_HEX_NEIGHBOURS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _dead_ends(theme: str) -> list[dict]:
    d = theme
    return [
        dict(label=f"Ślepy Zaułek {d} (N)", enemies=[], boss=0, items=[], doors=["N"],
             desc="Korytarz urywa się litą skałą fundamentów. Dalej nie ma drogi."),
        dict(label=f"Ślepy Zaułek {d} (S)", enemies=[], boss=0, items=[], doors=["S"],
             desc="Zawał gruzu zamyka przejście. Ślepy kąt."),
        dict(label=f"Ślepy Zaułek {d} (E)", enemies=[], boss=0, items=[], doors=["E"],
             desc="Woda gruntowa wypełnia korytarz po sufit. Nie przejdziesz."),
        dict(label=f"Ślepy Zaułek {d} (W)", enemies=[], boss=0, items=[], doors=["W"],
             desc="Przejście kończy się zamurowaną niszą grobową."),
    ]


DUNGEONS: list[dict] = [
    dict(
        key="katakumby_vilnogradu", label="Katakumby Vilnogradu",
        location_key="katakumby_vilnogradu",
        rooms=8, tile_category_key="katakumby_vilnogradu", tile_count=8,
        boss_tile_id=None,
        enemy_pool=["szczur_kanalowy", "szczurzy_roj", "ghul_katakumb",
                    "strzyga_katakumb", "skeleton", "zombie"],
        boss_enemy="kosciej_katakumb", loot_tier="rich",
        cooldown_hours=48, min_level=5,
        atmosphere=("Krypty, tunele przemytników i fundamenty starsze niż samo miasto, "
                    "splecione pod Vilnogradem w labirynt bez końca. W niszach leżą "
                    "pokolenia zmarłych, między nimi biegną szlaki, którymi towar "
                    "wchodzi do miasta z pominięciem rogatek — a najgłębiej czuwa coś, "
                    "co było tu, zanim położono pierwszy kamień."),
        room_types_json='{"combat":58,"chest":15,"trap":10,"riddle":7,"rest":10}',
        dungeon_difficulty=3, room_loot_chance=0.18, rest_heal_pct=18, rest_charges=2,
        category=dict(
            key="katakumby_vilnogradu", label="Katakumby Vilnogradu", sort_order=83,
            description="Podziemny labirynt pod stolicą — kamienne krypty z niszami "
                        "grobowymi, tunele przemytników, zatopione fundamenty i "
                        "sala tronowa kościeja na najstarszych murach miasta.",
            style_modifier=("underground catacomb crypt, carved stone burial niches, "
                            "stacked bones and skulls, smuggler tunnels, dripping "
                            "groundwater, cold torchlight, grey stone and cobweb, "
                            "old-city foundations aesthetic"),
            system_prompt=("Opisujesz komorę w Katakumbach Vilnogradu — podziemnym "
                           "labiryncie krypt, tuneli przemytników i fundamentów "
                           "starszych niż stolica. Skup się na kamiennych niszach "
                           "grobowych, stosach kości, kapiącej wodzie gruntowej, "
                           "zimnym świetle pochodni, pajęczynach i szczurach. Opis po "
                           "polsku, 2-3 zdania klimatyczne, zmysłowe, grobowe."),
            base_prompt=("underground catacomb chamber seen from directly straight "
                         "above, carved stone burial niches and stacked bones forming "
                         "the irregular room boundary, cracked flagstone floor, "
                         "dripping groundwater puddles, cobwebs, 2-3 open passages "
                         "leading off the edges, cold torchlight, painted tabletop RPG "
                         "battlemap art style, high detail, strict top-down orthographic "
                         "overhead view, square map tile, 2D game art, NO perspective, "
                         "NO side view, flat overhead, no text, no UI"),
        ),
        tiles=[
            dict(label="Wejście do Katakumb", enemies=[], boss=0, items=[],
                 desc="Schody z Dzielnicy Gildii schodzą w chłód i wilgoć. Ze środka "
                      "ciągnie zapachem kamienia, pleśni i czegoś starszego."),
            dict(label="Szczurza Nora", enemies=[("szczur_kanalowy", 2)], boss=0,
                 items=[],
                 desc="Nisze grobowe rozgrzebane do czysta, a w ciemności piszczy i "
                      "faluje coś wielkiego jak psy. Ślepia zapalają się parami."),
            dict(label="Tunel Przemytników", enemies=[("rzezimieszek_gildyjny", 1)],
                 boss=0, items=[("alchemical_reagent", 0.5)],
                 desc="Wąski chodnik podparty deskami, wybity ludzką ręką między "
                      "kryptami. Ktoś tu jeszcze pilnuje towaru i noża do gardła "
                      "obcego nie żałuje."),
            dict(label="Krypta Ghuli", enemies=[("ghul_katakumb", 1)], boss=0,
                 items=[],
                 desc="Sala pełna otwartych sarkofagów, cuchnąca grobem i głodem. Coś "
                      "prostuje się w cieniu niszy i odwraca ku tobie zapadłą twarz."),
            dict(label="Zatopione Fundamenty",
                 enemies=[("szczurzy_roj", 1)], boss=0, items=[],
                 desc="Najstarsze mury stoją do połowy w czarnej wodzie gruntowej. "
                      "Po powierzchni pływa piszcząca masa, która rzuca się na "
                      "wszystko ciepłe."),
            dict(label="Skarbiec Przemytników", enemies=[], boss=0,
                 items=[("relikt_pradawnych", 1.0), ("alchemical_reagent", 0.5),
                        ("bone_dust", 0.4)],
                 desc="Skrzynie ukryte w zamurowanej niszy: kontrabanda, którą ktoś "
                      "schował i po którą nie wrócił. Między beczkami leży zawiniątko "
                      "w naoliwionym płótnie."),
            dict(label="Legowisko Strzygi", enemies=[("strzyga_katakumb", 1)], boss=0,
                 items=[],
                 desc="Nisza wyścielona strzępami dwóch całunów. To, co tu mieszka, "
                      "pochowano dwa razy i dwa razy wstało — i właśnie się budzi."),
            dict(label="Cicha Nisza", enemies=[], boss=0, items=[],
                 desc="Zamurowana kaplica grobowa, sucha i cicha, gdzie woda nie "
                      "sięga. Można tu na chwilę przysiąść i złapać oddech."),
            dict(label="Zawalona Sztolnia", enemies=[("skeleton", 1), ("zombie", 1)],
                 boss=0, items=[],
                 desc="Stary wykop, którym wynoszono gruz, do połowy zasypany. Z mroku "
                      "brną ku tobie dwie sylwetki, które nie skończyły roboty."),
            dict(label="Sala Kościeja", enemies=[("kosciej_katakumb", 1)], boss=1,
                 items=[],
                 desc="Na fundamentach starszych niż miasto, na tronie z kości i "
                      "gruzu, siedzi Kościej Katakumb. Otwiera oczy pełne grobowego "
                      "chłodu, gdy wchodzisz — i zwołuje wszystko, co tu leży."),
            *_dead_ends("Ka"), *_dead_ends("Kb"),
        ],
    ),
]

# ── 5. STROJENIE RYZYKA TERENU ────────────────────────────────────────────────
# 5a. Odblok traktów: siatka KN-2 dała WSZYSTKIM road encounter_chance=0.0 (silnik
#     traktuje to jak strefę bezpieczną → trakty martwe dniem i nocą). Ustawiamy 0.05
#     (= baza terenu road), więc DZIEŃ 0.05 vs NOC ×1.5 = 0.075 (weryfikacja KN-7).
# 5b. Patrole hubów: JAWNE zero na pierścieniu wokół Vilnogradu i Volhynii — „pola/wsie
#     spokojne", trakt ryzykowny dopiero z dala od miasta.
# 5c. Pule miejsc zapomnianych: encounter_pool ZAWĘŻA pulę do tematycznych elit tam,
#     gdzie teren i tak jest gęstszy (hills 0.2, lake). Poza tymi hexami elity 'pool'
#     się nie losują.
WARD_HUBS: list[tuple[tuple[int, int], int]] = [
    ((-23, 22), 2),   # vilnograd_stolica (city)
    ((-20, 32), 2),   # volhynia_kupiecka (town)
]

FORGOTTEN_POOLS: list[tuple[tuple[int, int], int, list[str]]] = [
    ((-15, 27), 1, ["widmo_wisielca", "herold_umarlych"]),          # Szubieniczne Wzgórze
    ((-26, 42), 1, ["utopiec_stawowy", "topielica_opactwa"]),       # Zatopione Opactwo
    ((-35, 31), 1, ["kultysta_w_kaftanie", "arcykultysta_salonu",
                    "widmo_wisielca"]),                             # Pierwszy Tron
    ((-31, 32), 1, ["kultysta_w_kaftanie", "arcykultysta_salonu"]), # Dwór Czwartego
    ((-32, 34), 1, ["widmo_wisielca", "kultysta_w_kaftanie"]),      # Wieża Heroldów
]


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
        # Seed = źródło prawdy pól strojlnych (content-as-code #1202).
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


def seed_dungeon(conn: sqlite3.Connection, d: dict) -> int:
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
    conn.execute(
        "UPDATE game_dungeons SET enemy_pool = ?, boss_enemy = ?, atmosphere = ?, "
        "min_level = ?, cooldown_hours = ?, is_active = 1, tile_category_key = ?, "
        "tile_count = ? WHERE key = ?",
        (json.dumps(d["enemy_pool"]), d["boss_enemy"], d["atmosphere"],
         d["min_level"], d["cooldown_hours"], d["tile_category_key"],
         d["tile_count"], d["key"]),
    )
    return cur.rowcount


def seed_dungeon_tiles(conn: sqlite3.Connection, d: dict) -> dict:
    """Dedykowana kategoria kafli + kafle lochu. Kafle bez obrazków (grywalne, UI
    pokaże placeholder); grafiki FLUX = osobny follow-up. Idempotentny."""
    res = {"category": 0, "tiles": 0}
    tc = d["category"]
    cur = conn.execute(
        "INSERT OR IGNORE INTO dungeon_tile_categories (key, label, description, "
        "style_modifier, system_prompt, base_prompt, sort_order, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (tc["key"], tc["label"], tc["description"], tc["style_modifier"],
         tc["system_prompt"], tc["base_prompt"], tc["sort_order"]),
    )
    res["category"] += cur.rowcount
    for t in d["tiles"]:
        exists = conn.execute(
            "SELECT 1 FROM dungeon_tiles WHERE category_key = ? AND label = ?",
            (tc["key"], t["label"]),
        ).fetchone()
        if exists:
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
            "VALUES (?, ?, ?, ?, ?, '[]', ?, ?, '', NULL, ?, 1)",
            (tc["key"], t["label"], doors_json, enemies_json,
             items_json, exit_cond, t["desc"], int(t["boss"])),
        )
        res["tiles"] += 1
    return res


def seed_road_risk(conn: sqlite3.Connection) -> int:
    """5a — odblok traktów. Siatka KN-2 dała road encounter_chance=0.0 (=strefa
    bezpieczna → trakty martwe). Ustawiamy 0.05 (baza terenu road), by DZIEŃ vs NOC
    (×1.5) dało mierzalną różnicę. Idempotentny; wardy hubów re-zerują potem pierścień."""
    cur = conn.execute(
        "UPDATE world_hexes SET encounter_chance = 0.05 "
        "WHERE map_level=0 AND region=? AND hex_type='road' AND encounter_chance = 0",
        (REGION,),
    )
    return cur.rowcount


def seed_ward_hubs(conn: sqlite3.Connection) -> int:
    """5b — patrole hubów: JAWNE encounter_chance=0 na pierścieniu wokół Vilnogradu
    i Volhynii (#1390 nie nadpisuje zera terenem). „Pola/wsie spokojne", trakt
    ryzykowny dopiero z dala od miasta. Idempotentny."""
    n = 0
    for center, radius in WARD_HUBS:
        for q, r in _hex_ring(center, radius=radius):
            cur = conn.execute(
                "UPDATE world_hexes SET encounter_chance = 0 "
                "WHERE q=? AND r=? AND map_level=0 AND region=? AND encounter_chance != 0",
                (q, r, REGION),
            )
            n += cur.rowcount
    return n


def seed_forgotten_pools(conn: sqlite3.Connection) -> int:
    """5c — pule miejsc zapomnianych: elity scope='pool' wpisane w encounter_pool na
    pierścieniu wokół miejsc opuszczonych (§4). Poza tymi hexami silnik ich nie
    wylosuje. Seed re-aplikuje po reseedzie mapy (jak pule mitów MP-6 / WL-7)."""
    n = 0
    for center, radius, pool in FORGOTTEN_POOLS:
        for q, r in _hex_ring(center, radius=radius):
            row = conn.execute(
                "SELECT encounter_pool FROM world_hexes WHERE q=? AND r=? "
                "AND map_level=0 AND region=?", (q, r, REGION),
            ).fetchone()
            if row is None:
                continue
            try:
                existing = json.loads(row["encounter_pool"]) if row["encounter_pool"] else []
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, TypeError):
                existing = []
            merged = list(dict.fromkeys([*existing, *pool]))
            if merged == existing:
                continue
            conn.execute(
                "UPDATE world_hexes SET encounter_pool = ? WHERE q=? AND r=? "
                "AND map_level=0 AND region=?",
                (json.dumps(merged), q, r, REGION),
            )
            n += 1
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
            "created_by, min_level, max_level, tier FROM game_config_enemies WHERE key = ?",
            (e["key"],),
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
        # #1376 — brak inwersji tierów: max >= min.
        if row["max_level"] is not None and row["max_level"] < row["min_level"]:
            problems.append(f"{e['key']}: inwersja poziomów {row['min_level']}>{row['max_level']}")
    item_keys = {r[0] for r in conn.execute("SELECT key FROM game_config_items")}
    cons_keys = {r[0] for r in conn.execute("SELECT key FROM game_config_consumables")}
    for e in ENEMIES:
        for item_key, *_ in e["loot"]:
            if item_key not in item_keys and item_key not in cons_keys:
                problems.append(f"{e['key']}: loot → brak itemu {item_key}")
    dungs = {r[0] for r in conn.execute("SELECT key FROM game_dungeons")}
    for d in DUNGEONS:
        if d["boss_enemy"] not in valid_enemies:
            problems.append(f"loch {d['key']}: brak bossa {d['boss_enemy']}")
        for k in d["enemy_pool"]:
            if k not in valid_enemies:
                problems.append(f"loch {d['key']}: pula → brak wroga {k}")
        tile_enemy_keys = {k for t in d["tiles"] for k, _ in t["enemies"]}
        for k in tile_enemy_keys:
            if k not in valid_enemies:
                problems.append(f"loch {d['key']}: kafel → brak wroga {k}")
        tile_item_keys = {k for t in d["tiles"] for k, _ in t["items"]}
        for k in tile_item_keys:
            if k not in item_keys and k not in cons_keys:
                problems.append(f"loch {d['key']}: kafel → brak itemu {k}")
        if not any(t["boss"] for t in d["tiles"]):
            problems.append(f"loch {d['key']}: brak kafla bossa")
        boss_cat = {r[0] for r in conn.execute(
            "SELECT category_key FROM dungeon_tiles WHERE category_key = ? "
            "AND is_boss_tile = 1", (d["tile_category_key"],))}
        if d["tile_category_key"] not in boss_cat:
            problems.append(f"loch {d['key']}: kategoria {d['tile_category_key']} bez kafla bossa w DB")
        if d["key"] not in dungs:
            problems.append(f"loch {d['key']}: brak w game_dungeons")
    # Pule miejsc zapomnianych — enemy scope='pool' muszą istnieć.
    for center, radius, pool in FORGOTTEN_POOLS:
        for k in pool:
            if k not in valid_enemies:
                problems.append(f"pula {center}: brak wroga {k}")
    # Cele plotek muszą istnieć.
    locs = {r[0] for r in conn.execute("SELECT key FROM game_locations")}
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
    dun_n = 0
    tile_cat_n = 0
    tile_n = 0
    for d in DUNGEONS:
        dun_n += seed_dungeon(conn, d)
        tr = seed_dungeon_tiles(conn, d)
        tile_cat_n += tr["category"]
        tile_n += tr["tiles"]
    road_n = seed_road_risk(conn)
    ward_n = seed_ward_hubs(conn)
    pool_n = seed_forgotten_pools(conn)
    conn.commit()

    print(f"  wrogowie nowi:            {res['enemies']} (z {len(ENEMIES)})")
    print(f"  tabele łupów nowe:        {res['loot_tables']}")
    print(f"  wpisy łupów nowe:         {res['loot_entries']}")
    print(f"  spotkania nowe:           {enc_n} (z {len(ENCOUNTERS)})")
    print(f"  plotki nowe:              {rum_n} (z {len(RUMORS)})")
    print(f"  lochy nowe:               {dun_n} (z {len(DUNGEONS)})")
    print(f"  kategorie kafli nowe:     {tile_cat_n}")
    print(f"  kafle lochu nowe:         {tile_n}")
    print(f"  trakty odblokowane (0.05):{road_n}")
    print(f"  hexy patroli hubów (=0):  {ward_n}")
    print(f"  hexy pul zapomnianych:    {pool_n}")

    print("\n  spotkania per teren krainy (gradient tematyczny):")
    for row in conn.execute(
        "SELECT biome, COUNT(*) n, MIN(level_min) lo, MAX(level_max) hi, "
        "MIN(weight) wmin, MAX(weight) wmax FROM game_config_encounters "
        "WHERE region_tag = ? GROUP BY biome ORDER BY wmax DESC, biome", (REGION,),
    ):
        print(f"    {row['biome']:12s} {row['n']} scen | poziomy {row['lo']}–{row['hi']} "
              f"| wagi {row['wmin']:.0f}–{row['wmax']:.0f}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
