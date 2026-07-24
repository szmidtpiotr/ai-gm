#!/usr/bin/env python3
"""CB-5 (#1489/#1490) — obsada Czarnoboru: 2 frakcje elfów + 8 NPC-ikon + Erethil.

Źródło prawdy: docs/world/regions/czarnobor.md §8 (obsada). Wzorzec:
scripts/seed_siwe_granie_obsada.py (SG-6) — ta sama mechanika, inna kraina.

Dlaczego to ma znaczenie dla gry (read-path silnika):
  turn_pipeline → world_service.build_available_content_index() wstrzykuje do LLM
  blok "[AVAILABLE CONTENT]" z `location_npc_assignments`. Podpięta lokacja =
  narrator przedstawia KANONICZNĄ postać zamiast wymyślać zastępczą.
  `npcs.faction_key` czyta reputacja per-frakcja (#1103) → ceny w sklepie.

Erethil (wygnaniec, §8) dostaje WŁASNĄ lokację-obóz na skraju boru (macro, hex
(60,-24) — wolny forest z CB-3, na północnym skraju kniei), bo mieszka poza osadą.
Tworzona przez create_location (#1526 — jedne drzwi).

Idempotentny:
  - frakcje/NPC: INSERT OR IGNORE po kluczu (nie nadpisuje ręcznych zmian),
  - przypisania: INSERT OR IGNORE po UNIQUE(location_key, npc_key),
  - `game_locations.npc_keys` (JSON) przeliczany z tabeli przypisań.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_czarnobor_obsada.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_obsada.py
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_obsada.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

REGION = "czarnobor"

# ── Erethil mieszka poza osadą — własna lokacja-obóz na skraju boru (macro) ────
ERETHIL_CAMP = dict(
    key="obozowisko_erethila", label="Obozowisko Erethila",
    hex=(60, -24), biome="forest", tier=2, safe=1,
    icon="wilderness", subtype="hermit-camp",
    desc="Samotny szałas wygnańca na północnym skraju kniei, tam gdzie stróżowe "
         "drzewa milkną najgęściej. Erethil rozbił się z dala od Szeptu Koron — "
         "Krąg go nie chce, a on Kręgu. Kto szuka wieści o mrocznych elfach, "
         "trafia tu, bo nikt inny nie mówi o nich głośno.",
)

# ── Frakcje elfów (lore §3 — oś napięcia zamknięcie↔otwarcie; type 'order') ────
FACTIONS = [
    ("krag_starszych", "Krąg Starszych", "order",
     "Starszyzna Szeptu Koron. Strażnicy strojenia: przetrwać przez cierpliwość, "
     "zamknąć bór i śpiewać wardy dalej, aż ucichnie to, co pęka pod korzeniami."),
    ("zwiadowcy_boru", "Zwiadowcy Boru", "order",
     "Młodsze pokolenie strażników. Uważają, że samo strojenie już nie wystarcza — "
     "trzeba otworzyć bór i szukać przyczyny gaśnięcia drzew na zewnątrz."),
]

# ── 8 NPC-ikon (lore §8 — imiona i role WPROST z rozdziału) ────────────────────
NPCS = [
    # Elfy Szeptu Koron
    dict(key="nimriel_starsza", label="Nimriel, Starsza Kręgu", npc_type="quest_giver",
         faction="krag_starszych", shop=0, quest=1, crafter=None,
         desc="Twarz zamknięcia — najstarsza głos Kręgu Starszych. Pamięta bór, gdy "
              "jeszcze cały śpiewał, i wierzy, że ratunkiem jest cierpliwość, nie "
              "wyprawa. Zamyka ścieżki, których młodsi chcieliby spróbować.",
         prompt="Powolna, dostojna, waży każde słowo jak strojenie wardu. Nie zabrania "
                "wprost — tłumaczy, dlaczego bór milknie, gdy się go szarpie. Zleci "
                "zadanie służące ZAMKNIĘCIU boru i nigdy nie przyzna, że sama się boi, "
                "iż strojenie już nie działa."),
    dict(key="cathel_zwiadowca", label="Cathel, przywódca zwiadowców", npc_type="quest_giver",
         faction="zwiadowcy_boru", shop=1, quest=1, crafter=None,
         desc="Twarz otwarcia — prowadzi zwiadowców i handel wymienny z tym, co bór "
              "rodzi. To on wychodzi poza knieję i wraca ze skórami, wieściami i "
              "pytaniami, których Krąg woli nie zadawać. Werbuje do swojej wizji: "
              "szukać przyczyny gaśnięcia na zewnątrz.",
         prompt="Bezpośredni, żywy, mówi „musimy” zanim Krąg się zgodzi. Przy Targu "
                "Wymiennym targuje się uczciwie, ale między zdaniami sonduje, czy "
                "rozmówca stanie po stronie otwarcia. Zleca zadania odwrotne do "
                "Nimriel — wyprawy poza bór, ku milczącym drzewom i dalej."),
    dict(key="aerlin_stroicielka", label="Aerlin, mistrzyni strojenia", npc_type="quest_giver",
         faction="krag_starszych", shop=0, quest=1, crafter=None,
         desc="Opiekunka wardów i najczulsze ucho w borze — słyszy, które stróżowe "
              "drzewo zaczyna milknąć, zanim pień sczernieje. Uczy młodych w "
              "Pieśniarni i wysyła zwiadowców tam, gdzie pieśń się rwie.",
         prompt="Skupiona, cicha, mówi obrazami dźwięku i ciszy. Poda dokładnie, które "
                "drzewo gaśnie i jak daleko — a potem poprosi, by ktoś tam poszedł i "
                "sprawdził, czego ona sama usłyszeć już nie potrafi. Ponad spór "
                "zamknięcie↔otwarcie przedkłada ratowanie konkretnego wardu."),
    dict(key="sylvar_lukmistrz", label="Sylvar, łukmistrz", npc_type="merchant",
         faction="zwiadowcy_boru", shop=1, quest=0, crafter="bowyer",
         desc="Łukmistrz Łukodzielni — gnie cis, kręci cięciwy, pierzy strzały i "
              "naprawia sprzęt lepiej niż ktokolwiek na skraju kniei. O drewnie boru "
              "wie tyle, że pozna wiek stróżowego drzewa po jednym wiórze.",
         prompt="Małomówny przy pracy, rozgadany o łukach. Ocenia człowieka po tym, jak "
                "trzyma broń. Za dobry cis weźmie uczciwie, tandetnym naciągiem obrazi "
                "się bardziej niż obelgą. Naprawi wszystko, co da się nagiąć."),
    # Ludzie skraju boru
    dict(key="bartel_kupiec", label="Bartel, kupiec z Ostępu", npc_type="merchant",
         faction=None, shop=1, quest=0, crafter=None,
         desc="Kupiec z Kresów, gospodarz kramów Ostępu Granicznego — jedynego stałego "
              "okna handlu elfy↔ludzie. Wozi tu towary ludzkie, dziegieć i futra, a "
              "wywozi to, co bór wypuści. Zna cenę wszystkiego po obu stronach granicy.",
         prompt="Rzeczowy, gadatliwy, twardy w targu, ale nie oszukuje: reputacja u elfów "
                "jest warta więcej niż jeden dobry interes. Chętnie wymienia wieści z "
                "Kresów za to, co się dzieje w głębi boru."),
    dict(key="hagen_starosta", label="Hagen, starosta drwali", npc_type="quest_giver",
         faction=None, shop=0, quest=1, crafter=None,
         desc="Starosta Obozu Drwali na zachodnim skraju — antagonista bez złej woli. "
              "Ma rodziny do wykarmienia i las do wycięcia, a że czasem pada stróżowe "
              "drzewo, to dla niego pech, nie świętokradztwo. Dla elfów wróg, dla "
              "swoich — człowiek, który daje chleb.",
         prompt="Twardy, zmęczony, mówi o robocie i o gębach do wyżywienia. Nie czuje "
                "się winny — pyta rozmówcę, czy jego dzieci mają głodować, żeby drzewo "
                "postało dłużej. Zleci zadania drwalskie sprzeczne z interesem elfów, "
                "ale nigdy z okrucieństwa."),
    dict(key="wolfram_lowca", label="Wolfram, łowca wilków", npc_type="neutral",
         faction=None, shop=0, quest=1, crafter=None,
         desc="Sezonowy łowca wilków z Kresów, gospodarz Stanicy Wilczej na stepie. "
              "Zna każdą watahę po głosie i czyta step jak elfy czytają bór. Futra to "
              "jego chleb, a wilki — jego całe życie i cała rozmowa.",
         prompt="Szorstki, oszczędny w słowach, ożywia się tylko przy wilkach. Da "
                "robotę łowiecką i wskaże drogę przez step lepiej niż każda mapa. "
                "O borze mówi z dystansem — to nie jego świat, on woli otwartą trawę."),
    dict(key="erethil_wygnaniec", label="Erethil, wygnaniec", npc_type="quest_giver",
         faction=None, shop=0, quest=1, crafter=None,
         desc="Elf wygnany na skraj boru — szary informator o mrocznych elfach. Krąg "
              "go nie chce, bo mówi głośno o tym, o czym oni milczą: gdzie odeszli ci, "
              "co zaczęli rozdzierać pęknięcia. Mieszka sam, a wie więcej niż cała "
              "Pieśniarnia razem wzięta.",
         prompt="Gorzki, przenikliwy, mówi półsłówkami i sprawdza, ile rozmówca już "
                "wie. Nie ufa nikomu z Kręgu, otwiera się przed tym, kto potraktuje "
                "mroczne elfy jak fakt, nie plotkę. O swoim wygnaniu nie mówi wprost — "
                "kończy zawsze tym, że bór milknie nie bez powodu."),
]

# ── Przypisania NPC → lokacja (hub = cała osada, sub = konkretna pinezka) ──────
NPC_ASSIGNMENTS = [
    # Poziom huba: elfy Szeptu Koron jako mieszkańcy osady
    ("szept_koron", "nimriel_starsza", "resident"),
    ("szept_koron", "cathel_zwiadowca", "resident"),
    ("szept_koron", "aerlin_stroicielka", "resident"),
    ("szept_koron", "sylvar_lukmistrz", "resident"),
    # Sub-lokacje Szeptu Koron
    ("szept_krag_starszych", "nimriel_starsza", "resident"),
    ("szept_krag_starszych", "cathel_zwiadowca", "visitor"),   # oś napięcia §3
    ("szept_piesniarnia", "aerlin_stroicielka", "resident"),
    ("szept_lukodzielnia", "sylvar_lukmistrz", "resident"),
    ("szept_targ_wymienny", "cathel_zwiadowca", "resident"),   # handel wymienny
    # Ludzie skraju — przy swoich lokacjach makro (CB-4)
    ("ostep_graniczny", "bartel_kupiec", "resident"),
    ("oboz_drwali", "hagen_starosta", "resident"),
    ("stanica_wilcza", "wolfram_lowca", "resident"),
    # Wygnaniec przy własnym obozie
    ("obozowisko_erethila", "erethil_wygnaniec", "resident"),
]


def ensure_erethil_camp(conn):
    from app.services.location_factory import LocationSource, create_location
    q, r = ERETHIL_CAMP["hex"]
    if conn.execute("SELECT 1 FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)).fetchone() is None:
        print(f"  ✗ brak hexa ({q},{r}) dla obozu Erethila — sprawdź seed krainy")
        return False
    res = create_location(
        conn,
        key=ERETHIL_CAMP["key"], label=ERETHIL_CAMP["label"], source=LocationSource.SEED,
        description=ERETHIL_CAMP["desc"], location_type="macro",
        biome=ERETHIL_CAMP["biome"], region=REGION, tier=ERETHIL_CAMP["tier"],
        safe_for_rest=ERETHIL_CAMP["safe"], map_icon=ERETHIL_CAMP["icon"],
        location_subtype=ERETHIL_CAMP["subtype"], hex_q=q, hex_r=r, hex_level=0,
        commit=False,
    )
    if not res["created"]:
        conn.execute(
            "UPDATE game_locations SET label=?, description=?, region=?, "
            "updated_at=datetime('now') WHERE key=?",
            (ERETHIL_CAMP["label"], ERETHIL_CAMP["desc"], REGION, ERETHIL_CAMP["key"]),
        )
    print(f"  Erethil obóz {ERETHIL_CAMP['key']} @ ({q},{r}) {'NEW' if res['created'] else 'refresh'}")
    return True


def apply(conn):
    n_fac = n_npc = n_na = 0
    for key, name, ftype, desc in FACTIONS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_factions (key, name, faction_type, description, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (key, name, ftype, desc))
        n_fac += cur.rowcount or 0

    for n in NPCS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO npcs
                 (key, label, npc_type, description, personality_json, personality_prompt,
                  is_shop, shop_inventory_json, is_quest_giver, is_crafter, crafter_type,
                  faction_key, is_active, review_status, keyword_triggers)
               VALUES (?, ?, ?, ?, '{}', ?, ?, '[]', ?, ?, ?, ?, 1, 'permanent', '[]')""",
            (n["key"], n["label"], n["npc_type"], n["desc"], n["prompt"],
             int(n["shop"]), int(n["quest"]), int(bool(n["crafter"])), n["crafter"],
             n["faction"]))
        n_npc += cur.rowcount or 0

    for loc, npc, atype in NPC_ASSIGNMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
            "VALUES (?, ?, ?, 1)", (loc, npc, atype))
        n_na += cur.rowcount or 0

    touched = {a[0] for a in NPC_ASSIGNMENTS}
    for loc in sorted(touched):
        npc_keys = [r[0] for r in conn.execute(
            "SELECT npc_key FROM location_npc_assignments WHERE location_key=? AND is_active=1 ORDER BY npc_key", (loc,))]
        conn.execute("UPDATE game_locations SET npc_keys=? WHERE key=?",
                     (json.dumps(npc_keys, ensure_ascii=False), loc))
    conn.commit()
    return {"factions": n_fac, "npcs": n_npc, "npc_assignments": n_na}


def verify(conn):
    problems = []
    for loc, npc, _ in NPC_ASSIGNMENTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc,)).fetchone():
            problems.append(f"przypisanie NPC do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc,)).fetchone():
            problems.append(f"nieistniejący NPC: {npc}")
    for n in NPCS:
        if n["faction"] and not conn.execute(
                "SELECT 1 FROM game_config_factions WHERE key=?", (n["faction"],)).fetchone():
            problems.append(f"{n['key']}: brak frakcji {n['faction']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    ensure_erethil_camp(conn)
    conn.commit()

    res = apply(conn)
    print(f"  frakcje elfów nowe:     {res['factions']}")
    print(f"  NPC-ikony nowe:         {res['npcs']}")
    print(f"  przypisania NPC nowe:   {res['npc_assignments']}")

    rows = conn.execute("""
        SELECT gl.label AS loc, n.label AS npc, a.assignment_type
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs n ON n.key = a.npc_key
        WHERE gl.region = 'czarnobor' AND a.is_active = 1
        ORDER BY gl.label, n.label""").fetchall()
    print(f"\n  obsada krainy ({len(rows)} przypisań):")
    for r in rows:
        print(f"    {r['loc']:38s} ← {r['npc']} ({r['assignment_type']})")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
