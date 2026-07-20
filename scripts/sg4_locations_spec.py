#!/usr/bin/env python3
"""SG-4 (#1481) — katalog lokacji makro Siwych Grań + reguły ich rozstawienia.

Jedno źródło prawdy dla dwóch narzędzi:
  * scripts/sg4_place_locations.py  — sadzi lokacje na hexach w pliku kanonu
    (data/regions/region_siwe_granie.json) i dokłada zaczepy traktu,
  * scripts/seed_siwe_granie_locations.py — wsiewa rekordy `game_locations`
    do DB i spina je z hexami przez `link_location_to_hex` (#1305).

Opisy i atmosfera są PRZEPISANE z lore: docs/world/regions/siwe_granie.md §4.

TRZY KLASY (wzorzec „droga = tętnica, atrakcje obok niej"):
  A — ZASIEDLONE: max 1 hex od traktu (karawany muszą dojechać). Dostają
      hex-zaczep `road` w sąsiedztwie, żeby algorytm trasowania miał cel.
  B — OPUSZCZONE: 2–5 hexów OD traktu, celowo BEZ drogi. Zjazd w dzicz jest
      decyzją gracza. Pozycja wybierana automatycznie (target_row + strona).
  C — ZA GRANICĄ DRÓG: lodowiec i głęboka tundra. Dojście = przeprawa (§4b).
"""

# Osie geometrii: kolumna = q, wiersz "północ-południe" liczony jak w mapie:
#   row = -r - q//2   (row 1 = południowa granica „ku Kresom", row 51 = lodowiec)

# Współrzędne osiowe (q, r).
KARAWANSERAJ_HEX = (12, -14)      # row 8 — NA trakcie głównym Przesmyk → Gród
TERMINUS_ANCHOR = (20, -53)       # row 43 — koniec traktu na skraju tundry (§4b)

# Teren, na którym wolno postawić lokację klasy B (opuszczone, w górach).
B_TERRAIN = ("mountain", "snow", "hills", "heath", "las_iglasty", "siarka")

