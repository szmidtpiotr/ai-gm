#!/usr/bin/env python3
"""MP-6 — zawartość bojowa i „żywa" Martwych Pustkowi: wrogowie + spotkania + plotki
+ dwa lochy (Aschfeld farm, Krypta Krwawego Hrabiego = fabularny endgame).

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §1–§8 + charakter pul ustalony
w zadaniu MP-6. Wzorzec 1:1: scripts/seed_czarnobor_bestia.py (CB-6) i
scripts/seed_siwe_granie_bestia.py (SG-6b #1481).

CHARAKTER KRAINY (kanon): NIEUMARLI NAJGĘŚCIEJ W ŚWIECIE — ale z GRADIENTEM:
  * trakt (road)        — znośny, przejezdny (najniższa szansa),
  * skraj (heath)       — obrzeża: padlinożercy + relikciarze + rzadcy nieumarli,
  * sól (sol)           — SPOKOJNIEJ: sól tłumi Rdzeń (smaczek spójny z lore §2),
  * martwa_ziemia       — gęsto: ghule, szkielety, widma kolonistów, kultyści,
  * ruiny (ruins)       — najgęściej: „miasta umarłych", elity mitów,
  * strefy mitów        — Świątynia / Twierdza / Studnia Głosów: elitarne pule
                          (scope='pool') = sygnał „ZAWRÓĆ".

GRADIENT SZANSY jest już ustawiony w MP-1 (hex_type_config.encounter_base_chance):
  road 0.05 < heath 0.20 < sol 0.28 < martwa_ziemia 0.42 < ruins 0.60.
Tutaj dokładamy PULĘ SCEN (game_config_encounters) z wagami W TYM SAMYM gradiencie
(sol = mniej scen, niższe wagi; ruiny = najwięcej, najcięższe) oraz identyczność
tematyczną (nieumarli). Frekwencję daje chance, treść i ciężar — wagi scen.

CO CZYTA SILNIK (żeby treść nie była martwym wpisem w adminie):
  * `game_config_enemies` → `encounter_service.eligible_enemy_pool()` (~50% spotkań):
    world_scope, review_status, is_active, pasmo poziomów, `terrain_tags` vs teren
    hexa, `region_tag` vs kraina. sol/martwa_ziemia/ruins → tag `ruins` (MP-1
    `_HEX_TYPE_TO_TERRAIN`), heath → `plains`.
  * `game_config_encounters` → `encounter_catalog_service.draw_combat()` (~50%):
    kind/biome/poziom + `region_tag`. `biome` = WPROST `world_hexes.hex_type`
    (sol / martwa_ziemia / ruins / heath / road) — dlatego pula scen ROZRÓŻNIA
    sól od martwej ziemi (czego filtr terenu wrogów nie umie, bo oba → `ruins`).
  * `world_rumors` → `rumor_service.draw_for_region()` (pula regionu > plotka per bohater).
  * `game_dungeons` → Aschfeld (farm) + Krypta Krwawego Hrabiego (fabularny).
  * `world_hexes.encounter_pool` → pule stref mitów: elity (scope='pool') pojawiają
    się WYŁĄCZNIE na pierścieniach wokół Świątyni/Twierdzy/Studni Głosów.

WARTOŚCI STARTOWE (Numbers Policy): staty wrogów, wagi/pasma scen, promienie pul,
cooldown lochów — wszystko strojlne w Sandboxie. Pasma pod bohatera 1–8 bez inwersji
tierów (#1376): weak < standard < elite < boss. Krypta: cooldown 8760 h (≈ rok) =
de-facto brak farmy — loch fabularny, jak przyszły Hutman; strój = wartość startowa.

Idempotentny: INSERT OR IGNORE po kluczu; plotki po treści; pule stref nadpisują tylko
wskazane pierścienie. Seed = źródło prawdy pól strojlnych (content-as-code #1202).

    docker cp scripts/seed_martwe_pustkowia_bestia.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_bestia.py
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_bestia.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "martwe_pustkowia"

# ── 1. WROGOWIE ───────────────────────────────────────────────────────────────
# Nieumarli w większości JUŻ ISTNIEJĄ globalnie (skeleton, zombie, ghoul, ghost,
# wraith, undead_champion, vampire, lich…) i dochodzą na terenie `ruins`. Te wpisy
# UZUPEŁNIAJĄ braki tożsamości krainy i dają smak: piaskowe ghule, widma kolonistów
# Wycofania, kościane sępy, kultyści pęknięcia, elity stref mitów + dwóch bossów.
# terrain='ruins' → sol/martwa_ziemia/ruins; terrain='plains' → heath (skraj).
# scope: 'global' = kompozytor bierze na pasującym terenie; 'pool' = tylko tam,
# gdzie klucz wpisano do world_hexes.encounter_pool (strefy mitów) / boss lochu.
ENEMIES: list[dict] = [
    # ── weak (skraj / obrzeża, hero 1-3) ─────────────────────────────────────
    dict(
        key="kosciany_sep", label="Kościany Sęp", tier="weak",
        hp=9, ac=12, atk=3, die="1d6", dmg=0, apt=1, xp=55,
        lvl=(1, 3), terrain="plains", scope="global", dmg_type="physical",
        desc="Nad pustkowiem zawsze coś krąży. Sępy o pierzu zlepionym popiołem i "
             "kościach prześwitujących przez skórę spadają na wszystko, co przestało "
             "się ruszać — i na to, co jeszcze się rusza, a już nie ucieknie.",
        loot=[("bone_dust", 55, 1, 2), ("alchemical_reagent", 20, 1, 1)], gold=(0, 3),
    ),
    dict(
        key="piaskowy_ghul", label="Piaskowy Ghul", tier="weak",
        hp=13, ac=12, atk=3, die="1d6", dmg=1, apt=1, xp=62,
        lvl=(1, 3), terrain="ruins", scope="global", dmg_type="physical",
        desc="Zagrzebany w popiele i soli leży płytko — dopóki nie usłyszy kroków. "
             "Wtedy wygrzebuje się jednym szarpnięciem, sypiąc suchą ziemią, i rzuca "
             "się na nogi, zanim zdążysz zrozumieć, że kopiec przy ścieżce był nim.",
        loot=[("bone_dust", 60, 1, 2), ("healing_herb", 25, 1, 1)], gold=(0, 4),
    ),
    # ── standard (martwa ziemia / ruiny, hero 2-6) ───────────────────────────
    dict(
        key="solny_umarlak", label="Solny Umarlak", tier="standard",
        hp=18, ac=13, atk=4, die="1d6", dmg=1, apt=1, xp=95,
        lvl=(2, 5), terrain="ruins", scope="global", dmg_type="physical",
        desc="Sól, która tłumi Rdzeń, zakonserwowała i jego. Skorupa białych "
             "kryształów pęka na stawach, gdy idzie — powoli, bo sól trzyma go w "
             "kupie tak samo, jak trzymała w ziemi. Na równinie solnej takich jest "
             "mniej, ale każdy jest twardszy, niż wygląda.",
        loot=[("szczypta_soli", 45, 1, 2), ("bone_dust", 35, 1, 2)], gold=(0, 8),
    ),
    dict(
        key="widmo_kolonisty", label="Widmo Kolonisty", tier="standard",
        hp=20, ac=12, atk=5, die="1d8", dmg=1, apt=1, xp=120,
        lvl=(2, 5), terrain="ruins", scope="global", dmg_type="necrotic",
        desc="Sine widmo w wyblakłym cesarskim stroju z południa. Koloniści, których "
             "Korona porzuciła przy Wycofaniu, wciąż idą tam, skąd mieli po nich "
             "przyjść. Nie napada — zachodzi drogę, jakby pytało, kiedy wreszcie "
             "wracacie, a odpowiedzi nie znosi.",
        loot=[("alchemical_reagent", 45, 1, 2), ("relikt_pradawnych", 12, 1, 1),
              ("bone_dust", 30, 1, 2)], gold=(2, 12),
    ),
    dict(
        key="kultysta_pekniecia", label="Kultysta Pęknięcia", tier="standard",
        hp=24, ac=12, atk=5, die="1d8", dmg=1, apt=1, xp=140,
        lvl=(3, 6), terrain="ruins", scope="global", dmg_type="necrotic",
        desc="Żywy — na razie. Pielgrzymują na Pustkowia rozdzierać stare pieczęcie, "
             "bo wierzą, że przez pęknięcie przemówi to, co pod spodem. Tną się, żeby "
             "krew wsiąkła w ziemię, i tną ciebie z tego samego powodu.",
        loot=[("alchemical_reagent", 50, 1, 2), ("relikt_pradawnych", 15, 1, 1),
              ("bandage", 25, 1, 1)], gold=(3, 16),
    ),
    # ── elite (głębia / strefy mitów, hero 5-8) ──────────────────────────────
    dict(
        key="popielny_rycerz", label="Popielny Rycerz", tier="elite",
        hp=32, ac=14, atk=6, die="1d8", dmg=2, apt=1, xp=190,
        lvl=(5, 8), terrain="ruins", scope="global", dmg_type="physical",
        desc="Zbroja cesarskiego garnizonu, wypalona popiołem do szarości, i to, co "
             "w niej zostało. Stał na warcie w Aschfeld, gdy przyszedł rozkaz odwrotu "
             "— i nie usłyszał go. Wciąż pełni służbę na posterunku, którego nie ma.",
        loot=[("krag_soli", 20, 1, 1), ("alchemical_reagent", 40, 1, 2),
              ("relikt_pradawnych", 18, 1, 1)], gold=(6, 26),
    ),
    dict(
        key="widmo_studni", label="Widmo Studni Głosów", tier="elite",
        hp=30, ac=13, atk=6, die="1d8", dmg=1, apt=1, xp=195,
        lvl=(6, 8), terrain="ruins", scope="pool", dmg_type="necrotic",
        desc="Ze Studni Głosów słychać szepty; Piętnowani zakazują słuchać dłużej niż "
             "trzy oddechy. Kto posłuchał, zostaje przy szybie na zawsze — jako jeden "
             "z głosów. Nadchodzi bezgłośnie i mówi twoim własnym głosem, żebyś podszedł "
             "bliżej krawędzi.",
        loot=[("relikt_pradawnych", 22, 1, 1), ("alchemical_reagent", 40, 1, 2),
              ("kosciany_kompas", 8, 1, 1)], gold=(4, 20),
    ),
    dict(
        key="bezimienna_straz", label="Bezimienna Straż", tier="elite",
        hp=34, ac=14, atk=7, die="1d8", dmg=2, apt=1, xp=205,
        lvl=(6, 8), terrain="ruins", scope="pool", dmg_type="physical",
        desc="Z Twierdzy Bezimiennego nie wrócił nikt — nie ma legend, bo nie ma "
             "świadków. Zostaje tylko to, co stoi w jej bramie: wysokie, milczące, bez "
             "twarzy pod hełmem. Nie ściga poza swój krąg. Nie musi. Nikt, kto wszedł "
             "w krąg, nie wyszedł, żeby ostrzec następnego.",
        loot=[("krag_soli", 22, 1, 1), ("relikt_pradawnych", 20, 1, 1),
              ("alchemical_reagent", 35, 1, 2)], gold=(8, 30),
    ),
    # ── bossowie lochów (scope='pool': nie wychodzą na podróż) ────────────────
    dict(
        key="komendant_aschfeld", label="Popielny Komendant", tier="boss",
        hp=58, ac=14, atk=7, die="1d10", dmg=2, apt=1, xp=350,
        lvl=(4, None), terrain="ruins", scope="pool", dmg_type="physical",
        desc="Ostatni, który kazał kolonii się bronić, gdy z południa przyszedł "
             "rozkaz odwrotu, a z głębi pustkowi — coś innego. Trzyma cesarską pieczęć "
             "w spopielałej dłoni i wciąż wydaje rozkazy garnizonowi, który stoi za "
             "nim martwym szeregiem.",
        loot=[("relikt_pradawnych", 30, 1, 1), ("krag_soli", 20, 1, 1),
              ("alchemical_reagent", 50, 1, 2)], gold=(15, 55),
    ),
    dict(
        key="krwawy_hrabia", label="Krwawy Hrabia", tier="boss",
        hp=72, ac=15, atk=8, die="1d10", dmg=3, apt=2, xp=440,
        lvl=(8, None), terrain="ruins,castle", scope="pool", dmg_type="necrotic",
        desc="Rycerz, który targował się z Rdzeniem o nieśmiertelność — i dostał ją. "
             "Nie umarł do dziś, i lepiej, żeby był umarł. W krypcie pod solą siedzi na "
             "tronie z kości własnych poddanych, blady jak wosk, i wstaje tylko wtedy, "
             "gdy ktoś jest dość głupi, żeby zejść na dół. Ostrzeżenie, co robi "
             "targowanie się z tym, co pod spodem.",
        loot=[("relikt_pradawnych", 40, 1, 1), ("krag_soli", 25, 1, 1),
              ("kosciany_kompas", 15, 1, 1), ("alchemical_reagent", 45, 1, 3)],
        gold=(40, 120),
    ),
]

# ── 2. SPOTKANIA ──────────────────────────────────────────────────────────────
# (klucz, biome=hex_type, poziomy, waga, wrogowie[(key,nazwa,ile)], tytuł, scena)
# WAGI = gradient krainy: road 10-12 · sol 14-18 (sól tłumi) · heath 20-24 (skraj)
# · martwa_ziemia 24-28 (gęsto) · ruins 22-30 (najgęściej, elity). Liczba scen też
# w gradiencie: sól = 3 lekkie, ruiny = 5 ciężkich.
ENCOUNTERS: list[dict] = [
    # ── road (33 hexy) — trakt: najlżej, przejezdny ──────────────────────────
    dict(key="mp_road_sep", biome="road", lvl=(1, 4), w=12,
         enemies=[("kosciany_sep", "kościany sęp", 1)],
         title="Cień nad traktem",
         scene="Cień przechodzi po popielatych płytach traktu raz, drugi, coraz niżej. "
               "Kościany sęp zatacza koła nad czymś przed tobą — albo nad tobą."),
    dict(key="mp_road_ghul", biome="road", lvl=(2, 5), w=10,
         enemies=[("piaskowy_ghul", "piaskowy ghul", 1)],
         title="Kopiec przy słupie milowym",
         scene="Przy przewróconym słupie milowym leży kopiec suchej ziemi, za równy, "
               "żeby usypał go wiatr. Kiedy mijasz go o krok, kopiec się rusza."),
    dict(key="mp_road_kultysta", biome="road", lvl=(3, 6), w=10,
         enemies=[("kultysta_pekniecia", "kultysta pęknięcia", 1)],
         title="Pielgrzym na trakcie",
         scene="Na środku traktu klęczy postać w kapturze i nożem kreśli coś na płytach. "
               "Podnosi głowę, gdy podchodzisz — i uśmiecha się, jakby na ciebie czekał."),
    # ── sol (333 hexy) — solna równina: SÓL TŁUMI, spokojniej ─────────────────
    dict(key="mp_sol_umarlak", biome="sol", lvl=(2, 5), w=18,
         enemies=[("solny_umarlak", "solny umarlak", 1)],
         title="Biały na białym",
         scene="Na solnej równinie widać daleko i nie ma się gdzie schować — dlatego "
               "widzisz go od dawna. Biała skorupa pęka na jego stawach z każdym "
               "powolnym krokiem w twoją stronę."),
    dict(key="mp_sol_sep", biome="sol", lvl=(1, 4), w=16,
         enemies=[("kosciany_sep", "kościany sęp", 1)],
         title="Coś zostało na równinie",
         scene="Sól chrzęści pod butami tak głośno, że słychać cię z daleka. Nad "
               "punktem przed tobą krąży kościany sęp — coś tam leży, a on nie lubi "
               "dzielić się padliną."),
    dict(key="mp_sol_ghul", biome="sol", lvl=(1, 3), w=14,
         enemies=[("piaskowy_ghul", "piaskowy ghul", 1)],
         title="Rzadki gość na soli",
         scene="Tu, gdzie sól tłumi Rdzeń, umarli chodzą rzadziej — ale ten dowlókł się "
               "aż na równinę. Wygrzebuje się spod solnej skorupy, sypiąc białym pyłem."),
    # ── heath (1085 hexów) — skraj/obrzeża: padlinożercy + relikciarze ────────
    dict(key="mp_heath_sepy", biome="heath", lvl=(1, 4), w=24,
         enemies=[("kosciany_sep", "kościany sęp", 2)],
         title="Stado nad wrzosem",
         scene="Nad wrzosowiskiem dwa kościane sępy schodzą kręgami coraz niżej. Nie "
               "czekają, aż padniesz — na pustkowiu nauczyły się, że czasem warto "
               "pomóc."),
    dict(key="mp_heath_ghule", biome="heath", lvl=(1, 4), w=22,
         enemies=[("piaskowy_ghul", "piaskowy ghul", 2)],
         title="Kopce w zaroślach",
         scene="Wrzos rośnie kępami na dwóch kopcach po prawej. Kiedy staje ci na drodze "
               "pierwszy ghul, drugi wygrzebuje się już z tyłu — czekały na parę nóg."),
    dict(key="mp_heath_poszukiwacze", biome="heath", lvl=(2, 5), w=20,
         enemies=[("bandit", "relikciarz-rabuś", 2)],
         title="Gorączka reliktów",
         scene="Przy rozkopanym kopcu dwóch obdartusów sortuje kości i skorupy. "
               "Prostują się z łopatami w garści — na Pustkowia ściągnęła ich gorączka "
               "reliktów, a ty wyglądasz na kogoś, kto już coś znalazł."),
    # ── martwa_ziemia (692 hexy) — serce krainy: gęsto ───────────────────────
    dict(key="mp_martwa_ghule", biome="martwa_ziemia", lvl=(3, 6), w=28,
         enemies=[("piaskowy_ghul", "piaskowy ghul", 2), ("ghoul", "ghul", 1)],
         title="Ziemia pełna rąk",
         scene="Szara ziemia rusza się w kilku miejscach naraz. Najpierw dłonie, potem "
               "reszta — martwa_ziemia oddaje to, co przyjęła, i oddaje głodne."),
    dict(key="mp_martwa_szkielety", biome="martwa_ziemia", lvl=(2, 5), w=26,
         enemies=[("skeleton", "szkielet", 2), ("widmo_kolonisty", "widmo kolonisty", 1)],
         title="Szereg, który nie odszedł",
         scene="Na popielisku stoi kilka sylwetek w wyblakłych strojach z południa. "
               "Nie odchodzą, choć rozkaz odwrotu padł pokolenia temu. Odwracają się "
               "ku tobie wszystkie naraz."),
    dict(key="mp_martwa_kultysci", biome="martwa_ziemia", lvl=(3, 6), w=24,
         enemies=[("kultysta_pekniecia", "kultysta pęknięcia", 2)],
         title="Krew w popiele",
         scene="Dwóch pielgrzymów klęczy nad szczeliną w ziemi i po kolei tnie sobie "
               "dłonie, żeby krew wsiąkła w pęknięcie. Kiedy cię widzą, uznają, że "
               "twoja też się nada."),
    dict(key="mp_martwa_widma", biome="martwa_ziemia", lvl=(4, 7), w=24,
         enemies=[("widmo_kolonisty", "widmo kolonisty", 2), ("wraith", "widmo", 1)],
         title="Procesja donikąd",
         scene="Sine widma idą równym szeregiem przez popiół, twarzami w jedną stronę "
               "— tam, skąd mieli przyjść po nich. Kiedy wchodzisz im w drogę, "
               "procesja skręca ku tobie, jakbyś to ty był powodem."),
    # ── ruins (301 hexów) — miasta umarłych: najgęściej, elity ────────────────
    dict(key="mp_ruins_nieumarli", biome="ruins", lvl=(2, 5), w=30,
         enemies=[("skeleton", "szkielet", 2), ("ghoul", "ghul", 1)],
         title="Miasto umarłych",
         scene="Między osypanymi murami coś się porusza w co drugim cieniu. Ruiny "
               "Pradawnych nigdy nie stoją puste — a to, co je zajęło, właśnie cię "
               "zauważyło."),
    dict(key="mp_ruins_widma", biome="ruins", lvl=(4, 7), w=28,
         enemies=[("widmo_kolonisty", "widmo kolonisty", 2), ("wraith", "widmo", 1)],
         title="Ulica bez końca",
         scene="Zaułek między ruinami wygląda tak samo z każdej strony, a sine sylwetki "
               "suną nim ku tobie równocześnie z trzech wylotów. Mur za plecami jest "
               "jedynym pewnikiem."),
    dict(key="mp_ruins_rycerz", biome="ruins", lvl=(6, 8), w=26,
         enemies=[("popielny_rycerz", "popielny rycerz", 1), ("skeleton", "szkielet", 2)],
         title="Warta, która nie usłyszała odwrotu",
         scene="W bramie ruin stoi zbroja szara od popiołu, a przy niej dwie kości "
               "w hełmach. Popielny rycerz nie pyta o hasło — pełni służbę na "
               "posterunku, którego już nie ma, i ty jesteś naruszeniem."),
    dict(key="mp_ruins_kultysci", biome="ruins", lvl=(4, 7), w=24,
         enemies=[("kultysta_pekniecia", "kultysta pęknięcia", 2), ("ghoul", "ghul", 1)],
         title="Pieczęć, którą ktoś rozdziera",
         scene="W sercu ruin pielgrzymi kują coś w kamiennej płycie z pieczęcią. Spod "
               "płyty dobiega drapanie — i nie oni je wydają. Odwracają się do ciebie "
               "z ulgą, jakby przyszło im nowe narzędzie."),
    dict(key="mp_ruins_champion", biome="ruins", lvl=(6, 9), w=22,
         enemies=[("undead_champion", "nieumarły mistrz", 1), ("skeleton", "szkielet", 2)],
         title="Ktoś tu rządzi umarłymi",
         scene="Kości nie ruszają się przypadkiem — ustawiają w szyk. Pośrodku stoi "
               "coś większego, w zbroi zrośniętej z ciałem, i podnosi rękę. Na ten "
               "znak reszta rusza."),
]

# ── 3. PLOTKI ─────────────────────────────────────────────────────────────────
# truth_flag=1 → plotka prawdziwa (kanon). Tajemnice krainy zostają PYTANIAMI:
# DLACZEGO Korona porzuciła kolonię i CO leży w Świątyni Pradawnych — bez odpowiedzi.
RUMORS: list[tuple[str, int, str | None, str | None]] = [
    ("W Aschfeld cesarskie pieczęcie wiszą wciąż na drzwiach, których nikt nie złamał. "
     "Koloniści jakby wyszli w jedną noc — a raczej nie wyszli wcale. Kto tam zejdzie, "
     "wraca z reliktami albo nie wraca.", 1, "dungeon", "aschfeld"),
    ("Archiwa Wieży Kronikarzy urywają się w pół zdania na roku Wycofania. Ktoś przestał "
     "pisać w środku wyrazu — i nikt nie umie powiedzieć, czemu Korona rzuciła kolonię "
     "w jedno pokolenie.", 1, "location", "wieza_kronikarzy"),
    ("Ze Studni Głosów słychać szepty. Piętnowani zakazują słuchać dłużej niż trzy "
     "oddechy — mówią, że kto posłucha, zostaje przy szybie na zawsze jako jeden "
     "z głosów.", 1, "location", "studnia_glosow"),
    ("W krypcie pod solą leży rycerz, który targował się z Rdzeniem o nieśmiertelność "
     "— i dostał ją. Nie umarł do dziś. Lepiej, żeby był.", 1, "dungeon",
     "krypta_krwawego_hrabiego"),
    ("Obóz Gorączki rośnie szybciej niż rozum. Kopią za reliktami Pradawnych, "
     "rozgrzebują groby — i budzą to, co pod nimi spało od Pęknięcia.", 1, "location",
     "oboz_goraczki"),
    ("Na solnej równinie umarli chodzą rzadziej — sól im nie służy, tłumi to, co je "
     "trzyma na nogach. Piętnowani zbierają ją najbliżej pęknięć, gdzie rodzi się "
     "najczystsza.", 1, "location", "pustkowie_solne"),
    ("W głębi pustkowi leży Świątynia Pradawnych. Nikt nie mówi, co w niej jest — "
     "mówią tylko jedno słowo: nie idź.", 1, "location", "swiatynia_pradawnych"),
    ("Z Twierdzy Bezimiennego nie wrócił nikt. Nie ma o niej legend, bo nie ma "
     "świadków — jest tylko cisza i to, co stoi w jej bramie.", 1, "location",
     "twierdza_bezimiennego"),
    ("Pola Szkła to ziemia stopiona w szkło w chwili Pęknięcia. W bezwietrzny dzień "
     "słychać tam własne kroki sprzed godziny — kraina niczego nie zapomina.", 1,
     "location", "pola_szkla"),
    ("Na Cmentarzysku Machin leżą szczątki Pradawnych — coś między rzeźbą a szkieletem. "
     "Nikt nie wie, do czego służyły, a poszukiwacze, co je rozbierają na części, "
     "znikają jeden po drugim.", 1, "location", "cmentarzysko_machin"),
    ("Imperialny trakt urywa się przy ruinie-bramie na skraju krainy. Słupy milowe "
     "prowadzą donikąd — po tamtej stronie las połknął drogę, po tej połknął ją "
     "popiół.", 1, "location", "koniec_traktu"),
    ("W Ruinach Klasztoru Pradawnych trawa nie rośnie, a kultyści pielgrzymują tam "
     "rozdzierać stare pieczęcie. Powiadają, że jedna z nich zaczyna ustępować.", 1,
     "location", "ruiny_klasztoru_pradawnego"),
    ("Na martwej ziemi wędrują sine widma w cesarskich strojach z południa — koloniści, "
     "których porzucono przy Wycofaniu. Idą wciąż tam, skąd mieli przyjść po nich.",
     1, None, None),
]

# ── 4. LOCHY ──────────────────────────────────────────────────────────────────
# Aschfeld = FARMOWALNY (cooldown 48h). Krypta Krwawego Hrabiego = FABULARNY endgame
# (cooldown ≈ rok = de-facto brak farmy, jak przyszły Hutman; min_level 8). Silnik
# lochów kafelkowych (#1507): enter_dungeon_tiles WYMAGA `tile_category_key` (inaczej
# 409) → każdy loch dostaje DEDYKOWANĄ kategorię kafli z własnymi kaflami niosącymi
# wrogów z puli krainy i kaflem bossa. Kafle bez obrazków (jak Utopiona Wieś/smoke —
# grywalne, UI pokaże placeholder); grafiki FLUX .170 = osobny follow-up.
_HEX_NEIGHBOURS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

# §2 „sól tłumi Rdzeń" — na solnej równinie nieumarli chodzą NAJRZADZIEJ z całego
# pustkowia (poza samym traktem). MP-1 dał solI 0.28; MP-6 obniża ją PONIŻEJ heath
# (0.20), by gradient wprost oddał smaczek lore: road 0.05 < sol 0.18 < heath 0.20
# < martwa_ziemia 0.42 < ruins 0.60. `sol` jako teren istnieje wyłącznie w tej
# krainie, więc strojenie jego bazowej szansy nie dotyka innych krain. Wartość
# startowa (Numbers Policy, strojlna w Sandboxie).
SOL_ENCOUNTER_BASE_CHANCE = 0.18

# Zaślepki grafu (1-drzwiowe): grapher (draw_tile_graph) domyka nimi otwarte drzwi
# odgałęzień. Cztery kierunki × 2 komplety = zapas domykaczy, żeby graf zamykał się
# bez fallbacku „open doors". Wspólne dla obu lochów (dołączane per motyw niżej).
def _dead_ends(theme: str) -> list[dict]:
    d = theme
    return [
        dict(label=f"Ślepy Zaułek {d} (N)", enemies=[], boss=0, items=[], doors=["N"],
             desc="Droga urywa się bez wyjścia. Ślepy kąt."),
        dict(label=f"Ślepy Zaułek {d} (S)", enemies=[], boss=0, items=[], doors=["S"],
             desc="Zawał zamyka przejście. Dalej nie ma drogi."),
        dict(label=f"Ślepy Zaułek {d} (E)", enemies=[], boss=0, items=[], doors=["E"],
             desc="Przejście kończy się litą ścianą."),
        dict(label=f"Ślepy Zaułek {d} (W)", enemies=[], boss=0, items=[], doors=["W"],
             desc="Kąt, z którego nie ma wyjścia."),
    ]

DUNGEONS: list[dict] = [
    dict(
        key="aschfeld", label="Aschfeld", location_key="aschfeld",
        rooms=6, tile_category_key="aschfeld", tile_count=6, boss_tile_id=None,
        enemy_pool=["piaskowy_ghul", "solny_umarlak", "widmo_kolonisty",
                    "skeleton", "zombie", "ghoul"],
        boss_enemy="komendant_aschfeld", loot_tier="rich",
        cooldown_hours=48, min_level=4,
        atmosphere=("Porzucona kolonia cesarska pod popiołem i solą. Puste koszary, "
                    "cesarskie pieczęcie na drzwiach, których nikt nie złamał, i "
                    "garnizon, który nigdy nie usłyszał rozkazu odwrotu — stoi na "
                    "posterunkach do dziś."),
        room_types_json='{"combat":55,"chest":15,"trap":10,"riddle":10,"rest":10}',
        dungeon_difficulty=2, room_loot_chance=0.15, rest_heal_pct=20, rest_charges=2,
        category=dict(
            key="aschfeld", label="Aschfeld", sort_order=71,
            description="Porzucona kolonia imperialna zasypana popiołem i solą — puste "
                        "koszary, kaplica Latarni, cesarskie ruiny z martwym garnizonem.",
            style_modifier=("abandoned imperial colony ruins, ash-covered cobblestone, "
                            "salt-crusted stone walls, faded imperial banners, collapsed "
                            "wooden barracks, grey desolate wasteland aesthetic, cold "
                            "overcast light"),
            system_prompt=("Opisujesz pomieszczenie w Aschfeld — porzuconej kolonii "
                           "cesarskiej na Martwych Pustkowiach. Skup się na popiele i "
                           "soli na kamieniu, pustych koszarach, cesarskich pieczęciach, "
                           "wyblakłych sztandarach, ciszy i martwym garnizonie. Opis po "
                           "polsku, 2-3 zdania klimatyczne, zmysłowe."),
            base_prompt=("abandoned imperial colony ruin chamber seen from directly "
                         "straight above, ash-covered cobblestone floor, salt-crusted "
                         "collapsed stone walls forming the irregular room boundary, "
                         "broken imperial banners and rusted armor stands, 2-3 open "
                         "passages leading off the edges, grey overcast lighting, "
                         "painted tabletop RPG battlemap art style, high detail, strict "
                         "top-down orthographic overhead view, square map tile, 2D game "
                         "art, NO perspective, NO side view, flat overhead, no text, no UI"),
        ),
        tiles=[
            dict(label="Brama Kolonii", enemies=[], boss=0, items=[],
                 desc="Cesarska brama Aschfeld stoi otworem — nikt jej nie zamknął przy "
                      "odwrocie. Za nią kolonia tonie w popiele i soli."),
            dict(label="Rozbity Plac", enemies=[("piaskowy_ghul", 1)], boss=0, items=[],
                 desc="Rynek zasypany szarym pyłem. Jeden z kopców przy studni "
                      "prostuje się na twój widok."),
            dict(label="Koszary", enemies=[("skeleton", 2)], boss=0, items=[],
                 desc="Prycze stoją równo, jakby garnizon miał zaraz wstać. Wstaje — "
                      "ale nie ci, których byś chciał."),
            dict(label="Kaplica Latarni", enemies=[("widmo_kolonisty", 1)], boss=0, items=[],
                 desc="W kaplicy zgasł ogień Latarni pokolenia temu. Przy zimnym "
                      "ołtarzu klęczy sine widmo i wciąż się modli o powrót."),
            dict(label="Zasypany Rynek", enemies=[("solny_umarlak", 2)], boss=0, items=[],
                 desc="Sól wżarła się w bruk i w tych, co na nim padli. Białe skorupy "
                      "pękają, gdy się podnoszą."),
            dict(label="Archiwum", enemies=[], boss=0,
                 items=[("alchemical_reagent", 1.0), ("relikt_pradawnych", 0.4)],
                 desc="Regały pełne zbutwiałych ksiąg, urwanych w pół zdania. Wśród "
                      "nich okuta skrzynia kronikarza, wciąż zamknięta."),
            dict(label="Studnia Kolonii", enemies=[("zombie", 2)], boss=0, items=[],
                 desc="Woda w studni jest czarna i śmierdzi. Coś w niej pluska, a "
                      "potem wychlupuje na cembrowinę."),
            dict(label="Zbrojownia", enemies=[("piaskowy_ghul", 1), ("skeleton", 1)],
                 boss=0, items=[],
                 desc="Rzędy rdzewnych włóczni i pustych zbroi. Część zbroi nie jest "
                      "pusta — i sięga po broń szybciej niż ty."),
            dict(label="Wypalony Zajazd", enemies=[], boss=0, items=[],
                 desc="Zajazd dla kupców, w którym nigdy nie było kupców. Da się tu "
                      "przysiąść przy zimnym palenisku i złapać oddech."),
            dict(label="Dom Komendanta", enemies=[("komendant_aschfeld", 1)], boss=1, items=[],
                 desc="Największy dom w kolonii, z cesarskim orłem nad progiem. W środku "
                      "komendant trzyma pieczęć w spopielałej dłoni i szykuje garnizon "
                      "do obrony, która się nie skończyła."),
            *_dead_ends("Aa"), *_dead_ends("Ab"),
        ],
        # Pierścień strefy mitów wokół samego lochu NIE jest ustawiany (to loch,
        # nie mit). Pula stref mitów — patrz MYTH_POOLS niżej.
        myth_pool=None,
    ),
    dict(
        key="krypta_krwawego_hrabiego", label="Krypta Krwawego Hrabiego",
        location_key="krypta_krwawego_hrabiego",
        rooms=7, tile_category_key="krypta_krwawego_hrabiego", tile_count=7,
        boss_tile_id=None,
        enemy_pool=["widmo_kolonisty", "popielny_rycerz", "ghoul", "wraith",
                    "undead_champion", "bezimienna_straz"],
        boss_enemy="krwawy_hrabia", loot_tier="rich",
        # Fabularny endgame krainy: cooldown ≈ rok = de-facto brak farmy (jak przyszły
        # Hutman). min_level 8 = wrota endgame. Wartości startowe (Numbers Policy).
        cooldown_hours=8760, min_level=8,
        atmosphere=("Krypta pod solą, do której rycerz-wampir ściągnął kości własnych "
                    "poddanych. Krew nie wsiąkła w kamień — stoi w rynnach. Gdzieś "
                    "w głębi bije wolno serce, którego dawno nie powinno już być."),
        room_types_json='{"combat":60,"chest":15,"trap":10,"riddle":5,"rest":10}',
        dungeon_difficulty=3, room_loot_chance=0.2, rest_heal_pct=15, rest_charges=1,
        category=dict(
            key="krypta_krwawego_hrabiego", label="Krypta Krwawego Hrabiego",
            sort_order=72,
            description="Podziemna krypta rycerza-wampira pod solną równiną — sarkofagi, "
                        "rynny zakrzepłej krwi, kości poddanych ułożone w ściany, "
                        "świece z łoju gasnące na czarnej wodzie.",
            style_modifier=("vampire lord crypt, black stone sarcophagi, congealed blood "
                            "in floor channels, walls of stacked human bones, guttering "
                            "tallow candles, deep red and black gothic tomb aesthetic, "
                            "cold damp underground"),
            system_prompt=("Opisujesz komnatę w Krypcie Krwawego Hrabiego — podziemnym "
                           "grobowcu rycerza-wampira pod solą. Skup się na czarnym "
                           "kamieniu, sarkofagach, zakrzepłej krwi w rynnach, ścianach "
                           "z kości, dogasających świecach i chłodzie. Opis po polsku, "
                           "2-3 zdania klimatyczne, zmysłowe, mroczne."),
            base_prompt=("underground vampire crypt chamber seen from directly straight "
                         "above, black stone floor with channels of congealed dark blood, "
                         "walls of stacked human bones and stone sarcophagi forming the "
                         "irregular room boundary, guttering candles, 2-3 dark archway "
                         "passages leading off the edges, deep red and black gothic "
                         "lighting, painted tabletop RPG battlemap art style, high "
                         "detail, strict top-down orthographic overhead view, square map "
                         "tile, 2D game art, NO perspective, NO side view, flat overhead, "
                         "no text, no UI"),
        ),
        tiles=[
            dict(label="Zejście do Krypty", enemies=[], boss=0, items=[],
                 desc="Schody nurkują pod solną skorupę w chłód i smród żelaza. Na "
                      "ostatnim stopniu kamień jest lepki i ciemny."),
            dict(label="Sala Sarkofagów", enemies=[("ghoul", 1)], boss=0, items=[],
                 desc="Rzędy czarnych sarkofagów, jeden z wieków zsunięty. To, co z "
                      "niego wyszło, wciąż tu jest."),
            dict(label="Galeria Portretów", enemies=[("widmo_kolonisty", 2)], boss=0, items=[],
                 desc="Portrety zblakłych twarzy patrzą ze ścian. Dwie z nich zeszły "
                      "z ram i suną ku tobie korytarzem."),
            dict(label="Krwawa Kaplica", enemies=[("wraith", 1)], boss=0, items=[],
                 desc="Ołtarz z rynną, którą krew wciąż spływa, choć nie ma skąd. Nad "
                      "nim wisi widmo, obracając się powoli w twoją stronę."),
            dict(label="Katakumby", enemies=[("undead_champion", 1)], boss=0, items=[],
                 desc="Ściany z kości poddanych, ułożonych w wzór. Pośrodku stoi coś "
                      "w zroślej z ciałem zbroi i patrzy, jak wchodzisz."),
            dict(label="Skarbiec Hrabiego", enemies=[], boss=0,
                 items=[("relikt_pradawnych", 1.0), ("krag_soli", 0.5)],
                 desc="Skrzynie okute srebrem, poczerniałe od wieków. Hrabia zabrał "
                      "ze sobą wszystko, co miał — i wszystko wciąż tu jest."),
            dict(label="Studnia Krwi", enemies=[("popielny_rycerz", 1)], boss=0, items=[],
                 desc="W posadzce ziejąca studnia pełna czarnej cieczy. Strzeże jej "
                      "zbroja szara od popiołu, która nie przepuści cię dalej."),
            dict(label="Krypta Straży", enemies=[("bezimienna_straz", 1)], boss=0, items=[],
                 desc="Przed komnatą Hrabiego stoi wysoka, milcząca postać bez twarzy "
                      "pod hełmem. Nie ostrzega. Nie musi."),
            dict(label="Alkowa Ciszy", enemies=[], boss=0, items=[],
                 desc="Zakątek za filarem, gdzie krew nie sięga. Można tu na chwilę "
                      "przysiąść, zanim zejdziesz głębiej."),
            dict(label="Komnata Hrabiego", enemies=[("krwawy_hrabia", 1)], boss=1, items=[],
                 desc="Na tronie z kości siedzi rycerz blady jak wosk, z koroną wrośniętą "
                      "w czoło. Otwiera oczy, gdy wchodzisz — i wstaje, bo ktoś wreszcie "
                      "był dość głupi, żeby zejść na dół."),
            *_dead_ends("Ka"), *_dead_ends("Kb"),
        ],
        myth_pool=None,
    ),
]

# ── 5. PULE STREF MITÓW ───────────────────────────────────────────────────────
# §4 hierarchia tajemnic: Świątynia Pradawnych / Twierdza Bezimiennego / Studnia
# Głosów = sygnał „ZAWRÓĆ". Elity (scope='pool') pojawiają się WYŁĄCZNIE na
# pierścieniach wokół tych hexów (poza nimi silnik nie może ich wylosować).
# Świątynia (mit ŚWIATA) = najgroźniejsza: obie elity.
MYTH_POOLS: list[tuple[tuple[int, int], int, list[str]]] = [
    ((66, 50), 1, ["widmo_studni"]),                       # Studnia Głosów
    ((74, 52), 1, ["bezimienna_straz"]),                   # Twierdza Bezimiennego
    ((79, 26), 1, ["bezimienna_straz", "widmo_studni"]),   # Świątynia Pradawnych
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


def seed_sol_chance(conn: sqlite3.Connection) -> int:
    """§2 smaczek — sól tłumi Rdzeń: obniż bazową szansę spotkań na `sol` poniżej
    heath, żeby gradient wprost oddał lore (sól = najspokojniejszy teren pustkowia
    poza traktem). Idempotentny: aktualizuje tylko gdy wartość inna."""
    cur = conn.execute(
        "UPDATE hex_type_config SET encounter_base_chance = ? "
        "WHERE hex_type = 'sol' AND encounter_base_chance != ?",
        (SOL_ENCOUNTER_BASE_CHANCE, SOL_ENCOUNTER_BASE_CHANCE),
    )
    return cur.rowcount


def seed_myth_pools(conn: sqlite3.Connection) -> int:
    """§4 — pule stref mitów. Elity scope='pool' wpisane w world_hexes.encounter_pool
    na pierścieniach wokół Świątyni/Twierdzy/Studni Głosów: sygnał „zawróć". Poza tymi
    hexami silnik nie może ich wylosować. Seed re-aplikuje po reseedzie mapy."""
    n = 0
    for center, radius, pool in MYTH_POOLS:
        for q, r in _hex_ring(center, radius=radius):
            row = conn.execute(
                "SELECT encounter_pool FROM world_hexes WHERE q=? AND r=? "
                "AND map_level=0 AND region=?", (q, r, REGION),
            ).fetchone()
            if row is None:
                continue  # poza krainą / poza mapą
            try:
                existing = json.loads(row["encounter_pool"]) if row["encounter_pool"] else []
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, TypeError):
                existing = []
            merged = list(dict.fromkeys([*existing, *pool]))  # unia, bez dubli
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
        if not any(t["boss"] for t in d["tiles"]):
            problems.append(f"loch {d['key']}: brak kafla bossa")
        boss_cat = {r[0] for r in conn.execute(
            "SELECT category_key FROM dungeon_tiles WHERE category_key = ? "
            "AND is_boss_tile = 1", (d["tile_category_key"],))}
        if d["tile_category_key"] not in boss_cat:
            problems.append(f"loch {d['key']}: kategoria {d['tile_category_key']} bez kafla bossa w DB")
        if d["key"] not in dungs:
            problems.append(f"loch {d['key']}: brak w game_dungeons")
    # Pule mitów — enemy scope='pool' muszą wylądować na hexach.
    for center, radius, pool in MYTH_POOLS:
        for k in pool:
            if k not in valid_enemies:
                problems.append(f"pula mitu {center}: brak wroga {k}")
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
    myth_n = seed_myth_pools(conn)
    sol_n = seed_sol_chance(conn)
    conn.commit()

    print(f"  wrogowie nowi:            {res['enemies']} (z {len(ENEMIES)})")
    print(f"  tabele łupów nowe:        {res['loot_tables']}")
    print(f"  wpisy łupów nowe:         {res['loot_entries']}")
    print(f"  spotkania nowe:           {enc_n} (z {len(ENCOUNTERS)})")
    print(f"  plotki nowe:              {rum_n} (z {len(RUMORS)})")
    print(f"  lochy nowe:               {dun_n} (z {len(DUNGEONS)})")
    print(f"  kategorie kafli nowe:     {tile_cat_n}")
    print(f"  kafle lochów nowe:        {tile_n}")
    print(f"  hexy pul mitów:           {myth_n}")
    print(f"  sol chance obniżona:      {sol_n} (→ {SOL_ENCOUNTER_BASE_CHANCE})")

    print("\n  spotkania per teren krainy (gradient):")
    for row in conn.execute(
        "SELECT biome, COUNT(*) n, MIN(level_min) lo, MAX(level_max) hi, "
        "MIN(weight) wmin, MAX(weight) wmax FROM game_config_encounters "
        "WHERE region_tag = ? GROUP BY biome ORDER BY wmax DESC, biome", (REGION,),
    ):
        print(f"    {row['biome']:14s} {row['n']} scen | poziomy {row['lo']}–{row['hi']} "
              f"| wagi {row['wmin']:.0f}–{row['wmax']:.0f}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
