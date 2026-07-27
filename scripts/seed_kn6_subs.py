#!/usr/bin/env python3
"""KN-6 (#1500) — życie poza stolicą: sub-lokacje osad Koronnych Nizin.

Źródło prawdy: docs/world/regions/koronne_niziny.md §4 (Volhynia / wsie spichlerzowe /
Rogatka Wschodnia). Wzorzec: scripts/seed_vilnograd_dzielnice.py (KN-5) — ta sama
mechanika (create_location sub + auto_assign_local_hex), inne huby.

Dokłada suby do 5 istniejących makro-hubów (wszystkie z hexem na mapie Piotra —
NIE ruszamy world_hexes map_level=0):

  * Volhynia (hub kupiecki, bump tier 2):  Plac Aukcyjny + Kantor  (aukcje/karawany;
    zajazd karawan = istniejąca Gospoda Szlaku, tylko odświeżamy opis pod karawany).
  * Mühlfeld (wieś spichlerzowa, exemplar): Młyn + Folwark + Karczma.
  * Kornbrück / Ährenau (wsie spichlerzowe): Folwark + Karczma.
    → tło buntu chłopskiego w opisach folwarków i wsi (pańszczyzna, dziesięcina, poborca).
  * Rogatka Wschodnia (komora celna):       Izba Celna + Posterunek  (Berta — KN-6 obsada;
    mechanika kontroli papierów = KN-8, tu sama lokacja + posterunek).

Usługi (Usługi modal #1292/#1394) wchodzą przez keyword na label/subtype lokalnym:
  karczma → nocleg/strawa/stajnia; kuźnia → naprawa; kaplica/klasztor → Światło.
Dlatego karczmy wsi dają odpoczynek i plotki na trakcie zbożowym.

Bez limitu subów (LOCAL_MAP_THRESHOLD=2 to MINIMUM; #1212 odrzuca tylko >1 hub).
Idempotentny — można puszczać wielokrotnie.

URUCHOMIENIE (w kontenerze backendu):
    docker cp scripts/seed_kn6_subs.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_kn6_subs.py
    docker exec ai-gm-dev-backend-1 python /app/seed_kn6_subs.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.local_hex_service import (  # noqa: E402
    auto_assign_local_hex,
    get_hub_hex_id,
    get_local_hexes,
    normalize_hub_local_hexes,
)
from app.services.location_factory import LocationSource, create_location  # noqa: E402

REGION = "koronne_niziny"

# ── Odświeżenie opisów makro-hubów (bunt chłopski / funkcja kupiecka) ────────────
HUB_REFRESH = {
    "volhynia_kupiecka": dict(
        tier=2, label="Volhynia, Miasto Kupieckie", subtype="trade-city",
        desc="Skrzyżowanie czterech traktów Korony i drugie po stolicy serce handlu — "
             "tu zbiegają się szlaki z Kresów, znad Wybrzeża Łez, od Vilnogradu i z "
             "zachodu. Karawany stoją bok w bok, na Placu Aukcyjnym licytuje się "
             "wszystko: konie, zboże, towar i pogłoski. W kantorach złoto zmienia "
             "właściciela szybciej niż na wojnie. Kto handluje w Koronnych Nizinach, "
             "prędzej czy później staje na volhyńskim bruku."),
    "muhlfeld": dict(
        tier=1, label="Mühlfeld", subtype="granary-village",
        desc="Wieś spichlerzowa na złotych łanach na północ od stolicy — młyny mielą "
             "dzień i noc, folwark bierze pańszczyznę, a wozy ze zbożem ciągną do "
             "Vilnogradu bez końca. Karmi miasto i sama chudnie: dziesięcina rośnie "
             "szybciej niż plon. W karczmie mówi się półgłosem o widłach i o tym, że "
             "poborca bywa tu częściej niż ksiądz — tło buntu, o którym w salonach cisza."),
    "kornbruck": dict(
        tier=1, label="Kornbrück", subtype="granary-village",
        desc="Osada przy trakcie na wschodnim skraju łanów, gdzie zboże przekracza rzekę "
             "w drodze na targi. Spichlerze pełne, ludzie chudzi — cała nadwyżka jedzie "
             "dalej. Na folwarku pańszczyzna, w karczmie gniew: starzy pamiętają rok, "
             "gdy chłopi z widłami zawrócili wóz poborcy. Korona pamięta go dłużej."),
    "ahrenau": dict(
        tier=1, label="Ährenau", subtype="granary-village",
        desc="Wieś w sercu pól między Vilnogradem a Volhynią — samo złoto kłosów po "
             "horyzont. Najżyźniejsza ziemia krainy i najciężej opodatkowana. Folwark "
             "rośnie, chałupy się walą; w karczmie liczy się ziarna przed oddaniem "
             "dziesięciny i szepcze, że kiedyś żyło się tu dostatnio — zanim przyszli "
             "rachmistrze Korony."),
}

# ── Nowe suby: (hub_key, sub_key, label, subtype, icon, tier, safe, biome, desc) ──
SUBS = [
    # Volhynia — hub kupiecki (§4): aukcje + kantor. Zajazd karawan = Gospoda Szlaku (odśw.).
    ("volhynia_kupiecka", "volhynia_plac_aukcyjny", "Volhynia: Plac Aukcyjny",
     "auction-square", "town", 2, 1, "urban",
     "Wielki brukowany plac, na którym od świtu bije młotek licytatora. Idą pod niego "
     "karawanowe konie, całe wozy zboża, sól z południa, egzotyka z Kresów i rzeczy, "
     "których pochodzenia lepiej nie badać. Kto zna cenę, wychodzi bogatszy; kto nie — "
     "wychodzi mądrzejszy. Aukcje Volhynii wyznaczają ceny dla całej krainy."),
    ("volhynia_kupiecka", "volhynia_kantor", "Volhynia: Kantor",
     "kantor", "town", 2, 1, "urban",
     "Kantor pod arkadami targowiska — tu złoto zmienia się w papier, a papier w złoto, "
     "i tu kupiec zostawia majątek, zanim ruszy dalej traktem. Rachmistrze liczą w "
     "ciszy, strażnik stoi przy drzwiach, a księgi pamiętają każdy dług. (Weksle "
     "kantorów — pełna mechanika w KN-8; tu sam kantor i wymiana.)"),
    # Mühlfeld — exemplar wsi spichlerzowej: młyn + folwark + karczma.
    ("muhlfeld", "muhlfeld_mlyn", "Mühlfeld: Młyn",
     "mill", "town", 1, 1, "plains",
     "Wielki młyn wodny nad odnogą rzeki — koło obraca się dzień i noc, kamienie "
     "mielą ziarno całej okolicy. Młynarz płaci Koronie miarkę od każdego korca i "
     "narzeka ciszej niż turkocze koło. Worki mąki jadą do Vilnogradu; chleb, który z "
     "nich wyjdzie, rzadko wraca na wieś."),
    ("muhlfeld", "muhlfeld_folwark", "Mühlfeld: Folwark",
     "manor-farm", "town", 1, 1, "plains",
     "Pański folwark na skraju łanów — dwór ekonoma, stodoły i pola, na których chłopi "
     "odrabiają pańszczyznę od świtu do zmroku. Tu najgęściej wisi w powietrzu bunt: "
     "dziesięcina rośnie, plon zostaje na dole tabeli, a ekonom liczy dni pracy "
     "dokładniej niż Korona liczy poddanych. Iskra czeka tylko na jeden zły rok."),
    ("muhlfeld", "muhlfeld_karczma", "Mühlfeld: Karczma Pod Kołem",
     "karczma", "town", 1, 1, "plains",
     "Niska karczma przy młyńskiej drodze — nocleg, gorąca strawa i piwo dla furmanów "
     "wiozących zboże. Przy dłuższym stole zawsze ktoś półgłosem liczy krzywdy: "
     "pańszczyznę, myto, poborcę. Karczmarz udaje, że nie słyszy, i dolewa. Dobre "
     "miejsce, by złapać oddech i wieści z całych łanów."),
    # Kornbrück — folwark + karczma.
    ("kornbruck", "kornbruck_folwark", "Kornbrück: Folwark Nadrzeczny",
     "manor-farm", "town", 1, 1, "plains",
     "Folwark tuż nad brodem, przez który zboże Kornbrück przechodzi na drugi brzeg. "
     "Pańszczyzna ciężka, ekonom twardy, a pamięć długa: to stąd wyszli chłopi, którzy "
     "raz zawrócili wóz poborcy widłami. Od tamtej wiosny na folwarku bywa więcej "
     "strażników niż parobków."),
    ("kornbruck", "kornbruck_karczma", "Kornbrück: Karczma Nad Brodem",
     "karczma", "town", 1, 1, "plains",
     "Karczma nad rzecznym brodem — ostatni dach z prawdziwym łóżkiem, zanim trakt "
     "wejdzie w łany. Zatrzymują się tu furmani, przemytnicy soli i ci, co wolą "
     "przeczekać kontrolę na rogatce. Nocleg, strawa, konował dla konia — i cichy gwar "
     "o tym, komu w krainie coraz ciaśniej."),
    # Ährenau — folwark + karczma.
    ("ahrenau", "ahrenau_folwark", "Ährenau: Wielki Folwark",
     "manor-farm", "town", 1, 1, "plains",
     "Największy folwark krainy — na najżyźniejszej ziemi, więc i pańszczyzna tu "
     "najcięższa. Dwór ekonoma rośnie w oczach, chałupy poddanych walą się w błoto. "
     "Starzy mówią, że kiedyś była to wolna wieś; dziś liczy się każde ziarno przed "
     "dziesięciną, a gniew dojrzewa razem ze zbożem."),
    ("ahrenau", "ahrenau_karczma", "Ährenau: Karczma Pod Snopem",
     "karczma", "town", 1, 1, "plains",
     "Karczma w sercu pól — pełna w dni targowe, cicha i gniewna po żniwach, gdy "
     "wozy odjadą do Vilnogradu, a stodoły chłopów zostaną puste. Nocleg i strawa dla "
     "wędrowca; dla miejscowych — jedyne miejsce, gdzie wolno powiedzieć głośno to, "
     "czego na folwarku nie wolno nawet szeptać."),
    # Rogatka Wschodnia — izba celna (Berta) + posterunek.
    ("rogatka_wschodnia", "rogatka_izba_celna", "Rogatka Wschodnia: Izba Celna",
     "customs-house", "town", 1, 1, "plains",
     "Ciasna izba przy szlabanie, w której Korona czyta przybysza, zanim wpuści go na "
     "swoje trakty. Za stołem Berta Twarda Pieczęć — glejt, myto, papiery. List żelazny "
     "otwiera drzwi bez pytań; fałszywe papiery to test i ryzyko. (Pełna mechanika "
     "kontroli papierów — KN-8; tu izba i pieczęć.)"),
    ("rogatka_wschodnia", "rogatka_posterunek", "Rogatka Wschodnia: Posterunek",
     "guardpost", "town", 1, 1, "plains",
     "Drewniany posterunek straży celnej przy trakcie z Kresów — kilku zbrojnych, "
     "koniowiąz, areszt na jedną noc i szlaban, który podnosi się dopiero po pieczęci "
     "z izby. Tędy przechodzi każdy, kto wchodzi do Koronnych Nizin od wschodu; kto "
     "próbuje ominąć rogatkę bokiem, prędzej trafi na patrol niż na wolność."),
]

# huby, którym po dołożeniu subów przebudowujemy mapę lokalną (≥2 suby).
LOCAL_MAP_HUBS = ["volhynia_kupiecka", "muhlfeld", "kornbruck", "ahrenau", "rogatka_wschodnia"]

_REFRESH_SUB = """
UPDATE game_locations SET
  label=?, description=?, region=?, map_icon=?, tier=?,
  location_subtype=?, safe_for_rest=?, is_active=1, updated_at=datetime('now')
