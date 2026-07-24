#!/usr/bin/env python3
"""CB-4 — seed Czarnoboru: lokacje makro (osady, POI, miejsca zapomniane).

Zgodne z docs/world/regions/czarnobor.md §4 (katalog) + §5 (pasy terenu) + §7
(Czarne Serce). BEZ sub-lokacji Szeptu Koron — te idą w CB-5.

Wiązanie z mapą ZAWSZE przez link_location_to_hex (kanon = world_hexes.location_key);
GOTCHA #1305: goły INSERT bez hexa czyści reconcile. create_location robi link
wewnętrznie (patrz location_factory). Idempotentne — bezpieczne do re-runu.

Uruchamiać W KONTENERZE (DB_PATH=/data/ai_gm.db):
    docker cp scripts/seed_czarnobor_locations.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_czarnobor_locations.py

Po seedzie: snapshot_content.py (game_locations.json) + snapshot_world_map.py
--region czarnobor (region_czarnobor.json) → commit (content-as-code #1202).
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.location_factory import LocationSource, create_location  # noqa: E402
from app.services.hex_location_link import link_location_to_hex  # noqa: E402

DB_PATH = "/data/ai_gm.db"
REGION = "czarnobor"

# ── Istniejące POI (z pliku seedu) — zostają na hexach z CB-3; poprawiamy opisy
#    i etykiety wg lore §4. (key, hex_q, hex_r, new_label, new_description)
POI_UPDATES = [
    ("bor_zmarlych", 69, -17, "Bór Zmarłych",
     "Pierwszy wygasły okręg sieci stróżowych drzew — pnie sczerniały jak smoła, "
     "gdy wardy zgasły. Czarny las wciąż rozrasta się ku Kresom. Żywi tu nie nocują; "
     "pod korzeniami coś pamięta."),
    ("las_czarnych_drzew", 61, -5, "Knieja Czarnych Drzew",
     "Gęsta knieja smolistych, wygasłych stróżowych drzew na skraju Boru Zmarłych. "
     "Liście szepczą imiona, a ścieżki lubią zawracać wędrowca w głąb."),
    ("trzesawiska_mgiel", 70, 4, "Trzęsawiska Mgieł",
     "Bezkresne bagna spowite białą mgłą na południu krainy — próg ku Martwym "
     "Pustkowiom. Kto zboczy z grobli, ten karmi utopce."),
    ("bagienna_knieja", 80, -8, "Bagienna Knieja",
     "Zatopiony las na palach, gdzie drzewa rosną wprost z czarnej wody. Domena "
     "smolarzy i komarów; mgła nie podnosi się nawet w południe."),
    ("step_wilkow", 87, -32, "Step Wilków",
     "Trawiasty kraniec kontynentu na wschodzie. Watahy wyją po zmroku, a sezonowi "
     "łowcy z Kresów ciągną tu po futra."),
]

# ── Nowe lokacje makro.
#    (key, label, hex_q, hex_r, biome, tier, safe, map_icon, subtype, description)
NEW_LOCATIONS = [
    # Zasiedlone (§4) — pasy §5: zachód/centrum/step/bagno.
    ("ostep_graniczny", "Ostęp Graniczny", 74, 8, "rural", 1, 1, "town", "trade-post",
     "Jedyne stałe okno wymiany elfy↔ludzie na zachodnim skraju boru. Kupcy z Kresów "
     "rozkładają tu kramy; dalej w las obcych już się nie wpuszcza. Handel prowadzi Bartel."),
    ("oboz_drwali", "Obóz Drwali", 55, -7, "forest", 2, 1, "town", "lumber-camp",
     "Ludzki obóz na zachodnim skraju — starosta Hagen i rodziny, które trzeba "
     "wykarmić. Siekiery jedzą las, czasem ścinając stróżowe drzewo: dla elfów "
     "świętokradztwo, dla drwali chleb."),
    ("smolarnia_na_palach", "Smolarnia na Palach", 73, 6, "swamp", 2, 1, "town", "tar-camp",
     "Osada smolarzy wzniesiona na palach nad bagnem. Pędzą tu dziegieć czarnodrzewny — "
     "smród żywicy niesie się na mile. Filar ekonomii krainy obok futer i drewna."),
    ("stanica_wilcza", "Stanica Wilcza", 85, -28, "plains", 2, 1, "town", "hunter-camp",
     "Sezonowa stanica łowców wilków z Kresów, wbita w step. Futra, wnyki i psy; "
     "Wolfram zna każdą watahę po głosie."),
    ("szept_koron", "Szept Koron", 74, -12, "forest", 1, 1, "forest", "elven-hub",
     "Hub elfów w koronach starych drzew — ludzkie tłumaczenie niezapisanej elfickiej "
     "nazwy. Krąg Starszych stroi gasnące wardy, a Gościnne Drzewo jako jedyne przyjmuje "
     "obcych na nocleg. (Wnętrze osady — sub-lokacje — dobuduje kolejny etap.)"),

    # Zapomniane (§4) — rozsiane wg pasów.
    ("milczace_drzewo_1", "Milczące Drzewo — Smolny Konar", 62, -11, "forest", 2, 0, "forest", "extinct-warden",
     "Wygasłe stróżowe drzewo; pień czarny jak smoła, korona martwa. Elfy pamiętają "
     "jego pieśń — dziś milczy. Coś pod korzeniami czeka na tego, kto zapyta."),
    ("milczace_drzewo_2", "Milczące Drzewo — Rozdarta Pieśń", 67, -3, "forest", 2, 0, "forest", "extinct-warden",
     "Kolejny zgasły ward w głębi kniei. Kora spękana jak po ciosie; zwierzyna omija "
     "je łukiem. Mini-trop dla tych, co badają, czemu bór milknie."),
    ("milczace_drzewo_3", "Milczące Drzewo — Siwy Strażnik", 58, -19, "forest", 3, 0, "forest", "extinct-warden",
     "Najbardziej na północ wysunięte z martwych drzew. Zgasło niedawno — żywica jeszcze "
     "cieknie czarnymi łzami. Aerlin wysyła tu zwiadowców."),
    ("stare_gniazdo", "Stare Gniazdo", 66, -15, "forest", 3, 0, "ruin", "abandoned-elf-nest",
     "Pierwsza osada elfów, dziś opuszczona w sercu Boru Zmarłych — porzucona, gdy "
     "drzewa wokół sczerniały. Puste pomosty w koronach, zarośnięte ścieżki. Loch questowy."),
    ("utopiona_wies", "Utopiona Wieś", 76, 0, "swamp", 3, 0, "ruin", "drowned-village",
     "Ludzka wieś pochłonięta przez trzęsawisko — dachy sterczą z czarnej wody. Nocą "
     "świecą w niej ślepia utopców. Farmowalny loch."),
    ("polana_schizmy", "Polana Schizmy", 65, -9, "forest", 3, 0, "wilderness", "cursed-clearing",
     "Miejsce rozłamu, gdzie część elfów wybrała rozdzieranie pęknięć zamiast strojenia. "
     "Trawa rośnie tu czarna; elfy tam nie chodzą."),
    ("kurhan_wilczego_krola", "Kurhan Wilczego Króla", 90, -27, "plains", 3, 0, "tomb", "barrow",
     "Przedelficki kurhan na stepie. Wilki okrążają go nocami, lecz nigdy nie wchodzą "
     "do środka. Co leży pod kopcem — nikt żywy nie sprawdził."),
    ("zarosniety_trakt", "Zarośnięty Trakt", 74, 12, "forest", 2, 0, "wilderness", "overgrown-road",
     "Stary imperialny gościniec biegnący na południe ku Pustkowiom, zjedzony przez las. "
     "Kamienie milowe tkwią w pniach. Czemu Imperium porzuciło tę drogę?"),
    ("czarne_serce", "Czarne Serce", 65, -17, "forest", 5, 0, "ruin", "myth-site",
     "Najgłębiej w Borze Zmarłych rosło Pradrzewo — kotwica całej sieci wardów. Gdy "
     "zgasło, sczerniał cały okręg. Pod martwymi korzeniami zieje największe pęknięcie "
     "Rdzenia w krainie. Bór nie wpuszcza: ścieżki zawracają, strach narasta. "
     "(Wejście zamknięte narracyjnie — bez questów.)"),
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        n_new = 0
        n_upd = 0

        # 1) POI — update opisu/etykiety + (re)link do hexa z CB-3.
        for key, q, r, label, desc in POI_UPDATES:
            row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (key,)).fetchone()
            if not row:
                print(f"  ! POI {key} brak w DB — pomijam update (spodziewany był z seedu)")
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
                # istniał — odśwież opis/etykietę i upewnij się o regionie + hexie
                conn.execute(
                    "UPDATE game_locations SET label = ?, description = ?, region = ?, "
                    "updated_at = datetime('now') WHERE key = ?",
                    (label, desc, REGION, key),
                )
                link_location_to_hex(conn, key, q, r, level=0)
                print(f"  ~ {key} (istniał) -> hex ({q},{r})")

        conn.commit()

        # Weryfikacja: ile lokacji czarnobor ma hex (kanon world_hexes.location_key).
        linked = conn.execute(
            "SELECT gl.key, wh.q, wh.r FROM game_locations gl "
            "JOIN world_hexes wh ON wh.location_key = gl.key AND wh.map_level = 0 "
            "WHERE gl.region = ? AND gl.location_type = 'macro' ORDER BY gl.key",
            (REGION,),
        ).fetchall()
        total_macro = conn.execute(
            "SELECT COUNT(*) FROM game_locations WHERE region = ? AND location_type = 'macro'",
            (REGION,),
        ).fetchone()[0]

        print(f"\n✓ Nowych: {n_new} · zaktualizowanych POI: {n_upd}")
        print(f"  Makro-lokacji regionu '{REGION}': {total_macro} · z hexem: {len(linked)}")
        print("  Lokacja -> hex:")
        for row in linked:
            print(f"    {row['key']:28s} ({row['q']},{row['r']})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
