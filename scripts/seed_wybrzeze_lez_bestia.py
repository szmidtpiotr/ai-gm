#!/usr/bin/env python3
"""WL-7 — zawartość bojowa i „żywa" Wybrzeża Łez: wrogowie + spotkania + plotki
+ dwa lochy (Cmentarzysko Wraków = farm pływowo-bramkowany, Jaskinie Skarbów = farm
z przeciekającą klątwą).

Źródło prawdy: docs/world/regions/wybrzeze_lez.md §1–§9 + charakter pul ustalony
w zadaniu WL-7. Wzorzec 1:1: scripts/seed_martwe_pustkowia_bestia.py (MP-6) i
scripts/seed_czarnobor_bestia.py (CB-6).

CHARAKTER KRAINY (kanon §1, §4): morze jako żywioł i grób; mrok KARMI. GRADIENT
zagrożeń po terenie:
  * porty (town) + pierścień wokół nich — BEZPIECZNE (ward encounter_chance=0),
  * trakt (road) / zaplecze (plains, heath, forest) — piraci i przemytnicy, lekko,
  * wydmy (wydmy) — nadmorska dzicz: zasadzki rozbójników,
  * wybrzeże (coast) — CIĘŻKO: szabrownicy, nieumarli marynarze z wraków,
  * mielizny (plycizna) — NAJRYZYKOWNIEJ przy zmianie pływu: topielce i utopce,
  * LATARNIA TOPIELCÓW + rafy — NAJGORSZE PULE: elity Głębi (scope='pool').

GRADIENT SZANSY jest już ustawiony w WL-1 (hex_type_config.encounter_base_chance):
  coast 0.15 · wydmy 0.12 · plycizna 0.30 (najwyższa przejezdna) — mielizny same
  z siebie ryzykowne. Tu dokładamy PULĘ SCEN (game_config_encounters) z wagami
  W TYM SAMYM gradiencie (mielizny = najcięższe, najwięcej scen; trakt = najlżej)
  oraz tożsamość tematyczną (piraci → topielce → nieumarli → Głębia).

„WYBRZEŻE PRZY LATARNI NAJGORSZE": per-hex `encounter_chance` NIE potrafi PODNIEŚĆ
szansy powyżej bazy terenu (#1390 — teren nadpisuje; jedyny działający lewar w dół
to jawne 0 = strefa bezpieczna). Dlatego „najgorsze" realizujemy PULĄ, nie szansą:
elity Głębi (`cos_z_sieci`, `glebinowy_pomiot`, scope='pool', terrain_tags PUSTE =
generyczne, więc przechodzą przez filtr każdego terenu pierścienia) wpisane w
`world_hexes.encounter_pool` na pierścieniu wokół Latarni. `_apply_pool_keys`
(BL-A7 #1423) ZAWĘŻA tam pulę wyłącznie do tych elit → pod Latarnią trafiasz tylko
na to, co najgorsze (o ile poziom bohatera je dopuszcza; niżej — łagodny fallback).

CO CZYTA SILNIK:
  * `game_config_enemies` → `encounter_service.eligible_enemy_pool()` (~50% spotkań):
    world_scope, review_status, is_active, pasmo poziomów, `terrain_tags` vs teren
    hexa, `region_tag` vs kraina. coast/rafy/morze → tag `river`; plycizna → `swamp`;
    wydmy → `plains` (WL-1 `_HEX_TYPE_TO_TERRAIN`).
  * `game_config_encounters` → `encounter_catalog_service.draw_combat()` (~50%):
    kind/biome/poziom + `region_tag`. `biome` = WPROST `world_hexes.hex_type`
    (coast / plycizna / wydmy / plains / heath / road / forest) — pula scen ROZRÓŻNIA
    wybrzeże od mielizny od zaplecza (czego filtr terenu wrogów nie umie, bo coast
    i plycizna oba są „wodne"). Elit Głębi (pool) NIE ma w scenach — tylko w puli
    Latarni i w lochach, żeby nie wyciekły na całe wybrzeże.
  * `world_rumors` → `rumor_service.draw_for_region()`.
  * `game_dungeons` → Cmentarzysko Wraków (farm, bramka pływowa) + Jaskinie Skarbów
    (farm, klątwa). Bramka pływowa Cmentarzyska = `tide_service.dungeon_blocked_by_tide`
    (synergia z WL-5) — wpięta w `POST /dungeons/{key}/enter`.
  * `world_hexes.encounter_pool` → pula Latarni (elity scope='pool' tylko tam).
  * `world_hexes.encounter_chance = 0` → strefy bezpieczne wokół portów.

WARTOŚCI STARTOWE (Numbers Policy): staty wrogów, wagi/pasma scen, promienie pul
i wardów, cooldown lochów — wszystko strojlne w Sandboxie. Pasma pod bohatera 3–9
bez inwersji tierów (#1376): weak < standard < elite < boss.

Idempotentny: INSERT OR IGNORE po kluczu; plotki po treści; pule/wardy nadpisują
tylko wskazane pierścienie. Seed = źródło prawdy pól strojlnych (content-as-code
#1202) — game_config_encounters / world_rumors / dungeon_tiles / world_hexes.pool
NIE są w CONTENT_TABLES snapshotu, więc ten skrypt jest ich jedynym źródłem prawdy.

    docker cp scripts/seed_wybrzeze_lez_bestia.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_wybrzeze_lez_bestia.py
    docker exec ai-gm-dev-backend-1 python /app/seed_wybrzeze_lez_bestia.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "wybrzeze_lez"

# ── 1. WROGOWIE ───────────────────────────────────────────────────────────────
# Globalni nieumarli (skeleton, zombie, ghoul, wraith, undead_champion) JUŻ ISTNIEJĄ
# i dochodzą na terenie wodnym (coast/rafy → tag `river`). Reużywamy też
# `bagienny_topielec` (swamp,river 6-10) i `topielec_mielizny` (swamp 2-5) w scenach
# mielizn — bez duplikatów. Te wpisy UZUPEŁNIAJĄ braki tożsamości Wybrzeża:
#   * piraci i przemytnicy — ląd/porty (terrain plains,river = wydmy + coast + zaplecze),
#   * topielec morski + kultysta Głębi — mielizny/wybrzeże (swamp,river),
#   * nieumarły marynarz — wraki i wybrzeże (river),
#   * elity Głębi (cos_z_sieci, glebinowy_pomiot, scope='pool', terrain PUSTE) — pula
#     Latarni + lochy: „najgorsze",
#   * dwaj bossowie lochów (scope='pool': nie wychodzą na podróż).
ENEMIES: list[dict] = [
    # ── weak (zaplecze / wydmy / porty, hero 3-5) ────────────────────────────
    dict(
        key="morski_rozbojnik", label="Morski Rozbójnik", tier="weak",
        hp=18, ac=13, atk=4, die="1d6", dmg=1, apt=1, xp=85,
        lvl=(3, 5), terrain="plains,river", scope="global", dmg_type="physical",
        desc="Prawo Korony kończy się na linii przyboju, a za nią rządzi kordelas. "
             "Zeszli z czarnej galery po to, co da się zabrać z brzegu — a ty "
             "wyglądasz na kogoś, kto ma przy sobie coś więcej niż sól.",
        loot=[("krag_soli", 40, 1, 1), ("bandage", 30, 1, 1),
              ("szczypta_soli", 35, 1, 2)], gold=(3, 16),
    ),
    # ── standard (wybrzeże / mielizny / kult, hero 3-7) ──────────────────────
    dict(
        key="przemytnik_soli", label="Przemytnik", tier="standard",
        hp=24, ac=13, atk=5, die="1d6", dmg=1, apt=1, xp=120,
        lvl=(3, 6), terrain="plains,river", scope="global", dmg_type="physical",
        desc="Nosi towar, o który nie wypada pytać, i nóż na tych, co pytają. "
             "Kontrabanda z Czarnego Targu idzie tędy w głąb lądu, a świadek na "
             "ścieżce to jeden świadek za dużo.",
        loot=[("krag_soli", 45, 1, 2), ("alchemical_reagent", 35, 1, 1),
              ("szczypta_soli", 30, 1, 2)], gold=(5, 22),
    ),
    dict(
        key="topielec_morski", label="Topielec Morski", tier="standard",
        hp=28, ac=13, atk=5, die="1d8", dmg=1, apt=1, xp=140,
        lvl=(4, 7), terrain="swamp,river", scope="global", dmg_type="necrotic",
        desc="Morze oddaje utopionych, ale nie takich, jakimi byli. Zielonosina "
             "skóra, wodorosty we włosach i płuca pełne słonej wody — wychodzi z "
             "mielizny, gdy pływ się zmienia, i chce, żebyś poszedł tam, skąd on "
             "wrócił.",
        loot=[("bone_dust", 45, 1, 2), ("alchemical_reagent", 30, 1, 1),
              ("healing_herb", 20, 1, 1)], gold=(0, 8),
    ),
    dict(
        key="nieumarly_marynarz", label="Nieumarły Marynarz", tier="standard",
        hp=26, ac=13, atk=5, die="1d8", dmg=1, apt=1, xp=135,
        lvl=(4, 7), terrain="river", scope="global", dmg_type="necrotic",
        desc="Załoga statku, który latarnia zwabiła na rafy, nie doszła do brzegu "
             "— i nie odeszła. Nocą marynarze w zbutwiałych łachmanach schodzą z "
             "wraków i wracają do jedynej roboty, jaką znają: obsadzić pokład i nie "
             "wpuścić obcego.",
        loot=[("bone_dust", 50, 1, 2), ("krag_soli", 25, 1, 1),
              ("alchemical_reagent", 25, 1, 1)], gold=(2, 14),
    ),
    dict(
        key="kultysta_glebi", label="Kultysta Głębi", tier="standard",
        hp=30, ac=12, atk=6, die="1d8", dmg=1, apt=1, xp=155,
        lvl=(4, 7), terrain="swamp,river", scope="global", dmg_type="necrotic",
        desc="Modli się do tego, co pod dnem, i twierdzi, że to Głębia wzywa statki "
             "na rafy. Przy Świątyni Topielców składa morzu, co morze lubi — a lubi "
             "krew i oddech. Twój by się nadał.",
        loot=[("relikt_pradawnych", 18, 1, 1), ("alchemical_reagent", 40, 1, 2),
              ("bandage", 25, 1, 1)], gold=(3, 18),
    ),
    # ── elite (herszt piracki + elity Głębi, hero 6-9) ───────────────────────
    dict(
        key="bosman_herszt", label="Bosman-Herszt", tier="elite",
        hp=44, ac=14, atk=7, die="1d10", dmg=2, apt=1, xp=230,
        lvl=(6, 9), terrain="plains,river", scope="global", dmg_type="physical",
        desc="Bosman jednej z czarnych galer, co dorobił się własnej załogi i "
             "własnej ceny za głowę. Zna każdą rafę i każdą zatoczkę, a przy pasie "
             "nosi zwoje warte więcej niż jego statek — mapy szlaków, o które komuś "
             "bardzo zależy.",
        loot=[("mapa_smolnego", 8, 1, 1), ("krag_soli", 40, 1, 2),
              ("alchemical_reagent", 40, 1, 2), ("relikt_pradawnych", 15, 1, 1)],
        gold=(15, 60),
    ),
    dict(
        key="cos_z_sieci", label="Coś z Sieci", tier="elite",
        hp=46, ac=13, atk=7, die="1d10", dmg=2, apt=2, xp=245,
        lvl=(6, 9), terrain="", scope="pool", dmg_type="necrotic",
        desc="Rybacy wyciągają w sieciach różne rzeczy; niektóre jeszcze się ruszają "
             "i lepiej ich nie tykać. Bezokie, obwiedzione łuską i wodorostami, "
             "przyszło z Głębi tam, gdzie latarnia zwabia statki. Nie tonie i nie "
             "oddycha — po prostu jest, i chce cię zabrać ze sobą pod wodę.",
        loot=[("relikt_pradawnych", 25, 1, 1), ("bone_dust", 45, 1, 3),
              ("alchemical_reagent", 40, 1, 2)], gold=(6, 26),
    ),
    dict(
        key="glebinowy_pomiot", label="Głębinowy Pomiot", tier="elite",
        hp=42, ac=14, atk=7, die="1d8", dmg=2, apt=2, xp=240,
        lvl=(6, 9), terrain="", scope="pool", dmg_type="necrotic",
        desc="Kult Topielców mówi, że Głębia rodzi własne dzieci i wysyła je na "
             "brzeg, gdy latarnia zapala się sama. Kłębowisko macek, łusek i czegoś, "
             "co kiedyś mogło być człowiekiem — pełznie z przyboju ku światłu i ku "
             "wszystkiemu, co ciepłe.",
        loot=[("relikt_pradawnych", 25, 1, 1), ("bone_dust", 40, 1, 3),
              ("krag_soli", 25, 1, 1)], gold=(6, 24),
    ),
    # ── bossowie lochów (scope='pool': tylko w kaflach lochów) ────────────────
    dict(
        key="utopiony_kapitan", label="Utopiony Kapitan", tier="boss",
        hp=70, ac=15, atk=8, die="1d10", dmg=3, apt=2, xp=430,
        lvl=(5, None), terrain="river,castle", scope="pool", dmg_type="necrotic",
        desc="Kapitan, którego latarnia zwabiła na rafy pierwszego — i który wciąż "
             "nie przyjął, że statek zatonął. Na mostku widmowego okrętu w sercu "
             "Cmentarzyska Wraków trzyma ster spuchniętą dłonią i zwołuje załogę, "
             "gdy tylko ktoś dość głupi wejdzie na pokład przy odpływie.",
        loot=[("mapa_smolnego", 18, 1, 1), ("relikt_pradawnych", 35, 1, 1),
              ("krag_soli", 30, 1, 2), ("bone_dust", 40, 1, 3)],
        gold=(40, 120),
    ),
    dict(
        key="straznik_klatwy", label="Strażnik Klątwy", tier="boss",
        hp=64, ac=15, atk=8, die="1d10", dmg=2, apt=2, xp=400,
        lvl=(6, None), terrain="", scope="pool", dmg_type="necrotic",
        desc="W Jaskiniach Skarbów klątwa przecieka: każdy łup zabrany stąd wraca "
             "nocą jako nieumarły i wlecze się z powrotem do jaskiń. Na dnie, na "
             "kopcu z tego, czego nikt nie zdążył wynieść, siedzi ten, który pilnuje, "
             "by wróciło wszystko — łącznie z tobą.",
        loot=[("relikt_pradawnych", 40, 1, 1), ("krag_soli", 30, 1, 2),
              ("bone_dust", 45, 1, 3), ("alchemical_reagent", 40, 1, 2)],
        gold=(35, 110),
    ),
]

# ── 2. SPOTKANIA ──────────────────────────────────────────────────────────────
# (klucz, biome=hex_type, poziomy, waga, wrogowie[(key,nazwa,ile)], tytuł, scena)
# WAGI = gradient krainy: road 10-12 · plains/heath/forest 14-16 · wydmy 18-20
# · coast 22-26 (wybrzeże cięższe) · plycizna 24-28 (mielizny najryzykowniej).
# Elit Głębi (cos_z_sieci / glebinowy_pomiot, scope='pool') NIE ma w scenach —
# wyłącznie w puli Latarni i lochach, żeby nie wyciekły na całe wybrzeże.
ENCOUNTERS: list[dict] = [
    # ── road (52 hexy) — trakt: najlżej ──────────────────────────────────────
    dict(key="wl_road_rozbojnicy", biome="road", lvl=(3, 5), w=12,
         enemies=[("morski_rozbojnik", "morski rozbójnik", 1)],
         title="Rogatka rozbójników",
         scene="Na trakcie od strony portu ktoś zawadził drogę beczką i sieciami. "
               "Zza nich wychodzi zbój z kordelasem — myto pobiera po swojemu."),
    dict(key="wl_road_przemytnicy", biome="road", lvl=(3, 6), w=10,
         enemies=[("przemytnik_soli", "przemytnik", 1)],
         title="Nocny transport",
         scene="Ktoś prowadzi juczne zwierzę traktem po zmroku, bez pochodni. Kiedy "
               "cię dostrzega, ręka idzie do noża zamiast do czapki — świadek to "
               "kłopot."),
    # ── plains (317 hexów) — zaplecze lądowe: zagony piratów ─────────────────
    dict(key="wl_plains_pirat", biome="plains", lvl=(3, 5), w=16,
         enemies=[("morski_rozbojnik", "morski rozbójnik", 2)],
         title="Zagon na wieś",
         scene="Dwaj zbóje wracają od strony wsi z workami przez ramię. Widzą cię i "
               "uznają, że dobra jest jeszcze za mało, a ty masz przy sobie resztę."),
    dict(key="wl_plains_przemyt", biome="plains", lvl=(3, 6), w=14,
         enemies=[("przemytnik_soli", "przemytnik", 2)],
         title="Skład na rozstajach",
         scene="Za kępą krzaków dwóch ludzi przekłada zawiniątka z juków do juków. "
               "Prostują się jak jeden mąż — nie lubią, gdy ktoś liczy ich pakunki."),
    # ── heath (215 hexów) — wrzosowiska nadmorskie ───────────────────────────
    dict(key="wl_heath_banda", biome="heath", lvl=(3, 6), w=16,
         enemies=[("morski_rozbojnik", "morski rozbójnik", 1),
                  ("przemytnik_soli", "przemytnik", 1)],
         title="Obóz na wrzosowisku",
         scene="Nad wrzosem snuje się dym z małego ogniska. Przy nim zbój i "
               "przemytnik dzielą łup — twoje nadejście traktują jak trzecią porcję "
               "do rozdania."),
    dict(key="wl_heath_kultysci", biome="heath", lvl=(4, 7), w=14,
         enemies=[("kultysta_glebi", "kultysta Głębi", 1)],
         title="Znak na kamieniu",
         scene="Na płaskim głazie ktoś wyrył spiralę i obłożył ją muszlami. Przy niej "
               "klęczy postać w kapturze, mamrocząc ku morzu, i odwraca się do "
               "ciebie z uśmiechem, jakby morze cię przysłało."),
    # ── forest (246 hexów) — kępy lasu przy ujściu ───────────────────────────
    dict(key="wl_forest_przemyt", biome="forest", lvl=(3, 6), w=14,
         enemies=[("przemytnik_soli", "przemytnik", 2)],
         title="Kryjówka w zagajniku",
         scene="Wśród nadmorskich sosen stoi szałas obwieszony sieciami. Dwóch ludzi "
               "wyskakuje spomiędzy pni — trafiłeś na skład, którego mieli nie "
               "znaleźć obcy."),
    # ── wydmy (134 hexy) — nadmorska dzicz: zasadzki ──────────────────────────
    dict(key="wl_wydmy_zasadzka", biome="wydmy", lvl=(3, 5), w=20,
         enemies=[("morski_rozbojnik", "morski rozbójnik", 2)],
         title="Zasadzka w wydmach",
         scene="Piach tłumi kroki, więc słyszysz ich za późno. Dwaj zbóje zrywają się "
               "zza grzbietu wydmy — czekali na kogoś takiego jak ty przy szlaku na "
               "brzeg."),
    dict(key="wl_wydmy_marynarz", biome="wydmy", lvl=(4, 7), w=18,
         enemies=[("nieumarly_marynarz", "nieumarły marynarz", 1)],
         title="Wyrzucony przez morze",
         scene="Na skraju wydm leży coś na wpół zasypanego piaskiem, w strzępach "
               "marynarskiej koszuli. Kiedy podchodzisz, to coś wygrzebuje rękę i "
               "dźwiga się na nogi."),
    # ── coast (249 hexów) — wybrzeże: szabrownicy, marynarze z wraków ─────────
    dict(key="wl_coast_wraki", biome="coast", lvl=(4, 7), w=26,
         enemies=[("nieumarly_marynarz", "nieumarły marynarz", 2)],
         title="Marynarze z wraków",
         scene="Na plaży sterczą żebra rozbitego kadłuba, a wokół nich rusza się "
               "kilka sylwetek w zbutwiałych łachmanach. Schodzą z wraku ku tobie "
               "równym, marynarskim krokiem, jakby wciąż byli na wachcie."),
    dict(key="wl_coast_szabrownicy", biome="coast", lvl=(3, 6), w=24,
         enemies=[("morski_rozbojnik", "morski rozbójnik", 2),
                  ("przemytnik_soli", "przemytnik", 1)],
         title="Szabrownicy na plaży",
         scene="Morze wyrzuciło ładunek i już się przy nim krzątają. Trzech ludzi z "
               "hakami i workami odwraca się od skrzyń — nowy na plaży to konkurent "
               "albo świadek, a jedno i drugie się załatwia."),
    dict(key="wl_coast_topielec", biome="coast", lvl=(4, 7), w=22,
         enemies=[("topielec_morski", "topielec morski", 1)],
         title="Coś wyszło z przyboju",
         scene="Fala cofa się z plaży i zostawia sylwetkę, która nie powinna stać. "
               "Zielonosina, ociekająca wodą, rusza ku tobie po mokrym piachu z "
               "płucami pełnymi morza."),
    dict(key="wl_coast_bosman", biome="coast", lvl=(6, 9), w=22,
         enemies=[("bosman_herszt", "bosman-herszt", 1),
                  ("morski_rozbojnik", "morski rozbójnik", 2)],
         title="Herszt z załogą",
         scene="Na brzegu dobiła szalupa, a z niej zszedł ktoś, kogo reszta słucha bez "
               "słowa. Bosman-herszt mierzy cię wzrokiem jak towar, a jego ludzie "
               "rozchodzą się, żeby odciąć ci drogę na ląd."),
    # ── plycizna (448 hexów) — mielizny: NAJRYZYKOWNIEJ przy zmianie pływu ─────
    dict(key="wl_plycizna_topielce", biome="plycizna", lvl=(4, 7), w=28,
         enemies=[("topielec_morski", "topielec morski", 2)],
         title="Topielce przy zmianie pływu",
         scene="Woda zaczyna wracać na mieliznę, a razem z nią wychodzą oni — dwie "
               "zielonosine postaci brną ku tobie przez płytki nurt. Pływ jest ich "
               "sprzymierzeńcem; ty masz coraz mniej suchego gruntu pod nogami."),
    dict(key="wl_plycizna_mielizna", biome="plycizna", lvl=(3, 5), w=26,
         enemies=[("topielec_mielizny", "topielec z mielizny", 2)],
         title="Coś czeka w mieliźnie",
         scene="Płycizna wygląda pusto, dopóki nie zmącisz jej krokiem. Spod warstwy "
               "mułu podnoszą się dwie postaci, które przywarły do dna i czekały, aż "
               "ktoś przejdzie tędy przy odpływie."),
    dict(key="wl_plycizna_marynarz", biome="plycizna", lvl=(4, 7), w=24,
         enemies=[("nieumarly_marynarz", "nieumarły marynarz", 1),
                  ("topielec_morski", "topielec morski", 1)],
         title="Wachta na mieliźnie",
         scene="Na mieliźnie sterczy z wody złamany maszt, a przy nim czuwają dwie "
               "sylwetki — jedna w marynarskich łachmanach, druga ociekająca morzem. "
               "Pływ rośnie, a one nie mają dokąd się spieszyć. Ty masz."),
    dict(key="wl_plycizna_bagienny", biome="plycizna", lvl=(6, 9), w=24,
         enemies=[("bagienny_topielec", "bagienny topielec", 1)],
         title="Stary z mielizny",
         scene="Nie wszystko w mieliźnie jest świeżo utopione. To wygrzebuje się "
               "wolno, oblepione mułem i wodorostami zebranymi przez lata, i wie o "
               "pływach więcej niż ty — bo samo jest jednym z nich."),
]

# ── 3. PLOTKI ─────────────────────────────────────────────────────────────────
# truth_flag=1 → plotka prawdziwa (kanon). Tajemnice krainy zostają PYTANIAMI:
# KTO zapala Latarnię (§4 — ZAKAZ ROZSTRZYGANIA) i CO jest Głębią pod dnem — bez
# odpowiedzi. Cele location = klucze game_locations; dungeon = klucze game_dungeons.
RUMORS: list[tuple[str, int, str | None, str | None]] = [
    ("Latarnia Topielców stoi pusta od pokoleń, a mimo to nocą zapala się sama i "
     "wciąga statki na rafy. Jedni mówią, że to duch latarnika, inni że kult, jeszcze "
     "inni że sama Głębia woła — nikt nie widział, kto stoi tam z ogniem.", 1,
     "location", "czarnogrod_latarnia_topielcow"),
    ("W Radzie Pirackiej cztery fotele zajęte, a piąty pusty — kapitan, który go "
     "trzymał, przepadł na morzu i nie wrócił. Powiadają, że fotel jest do wzięcia dla "
     "tego, komu starczy noża i szczęścia.", 1, "location", "zatoka_rada_piracka"),
    ("Na Czarnym Targu handluje się towarem „z głębin” — rzeczami, które morze wyrzuca "
     "przy rafach albo które ktoś wyławia dalej, niż śmią zapuszczać się rybacy. Nie "
     "pytaj, skąd; zapłać i nie oglądaj się.", 1, "location",
     "czarnogrod_giełda_kontrabandy"),
    ("Kapitan Smolny narysował mapę raf i wraków, na której komuś bardzo zależy — bo "
     "kto ją ma, ten omija rzeź przy latarni i wie, gdzie leżą zatopione ładunki. "
     "Mapa gdzieś krąży między wrakami i portem.", 1, "dungeon", "cmentarzysko_wrakow"),
    ("W Jaskiniach Skarbów łupy same wracają do właściciela — do jaskiń. Klątwa "
     "przecieka: co stamtąd wyniesiesz, wstaje nocą jako nieumarłe i wlecze się z "
     "powrotem, a czasem po ciebie.", 1, "dungeon", "jaskinie_skarbow"),
    ("Do Cmentarzyska Wraków da się wejść tylko przy odpływie — przypływ zakrywa "
     "dojście między rafami i biada temu, kogo woda tam zastanie. Kto źle liczy pływ, "
     "zostaje na cmentarzysku na stałe.", 1, "dungeon", "cmentarzysko_wrakow"),
    ("Przy Świątyni Topielców kult składa morzu ofiary i twierdzi, że pod dnem coś "
     "leży — coś dużego, co pochłonęło je morze. Starzy rybacy mówią jedno: nie "
     "wypływaj tam, gdzie woda milknie.", 1, "location", "wybrzeze_świątynia_topielcow"),
    ("Na Wraki po zmroku schodzą marynarze, którzy nie doszli do brzegu — załoga "
     "statku, który latarnia zwabiła na skały. Wracają na pokład, jakby wciąż mieli "
     "wachtę, i nie znoszą żywych między sobą.", 1, "location",
     "wybrzeze_wraki_starych_statkow"),
    ("Zatoka Topielców leży na wyspie-twierdzy i słucha pięciu kapitanów, choć teraz "
     "jest ich czterech. Handluje się tam wszystkim, także ludźmi, a Korona nie ma "
     "tam nic do gadania.", 1, "location", "zatoka_topielcow"),
    ("W dzielnicy wyspiarzy w Czarnogrodzie mieszkają ci, co przypłynęli przez Sztorm "
     "Wieczny dwa pokolenia temu — i żaden nie wrócił do domu, bo domu już nie ma. "
     "Najlepsi marynarze i przemytnicy w porcie, bo nie mają dokąd wracać.", 1,
     "location", "czarnogrod_dzielnica_wyspiarzy"),
    ("Latarnia Starego na wybrzeżu wygasła, gdy stary latarnik zniknął. Nie znaleziono "
     "ciała, tylko otwartą księgę wacht i lampę pełną oliwy — jakby wyszedł na chwilę "
     "i nie wrócił.", 1, "location", "wybrzeze_latarnia_starego"),
    ("Rybacy z wsi na palach wyciągają czasem w sieciach coś, co jeszcze się rusza, a "
     "nie jest rybą. Wprawi zaraz wrzucają to z powrotem; nieprawi próbują sprzedać — "
     "i nieprawych ubywa.", 1, None, None),
    ("Wsie na palach nad mieliznami żyją z tego, co morze wyrzuci przy rafach. Zgaś "
     "latarnię, a uratujesz statki i zagłodzisz trzy osady — dlatego nikt jej nie "
     "gasi, choć każdy klnie.", 1, None, None),
    ("Warzelnie na mieliznach dają najtańszą sól świata — gorszą od górskiej i od "
     "pustynnej, ale morza nikt nie musi kopać. Sól idzie stąd w głąb lądu, a z nią "
     "kontrabanda schowana w beczkach.", 1, None, None),
]

# ── 4. LOCHY ──────────────────────────────────────────────────────────────────
# Cmentarzysko Wraków = FARM z BRAMKĄ PŁYWOWĄ (synergia WL-5): wejście tylko przy
# ODPŁYWIE (tide_service.dungeon_blocked_by_tide, wpięte w POST /dungeons/{key}/enter).
# Jaskinie Skarbów = FARM z klątwą (łupy wracają jako nieumarli — motyw w atmosferze
# i kaflach: skarby PILNOWANE przez to, co z nich wstało). Oba: silnik kafelkowy
# (#1507) — enter_dungeon_tiles WYMAGA `tile_category_key` (inaczej 409), więc każdy
# loch dostaje DEDYKOWANĄ kategorię kafli z wrogami z puli krainy i kaflem bossa.
# Kafle bez obrazków (grywalne, UI pokaże placeholder); grafiki FLUX = follow-up.
_HEX_NEIGHBOURS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _dead_ends(theme: str) -> list[dict]:
    d = theme
    return [
        dict(label=f"Ślepy Zaułek {d} (N)", enemies=[], boss=0, items=[], doors=["N"],
             desc="Korytarz urywa się litą skałą. Dalej nie ma drogi."),
        dict(label=f"Ślepy Zaułek {d} (S)", enemies=[], boss=0, items=[], doors=["S"],
             desc="Zawał zamyka przejście. Ślepy kąt."),
        dict(label=f"Ślepy Zaułek {d} (E)", enemies=[], boss=0, items=[], doors=["E"],
             desc="Woda wypełnia korytarz po sufit. Nie przejdziesz."),
        dict(label=f"Ślepy Zaułek {d} (W)", enemies=[], boss=0, items=[], doors=["W"],
             desc="Przejście kończy się ścianą oblepioną małżami."),
    ]


DUNGEONS: list[dict] = [
    dict(
        key="cmentarzysko_wrakow", label="Cmentarzysko Wraków",
        location_key="wybrzeze_wraki_starych_statkow",
        rooms=7, tile_category_key="cmentarzysko_wrakow", tile_count=7,
        boss_tile_id=None,
        enemy_pool=["nieumarly_marynarz", "topielec_morski", "cos_z_sieci",
                    "skeleton", "zombie"],
        boss_enemy="utopiony_kapitan", loot_tier="rich",
        cooldown_hours=48, min_level=5,
        atmosphere=("Pas raf, na którym latarnia zebrała najwięcej żniwa: kadłub przy "
                    "kadłubie, maszty jak las bez liści, a między nimi załogi, które "
                    "nie doszły do brzegu. Wejść można tylko przy odpływie — przypływ "
                    "zakrywa dojście i zamyka cię z tym, co wraca z wodą."),
        room_types_json='{"combat":58,"chest":15,"trap":10,"riddle":7,"rest":10}',
        dungeon_difficulty=3, room_loot_chance=0.18, rest_heal_pct=18, rest_charges=2,
        category=dict(
            key="cmentarzysko_wrakow", label="Cmentarzysko Wraków", sort_order=81,
            description="Pas raf zawalony rozbitymi statkami — połamane kadłuby, "
                        "przegniłe pokłady, zatopione ładownie i widmowy okręt "
                        "kapitana pośrodku, wszystko w rytmie pływu.",
            style_modifier=("shipwreck graveyard, shattered rotting hulls, broken masts "
                            "and tangled rigging, barnacle-crusted planks, seaweed and "
                            "tidal pools, grey-green drowned aesthetic, cold sea mist"),
            system_prompt=("Opisujesz miejsce w Cmentarzysku Wraków — pasie raf "
                           "zawalonym rozbitymi statkami na Wybrzeżu Łez. Skup się na "
                           "przegniłych kadłubach, połamanych masztach, wodorostach, "
                           "kałużach pływowych, słonej mgle i nieumarłych załogach. "
                           "Opis po polsku, 2-3 zdania klimatyczne, zmysłowe, morskie."),
            base_prompt=("shipwreck graveyard area seen from directly straight above, "
                         "rotting broken ship hull forming the irregular room boundary, "
                         "barnacle-crusted deck planks, tangled rigging and seaweed, "
                         "shallow tidal pools of dark water, 2-3 open gaps leading off "
                         "the edges, cold grey-green sea mist lighting, painted tabletop "
                         "RPG battlemap art style, high detail, strict top-down "
                         "orthographic overhead view, square map tile, 2D game art, NO "
                         "perspective, NO side view, flat overhead, no text, no UI"),
        ),
        tiles=[
            dict(label="Wejście na Cmentarzysko", enemies=[], boss=0, items=[],
                 desc="Odpływ odsłonił ścieżkę między kadłubami, śliską od wodorostów. "
                      "Woda odeszła — na jak długo, wie tylko morze."),
            dict(label="Połamany Kadłub", enemies=[("nieumarly_marynarz", 1)], boss=0,
                 items=[],
                 desc="Rozprute żebra statku sterczą ku niebu. Coś w łachmanach "
                      "marynarskich prostuje się w cieniu burty."),
            dict(label="Widmowy Pokład", enemies=[("nieumarly_marynarz", 2)], boss=0,
                 items=[],
                 desc="Przechylony pokład wciąż obsadzony wachtą, która nie zeszła na "
                      "ląd. Odwracają się do ciebie wszyscy naraz."),
            dict(label="Zatopiona Ładownia", enemies=[("topielec_morski", 1)], boss=0,
                 items=[],
                 desc="W ładowni stoi czarna woda po pas. Coś zielonosinego unosi się "
                      "twarzą w dół — dopóki nie wejdziesz."),
            dict(label="Gniazdo w Olinowaniu", enemies=[("cos_z_sieci", 1)], boss=0,
                 items=[],
                 desc="Poszarpane sieci i olinowanie wiszą jak pajęczyna między "
                      "masztami. W środku tkwi coś, co wyciągnięto z Głębi i co nie "
                      "chciało być wyciągnięte."),
            dict(label="Rozbita Ładownia Skarbów", enemies=[], boss=0,
                 items=[("relikt_pradawnych", 1.0), ("krag_soli", 0.5),
                        ("mapa_smolnego", 0.15)],
                 desc="Skrzynie ładunku rozbiły się o skały i wysypały zawartość na "
                      "dno. Między monetami i solą leży zwój w naoliwionym płótnie."),
            dict(label="Zalana Mesa", enemies=[("skeleton", 2)], boss=0, items=[],
                 desc="Stół mesy zastawiony jak do wieczerzy, oblepiony solą. Kości "
                      "wciąż siedzą przy nim i wstają, gdy siadasz nieproszony."),
            dict(label="Cicha Zatoczka", enemies=[], boss=0, items=[],
                 desc="Skrawek suchej rafy osłonięty burtą, gdzie pływ nie sięga. "
                      "Można tu na chwilę przysiąść i złapać oddech."),
            dict(label="Mostek Kapitana", enemies=[("utopiony_kapitan", 1)], boss=1,
                 items=[],
                 desc="Na przechylonym mostku widmowego okrętu stoi kapitan ze "
                      "spuchniętą dłonią na sterze. Otwiera oczy pełne morskiej wody, "
                      "gdy wchodzisz — i zwołuje załogę na ostatnią wachtę."),
            *_dead_ends("Wa"), *_dead_ends("Wb"),
        ],
    ),
    dict(
        key="jaskinie_skarbow", label="Jaskinie Skarbów",
        location_key="zatoka_jaskinie_skarbow",
        rooms=7, tile_category_key="jaskinie_skarbow", tile_count=7,
        boss_tile_id=None,
        enemy_pool=["nieumarly_marynarz", "cos_z_sieci", "ghoul", "skeleton",
                    "wraith"],
        boss_enemy="straznik_klatwy", loot_tier="rich",
        cooldown_hours=48, min_level=6,
        atmosphere=("Nadmorskie jaskinie, w których piraci od pokoleń chowają łup — i "
                    "z których łup sam wraca. Klątwa przecieka: co stąd wyniesiesz, "
                    "wstaje nocą jako nieumarłe i wlecze się z powrotem. Dlatego "
                    "skarby wciąż tu leżą, a pilnują ich ci, co po nie sięgnęli."),
        room_types_json='{"combat":55,"chest":20,"trap":10,"riddle":5,"rest":10}',
        dungeon_difficulty=3, room_loot_chance=0.22, rest_heal_pct=15, rest_charges=1,
        category=dict(
            key="jaskinie_skarbow", label="Jaskinie Skarbów", sort_order=82,
            description="Nadmorskie jaskinie pełne pirackiego łupu i przeciekającej "
                        "klątwy — skrzynie skarbów, monety w mule, kapiące stalaktyty "
                        "i nieumarli, którzy wrócili razem ze swoim złotem.",
            style_modifier=("sea cave treasure hoard, wet dripping limestone, piles of "
                            "gold coins and pirate chests in mud, glistening stalactites, "
                            "dark tidal water, eerie green-gold glow, cursed damp "
                            "aesthetic"),
            system_prompt=("Opisujesz komorę w Jaskiniach Skarbów — nadmorskiej "
                           "jaskini pełnej pirackiego łupu i przeciekającej klątwy na "
                           "Wybrzeżu Łez. Skup się na mokrym wapieniu, kapiącej wodzie, "
                           "kupach monet i skrzyń w mule, zimnym blasku i nieumarłych, "
                           "którzy wrócili po swoje. Opis po polsku, 2-3 zdania "
                           "klimatyczne, zmysłowe, mroczne."),
            base_prompt=("sea cave treasure chamber seen from directly straight above, "
                         "wet limestone floor with piles of gold coins and pirate "
                         "chests half-sunk in mud, dripping stalactites and rock walls "
                         "forming the irregular room boundary, dark shallow tidal water, "
                         "2-3 open cave passages leading off the edges, eerie green-gold "
                         "glow lighting, painted tabletop RPG battlemap art style, high "
                         "detail, strict top-down orthographic overhead view, square map "
                         "tile, 2D game art, NO perspective, NO side view, flat "
                         "overhead, no text, no UI"),
        ),
        tiles=[
            dict(label="Wejście do Jaskiń", enemies=[], boss=0, items=[],
                 desc="Wąska gardziel w skale, którą pływ wypełnia dwa razy na dobę. "
                      "Ze środka ciągnie zapachem soli, złota i czegoś zepsutego."),
            dict(label="Grota Kapiąca", enemies=[("nieumarly_marynarz", 1)], boss=0,
                 items=[],
                 desc="Ze stalaktytów kapie miarowo, jak zegar. W kącie stoi ktoś, kto "
                      "przyszedł tu odnieść swoje i już nie wyszedł."),
            dict(label="Skarbiec Zaklęty", enemies=[("ghoul", 1)], boss=0,
                 items=[("krag_soli", 1.0), ("relikt_pradawnych", 0.4)],
                 desc="Skrzynie spiętrzone pod ścianą, otwarte i pełne. Nad nimi czuwa "
                      "to, co samo tu wróciło razem ze złotem — i nie odda drugi raz."),
            dict(label="Sala Klątwy", enemies=[("wraith", 1)], boss=0, items=[],
                 desc="Ściany pokryte znakami wydrapanymi przez tych, co próbowali "
                      "klątwę zdjąć. Nad nimi wisi widmo, obracając się powoli ku "
                      "tobie."),
            dict(label="Głęboka Studnia", enemies=[("cos_z_sieci", 1)], boss=0,
                 items=[],
                 desc="W dnie jaskini ziejąca studnia pełna czarnej wody, połączona z "
                      "morzem. Coś z niej wypełza — łuska, wodorosty i głód."),
            dict(label="Komora Łupów", enemies=[("skeleton", 2)], boss=0,
                 items=[("relikt_pradawnych", 1.0), ("bone_dust", 0.6)],
                 desc="Monety leżą tu warstwami grubymi na piędź, a w nich sterczą "
                      "kości tych, co przyszli je wynieść. Kości podnoszą się, gdy "
                      "sięgasz."),
            dict(label="Sucha Półka", enemies=[], boss=0, items=[],
                 desc="Skalny występ nad linią pływu, suchy i cichy. Można tu "
                      "przysiąść, zanim zejdziesz głębiej po swoje."),
            dict(label="Zalana Sztolnia", enemies=[("nieumarly_marynarz", 1),
                                                    ("skeleton", 1)], boss=0, items=[],
                 desc="Stary wykop, którym piraci wnosili łup, teraz do połowy pod "
                      "wodą. Z mroku brną ku tobie dwie sylwetki, które nie skończyły "
                      "znoszenia."),
            dict(label="Serce Klątwy", enemies=[("straznik_klatwy", 1)], boss=1,
                 items=[],
                 desc="Na kopcu z monet i kości, których nikt nie zdążył wynieść, "
                      "siedzi Strażnik Klątwy. Wstaje, gdy wchodzisz — pilnuje, by "
                      "wróciło wszystko, łącznie z tobą."),
            *_dead_ends("Ja"), *_dead_ends("Jb"),
        ],
    ),
]

# ── 5. STREFY BEZPIECZNE (porty) + PULA LATARNI ──────────────────────────────
# §1/§4: porty bezpieczne. Jawne encounter_chance=0 = strefa bezpieczna (#1390 nie
# nadpisuje zera terenem) na pierścieniu wokół obu portów (Czarnogród, Zatoka).
WARD_PORTS: list[tuple[tuple[int, int], int]] = [
    ((-19, 65), 1),   # czarnogrod_port (town)
    ((-20, 102), 1),  # zatoka_topielcow (town)
]

# §4 „wybrzeże przy latarni najgorsze": elity Głębi (scope='pool', terrain PUSTE)
# na pierścieniu wokół Latarni Topielców. `_apply_pool_keys` zawęża tam pulę do
# tych elit → pod Latarnią trafiasz tylko na najgorsze (o ile poziom dopuszcza).
LIGHTHOUSE_POOL: list[tuple[tuple[int, int], int, list[str]]] = [
    ((-43, 108), 1, ["cos_z_sieci", "glebinowy_pomiot"]),  # latarnia_topielcow
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


def seed_ward_ports(conn: sqlite3.Connection) -> int:
    """§1/§4 — porty bezpieczne: jawne encounter_chance=0 na pierścieniu wokół obu
    portów (#1390 nie nadpisuje zera terenem). Idempotentny."""
    n = 0
    for center, radius in WARD_PORTS:
        for q, r in _hex_ring(center, radius=radius):
            cur = conn.execute(
                "UPDATE world_hexes SET encounter_chance = 0 "
                "WHERE q=? AND r=? AND map_level=0 AND region=? AND encounter_chance != 0",
                (q, r, REGION),
            )
            n += cur.rowcount
    return n


def seed_lighthouse_pool(conn: sqlite3.Connection) -> int:
    """§4 — pula Latarni: elity Głębi (scope='pool') wpisane w world_hexes.encounter_pool
    na pierścieniu wokół Latarni Topielców. Poza tymi hexami silnik ich nie wylosuje.
    Seed re-aplikuje po reseedzie mapy (jak pule mitów MP-6 / ward CB-6)."""
    n = 0
    for center, radius, pool in LIGHTHOUSE_POOL:
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
    # Pule Latarni — enemy scope='pool' muszą istnieć.
    for center, radius, pool in LIGHTHOUSE_POOL:
        for k in pool:
            if k not in valid_enemies:
                problems.append(f"pula Latarni {center}: brak wroga {k}")
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
    ward_n = seed_ward_ports(conn)
    pool_n = seed_lighthouse_pool(conn)
    conn.commit()

    print(f"  wrogowie nowi:            {res['enemies']} (z {len(ENEMIES)})")
    print(f"  tabele łupów nowe:        {res['loot_tables']}")
    print(f"  wpisy łupów nowe:         {res['loot_entries']}")
    print(f"  spotkania nowe:           {enc_n} (z {len(ENCOUNTERS)})")
    print(f"  plotki nowe:              {rum_n} (z {len(RUMORS)})")
    print(f"  lochy nowe:               {dun_n} (z {len(DUNGEONS)})")
    print(f"  kategorie kafli nowe:     {tile_cat_n}")
    print(f"  kafle lochów nowe:        {tile_n}")
    print(f"  hexy stref bezp. (=0):    {ward_n}")
    print(f"  hexy puli Latarni:        {pool_n}")

    print("\n  spotkania per teren krainy (gradient):")
    for row in conn.execute(
        "SELECT biome, COUNT(*) n, MIN(level_min) lo, MAX(level_max) hi, "
        "MIN(weight) wmin, MAX(weight) wmax FROM game_config_encounters "
        "WHERE region_tag = ? GROUP BY biome ORDER BY wmax DESC, biome", (REGION,),
    ):
        print(f"    {row['biome']:10s} {row['n']} scen | poziomy {row['lo']}–{row['hi']} "
              f"| wagi {row['wmin']:.0f}–{row['wmax']:.0f}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
