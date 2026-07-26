#!/usr/bin/env python3
"""MP-4 — seed Martwych Pustkowi: lokacje makro (osady, POI, miejsca zapomniane).

Zgodne z docs/world/regions/martwe_pustkowia.md §4 (katalog + HIERARCHIA TAJEMNIC)
+ §5 (pasy terenu). BEZ sub-lokacji Solnego Progu — te idą w MP-5.

Wiązanie z mapą ZAWSZE przez link_location_to_hex (kanon = world_hexes.location_key);
GOTCHA #1305: goły INSERT bez hexa czyści reconcile. create_location robi link
wewnętrznie (patrz location_factory). Idempotentne — bezpieczne do re-runu.

HIERARCHIA TAJEMNIC (§4 [ZATWIERDZONE]) — respektowana w opisach:
  * Świątynia Pradawnych  — mit ŚWIATA: opis atmosferyczny, ZERO questów/wejścia.
  * Twierdza Bezimiennego — long mystery krainy: „nikt nie wrócił", bez questu.
  * Krypta Krwawego Hrabiego — endgame krainy: na razie lokacja fabularna
    (farmowalny dungeon dobuduje MP-6).
  * Aschfeld — farmowalny dungeon otwarty od seedu.

DODATKOWO naprawia dwa zerwane linki hex↔lokacja (artefakt surowego dumpu FAZA RM):
  world_hexes (85,38) location_key 'krypta_hrabiego'  → game_locations 'krypta_krwawego_hrabiego'
  world_hexes (62,51) location_key 'klasztor_pradawny' → game_locations 'ruiny_klasztoru_pradawnego'
link_location_to_hex nadpisuje world_hexes.location_key kluczem lokacji (kanon).

Uruchamiać W KONTENERZE (DB_PATH=/data/ai_gm.db):
    docker cp scripts/seed_martwe_pustkowia_locations.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_martwe_pustkowia_locations.py

Po seedzie: snapshot_content.py (game_locations.json) + snapshot_world_map.py
--region martwe_pustkowia → commit (content-as-code #1202, created_by='seed').
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.location_factory import LocationSource, create_location  # noqa: E402
from app.services.hex_location_link import link_location_to_hex  # noqa: E402

DB_PATH = "/data/ai_gm.db"
REGION = "martwe_pustkowia"

# ── Kanoniczne POI (już w DB z surowego dumpu) — odświeżamy opis/etykietę wg
#    lore §4 i (RE)linkujemy do hexa. Dwa pierwsze naprawiają zerwany link
#    (hex trzymał stary klucz generatora). (key, hex_q, hex_r, label, description)
POI_UPDATES = [
    ("pustkowie_solne", 67, 39, "Pustkowie Solne",
     "Naturalna blizna świata: biała, najczystsza sól po horyzont, wypchnięta z ziemi "
     "wokół największych pęknięć Rdzenia. Im bliżej pęknięcia powstała, tym mocniej tłumi. "
     "Paradoks krainy — najcenniejszy towar rośnie na progu piekła. Na tych hexach nie ma "
     "wody: pełny odpoczynek wymaga bukłaka."),
    ("swiatynia_pradawnych", 79, 26, "Świątynia Pradawnych",
     "Tu Pradawni nadużyli Rdzenia i tu wydarzyło się Wielkie Pęknięcie — kraina umarła "
     "w jedną epokę. Serce ich cywilizacji, dziś oś, wokół której milczy cały świat. "
     "Nikt nie wchodzi; nikt nie wie, co za progiem. Mit ponad wszystkimi mitami — "
     "brama pozostaje zamknięta (opis atmosferyczny, bez wejścia i questów)."),
    ("twierdza_bezimiennego", 74, 52, "Twierdza Bezimiennego",
     "Czarna warownia bez herbu i imienia, wrośnięta w martwą ziemię. Ci, którzy tam "
     "poszli, nie wrócili — i tak zostaje. Piętnowani wskazują ją milczeniem. "
     "Długa tajemnica krainy: żaden quest jej nie otwiera."),
    ("krypta_krwawego_hrabiego", 85, 38, "Krypta Krwawego Hrabiego",
     "Grobowiec wampira-rycerza, który targował się z Rdzeniem o nieśmiertelność i "
     "wygrał gorzej, niż przegrał. Ostrzeżenie wykute w kamieniu, co robi Rdzeń z tymi, "
     "którzy go proszą. Endgame krainy — na razie lokacja fabularna (farmowalny loch "
     "dobuduje MP-6)."),
    ("ruiny_klasztoru_pradawnego", 62, 51, "Ruiny Pradawnego Klasztoru",
     "Zawalony klasztor Pradawnych w południowym „mieście umarłych”. Kolumny sterczą "
     "z popiołu jak żebra, a w krużgankach echo nie milknie. Jedno z gęstszych gniazd "
     "nieumarłych krainy."),
]

# ── Nowe lokacje makro.
#    (key, label, hex_q, hex_r, biome, tier, safe, map_icon, subtype, description)
NEW_LOCATIONS = [
    # ── Zasiedlone (§4) — enklawa na skraju strefy sol, przy zachodnim końcu traktu.
    ("solny_prog", "Solny Próg", 64, 37, "wasteland", 1, 1, "town", "enclave-hub",
     "Enklawa Piętnowanych na skraju solnej równiny — jedyni, którzy umieją ŻYĆ na "
     "pustkowiach. Odnoga starego traktu dochodzi tu od północy. Za murem z solnych "
     "cegieł: Dom Starszych, Cicha Sala pamięci Wycofania, Targ Przewodników z "
     "kontraktami na wyprawy w ruiny, magazyny i gospoda dla obcych. Napięcie krainy: "
     "ukryć się czy otworzyć. (Wnętrze enklawy — sub-lokacje — dobuduje MP-5.)"),
    ("oboz_goraczki", "Obóz Gorączki", 68, 41, "wasteland", 2, 1, "town", "boomtown",
     "Boomtown poszukiwaczy reliktów, ściągniętych z całego świata przez gorączkę. "
     "Namioty, paser, plotki i chaos rosnące szybciej niż rozum. Ludzie rozkopują "
     "groby i budzą to, co spało; Greta trzyma to razem, a Fabian skupuje relikty dla "
     "Brata Tomasza. Wyjściowa brama w ruiny — i w kłopoty."),
    ("misja_swiatla", "Misja Światła", 62, 40, "wasteland", 1, 1, "town", "light-outpost",
     "Placówka Świątyni na skraju enklawy. Brat Ansgar leczy każdego, kto przyjdzie; "
     "Siostra Verena obserwuje i notuje — „czy piętno to skażenie?”. Jedno z niewielu "
     "miejsc krainy z wodą. Trzy siły ciągną enklawę w trzy strony, a Światło jest jedną "
     "z nich."),
    ("solne_zniwa", "Solne Żniwa", 60, 42, "wasteland", 2, 1, "town", "salt-harvest",
     "Obozowisko zbieraczy w głębi solnej równiny. Piętnowani pod okiem Nadiry zeskrobują "
     "premium sól i ładują ją na karawany do Siwych Grań — szlak handlowy Pustkowia↔Granie. "
     "Ciężka, cicha praca; woda tylko z bukłaków przywiezionych z Misji."),

    # ── Miejsca opuszczone / zapomniane (§4).
    ("aschfeld", "Aschfeld", 79, 36, "wasteland", 3, 0, "ruin", "imperial-colony",
     "Porzucona kolonia imperialna z Ery Latarni — Korona werbowała tu osadników z "
     "południowych prowincji, a potem w jedno pokolenie ich zostawiła (Wycofanie). "
     "Domy stoją, ludzi nie ma; popiół wsypał się przez okna. Farmowalny dungeon, "
     "otwarty od seedu."),
    ("koniec_traktu", "Koniec Traktu", 69, 16, "heath", 2, 0, "ruin", "gate-ruin",
     "Brama-ruina na granicy z Czarnoborem, gdzie urywa się imperialny trakt (po drugiej "
     "stronie zarósł jako Zarośnięty Trakt). Słupy milowe stoją, ale prowadzą już donikąd. "
     "Pierwsze, co widzi każdy, kto wchodzi w krainę od północy: droga, którą Imperium "
     "porzuciło."),
    ("wieza_kronikarzy", "Wieża Kronikarzy", 74, 30, "wasteland", 3, 0, "ruin", "archive",
     "Imperialne archiwum z czasów kolonii, wzniesione przy trakcie. Zapiski urywają się "
     "w pół zdania — dokładnie tam, gdzie miały wyjaśnić, dlaczego Korona porzuciła "
     "Pustkowia. Questowe źródło prawdy o Wycofaniu: kto doczyta ostatnią stronę?"),
    ("pola_szkla", "Pola Szkła", 84, 30, "ashland", 3, 0, "wilderness", "glass-field",
     "Ziemia stopiona w szkło w chwili Pęknięcia — gładka, czarna tafla, w której odbija "
     "się martwe niebo. Żadnego wiatru, żadnego głosu; martwa cisza, która sama w sobie "
     "jest ostrzeżeniem. Blisko epicentrum, gdzie świat pękł."),
    ("cmentarzysko_machin", "Cmentarzysko Machin", 83, 42, "ruins", 3, 0, "ruin", "machine-graveyard",
     "Pole szczątków „machin” Pradawnych — coś między rzeźbą a szkieletem, z metalu, "
     "którego nikt już nie odlewa. Do czego służyły, nie wie nikt żywy. Leżą tu od "
     "Wielkiego Pęknięcia, wpół zapadnięte w popiół, i czasem drgają, gdy Rdzeń pod "
     "spodem się porusza."),
    ("studnia_glosow", "Studnia Głosów", 66, 50, "ruins", 3, 0, "ruin", "haunted-well",
     "Szyb w południowym mieście umarłych, z którego dnem szemrzą szepty — czyjeś, "
     "obce, nigdy dwa razy te same. Piętnowani zakazują słuchać dłużej niż trzy oddechy: "
     "kto łamie zakaz, wraca odmieniony albo nie wraca wcale."),
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        n_new = 0
        n_upd = 0

        # 1) Kanoniczne POI — update opisu/etykiety + (re)link do hexa (naprawia
        #    zerwane linki krypty i klasztoru: hex trzymał stary klucz generatora).
        for key, q, r, label, desc in POI_UPDATES:
            row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (key,)).fetchone()
            if not row:
                print(f"  ! POI {key} brak w DB — pomijam (spodziewany był z dumpu RM)")
                continue
            conn.execute(
                "UPDATE game_locations SET label = ?, description = ?, region = ?, "
                "updated_at = datetime('now') WHERE key = ?",
                (label, desc, REGION, key),
            )
            link_location_to_hex(conn, key, q, r, level=0)
            n_upd += 1
            print(f"  ~ POI {key} -> hex ({q},{r})")

        # 2) Nowe lokacje makro (idempotentne po kluczu; link przez create_location).
        for (key, label, q, r, biome, tier, safe, icon, subtype, desc) in NEW_LOCATIONS:
            res = create_location(
                conn,
                key=key, label=label, source=LocationSource.SEED,
                description=desc, location_type="macro",
                biome=biome, region=REGION, tier=tier, safe_for_rest=safe,
                map_icon=icon, location_subtype=subtype,
                hex_q=q, hex_r=r, hex_level=0,
                commit=False,
            )
            if res["created"]:
                n_new += 1
                print(f"  + {key} -> hex ({q},{r})")
            else:
                conn.execute(
                    "UPDATE game_locations SET label = ?, description = ?, region = ?, "
                    "updated_at = datetime('now') WHERE key = ?",
                    (label, desc, REGION, key),
                )
                link_location_to_hex(conn, key, q, r, level=0)
                print(f"  ~ {key} (istniał) -> hex ({q},{r})")

        conn.commit()

        # Weryfikacja: makro-lokacje regionu z hexem (kanon world_hexes.location_key).
        linked = conn.execute(
            "SELECT gl.key, wh.q, wh.r FROM game_locations gl "
            "JOIN world_hexes wh ON wh.location_key = gl.key AND wh.map_level = 0 "
            "WHERE gl.region = ? AND gl.location_type = 'macro' ORDER BY wh.r, wh.q",
            (REGION,),
        ).fetchall()
        total_macro = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE region = ? AND location_type = 'macro'",
            (REGION,),
        ).fetchone()[0]
        orphan = conn.execute(
            "SELECT gl.key FROM game_locations gl "
            "WHERE gl.region = ? AND gl.location_type = 'macro' AND NOT EXISTS "
            "(SELECT 1 FROM world_hexes wh WHERE wh.location_key = gl.key AND wh.map_level = 0) "
            "ORDER BY gl.key",
            (REGION,),
        ).fetchall()

        print(f"\n✓ Nowych: {n_new} · zaktualizowanych POI: {n_upd}")
        print(f"  Makro-lokacji regionu '{REGION}': {total_macro} · z hexem: {len(linked)}")
        print("  Lokacja -> hex (wg położenia):")
        for row in linked:
            print(f"    {row['key']:28s} ({row['q']},{row['r']})")
        if orphan:
            print("  ! BEZ HEXA (do sprawdzenia):")
            for row in orphan:
                print(f"    {row['key']}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
