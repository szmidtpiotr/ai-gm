#!/usr/bin/env python3
"""SG-5 (#1481) — Kamienny Gród: hub + sub-lokacje (struktura osady #1212).

Jedno źródło prawdy dla dwóch narzędzi:
  * scripts/sg5_place_grod.py     — wbija hub w hex kanonu (data/regions/…),
  * scripts/seed_kamienny_grod.py — wsiewa `game_locations` (hub + suby),
    spina hub z hexem (`link_location_to_hex`, #1305) i buduje mapę lokalną
    map_level=1 (`auto_assign_local_hex`, FAZA ML #993).

Opisy wprost z lore: docs/world/regions/siwe_granie.md §2, §4, §9.

KOLEJNOŚĆ SUB-LOKACJI MA ZNACZENIE: `auto_assign_local_hex` układa je po `id ASC`
na pierścieniu, więc pierwsza dostaje hex (0,0) — środek mapy lokalnej. Dlatego
pierwsza jest Brama-Most: wchodzi się przez nią i z niej rozchodzi po mieście.
"""

HUB_HEX = (16, -17)   # zarezerwowany w SG-2/SG-3, wolny do tej pory

HUB = dict(
    key="kamienny_grod", label="Kamienny Gród",
    hex_type="town", icon="castle", tier=2, biome="urban",
    subtype="fortress-city", safe=1, visible=1,
    desc="Stolica Grań i ostatnie duże miasto krasnoludów — twierdza wykuta w ścianie "
         "doliny, do której wchodzi się jedną bramą-mostem przerzuconą nad przepaścią. "
         "Trwa mimo exodusu: Wielka Kuźnia bije, targ handluje solą i srebrem, a Sala "
         "Rodów co wieczór kłóci się o to samo — czy wracać do Hutmana.",
    atmo="Kuźniany żar i zimny przeciąg z przepaści mieszają się na ulicach; wszędzie "
         "słychać młot, a pod nim, głębiej, coś, czego nikt nie nazywa.",
)

# safe=1 → odpoczynek bezpieczny, niższa szansa na zdarzenie na mapie lokalnej
# (local_hex_service: SAFE 0.10 vs RISKY 0.20 — wartości startowe).
SUBS = [
    dict(
        key="grod_brama_most", label="Kamienny Gród: Brama-Most",
        subtype="gate", icon="fortress", safe=0, tier=2, biome="urban",
        desc="Jedyne wejście do Grodu: kamienny most przerzucony nad przepaścią tak "
             "głęboką, że nie słychać dna. Po drugiej stronie wrota z żelaza i dwóch "
             "wartowników, którzy pytają o imię rodu, zanim zapytają o cokolwiek innego.",
        atmo="Wiatr z przepaści szarpie płaszczem, a most odpowiada niskim, kamiennym "
             "pomrukiem na każdy krok.",
    ),
    dict(
        key="grod_pod_rdzawym_mlotem", label="Kamienny Gród: Pod Rdzawym Młotem",
        subtype="tavern", icon="town", safe=1, tier=1, biome="urban",
        desc="Szynk pod znakiem rdzawego młota — pierwsze schronienie każdego, kto wszedł "
             "mostem. Piwo gęste, izby ciasne, a plotka o stukaniu dojdzie do ciebie, "
             "zanim zdążysz zdjąć płaszcz.",
        atmo="Niski strop, sadza na belkach, gwar przy długich stołach i młot nad "
             "szynkwasem, którego nikt nigdy nie zdjął.",
    ),
    dict(
        key="grod_wielka_kuznia", label="Kamienny Gród: Wielka Kuźnia",
        subtype="smithy", icon="fortress", safe=1, tier=2, biome="urban",
        desc="Serce Grodu i najgorętsze miejsce w całych Graniach — dwadzieścia palenisk "
             "pod jednym sklepieniem. Tu się naprawia, przekuwa i kupuje żelazo, a mistrz "
             "kuźni wie o soli więcej niż niejeden kapłan.",
        atmo="Żar bije w twarz od progu, iskry idą w górę jak stado, a rozmowę trzeba "
             "prowadzić krzykiem.",
    ),
    dict(
        key="grod_sala_rodow", label="Kamienny Gród: Sala Rodów",
        subtype="hall", icon="castle", safe=1, tier=2, biome="urban",
        desc="Wykuta w skale sala z kronikami wszystkich rodów Grań — także tych, których "
             "już nie ma. To tu starszyzna wydaje zakazy i to tu Młotodzierżcy podważają "
             "je najgłośniej.",
        atmo="Rzędy rodowych znaków na ścianach, jedno miejsce starannie skute do gołego "
             "kamienia i nikt nie tłumaczy dlaczego.",
    ),
    dict(
        key="grod_targ_solny", label="Kamienny Gród: Targ Solny",
        subtype="market", icon="town", safe=1, tier=1, biome="urban",
        desc="Kryty targ pod skalnym nawisem: sól, srebro, suszone mięso i towary z Kresów "
             "przywiezione karawaną. Woreczek soli przy pasie kupisz tu taniej niż "
             "gdziekolwiek indziej — i nikt nie pyta, po co.",
        atmo="Chrzęst solnych kryształów pod butami, targowanie w trzech językach i zapach "
             "dymu z rożna.",
    ),
]

# lore §9 — domyślny start krasnoluda i warianty dla planu LLM. Zapisane tu jako
# DANE; wpięcie w silnik startu (rasa → kraina → whitelista) to osobne zadanie,
# bo wymaga kodu, nie seeda.
START_DEFAULT = "grod_pod_rdzawym_mlotem"
START_WHITELIST = ["grod_pod_rdzawym_mlotem", "karawanseraj_na_trakcie", "wyrobisko_srebrnej_zyly"]
