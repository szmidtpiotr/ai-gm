#!/usr/bin/env python3
"""SG-6b (#1481) — zawartość bojowa i „żywa" Siwych Grań: wrogowie + spotkania + plotki.

Źródło prawdy: docs/world/regions/siwe_granie.md §1/§4/§5/§6/§7 + pule ustalone
w dyskusji #1481. Wzorzec: scripts/seed_siwe_granie_obsada.py (SG-6).

CO CZYTA SILNIK (żeby ta treść nie była martwym wpisem w adminie):
  * `game_config_enemies` → `encounter_service.eligible_enemy_pool()` (kompozytor,
    ~50% spotkań) — filtry: world_scope, review_status, is_active, pasmo poziomów,
    `terrain_tags` vs teren hexa oraz (SG-6b) `region_tag` vs kraina hexa,
  * `game_config_encounters` → `encounter_catalog_service.draw_combat()` (drugie ~50%)
    — filtry: kind/biome/poziom oraz (SG-6b) `region_tag`,
  * `world_rumors` → `world_rumor_service.draw_for_region()` w `rumor_service.eavesdrop_rumor()`
    — pula regionu ma 60% pierwszeństwa przed plotką generowaną per bohater.

TERENY: `biome` w katalogu spotkań porównuje się WPROST z `world_hexes.hex_type`.
Wrogowie mają własny, uboższy słownik `terrain_tags`, na który hex_type jest mapowany
(`_HEX_TYPE_TO_TERRAIN`, SG-1): grania/przelecz/lodowiec/siarka → mountain,
snow/tundra/heath → plains, las_iglasty → forest. Dlatego wrogom nadajemy tagi ze
starego słownika, a scenom — realne hex_type krainy.

WARTOŚCI STARTOWE (Numbers Policy): staty wrogów, `weight` i `level_min/max` scen —
wszystko do strojenia w Sandboxie. Pasma dobrane pod bohatera 1–8 bez inwersji tierów
(#1376): weak < standard < elite w wartości zagrożenia.

Idempotentny: INSERT OR IGNORE po kluczu; plotki po treści; pula hexa nadpisywana
tylko dla wskazanych hexów sanktuarium.

    docker cp scripts/seed_siwe_granie_bestia.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_bestia.py
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_bestia.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "siwe_granie"

# ── 1. WROGOWIE ───────────────────────────────────────────────────────────────
# world_scope: 'global' = kompozytor może ich wziąć na pasującym terenie w tej krainie;
# 'pool' = TYLKO tam, gdzie autor wpisał klucz do world_hexes.encounter_pool.
ENEMIES: list[dict] = [
    dict(
        key="sniezny_wilk", label="Śnieżny Wilk", tier="standard",
        hp=12, ac=12, atk=3, die="1d6", dmg=0, apt=1, xp=80,
        lvl=(1, 3), terrain="mountain,plains,forest", scope="global",
        dmg_type="physical",
        desc="Biała wataha grań. Większy i cichszy od wilków z nizin — zimą schodzi "
             "za karawanami aż pod bramy hołdów i czeka, aż ktoś zostanie z tyłu.",
        loot=[("wolf_pelt", 70, 1, 1), ("healing_herb", 30, 1, 1)], gold=(0, 4),
    ),
    dict(
        key="ognik_siarkowy", label="Ognik Siarkowy", tier="weak",
        hp=10, ac=13, atk=3, die="1d4", dmg=1, apt=1, xp=48,
        lvl=(2, 4), terrain="mountain", scope="global", dmg_type="fire",
        desc="Kłąb ognia tańczący nad szczeliną wyziewu. Zbieracze siarki mówią, "
             "że ognik nie goni — po prostu jest tam, gdzie zaraz staniesz.",
        loot=[("alchemical_reagent", 45, 1, 1), ("bone_dust", 35, 1, 2)], gold=(0, 3),
    ),
    dict(
        key="zamarzniety_pielgrzym", label="Zamarznięty Pielgrzym", tier="standard",
        hp=16, ac=11, atk=4, die="1d6", dmg=0, apt=1, xp=92,
        # 'ruins' bo sam hex sanktuarium jest ruiną — bez tego tagu filtr terenu
        # odsiewał pielgrzymów dokładnie tam, gdzie mają się pojawiać.
        lvl=(2, 5), terrain="mountain,plains,ruins", scope="pool", dmg_type="physical",
        desc="Postać wmarznięta w lód po pas, wciąż zwrócona twarzą pod górę. Gdy "
             "podejdziesz zbyt blisko, procesja rusza dalej — tak, jak szła.",
        loot=[("incense_bundle", 50, 1, 1), ("holy_symbol", 30, 1, 1)], gold=(1, 8),
    ),
    dict(
        key="harpia_granicka", label="Harpia Graniowa", tier="standard",
        hp=18, ac=13, atk=5, die="1d6", dmg=1, apt=1, xp=115,
        lvl=(3, 6), terrain="mountain,hills", scope="global", dmg_type="physical",
        desc="Gnieździ się w urwiskach nad przełęczami. Nie atakuje wprost — "
             "krzykiem odbitym od ścian próbuje strącić ofiarę z półki skalnej.",
        loot=[("silk_thread", 40, 1, 2), ("hunting_horn", 20, 1, 1)], gold=(2, 14),
    ),
    dict(
        key="widmo_lodowe", label="Widmo Lodowe", tier="standard",
        hp=20, ac=12, atk=5, die="1d8", dmg=0, apt=1, xp=125,
        lvl=(3, 7), terrain="mountain,plains,ruins", scope="global", dmg_type="cold",
        desc="Sine zawirowanie śniegu, które porusza się pod wiatr. Krasnoludy nie "
             "nazywają go duchem — mówią po prostu: „to, co zostało na lodzie”.",
        loot=[("bone_dust", 55, 1, 2), ("ancient_scroll", 15, 1, 1)], gold=(0, 10),
    ),
    dict(
        key="salamandra_siarkowa", label="Salamandra Siarkowa", tier="standard",
        hp=24, ac=13, atk=5, die="1d8", dmg=1, apt=1, xp=145,
        lvl=(4, 7), terrain="mountain", scope="global", dmg_type="fire",
        desc="Grzeje się w gorących rozpadlinach Czarnych Skał. Skóra pokryta "
             "żółtym nalotem; oddech pachnie zapałkami na sekundę przed ciosem.",
        loot=[("alchemical_reagent", 60, 1, 2), ("oil_flask", 35, 1, 2)], gold=(3, 18),
    ),
    dict(
        key="troll_gorski", label="Troll Górski", tier="elite",
        hp=46, ac=15, atk=7, die="1d10", dmg=3, apt=1, xp=280,
        lvl=(6, 9), terrain="mountain,hills", scope="global", dmg_type="physical",
        desc="Kawał grani, który wstaje. Trolle śpią wrośnięte w piarg i budzą się "
             "wtedy, gdy ktoś idzie zbyt hałaśliwie — a krasnoludy chodzą hałaśliwie.",
        loot=[("iron_ore", 60, 1, 3), ("bear_hide", 30, 1, 1),
              ("dragon_scale_shard", 8, 1, 1)], gold=(10, 45),
    ),
]

# ── 2. SPOTKANIA ──────────────────────────────────────────────────────────────
# (klucz, biome=hex_type, poziomy, waga, wrogowie, tytuł, scena)
# WAGI startowe: dzicz 25–30, teren graniczny 18–22, TRAKT 10–12 (trakt ma być
# bezpieczniejszy od dziczy — karawany, patrole rodowe, ubita droga).
ENCOUNTERS: list[dict] = [
    # ── grania (44 hexy) — granie i urwiska
    dict(key="sg_grania_wilki", biome="grania", lvl=(1, 4), w=28,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Biała wataha na grani",
         scene="Śnieg przed tobą rusza się w trzech miejscach naraz. Wilki wyszły z zaspy "
               "bez jednego dźwięku i już są między tobą a zejściem z grani."),
    dict(key="sg_grania_lawina", biome="grania", lvl=(2, 6), w=22,
         enemies=[("harpia_granicka", "harpia graniowa", 1)],
         title="Krzyk nad półką skalną",
         scene="Nad tobą odbija się od ścian krzyk, który nie brzmi jak ptak. Sekundę "
               "później rusza pierwszy kamień, a za nim cała półka sypie się w dół — "
               "ktoś strącił go celowo."),
    dict(key="sg_grania_troll", biome="grania", lvl=(6, 9), w=18,
         enemies=[("troll_gorski", "troll górski", 1)],
         title="Piarg, który wstaje",
         scene="Mijasz zwał głazów, który pamiętasz z drogi w tę stronę. Tyle że teraz "
               "zwał ma ramiona i właśnie się prostuje."),
    # ── przelecz (4 hexy) — przełęcze
    dict(key="sg_przelecz_harpie", biome="przelecz", lvl=(3, 7), w=25,
         enemies=[("harpia_granicka", "harpia graniowa", 2)],
         title="Zasadzka na przełęczy",
         scene="Przełęcz jest wąska jak korytarz i tak samo dobrze niesie dźwięk. "
               "Dwa cienie odrywają się od ścian po obu stronach jednocześnie."),
    dict(key="sg_przelecz_wilki", biome="przelecz", lvl=(1, 4), w=25,
         enemies=[("sniezny_wilk", "śnieżny wilk", 3)],
         title="Wataha w gardzieli przełęczy",
         scene="Ślady na śniegu prowadzą w obie strony — wataha przeszła tędy i wróciła. "
               "Wróciła po ciebie."),
    # ── tundra (182 hexy) — największy teren krainy
    dict(key="sg_tundra_wilki", biome="tundra", lvl=(1, 4), w=30,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Trop w zamarzniętym mchu",
         scene="Na tundrze nie ma się gdzie schować — ani tobie, ani im. Wilki idą "
               "równolegle do ciebie od dłuższej chwili i właśnie zaczęły się zbliżać."),
    dict(key="sg_tundra_widmo", biome="tundra", lvl=(3, 7), w=22,
         enemies=[("widmo_lodowe", "widmo lodowe", 1)],
         title="Śnieg pod wiatr",
         scene="Zawieja idzie z północy, ale jeden słup śniegu sunie dokładnie przeciwnie. "
               "Zatrzymuje się, gdy ty się zatrzymujesz."),
    dict(key="sg_tundra_pustka", biome="tundra", lvl=(2, 6), w=18,
         enemies=[("sniezny_wilk", "śnieżny wilk", 1), ("widmo_lodowe", "widmo lodowe", 1)],
         title="Coś szło tędy przed tobą",
         scene="Padlina renifera, rozgrzebana, ale nietknięta — mięso zostało. Wilk "
               "krąży w oddali i nie podchodzi. Boi się nie ciebie."),
    # ── lodowiec (147 hexów) — Lodowy Pas
    dict(key="sg_lodowiec_widma", biome="lodowiec", lvl=(3, 8), w=28,
         enemies=[("widmo_lodowe", "widmo lodowe", 2)],
         title="Na lodzie nie ma cieni",
         scene="Lód jest tu przezroczysty na wiele metrów w głąb i pod stopami widać "
               "ciemne kształty. Dwa z nich właśnie zaczęły podnosić się ku powierzchni."),
    dict(key="sg_lodowiec_szczelina", biome="lodowiec", lvl=(5, 9), w=20,
         enemies=[("widmo_lodowe", "widmo lodowe", 1), ("troll_gorski", "troll lodowej grani", 1)],
         title="Szczelina, która oddycha",
         scene="Ze szczeliny bije ciepłe powietrze — na lodowcu to niemożliwe. "
               "Coś dużego przespało tam zimę i właśnie się poruszyło."),
    # ── siarka (50 hexów) — Siarkowe Pola. Rzadziej, ale zawsze z oparami.
    dict(key="sg_siarka_ogniki", biome="siarka", lvl=(2, 5), w=20,
         enemies=[("ognik_siarkowy", "ognik siarkowy", 2)],
         title="Wyziew i światła",
         scene="Żółty opar kładzie się przy ziemi i szczypie w gardło. W jego środku "
               "tańczą dwa światełka, które nie są odbiciem twojej pochodni."),
    dict(key="sg_siarka_salamandra", biome="siarka", lvl=(4, 8), w=18,
         enemies=[("salamandra_siarkowa", "salamandra siarkowa", 1)],
         title="Ciepły kamień",
         scene="Skała pod dłonią jest ciepła jak bok pieca. Coś zsuwa się z niej powoli, "
               "zostawiając na kamieniu żółty ślad, i patrzy na ciebie bez pośpiechu."),
    dict(key="sg_siarka_rzadkie", biome="siarka", lvl=(3, 7), w=12,
         enemies=[("ognik_siarkowy", "ognik siarkowy", 1),
                  ("salamandra_siarkowa", "salamandra siarkowa", 1)],
         title="Pole wyziewów",
         scene="Zbieracze siarki zostawili tu żerdzie wbite w ziemię co kilka kroków — "
               "znak, którędy da się przejść bez omdlenia. Trzy żerdzie dalej ktoś "
               "wywrócił je celowo."),
    # ── hills (116 hexów) — doliny i stoki
    dict(key="sg_hills_wilki", biome="hills", lvl=(1, 4), w=28,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Wataha na stoku",
         scene="Poniżej linii śniegu wilki są chudsze i śmielsze. Ta trójka nie ucieka, "
               "gdy krzyczysz — one już próbowały tej sztuczki wcześniej."),
    dict(key="sg_hills_bandyci", biome="hills", lvl=(2, 6), w=25,
         enemies=[("bandit", "zbój z dolin", 2)],
         title="Rogatka bez rogatki",
         scene="Dwóch chłopa siedzi przy ognisku dokładnie w miejscu, gdzie ścieżka "
               "zwęża się między głazami. Wstają bez pośpiechu — nie są zaskoczeni."),
    dict(key="sg_hills_harpia", biome="hills", lvl=(3, 7), w=20,
         enemies=[("harpia_granicka", "harpia graniowa", 1)],
         title="Cień, który zatacza koła",
         scene="Cień przechodzi po ziemi trzeci raz i za każdym razem jest niżej."),
    # ── heath (69 hexów) — wrzosowiska/przedgórza
    dict(key="sg_heath_wilki", biome="heath", lvl=(1, 4), w=25,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Ślady w oszronionym wrzosie",
         scene="Wrzos jest tu sztywny od szronu i chrzęści przy każdym kroku — twoim "
               "i ich. Dlatego słyszysz je, zanim zobaczysz."),
    dict(key="sg_heath_zbiegowie", biome="heath", lvl=(2, 5), w=22,
         enemies=[("zbieg", "wygnaniec z hołdu", 2)],
         title="Ci, którym nie starczyło hołdu",
         scene="Trzy postacie grzeją się przy ogniu tak małym, że prawie niewidocznym. "
               "Kiedy podnoszą głowy, widać, że dawno przestali pytać, kto idzie."),
    dict(key="sg_heath_widmo", biome="heath", lvl=(4, 8), w=15,
         enemies=[("widmo_lodowe", "widmo lodowe", 1)],
         title="Zimno, które przyszło za nisko",
         scene="Szron na wrzosie układa się w pas szerokości drogi, ciągnący się "
               "z północy aż do twoich stóp. Na jego końcu coś stoi."),
    # ── road (102 hexy) — trakt. Najniższe wagi: droga jest bezpieczniejsza.
    dict(key="sg_road_wilki", biome="road", lvl=(1, 4), w=12,
         enemies=[("sniezny_wilk", "śnieżny wilk", 1)],
         title="Wilk przy trakcie",
         scene="Pojedynczy wilk siedzi na kopcu przy drodze i patrzy, jak przechodzisz. "
               "Kiedy mijasz go o dziesięć kroków, rusza za tobą."),
    dict(key="sg_road_rozbojnicy", biome="road", lvl=(3, 7), w=12,
         enemies=[("brigand", "rozbójnik ze Starej Przełęczy", 2)],
         title="Myto, którego nikt nie ustanowił",
         scene="Na trakcie leży przewrócony wóz, za dobrze ustawiony, żeby przewrócił się "
               "sam. Zza niego wychodzi dwóch ludzi i pyta uprzejmie o opłatę."),
    dict(key="sg_road_karawana", biome="road", lvl=(2, 6), w=10,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Karawana w tarapatach",
         scene="Kilkaset kroków przed tobą stoi wóz karawany, a wokół niego krążą "
               "białe kształty. Woźnica jeszcze żyje i właśnie cię zobaczył."),
    # ── bridge (19 hexów) — mosty nad przepaściami
    dict(key="sg_bridge_harpie", biome="bridge", lvl=(3, 7), w=18,
         enemies=[("harpia_granicka", "harpia graniowa", 2)],
         title="Most i skrzydła",
         scene="Most wisi nad przepaścią, w której nie widać dna. W połowie przeprawy "
               "z dołu, spod desek, wzbija się coś na skrzydłach."),
    # ── ruins (15 hexów) — Wyssane Hołdy, Cmentarz Młotów, Echo-Wieża
    dict(key="sg_ruins_widma", biome="ruins", lvl=(3, 7), w=25,
         enemies=[("widmo_lodowe", "widmo lodowe", 1), ("skeleton", "kość rodowa", 2)],
         title="Hołd, którego nikt nie zamknął",
         scene="Bramy hołdu stoją otworem od dwudziestu lat. W środku nadal pali się "
               "jedno palenisko — i to jest najgorsze, co możesz tu zobaczyć."),
    dict(key="sg_ruins_troll", biome="ruins", lvl=(6, 9), w=15,
         enemies=[("troll_gorski", "troll ruin", 1)],
         title="Lokator",
         scene="Ktoś ułożył głazy w wejściu do sali rodowej tak, żeby zostawić jedno "
               "przejście. Ktoś, kto tu mieszka i lubi mieć jedne drzwi."),
    # ── snow / mountain / las_iglasty — tereny zaplanowane w §5, jeszcze nie na mapie
    dict(key="sg_snow_wilki", biome="snow", lvl=(1, 4), w=28,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2)],
         title="Biała wataha",
         scene="Zaspa przed tobą ma dwa ciemne punkty, które mrugają."),
    dict(key="sg_snow_widmo", biome="snow", lvl=(3, 7), w=20,
         enemies=[("widmo_lodowe", "widmo lodowe", 1)],
         title="Zawieja z jednej strony",
         scene="Śnieg sypie ci w twarz, choć wiatr wieje w plecy."),
    dict(key="sg_mountain_troll", biome="mountain", lvl=(6, 9), w=20,
         enemies=[("troll_gorski", "troll górski", 1)],
         title="Strażnik piargu",
         scene="Ścieżka zwęża się do szerokości barków, a zwał kamieni po prawej "
               "właśnie odwrócił głowę."),
    dict(key="sg_mountain_harpie", biome="mountain", lvl=(3, 7), w=25,
         enemies=[("harpia_granicka", "harpia graniowa", 2)],
         title="Gniazdo nad ścieżką",
         scene="Pod ścianą leżą kości owiec obrane do czysta. Wysoko nad tobą coś "
               "przestało krzyczeć — i to gorszy znak niż krzyk."),
    dict(key="sg_las_iglasty_wilki", biome="las_iglasty", lvl=(1, 5), w=28,
         enemies=[("sniezny_wilk", "śnieżny wilk", 2), ("wolf", "wilk", 1)],
         title="Świerkowy pas",
         scene="Gałęzie zrzucają śnieg tam, gdzie nikt ich nie trącił. Wataha "
               "prowadzi cię ku gęstwinie od kilkunastu kroków."),
    dict(key="sg_las_iglasty_bandyci", biome="las_iglasty", lvl=(2, 6), w=22,
         enemies=[("bandit_thug", "leśny oprych", 2)],
         title="Ognisko za gęstwiną",
         scene="Dym idzie nisko między świerkami. Przy ogniu siedzi dwóch, a trzeci "
               "właśnie wraca z chrustem — i staje, widząc ciebie."),
]

# ── 3. PLOTKI ─────────────────────────────────────────────────────────────────
# truth_flag=1 → plotka prawdziwa (kanon). Tajemnice krainy zostają PYTANIAMI:
# ani Lodowa Brama, ani natura Rdzenia nie dostają odpowiedzi.
RUMORS: list[tuple[str, int, str | None, str | None]] = [
    ("W Wyrobisku Srebrnej Żyły stukanie słychać teraz na drugiej zmianie, nie tylko "
     "na trzeciej. Sztygar mówi, że to woda w skale. Nikt mu nie wierzy, ale nikt "
     "też nie przestał kopać.", 1, "location", "wyrobisko_srebrnej_zyly"),
    ("Starszyzna zabroniła schodzić poniżej Linii Soli i tyle. Nie tłumaczy się. "
     "A jak coś się nie tłumaczy przez dwadzieścia lat, to znaczy, że wie więcej, "
     "niż mówi.", 1, "location", "posterunek_linii_soli"),
    ("Dagna Młotodzierżca werbuje w szynku, nie w Sali Rodów — bo w Sali Balrik "
     "kazałby jej zamilknąć, a przy stole nikt nie ma takiej władzy.", 1, None, None),
    ("Woreczek soli u pasa to nie przesąd. Górnik bez soli nie zejdzie, choćbyś mu "
     "płacił podwójnie.", 1, None, None),
    ("Kupcowa Helga wozi sól aż na Kresy i wraca z pustym wozem, ale nigdy z pustą "
     "sakiewką. Solnobrodzi mają teraz więcej złota niż Srebrnożylni.", 1, None, None),
    ("Wygnańcy Lodu handlują po cichu z Młotodzierżcami. Wyklęci wyklętymi, "
     "a żelazo żelazem.", 1, "location", "oboz_wygnancow_lodu"),
    ("Wygnańcy widzieli lodowiec z bliska jak nikt inny — i to oni schodzą z niego "
     "najniżej, jak się da. Boją się czegoś bardziej niż wyklęcia.", 1, "location",
     "oboz_wygnancow_lodu"),
    ("Sanktuarium na Lodowym Pasie stoi puste od pokoleń, a mimo to ktoś odgarnia "
     "z niego śnieg. Pytanie brzmi: kto i po co.", 1, "location",
     "sanktuarium_zamarznietej_pielgrzymki"),
    ("Wokół sanktuarium stoją ludzie wmarznięci w lód, wszyscy twarzami pod górę. "
     "Nikt nie wie, skąd przyszli ani czemu szli w tamtą stronę.", 1, "location",
     "sanktuarium_zamarznietej_pielgrzymki"),
    ("Na Cmentarzu Młotów każdy młot wbity w lód to jeden poległy z exodusu. "
     "Podobno nocą któryś z nich dzwoni — i wtedy reszta milczy.", 1, "location",
     "cmentarz_mlotow"),
    ("W Echo-Wieży zostały zapisy nasłuchu stukania. Ostatni obserwator odszedł, "
     "ale kart nie zabrał. Widać uznał, że są ważniejsze niż on.", 1, "location",
     "echo_wieza"),
    ("Sztolnia Umarłego Rodu jest pusta od pokoleń, tylko grób w niej pilnowany. "
     "Przez co — o to już nikt nie pyta drugi raz.", 1, "dungeon",
     "sztolnia_umarlego_rodu"),
    ("Do Kopalni Czarnego Hutmana schodzi się jednym korytarzem i nikt nie wraca "
     "tą samą drogą, bo nie wraca wcale. Młotodzierżcy uważają, że to kwestia "
     "odpowiedniej liczby toporów.", 1, "dungeon", "kopalnia_czarnego_hutmana"),
    ("Na lodowcu stoją wmarznięte wrota. Nikt nie wie, kto je postawił ani co jest "
     "za nimi — i nikt nie zna nikogo, kto próbowałby się dowiedzieć.", 1, "location",
     "lodowa_brama"),
    ("Zakaz wchodzenia na Lodowy Pas jest starszy niż zakaz kopania poniżej soli. "
     "Stare krasnoludy mówią, że oba wydał ten sam ktoś, ale żadne nie powie kto.",
     1, None, None),
]

# Hexy, na których wolno spotkać zamarzniętych pielgrzymów: sam hex sanktuarium
# i jego bezpośrednie sąsiedztwo (pielgrzymka szła procesją, nie rozproszyła się
# po całym lodowcu). Kluczowe: `zamarzniety_pielgrzym` ma world_scope='pool',
# więc POZA tymi hexami silnik nie może go w ogóle wylosować.
SANCTUARY_HEX = (36, -65)
SANCTUARY_POOL = ["zamarzniety_pielgrzym", "widmo_lodowe"]
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
        # Seed jest źródłem prawdy dla pól „strojlnych" (content-as-code #1202): przy
        # powtórnym uruchomieniu dociągamy je do wartości z pliku, nie zostawiając
        # rozjazdu DB ↔ repo. Reszta rekordu (opisy, łupy) zostaje bez zmian.
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


def seed_sanctuary_pool(conn: sqlite3.Connection) -> int:
    """Autorska pula wrogów wokół sanktuarium — jedyne miejsce, gdzie silnik może
    wylosować zamarzniętych pielgrzymów (world_scope='pool')."""
    n = 0
    for q, r in _hex_ring(SANCTUARY_HEX, radius=1):
        row = conn.execute(
            "SELECT encounter_pool FROM world_hexes WHERE q=? AND r=? AND map_level=0",
            (q, r),
        ).fetchone()
        if not row:
            continue
        try:
            current = json.loads(row[0] or "[]")
        except Exception:
            current = []
        merged = sorted(set(current) | set(SANCTUARY_POOL))
        if merged == sorted(set(current)):
            continue
        conn.execute(
            "UPDATE world_hexes SET encounter_pool = ? WHERE q=? AND r=? AND map_level=0",
            (json.dumps(merged), q, r),
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
    pool_n = seed_sanctuary_pool(conn)
    conn.commit()

    print(f"  wrogowie nowi:            {res['enemies']} (z {len(ENEMIES)})")
    print(f"  tabele łupów nowe:        {res['loot_tables']}")
    print(f"  wpisy łupów nowe:         {res['loot_entries']}")
    print(f"  spotkania nowe:           {enc_n} (z {len(ENCOUNTERS)})")
    print(f"  plotki nowe:              {rum_n} (z {len(RUMORS)})")
    print(f"  hexy sanktuarium z pulą:  {pool_n}")

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