WHERE key=?
"""


def upsert_sub(conn, hub_key, hub_id, key, label, subtype, icon, tier, safe, biome, desc):
    res = create_location(
        conn,
        key=key, label=label, source=LocationSource.SEED,
        description=desc, location_type="sub",
        parent_key=hub_key, parent_id=hub_id, region=REGION,
        map_icon=icon, tier=tier, biome=biome,
        location_subtype=subtype, safe_for_rest=safe,
        visible_before_visit=0, canonical=True, commit=False,
    )
    if not res["created"]:
        conn.execute(_REFRESH_SUB, (label, desc, REGION, icon, tier, subtype, safe, key))
        conn.execute(
            "UPDATE game_locations SET parent_key=?, parent_id=? WHERE key=?",
            (hub_key, hub_id, key),
        )
    return res["created"]


def reattach_local_hexes(conn, hub_key, sub_keys):
    hub_hex_id = get_hub_hex_id(conn, hub_key)
    if hub_hex_id is None or not sub_keys:
        return 0
    marks = ",".join("?" * len(sub_keys))
    cur = conn.execute(
        f"UPDATE world_hexes SET parent_hex_id=? "
        f"WHERE map_level=1 AND location_key IN ({marks}) "
        f"AND (parent_hex_id IS NULL OR parent_hex_id != ?)",
        (hub_hex_id, *sub_keys, hub_hex_id),
    )
    return cur.rowcount or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    hub_ids = {}
    for hub_key in {s[0] for s in SUBS} | set(HUB_REFRESH):
        row = conn.execute("SELECT id FROM game_locations WHERE key=?", (hub_key,)).fetchone()
        if row is None:
            print(f"  ✗ brak huba {hub_key} — najpierw seed makro (KN-4)")
            return 1
        hub_ids[hub_key] = row["id"]

    # 1) odśwież opisy/tier makro-hubów
    for k, spec in HUB_REFRESH.items():
        conn.execute(
            "UPDATE game_locations SET label=?, description=?, region=?, tier=?, "
            "location_subtype=?, is_active=1, updated_at=datetime('now') WHERE key=?",
            (spec["label"], spec["desc"], REGION, spec["tier"], spec["subtype"], k),
        )
        print(f"  ~ hub {k} (tier={spec['tier']})")

    # 1b) Gospoda Szlaku = zajazd karawan (odświeżenie opisu, jeśli istnieje)
    if conn.execute("SELECT 1 FROM game_locations WHERE key='volhynia_gospoda_szlaku'").fetchone():
        conn.execute(
            "UPDATE game_locations SET description=?, location_subtype='zajazd', "
            "updated_at=datetime('now') WHERE key='volhynia_gospoda_szlaku'",
            ("Wielki zajazd karawan przy zbiegu czterech traktów — stajnie na setki "
             "koni, izby dla kupców i gwar w dwudziestu językach. Tu karawany łączą "
             "się przed drogą i dzielą po niej, tu najeci strażnicy szukają kolejnego "
             "szlaku. Nocleg, strawa, stajnia i wieści z całej Korony pod jednym dachem.",),
        )
        print("  ~ volhynia_gospoda_szlaku (zajazd karawan)")

    # 2) nowe suby
    for hub_key, key, label, subtype, icon, tier, safe, biome, desc in SUBS:
        created = upsert_sub(conn, hub_key, hub_ids[hub_key], key, label, subtype,
                             icon, tier, safe, biome, desc)
        print(f"  {'+' if created else '~'} {key:28s} ({hub_key})")
    conn.commit()

    # 3) przepięcie osieroconych lokalnych hexów + mapa lokalna dla hubów ≥2 suby
    for hub_key in LOCAL_MAP_HUBS:
        subs = [r["key"] for r in conn.execute(
            "SELECT key FROM game_locations WHERE parent_key=? AND is_active=1", (hub_key,))]
        if len(subs) < 2:
            print(f"  · {hub_key}: {len(subs)} sub — brak mapy lokalnej (próg 2)")
            continue
        reattach_local_hexes(conn, hub_key, subs)
        auto_assign_local_hex(conn, subs[0], hub_key)
        normalize_hub_local_hexes(conn, hub_key)
        conn.commit()
        local = get_local_hexes(conn, hub_key)
        print(f"  mapa lokalna {hub_key}: {len(local)} hexów map_level=1")

    # 4) kontrola
    problems = []
    for hub_key, key, *_ in SUBS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (key,)).fetchone():
            problems.append(f"sub {key} nieaktywny")
    for hub_key in LOCAL_MAP_HUBS:
        orphan = conn.execute(
            "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1 "
            "AND key NOT IN (SELECT location_key FROM world_hexes WHERE map_level=1 "
            "AND location_key IS NOT NULL)", (hub_key,)).fetchone()["c"]
        n = conn.execute("SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1",
                         (hub_key,)).fetchone()["c"]
        if n >= 2 and orphan:
            problems.append(f"{hub_key}: {orphan} subów bez hexa lokalnego")

    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY: " + "; ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
