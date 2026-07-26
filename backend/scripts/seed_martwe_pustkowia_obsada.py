#!/usr/bin/env python3
"""MP-5 (#1494) — obsada Martwych Pustkowi: 3 frakcje + 8 NPC-ikon + przypisania.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §7 (obsada), §3 (napięcia).
Wzorzec: scripts/seed_czarnobor_obsada.py (CB-5) — ta sama mechanika, inna kraina.

Dlaczego to ma znaczenie dla gry (read-path silnika):
  turn_pipeline → world_service.build_available_content_index() wstrzykuje do LLM
  blok "[AVAILABLE CONTENT]" z `location_npc_assignments`. Podpięta lokacja =
  narrator przedstawia KANONICZNĄ postać zamiast wymyślać zastępczą.
  `npcs.faction_key` czyta reputacja per-frakcja (#1103) → ceny w sklepie.

UWAGA RASA (#1475): Piętnowani mają POPIELATĄ SKÓRĘ i BLADE OCZY — wpisane wprost
w opisy czterech NPC Piętnowanych (spójność wizualna z rasą, którą kraina seeduje).

Idempotentny:
  - frakcje/NPC: INSERT OR IGNORE po kluczu (nie nadpisuje ręcznych zmian),
  - przypisania: INSERT OR IGNORE po UNIQUE(location_key, npc_key),
  - `game_locations.npc_keys` (JSON) przeliczany z tabeli przypisań.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_martwe_pustkowia_obsada.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_obsada.py
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_obsada.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "martwe_pustkowia"

# ── Frakcje (lore §3 — trzy siły ciągnące enklawę) ────────────────────────────
FACTIONS = [
    ("starsi_solnego_progu", "Starsi Solnego Progu", "clan",
     "Rada Piętnowanych — twarz UKRYCIA. Jedyni, którzy umieją żyć na pustkowiach, "
     "i wolą, by świat o tym zapomniał: otwarcie ściąga oko Światła i kultów. Stawka "
     "to przetrwanie tożsamości pod cudzym okiem."),
    ("przewodnicy_ruin", "Przewodnicy Ruin", "clan",
     "Młodsi Piętnowani — twarz OTWARCIA. Przewodnictwo po martwych miastach = złoto, "
     "a złoto to broń przeciw głodowi i Światłu. Uważają, że ukrywanie się dłużej nie "
     "wystarcza — trzeba handlować z obcymi, póki się da."),
    ("misja_swiatla", "Misja Światła", "order",
     "Placówka Świątyni na skraju pustkowi. Jedni niosą pomoc, inni obserwują, czy "
     "piętno to dar, czy skażenie. Trzecia siła ciągnąca enklawę — ku Światłu."),
]

# ── 8 NPC-ikon (lore §7 — imiona i role WPROST z rozdziału) ───────────────────
# Piętnowani: opisy MUSZĄ nieść popielatą skórę + blade oczy (#1475).
NPCS = [
    # Piętnowani
    dict(key="raszid_starszy", label="Raszid, Starszy enklawy", npc_type="quest_giver",
         faction="starsi_solnego_progu", shop=0, quest=1, crafter=None,
         desc="Twarz ukrycia — najstarszy głos Domu Starszych. Popielata skóra "
              "napięta na kościach jak wysuszona sól, blade, niemal bezbarwne oczy, "
              "które patrzą przez człowieka. Wierzy, że enklawa przetrwa tylko "
              "niewidzialna: kto otwiera bramę obcym, ten sprowadza Światło i kult.",
         prompt="Powolny, ostrożny, waży słowa jak wodę na pustyni. Nie zabrania "
                "wprost — tłumaczy, ile już razy „otwarcie” kosztowało Piętnowanych "
                "krew. Zleci zadanie służące UKRYCIU enklawy i nigdy nie przyzna, że "
                "sam boi się, iż ukrywać się dłużej już nie sposób."),
    dict(key="lejla_przewodniczka", label="Lejla, przewodniczka", npc_type="quest_giver",
         faction="przewodnicy_ruin", shop=0, quest=1, crafter=None,
         desc="Twarz otwarcia — prowadzi obcych w ruiny i wraca żywa, gdy inni nie "
              "wracają. Popielata skóra pokryta bliznami po soli, blade oczy, które "
              "w mroku ruin widzą lepiej niż cudze. Werbuje do swojej wizji: sprzedać "
              "przewodnictwo, póki pustkowia jeszcze mają co dać.",
         prompt="Bezpośrednia, żywa, mówi „chodź, pokażę” zanim Starsi się zgodzą. "
                "Ocenia człowieka po tym, czy da się na niego liczyć w ruinach. Zleca "
                "zadania odwrotne do Raszida — wyprawy w martwe miasta, ku reliktom "
                "i dalej. O ryzyku mówi wprost: pustynia ma zęby."),
    dict(key="nadira_zniwiarka", label="Nadira, mistrzyni solnych żniw", npc_type="merchant",
         faction="starsi_solnego_progu", shop=1, quest=0, crafter=None,
         desc="Mistrzyni Solnych Magazynów — wie o soli więcej niż ktokolwiek na "
              "świecie. Popielata skóra wyżarta solą do matowej bieli, blade oczy "
              "przywykłe do oślepiającej równiny. Zna każdą hałdę: która sól tłumi "
              "Rdzeń najmocniej, bo powstała najbliżej pęknięcia.",
         prompt="Rzeczowa, dumna z towaru, twarda w cenie soli premium. Nie targuje "
                "się o czystość — jej sól jest czystsza niż wszystko z Grań i ona to "
                "wie. Chętnie tłumaczy, czemu kręgi i klingi z jej magazynu ratują "
                "życie na pustkowiach, a tandeta z gór — nie."),
    dict(key="farid_kupiec", label="Farid, kupiec Targu Przewodników", npc_type="merchant",
         faction="przewodnicy_ruin", shop=1, quest=0, crafter=None,
         desc="Kupiec Targu Przewodników — handluje tym, czego pustkowia najbardziej "
              "strzegą: mapami ruin, kościanymi kompasami i reliktami spod piasku. "
              "Popielata skóra, blade oczy zmrużone w wiecznym targu. Zna cenę "
              "każdego martwego miasta i drogę do niego.",
         prompt="Gadatliwy, przebiegły, ale nie oszukuje: dobra reputacja przewodnika "
                "jest warta więcej niż jeden zły interes. Sprzedaje mapy i kompasy, "
                "kontraktuje wyprawy w ruiny i sonduje, czy rozmówca stanie po stronie "
                "otwarcia. O reliktach mówi z błyskiem w bladym oku."),
    # Ludzie
    dict(key="greta_szefowa", label="Greta, szefowa Obozu Gorączki", npc_type="merchant",
         faction=None, shop=1, quest=1, crafter=None,
         desc="Szefowa boomtownu poszukiwaczy — trzyma Obóz Gorączki w garści siłą "
              "woli i pięści. Prowadzi kramy ze sprzętem kopacza i bukłakami: kto "
              "kopie za reliktami, ten najpierw kupuje u niej kilof i wodę. Chaos "
              "obozu jest jej chlebem, byle płacił.",
         prompt="Szorstka, konkretna, mówi o robocie i o złocie. Da sprzęt, wskaże, "
                "gdzie kopać, i ostrzeże, gdzie już budzono to, co spało. Nie znosi "
                "gadania — pyta wprost, co kupujesz i czym płacisz. Zleci robotę "
                "kopacza, jeśli widzi w rozmówcy zysk dla obozu."),
    dict(key="brat_ansgar", label="Brat Ansgar, uzdrowiciel Misji", npc_type="ally",
         faction="misja_swiatla", shop=0, quest=1, crafter=None,
         desc="Uzdrowiciel Misji Światła — leczy każdego, kto dojdzie na skraj "
              "pustkowi, Piętnowanego czy obcego, bez pytań. Widzi w piętnie ludzi, "
              "nie skażenie, i dlatego sam napięcie z enklawą łagodzi, gdy Siostra "
              "Verena je zaostrza.",
         prompt="Łagodny, cierpliwy, mówi o ranach ciała i ducha. Poda pomoc i wodę, "
                "a między słowami prosi, by nie rozdzierać tego, co i tak już pęka. "
                "Ponad spór o piętno przedkłada konkretnego chorego przed sobą."),
    dict(key="siostra_verena", label="Siostra Verena, inkwizytorka-obserwatorka", npc_type="neutral",
         faction="misja_swiatla", shop=0, quest=1, crafter=None,
         desc="Inkwizytorka Świątyni wysłana, by patrzeć — antagonistka bez złej "
              "woli. Pyta jedno pytanie i nie odpuszcza: „czy piętno to dar, czy "
              "skażenie?”. Nie potępia z góry, ale zapisuje wszystko, a jej raport "
              "może zamknąć bramę enklawy szczelniej niż każdy wróg.",
         prompt="Chłodna, uważna, mówi pytaniami, nie wyrokami. Obserwuje rozmówcę "
                "równie pilnie jak Piętnowanych. Nie jest złoczyńcą — jest sumieniem "
                "Światła, które nie wie jeszcze, po której stronie stanąć, i właśnie "
                "to czyni ją groźną dla enklawy."),
    dict(key="fabian_paser", label="Fabian, skup reliktów", npc_type="merchant",
         faction=None, shop=1, quest=1, crafter=None,
         desc="Agent Brata Tomasza Kronikarza — siedzi w Obozie Gorączki i skupuje "
              "relikty spod piasku, płacąc za każde znalezisko z ruin. To on ściągnął "
              "na pustkowia gorączkę reliktów: gdzie płaci paser, tam rozkopują groby "
              "i budzą to, co spało.",
         prompt="Śliski, uprzejmy do granic, liczy w głowie szybciej niż mówi. Kupi "
                "każdy relikt i zapłaci uczciwie za dobry — bo Brat Tomasz płaci jemu "
                "jeszcze lepiej. Wypytuje, skąd znalezisko i co jeszcze leży w tej "
                "ruinie. O tym, po co Kronikarzowi relikty, milczy."),
]

# ── Przypisania NPC → lokacja (hub = cała enklawa, sub = konkretna pinezka) ────
NPC_ASSIGNMENTS = [
    # Poziom huba: czterej Piętnowani jako mieszkańcy enklawy
    ("solny_prog", "raszid_starszy", "resident"),
    ("solny_prog", "lejla_przewodniczka", "resident"),
    ("solny_prog", "nadira_zniwiarka", "resident"),
    ("solny_prog", "farid_kupiec", "resident"),
    # Sub-lokacje Solnego Progu (pinezki §4/§7)
    ("solny_prog_dom_starszych", "raszid_starszy", "resident"),
    ("solny_prog_targ_przewodnikow", "farid_kupiec", "resident"),      # kupiec/kontrakty
    ("solny_prog_targ_przewodnikow", "lejla_przewodniczka", "resident"),  # przewodniczka
    ("solny_prog_solne_magazyny", "nadira_zniwiarka", "resident"),     # sól premium
    # Ludzie — przy swoich lokacjach makro (MP-4)
    ("oboz_goraczki", "greta_szefowa", "resident"),
    ("oboz_goraczki", "fabian_paser", "resident"),
    ("misja_swiatla", "brat_ansgar", "resident"),
    ("misja_swiatla", "siostra_verena", "resident"),
    # Nadira dogląda też zbieraczy na równinie (§7 — mistrzyni żniw)
    ("solne_zniwa", "nadira_zniwiarka", "visitor"),
]


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
    # spójność rasy #1475: opisy Piętnowanych muszą nieść blade oczy
    for n in NPCS:
        if n["faction"] in ("starsi_solnego_progu", "przewodnicy_ruin"):
            if "blad" not in n["desc"].lower() or "popiel" not in n["desc"].lower():
                problems.append(f"{n['key']}: opis Piętnowanego bez popielatej skóry/bladych oczu (#1475)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    res = apply(conn)
    print(f"  frakcje nowe:           {res['factions']}")
    print(f"  NPC-ikony nowe:         {res['npcs']}")
    print(f"  przypisania NPC nowe:   {res['npc_assignments']}")

    rows = conn.execute("""
        SELECT gl.label AS loc, n.label AS npc, a.assignment_type
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs n ON n.key = a.npc_key
        WHERE gl.region = ? AND a.is_active = 1
        ORDER BY gl.label, n.label""", (REGION,)).fetchall()
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
