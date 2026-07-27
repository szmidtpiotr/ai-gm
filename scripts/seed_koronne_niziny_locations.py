#!/usr/bin/env python3
"""KN-4 — seed Koronnych Nizin: lokacje makro (zasiedlone + zapomniane).

Zgodne z docs/world/regions/koronne_niziny.md §4 (katalog + HIERARCHIA TAJEMNIC).
BEZ dzielnic Vilnogradu (sub-lokacje) — te idą w KN-5.

Wiązanie z mapą ZAWSZE przez link_location_to_hex (kanon = world_hexes.location_key);
GOTCHA #1305: goły INSERT bez hexa czyści reconcile. create_location robi link
wewnętrznie (patrz location_factory). Idempotentne — bezpieczne do re-runu.

HIERARCHIA TAJEMNIC (§4 [ZATWIERDZONE]) — respektowana w opisach:
  * Pierwszy Tron  — long mystery krainy: opis atmosferyczny, ZERO questów/wejścia.
  * Dwór Czwartego — endgame krainy: opis atmosferyczny, ZERO questów (finał intryg).
  * Katakumby Vilnogradu — miejski farmowalny dungeon, otwarty od seedu.
  * Sekret Rady Czterech — mit polityczny ŚWIATA: nietykany tu (nie jest lokacją).

NAPRAWIA dwa zerwane linki hex↔lokacja (grid KN-2 nadał hexom klucze-placeholdery
generatora zamiast kluczy realnych lokacji):
  world_hexes (-20,32) location_key 'volhynia'       → game_locations 'volhynia_kupiecka'
  world_hexes (-39,33) location_key 'klasztor_iskry'  → game_locations 'klasztor_iskry_centrum'
link_location_to_hex nadpisuje world_hexes.location_key kluczem lokacji (kanon).

Rogatka Wschodnia awansuje z sub → macro (komora celna to lokacja katalogu §4).

Nazwy wsi spichlerzowych: konwencja #997 (prowincja zachodnia = germańskie/hybrydy,
NIE realne polskie). Repurposuje 2 hexy-placeholdery typu 'village' na złotych łanach
+ 1 nowa na hexie pola_uprawne.

Uruchamiać W KONTENERZE (DB_PATH=/data/ai_gm.db):
    docker cp scripts/seed_koronne_niziny_locations.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_koronne_niziny_locations.py

Po seedzie: snapshot_content.py (game_locations.json) + snapshot_world_map.py
--region koronne_niziny → commit (content-as-code #1202, created_by='seed').
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.location_factory import LocationSource, create_location  # noqa: E402
from app.services.hex_location_link import link_location_to_hex  # noqa: E402

DB_PATH = "/data/ai_gm.db"
REGION = "koronne_niziny"

# ── Istniejące makro-huby z zerwanym linkiem (hex trzymał klucz-placeholder z KN-2).
#    Odświeżamy region + (re)linkujemy hex do realnego klucza lokacji.
#    (loc_key, hex_q, hex_r)
RELINK = [
    ("volhynia_kupiecka", -20, 32),
    ("klasztor_iskry_centrum", -39, 33),
]

# ── Rogatka Wschodnia: awans sub → macro (komora celna §4). Update opisu + relink.
ROGATKA = (
    "rogatka_wschodnia", -2, 14,
    "Rogatka Wschodnia",
    "Komora celna na trakcie z Kresów — pierwsza pieczęć Korony, jaką widzi przybysz "
    "ze wschodu. Berta Twarda Pieczęć sprawdza glejty, liczy myto i czyta papiery "
    "uważniej niż twarze. Tu mrok krainy pokazuje pierwszy ząb: nie kły, a stempel. "
    "List żelazny otwiera szlaban bez pytań; fałszywe papiery to test i ryzyko.",
)

# ── Nowe lokacje makro.
#    (key, label, hex_q, hex_r, biome, tier, safe, map_icon, subtype, description)
NEW_LOCATIONS = [
    # ── Zasiedlone: wsie spichlerzowe (§4). Prowincja karmi stolicę — i biednieje.
    #    Nazwy germańskie/hybrydowe (#997). Repurpose hexów-placeholderów village.
    ("muhlfeld", "Mühlfeld", -28, 19, "plains", 1, 1, "town", "granary-village",
     "Wieś spichlerzowa na złotych łanach na północ od stolicy — młyny mielą dzień "
     "i noc, a wozy ze zbożem ciągną do Vilnogradu bez końca. Karmi miasto i sama "
     "chudnie: podatek rośnie szybciej niż plon. Cicha złość pod strzechą — tło "
     "buntu chłopskiego, o którym w salonach się nie mówi."),
    ("kornbruck", "Kornbrück", -8, 37, "plains", 1, 1, "town", "granary-village",
     "Osada przy trakcie na wschodnim skraju łanów, gdzie zboże przekracza rzekę na "
     "drodze do targów. Spichlerze pełne, ludzie chudzi — cała nadwyżka jedzie dalej. "
     "Poborca Korony bywa tu częściej niż ksiądz."),
    ("ahrenau", "Ährenau", -25, 29, "plains", 1, 1, "town", "granary-village",
     "Wieś w sercu pól między Vilnogradem a Volhynią — samo złoto kłosów po horyzont. "
     "Najżyźniejsza ziemia krainy i najciężej opodatkowana. Starzy mówią, że kiedyś "
     "żyło się tu dostatnio; teraz liczy się ziarna przed oddaniem dziesięciny."),

    # ── Miejsca opuszczone / zapomniane (§4 + HIERARCHIA TAJEMNIC).
    ("pierwszy_tron", "Pierwszy Tron", -35, 31, "ruins", 2, 0, "ruin", "ancient-seat",
     "Ruiny pierwotnej siedziby Korony z początku Ery Latarni, wrośnięte w samotne "
     "wzgórze. Dwór przeniesiono nagle do Vilnogradu — kroniki milczą, dlaczego, a "
     "milczą tak zgodnie, że milczenie samo staje się pytaniem. Wiatr chodzi pustymi "
     "salami tronowymi, w których nikt już nie zasiada. Długa tajemnica krainy: "
     "żaden quest nie otwiera tego, czemu porzucono pierwszy tron. (Opis atmosferyczny "
     "— bez wejścia i questów.)"),
    ("zatopione_opactwo", "Zatopione Opactwo", -26, 42, "ruins", 2, 0, "ruin", "flooded-abbey",
     "Klasztor zalany, gdy przy budowie stawów młyńskich puszczono wodę — wieża "
     "sterczy z tafli jak palec wskazujący niebo. Światło nie tłumaczy, czemu "
     "opuszczono go tak szybko i czemu nikt nie osuszył gruntu. W bezwietrzne dni "
     "przez wodę widać dach kaplicy i coś, co lepiej zostawić pod powierzchnią."),
    ("dwor_czwartego", "Dwór Czwartego", -31, 32, "ruins", 3, 0, "ruin", "endgame-manor",
     "Spalona rezydencja rzekomego założyciela Rady — czwartego, o którym mówi się "
     "najciszej. Od pokoleń nikt nie kupuje tej ziemi, choć leży żyzna i tania. "
     "Zgliszcza nie zarosły, jakby ogień odebrał gruntowi pamięć wzrostu. Fabularny "
     "finał krainy intryg. (Opis atmosferyczny — bez questów; endgame otwiera się "
     "dopiero fabułą kampanii.)"),
    ("szubieniczne_wzgorze", "Szubieniczne Wzgórze", -15, 27, "plains", 2, 0, "ruin", "gallows-hill",
     "Wzgórze straceń Korony tuż za murami stolicy — belka po belce, sznur po sznurze, "
     "przez całą Erę Latarni. Cicho nawiedzone: nikt nie krzyczy, ale konie nie chcą "
     "tędy iść. Kto wisiał sprawiedliwie, a kto niewygodnie — wie tylko wiatr, który "
     "kołysze pustą pętlą."),
    ("wieza_heroldow", "Wieża Heroldów", -32, 34, "ruins", 2, 0, "ruin", "abandoned-archive",
     "Opuszczone archiwum rodowodów na samotnym wzgórzu — tu heroldowie spisywali, "
     "kto z kogo i kto ma prawo do czego. Wieżę zamknięto, gdy odpowiedź na jedno "
     "pytanie stała się niewygodna: kto NAPRAWDĘ ma prawo do tronu? Pergaminy gniją "
     "w kurzu, ale kilka linii wciąż da się odczytać — dla tego, kto zdąży przed "
     "innymi zainteresowanymi."),
    ("katakumby_vilnogradu", "Katakumby Vilnogradu", -22, 22, "urban", 2, 0, "ruin", "urban-dungeon",
     "Krypty, tunele przemytników i fundamenty starsze niż samo miasto — cały drugi "
     "Vilnograd pod Vilnogradem. Wejście tuż za murami stolicy, na trakcie: właz, "
     "o którym straż woli nie wiedzieć. Nocny Burmistrz trzyma tu swoje szlaki, a "
     "głębiej kamień pamięta czasy przed Koroną. Miejski farmowalny dungeon — otwarty "
     "od seedu."),
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        n_new = 0
        n_upd = 0

        # 1) Napraw zerwane linki istniejących hubów (hex → realny klucz lokacji).
        for key, q, r in RELINK:
            row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (key,)).fetchone()
            if not row:
                print(f"  ! RELINK {key} brak w DB — pomijam")
                continue
            conn.execute(
                "UPDATE game_locations SET region = ?, updated_at = datetime('now') WHERE key = ?",
                (REGION, key),
            )
            link_location_to_hex(conn, key, q, r, level=0)
            n_upd += 1
            print(f"  ~ RELINK {key} -> hex ({q},{r})")

        # 2) Rogatka Wschodnia: sub → macro + update opisu + relink.
        rkey, rq, rr, rlabel, rdesc = ROGATKA
        row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (rkey,)).fetchone()
        if row:
            conn.execute(
                "UPDATE game_locations SET label = ?, description = ?, region = ?, "
                "location_type = 'macro', location_subtype = 'customs-gate', "
                "map_icon = 'town', tier = 1, safe_for_rest = 1, updated_at = datetime('now') "
                "WHERE key = ?",
                (rlabel, rdesc, REGION, rkey),
            )
            link_location_to_hex(conn, rkey, rq, rr, level=0)
            n_upd += 1
            print(f"  ~ ROGATKA {rkey} (sub->macro) -> hex ({rq},{rr})")
        else:
            print(f"  ! ROGATKA {rkey} brak w DB — pomijam")

        # 3) Nowe lokacje makro (idempotentne po kluczu; link przez create_location).
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

        print(f"\n✓ Nowych: {n_new} · zaktualizowanych/relink: {n_upd}")
        print(f"  Makro-lokacji regionu '{REGION}': {total_macro} · z hexem: {len(linked)}")
        print("  Lokacja -> hex (wg położenia):")
        for row in linked:
            print(f"    {row['key']:26s} ({row['q']},{row['r']})")
        if orphan:
            print("  ! BEZ HEXA (do sprawdzenia):")
            for row in orphan:
                print(f"    {row['key']}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