LOCATIONS = [
    # ── KLASA A — zasiedlone, przy trakcie ────────────────────────────────
    dict(
        key="karawanseraj_na_trakcie", label="Karawanseraj na Trakcie", cls="A",
        fixed=KARAWANSERAJ_HEX, anchor=None, hex_type=None,   # zostaje `road`
        icon="town", tier=1, biome="mountain", subtype="wayside-inn", safe=1,
        desc="Kamienny dziedziniec z niskim murem i wielką stajnią przy samym trakcie — "
             "ostatni porządny postój przed Kamiennym Grodem. Zatrzymują się tu karawany "
             "z Kresów i przemytnicy schodzący ze Starej Przełęczy; za miskę kaszy kupisz "
             "nowinę, za srebro — czyjeś milczenie.",
        atmo="Zapach mokrej wełny, łoju i końskiego potu; nocą dzwonki jucznych kóz "
             "i kłótnie przy ogniu.",
    ),
    dict(
        key="wyrobisko_srebrnej_zyly", label="Wyrobisko Srebrnej Żyły", cls="A",
        fixed=(18, -28), anchor=(18, -27), hex_type="village",
        icon="cave", tier=3, biome="mountain", subtype="mining-village", safe=1,
        desc="Czynna kopalnia srebra i przyklejona do niej wioska gwarków — druga po Grodzie "
             "ostoja żywych ludzi w Graniach. Sztolnie kończą się grzecznie NAD Linią Soli "
             "i nikt nie schodzi niżej, choć od pół roku sztygarów budzi w nocy stukanie, "
             "które słychać coraz wyraźniej.",
        atmo="Zgrzyt kołowrotu, srebrny pył w mokrym powietrzu i cichy, miarowy stukot "
             "niosący się żyłą gdzieś spod stóp.",
    ),
    dict(
        key="gorace_zrodla", label="Gorące Źródła", cls="A",
        fixed=(23, -36), anchor=(23, -35), hex_type="village",
        icon="town", tier=3, biome="mountain", subtype="hot-springs", safe=1,
        desc="Jedyne ciepłe miejsce w Graniach — parujące niecki wśród śniegu, gdzie karawany "
             "zdejmują buty i rozwiązują języki. Kąpielisko, wodopój i giełda plotek w jednym.",
        atmo="Kłęby pary nad zieloną wodą, zapach siarki i mokrego kamienia, śmiech odbijający "
             "się od ścian doliny.",
    ),
    dict(
        key="posterunek_linii_soli", label="Posterunek Linii Soli", cls="A",
        fixed=(14, -35), anchor=(13, -34), hex_type="village",
        icon="fortress", tier=3, biome="underground", subtype="garrison", safe=1,
        desc="Sztolnia graniczna wykuta w soli — tu kończy się to, co wolno kopać. Wartownicy "
             "rodowi pilnują zejścia, spisują każdego, kto przechodzi, i nie przepuszczają "
             "nikogo bez pieczęci starszyzny.",
        atmo="Białe solne naloty na ścianach, chrzęst kryształów pod butem i cisza tak gęsta, "
             "że słychać własne tętno.",
    ),
    dict(
        key="siarkowe_pola", label="Siarkowe Pola", cls="A",
        fixed=(42, -33), anchor=(41, -33), hex_type="village",
        icon="wilderness", tier=2, biome="mountain", subtype="sulphur-camp", safe=1,
        desc="Obóz zbieraczy siarki pod Czarnymi Skałami — namioty z natłuszczonej skóry, "
             "taczki żółtego urobku i ludzie z chustami na twarzach. Opary tną w gardle, "
             "ale siarka płaci lepiej niż srebro.",
        atmo="Żółty pył osiada na wszystkim, powietrze drapie w płucach, a ziemia jest ciepła "
             "nawet w mróz.",
    ),

    # ── KLASA B — opuszczone, 2–5 hexów OD traktu, bez drogi ──────────────
    dict(
        key="sztolnia_umarlego_rodu", label="Sztolnia Umarłego Rodu", cls="B",
        target_row=13, side="w", hex_type="ruins",
        icon="cave", tier=2, biome="dungeon", subtype="cursed-mine", safe=0,
        desc="Opuszczona kopalnia rodu, którego już nie ma — płytsza i starsza niż Hutman, "
             "ale schodzi w tę samą ciemność. Dobre miejsce, żeby coś znaleźć. Dobre miejsce, "
             "żeby zostać.",
        atmo="Zawalone chodniki, pordzewiałe wózki na wykrzywionych szynach i przeciąg, "
             "który idzie z dołu, nie z góry.",
    ),
    dict(
        key="echo_wieza", label="Echo-Wieża", cls="B",
        target_row=16, side="e", hex_type="ruins",
        icon="mountain", tier=2, biome="mountain", subtype="watchtower", safe=0,
        desc="Krasnoludzki nasłuch stukania: szyb z rezonansowymi dzwonami, które miały mówić, "
             "jak głęboko sięga to, co się obudziło. Ostatni obserwator odszedł lata temu — "
             "zapisy zostały na pulpicie, dokładne aż do ostatniej nocy.",
        atmo="Dzwony wiszą nieruchomo, a mimo to co jakiś czas jeden z nich cicho odpowiada "
             "czemuś pod ziemią.",
    ),
    dict(
        key="grauhold", label="Grauhold — Wyssany Hołd", cls="B",
        target_row=21, side="e", hex_type="ruins",
        icon="ruin", tier=3, biome="mountain", subtype="abandoned-hold", safe=0,
        desc="Wyssany hołd rodu Grauhold — osada rodowa porzucona w czasie exodusu. Domy stoją, "
             "paleniska zimne, a w izbach zostało wszystko, czego nie dało się unieść.",
        atmo="Śnieg zawiał progi, drzwi kołyszą się na wietrze, a z kominów nie idzie nawet "
             "ślad dymu.",
    ),
    dict(
        key="silberhold", label="Silberhold — Wyssany Hołd", cls="B",
        target_row=24, side="w", hex_type="ruins",
        icon="ruin", tier=3, biome="mountain", subtype="abandoned-hold", safe=0,
        desc="Wyssany hołd rodu Silberhold — bogaci byli ze srebra i to srebro ich zgubiło: "
             "kopali dalej, niż wolno. Zostały szyby, zostały skrzynie, nie został nikt.",
        atmo="Srebrne żyły w ścianach błyskają w świetle pochodni, a echo kroków wraca o jeden "
             "krok za późno.",
    ),
    dict(
        key="kohlgrund", label="Kohlgrund — Wyssany Hołd", cls="B",
        target_row=30, side="e", hex_type="ruins",
        icon="ruin", tier=4, biome="mountain", subtype="abandoned-hold", safe=0,
        desc="Wyssany hołd rodu Kohlgrund — hołd węglowy, czarny od sadzy nawet po latach. "
             "Rodowe piece wygasły, ale zapach dymu nigdy stąd nie wywietrzał.",
        atmo="Czarny pył chrzęści pod butami, a ściany są ciepłe w miejscach, w których być "
             "ciepłe nie powinny.",
    ),
    dict(
        key="kaplica_zapomnianego_rodu", label="Kaplica Zapomnianego Rodu", cls="B",
        target_row=33, side="w", hex_type="ruins",
        icon="temple", tier=4, biome="mountain", subtype="ruined-chapel", safe=0,
        desc="Kaplica rodu wymazanego z kronik Sali Rodów. Kamień pamięta imię, którego "
             "w Grodzie nikt nie wypowiada — wykute jest na ołtarzu, tylko starannie skute dłutem.",
        atmo="Chłód głębszy niż na zewnątrz, świece dawno wypalone, a mimo to knoty są świeżo "
             "przycięte.",
    ),
    dict(
        key="stacja_pradawnych", label="Stacja Pradawnych", cls="B",
        target_row=36, side="e", hex_type="ruins",
        icon="ruin", tier=5, biome="mountain", subtype="ancient-ruin", safe=0,
        desc="Ruina starsza niż wszystkie krasnoludzkie hołdy razem wzięte — regularna, gładka, "
             "zbudowana z materiału, którego górnicy nie umieją nazwać. Pradawni byli tu przed "
             "nimi i zostawili po sobie tylko to.",
        atmo="Ściany bez jednej szczeliny, a wewnątrz nie ma śniegu, choć nie ma też dachu.",
    ),
    dict(
        key="frosthold", label="Frosthold — Wyssany Hołd", cls="B",
        target_row=39, side="w", hex_type="ruins",
        icon="ruin", tier=4, biome="tundra", subtype="abandoned-hold", safe=0,
        desc="Wyssany hołd rodu Frosthold — najwyżej położona osada rodowa, opuszczona jako "
             "pierwsza. Mróz zakonserwował ją tak dokładnie, że wygląda, jakby mieszkańcy "
             "wyszli wczoraj.",
        atmo="Wszystko pod szklistą warstwą lodu: stoły, narzędzia, buty przy drzwiach.",
    ),
    dict(
        key="cmentarz_mlotow", label="Cmentarz Młotów", cls="B",
        target_row=42, side="e", hex_type="ruins",
        icon="graveyard", tier=4, biome="tundra", subtype="graveyard", safe=0,
        desc="Pole młotów wbitych stylem w lód — jeden za każdego, kto nie doszedł podczas "
             "exodusu. Nikt tu nie mieszka, nikt nie sprząta, a rodowe znaki na trzonkach "
             "powoli zaciera wiatr.",
        atmo="Las stalowych głowic sterczących ze śniegu; nocą podobno któryś młot sam dzwoni, "
             "choć nie ma czym uderzyć.",
    ),

    # ── KLASA C — za granicą dróg (tundra i lodowiec, §4b) ────────────────
    dict(
        key="oboz_wygnancow_lodu", label="Obóz Wygnańców Lodu", cls="C",
        fixed=(22, -55), anchor=None, hex_type="village",
        icon="town", tier=4, biome="tundra", subtype="nomad-camp", safe=1,
        desc="Koczowisko wyklętego rodu na południowym skraju tundry — skórzane namioty, sanie "
             "i psy. Starszyzna wyklęła ich za złamanie zakazu lodowca, Młotodzierżcy handlują "
             "z nimi po cichu, a oni jako jedyni widzieli lód z bliska. Stąd wyrusza się na "
             "lodowiec — dalej trakt już nie idzie.",
        atmo="Dym z torfu kładzie się nisko, psy warczą w stronę północy, a nikt nie mówi "
             "głośno o tym, co jest za lodem.",
    ),
    dict(
        key="sanktuarium_zamarznietej_pielgrzymki",
        label="Sanktuarium Zamarzniętej Pielgrzymki", cls="C",
        fixed=(36, -65), anchor=None, hex_type="ruins",
        icon="temple", tier=5, biome="tundra", subtype="frozen-shrine", safe=0,
        desc="Puste sanktuarium na Lodowym Pasie, a wokół niego wmarznięta w lód procesja "
             "pielgrzymów sprzed pokoleń. Nikt nie wie, skąd przyszli ani czemu szli w górę. "
             "Sanktuarium jest puste — ale odśnieżone. Mieszka tu jeden człowiek, który nie "
             "pamięta, kiedy przyszedł.",
        atmo="Twarze w lodzie zwrócone w tę samą stronę; ścieżka do wrót jest starannie "
             "odgarnięta.",
    ),
    dict(
        key="zamarznieta_karawana", label="Zamarznięta Karawana", cls="C",
        fixed=(28, -63), anchor=None, hex_type="ruins",
        icon="ruin", tier=5, biome="tundra", subtype="frozen-wreck", safe=0,
        desc="Wraki wozów wmarznięte w lodową szczelinę, dyszlami skierowane w górę zbocza. "
             "Ładunek pod plandekami jest cały. Pytanie nie brzmi, co wieźli — tylko dlaczego "
             "jechali NA lodowiec, a nie z niego.",
        atmo="Płozy i koła sterczą z niebieskiego lodu, a pod stopami widać kształty, których "
             "lepiej nie oglądać z bliska.",
    ),
    dict(
        key="lodowa_brama", label="Lodowa Brama", cls="C",
        fixed=(30, -66), anchor=None, hex_type="ruins",
        icon="ruin", tier=5, biome="tundra", subtype="mystery", safe=0,
        # lore §4: long-term mystery krainy — ZERO questów i wejścia, sam opis
        desc="Wmarznięte w lodowiec wrota — dwuskrzydłowe, wyższe niż brama Kamiennego Grodu, "
             "bez klamki, zawiasu i szczeliny. Nikt nie wie, co jest za nimi, i nikt nie zna "
             "nikogo, kto by wiedział. Nie ma tu czego otwierać i nie ma dokąd wejść.",
        atmo="Lód wokół wrót jest przezroczysty jak szkło i nigdy nie topnieje, nawet gdy "
             "słońce stoi wprost nad nimi.",
    ),
]

BY_KEY = {loc["key"]: loc for loc in LOCATIONS}
