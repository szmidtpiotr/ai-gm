#!/usr/bin/env python3
"""SG-6 (#1481) — obsada Siwych Grań: rody (frakcje) + 8 NPC-ikon + wrogowie ruin.

Źródło prawdy: docs/world/regions/siwe_granie.md §2, §3, §7, §8.
Wzorzec: scripts/seed_kresy_obsada.py (#981) — ta sama mechanika, inna kraina.

Dlaczego to ma znaczenie dla gry (read-path silnika):
  turn_pipeline → world_service.build_available_content_index() wstrzykuje do LLM
  blok "[AVAILABLE CONTENT]" zbudowany z `location_npc_assignments` /
  `location_enemy_assignments`. Podpięta lokacja = narrator przedstawia KANONICZNĄ
  postać zamiast wymyślać zastępczą, i sięga po właściwe zagrożenie.
  `npcs.faction_key` czyta z kolei reputacja per-frakcja (#1103) → ceny w sklepie
  (`shop_service.combined_buy_multiplier`), więc rody nie są dekoracją.

Idempotentny:
  - frakcje i NPC: INSERT OR IGNORE po kluczu (nigdy nie nadpisuje ręcznych zmian),
  - przypisania: INSERT OR IGNORE po UNIQUE(location_key, *_key),
  - `game_locations.npc_keys` / `enemy_keys` (JSON) przeliczane z tabel przypisań.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_siwe_granie_obsada.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_obsada.py
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_obsada.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

# ── RODY = frakcje (lore §8; faction_type 'clan' dopuszczony przez CHECK) ─────
FACTIONS = [
    ("siwotarczy", "Ród Siwotarczych", "clan",
     "Starszyzna Grań. Strażnicy zakazów: Linii Soli i zakazu wchodzenia na lodowiec. "
     "Uważają, że przetrwanie jest ważniejsze od pamięci — trzeba czekać, aż stukanie ucichnie."),
    ("mlotodzierzcy", "Ród Młotodzierżców", "clan",
     "Rewizjoniści. Otwarcie mówią o powrocie do Kopalni Czarnego Hutmana i skończeniu tego, "
     "co się zaczęło. Po cichu handlują z Wygnańcami Lodu, bo tamci widzieli lodowiec z bliska."),
    ("solnobrodzi", "Ród Solnobrodych", "clan",
     "Ród solny — sztolnie, karawany i drugi towar eksportowy Grań. To ich woreczki soli "
     "wiszą u pasa każdego górnika, bo sól jest obojętna na Rdzeń."),
    ("srebrnozylni", "Ród Srebrnożylnych", "clan",
     "Ród srebra, gospodarze Wyrobiska Srebrnej Żyły. Kopią wysoko nad Linią Soli i pilnują, "
     "by tak zostało — choć stukanie w ich sztolniach słychać coraz wyraźniej."),
    ("wygnancy_lodu", "Wygnańcy Lodu", "clan",
     "Ród wyklęty za złamanie zakazu lodowca, koczujący w tundrze. Imię rodu wymazano "
     "z kronik Sali Rodów. Jako jedyni widzieli lód z bliska — i boją się go bardziej "
     "niż wyklęcia."),
]

# ── 8 NPC-ikon (lore §8; imiona i role WPROST z rozdziału — nic nie dopisane) ──
NPCS = [
    dict(key="balrik_siwotarczy", label="Balrik Siwotarczy", npc_type="quest_giver",
         faction="siwotarczy", shop=0, quest=1, crafter=None,
         desc="Starszy Rodów i głos zakazów w Sali Rodów. Siwa broda spleciona w trzy warkocze, "
              "po jednym za każdy hołd, który kazał porzucić. To on wyznaczył Linię Soli i to on "
              "co wieczór powtarza, że pod nią nie schodzi się po nic.",
         prompt="Powolny, ważący każde słowo, przyzwyczajony, że się go słucha. Nie krzyczy — "
                "wystarczy, że przestanie mówić. Zleci zadanie skierowane PRZECIW wyprawie do "
                "Hutmana i zapłaci uczciwie, ale nigdy nie przyzna, czego naprawdę się boi."),
    dict(key="dagna_mlotodzierzca", label="Dagna Młotodzierżca", npc_type="quest_giver",
         faction="mlotodzierzcy", shop=0, quest=1, crafter=None,
         desc="Przywódczyni rewizjonistów, młodsza od połowy sali i głośniejsza od całej. "
              "Werbuje do sprawy odbicia Kopalni Czarnego Hutmana — w Sali Rodów oficjalnie, "
              "a przy stole w szynku skuteczniej.",
         prompt="Bezpośrednia, zapalczywa, mówi „my” zanim ktokolwiek się zgodzi. Testuje "
                "rozmówcę jednym pytaniem: czy boisz się stukania, czy tego, co starszyzna "
                "zrobi, gdy je zignorujesz. Zleca zadania dokładnie odwrotne do Balrika."),
    dict(key="torvin_mistrz_kuzni", label="Torvin, mistrz Wielkiej Kuźni", npc_type="merchant",
         faction=None, shop=1, quest=0, crafter="smith",
         desc="Mistrz dwudziestu palenisk Wielkiej Kuźni. Ramiona jak miech kowalski, brwi "
              "wypalone dawno temu. Naprawia, przekuwa i sprzedaje żelazo — a o soli wie więcej "
              "niż niejeden kapłan, bo to on wykuwa okucia do solnych sztolni.",
         prompt="Małomówny przy pracy, gadatliwy przy piwie. Ocenia człowieka po tym, jak trzyma "
                "broń, a nie po tym, co mówi. Za dobre żelazo weźmie uczciwie, za tępe narzędzie "
                "obrazi się bardziej niż za obelgę."),
    dict(key="grimm_rdzawy", label="Grimm Rdzawy", npc_type="merchant",
         faction=None, shop=1, quest=0, crafter=None,
         desc="Karczmarz szynku „Pod Rdzawym Młotem” — pierwsze schronienie każdego, kto wszedł "
              "do Grodu mostem. Nad szynkwasem wisi młot, którego nigdy nie zdjął, i nikt już "
              "nie pyta czyj.",
         prompt="Serdeczny, ciekawski, pamięta każdą twarz. Nalewa i słucha, a potem opowiada "
                "dalej — plotka o stukaniu dojdzie do gościa, zanim zdejmie płaszcz. "
                "O polityce rodów mówi ostrożnie: u niego piją obie strony."),
    dict(key="helga_solnobroda", label="Helga Solnobroda", npc_type="merchant",
         faction="solnobrodzi", shop=1, quest=0, crafter=None,
         desc="Kupcowa solna z Targu Solnego, głowa handlu rodu Solnobrodych. Prowadzi karawany "
              "na Kresy i z powrotem, a woreczek soli sprzeda taniej niż ktokolwiek — bo wie, "
              "że górnik bez soli nie wraca.",
         prompt="Rzeczowa, twarda w targu, ale nie oszukuje: reputacja karawany jest warta "
                "więcej niż jeden zły interes. Zna ceny i drogi w całych Graniach i chętnie "
                "wymienia wiedzę o trakcie za wiadomość z Kresów."),
    dict(key="hadmar_obserwator", label="Hadmar, obserwator Echo-Wieży", npc_type="quest_giver",
         faction=None, shop=0, quest=1, crafter=None,
         desc="Stary krasnolud, który przez trzydzieści lat siedział w Echo-Wieży i słuchał "
              "dzwonów w szybie. Odszedł stamtąd, zanim zdążył oszaleć — zapisy zostawił na "
              "pulpicie, dokładne aż do ostatniej nocy. Dziś mieszka w Grodzie i mówi o Rdzeniu "
              "rzeczy, których starszyzna woli nie słyszeć.",
         prompt="Roztargniony, przeskakuje z tematu na temat, ale gdy mowa o stukaniu — nagle "
                "precyzyjny jak zegar. Poda liczby, głębokości i daty. Poprosi, by ktoś wrócił "
                "do Wieży po to, czego sam nie zdążył zabrać."),
    dict(key="brat_elias", label="Brat Elias", npc_type="neutral",
         faction=None, shop=0, quest=1, crafter=None,
         desc="Ostatni strażnik-pustelnik sanktuarium na Lodowym Pasie. Człowiek, nie krasnolud, "
              "i jedyny żywy na lodowcu. Odśnieża ścieżkę do wrót i nie pamięta, kiedy tu "
              "przyszedł ani kto go przysłał.",
         prompt="Łagodny, mówi cicho i wolno, jakby ważył każde słowo na mrozie. Odpowiada na "
                "pytania o pielgrzymkę spokojnie i bez sensu — jego wspomnienia się nie kleją. "
                "Nigdy nie tłumaczy, czemu sanktuarium jest odśnieżone."),
    dict(key="kettil_wodz_wygnancow", label="Kettil, wódz Wygnańców", npc_type="quest_giver",
         faction="wygnancy_lodu", shop=1, quest=1, crafter=None,
         desc="Wódz wyklętego rodu koczującego w tundrze. Handluje po cichu z Młotodzierżcami "
              "i to on wyprawia na lód każdego, kto ma dość rozumu, by zapytać o drogę. "
              "Jego ludzie widzieli lodowiec z bliska.",
         prompt="Nieufny wobec każdego z Grodu, bo Gród ich wyklął. Otwiera się, gdy ktoś "
                "potraktuje wyklęcie jak fakt, a nie jak wyrok. O lodowcu mówi niechętnie "
                "i zawsze kończy tak samo: że boi się go bardziej niż wyklęcia."),
]

# ── Przypisania NPC → lokacja (hub = całe miasto, sub = konkretne miejsce) ────
NPC_ASSIGNMENTS = [
    # Kamienny Gród — poziom huba: wszystkie miejskie twarze
    ("kamienny_grod", "balrik_siwotarczy", "resident"),
    ("kamienny_grod", "dagna_mlotodzierzca", "resident"),
    ("kamienny_grod", "torvin_mistrz_kuzni", "resident"),
    ("kamienny_grod", "grimm_rdzawy", "resident"),
    ("kamienny_grod", "helga_solnobroda", "resident"),
    ("kamienny_grod", "hadmar_obserwator", "resident"),
    # Sub-lokacje Grodu — konkretne pinezki
    ("grod_sala_rodow", "balrik_siwotarczy", "resident"),
    ("grod_sala_rodow", "dagna_mlotodzierzca", "visitor"),      # oś napięcia §3
    ("grod_pod_rdzawym_mlotem", "grimm_rdzawy", "resident"),
    ("grod_pod_rdzawym_mlotem", "dagna_mlotodzierzca", "visitor"),  # werbuje przy stole
    ("grod_wielka_kuznia", "torvin_mistrz_kuzni", "resident"),
    ("grod_targ_solny", "helga_solnobroda", "resident"),
    # Poza stolicą
    ("echo_wieza", "hadmar_obserwator", "visitor"),             # §8: Gród / Echo-Wieża
    ("sanktuarium_zamarznietej_pielgrzymki", "brat_elias", "resident"),
    ("oboz_wygnancow_lodu", "kettil_wodz_wygnancow", "resident"),
]

# ── Wrogowie: TYLKO miejsca opuszczone i lodowe z SG-4 ────────────────────────
# Zasiedlone (Gród, Karawanseraj, Wyrobisko, Posterunek, Źródła, Siarkowe Pola,
# Obóz Wygnańców) zostają czyste — tam się handluje, nie walczy.
# Lodowa Brama celowo BEZ wrogów: lore §4 mówi „zero questów i wejścia".
ENEMY_ASSIGNMENTS = [
    # Cmentarz Młotów — pamięć exodusu, nocą któryś młot dzwoni
    ("cmentarz_mlotow", "bladzacy_upior", 0.4, 1),
    ("cmentarz_mlotow", "ghost", 0.5, 2),
    ("cmentarz_mlotow", "skeleton", 0.4, 3),
    # Sztolnia Umarłego Rodu — farmowalny dungeon, tier niżej niż Hutman
    ("sztolnia_umarlego_rodu", "skeleton", 0.5, 3),
    ("sztolnia_umarlego_rodu", "ghoul", 0.4, 2),
    ("sztolnia_umarlego_rodu", "giant_spider", 0.4, 2),
    # Echo-Wieża — dzwony odpowiadają czemuś pod ziemią
    ("echo_wieza", "ghost", 0.4, 2),
    ("echo_wieza", "wraith", 0.3, 1),
    # Wyssane Hołdy — każdy z własnym charakterem
    ("grauhold", "zombie", 0.5, 3),
    ("grauhold", "skeleton", 0.4, 2),
    ("silberhold", "ghoul", 0.5, 2),
    ("silberhold", "kamienny_wojownik", 0.3, 1),      # strażnik skarbca rodu
    ("kohlgrund", "wynaturzony_trup", 0.5, 3),        # ściany ciepłe tam, gdzie nie powinny
    ("kohlgrund", "ghoul", 0.4, 2),
    ("frosthold", "mrozny_wilkolak", 0.4, 1),
    ("frosthold", "zombie", 0.4, 2),
    # Kaplica Zapomnianego Rodu — knoty świeżo przycięte
    ("kaplica_zapomnianego_rodu", "wraith", 0.4, 2),
    ("kaplica_zapomnianego_rodu", "ghost", 0.4, 2),
    # Stacja Pradawnych — nie krasnoludzkie i nie martwe
    ("stacja_pradawnych", "kamienny_wojownik", 0.4, 2),
    ("stacja_pradawnych", "golem_stone", 0.3, 1),
    # Lód
    ("sanktuarium_zamarznietej_pielgrzymki", "wraith", 0.3, 2),
    ("zamarznieta_karawana", "mrozny_wilkolak", 0.4, 2),
    ("zamarznieta_karawana", "ghost", 0.4, 2),
]


def apply(conn: sqlite3.Connection) -> dict:
    n_fac = n_npc = n_na = n_ea = 0

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

    for loc, enemy, spawn, maxc in ENEMY_ASSIGNMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO location_enemy_assignments (location_key, enemy_key, spawn_chance, max_count, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (loc, enemy, float(spawn), int(maxc)))
        n_ea += cur.rowcount or 0

    # Przelicz cache JSON w game_locations (mapa admina + fallback silnika)
    touched = {a[0] for a in NPC_ASSIGNMENTS} | {e[0] for e in ENEMY_ASSIGNMENTS}
    for loc in sorted(touched):
        npc_keys = [r[0] for r in conn.execute(
            "SELECT npc_key FROM location_npc_assignments WHERE location_key=? AND is_active=1 ORDER BY npc_key", (loc,))]
        enemy_keys = [r[0] for r in conn.execute(
            "SELECT enemy_key FROM location_enemy_assignments WHERE location_key=? AND is_active=1 ORDER BY enemy_key", (loc,))]
        conn.execute("UPDATE game_locations SET npc_keys=?, enemy_keys=? WHERE key=?",
                     (json.dumps(npc_keys, ensure_ascii=False),
                      json.dumps(enemy_keys, ensure_ascii=False), loc))
    conn.commit()
    return {"factions": n_fac, "npcs": n_npc, "npc_assignments": n_na, "enemy_assignments": n_ea}


def verify(conn: sqlite3.Connection) -> list[str]:
    """Twarde kontrole: klucze muszą istnieć, zasiedlone muszą zostać czyste."""
    problems = []
    for loc, npc, _ in NPC_ASSIGNMENTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc,)).fetchone():
            problems.append(f"przypisanie NPC do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc,)).fetchone():
            problems.append(f"nieistniejący NPC: {npc}")
    for loc, enemy, _, _ in ENEMY_ASSIGNMENTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc,)).fetchone():
            problems.append(f"przypisanie wroga do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM game_config_enemies WHERE key=?", (enemy,)).fetchone():
            problems.append(f"nieistniejący wróg: {enemy}")
    for n in NPCS:
        if n["faction"] and not conn.execute(
                "SELECT 1 FROM game_config_factions WHERE key=?", (n["faction"],)).fetchone():
            problems.append(f"{n['key']}: brak frakcji {n['faction']}")
    # zasiedlone i Lodowa Brama zostają bez wrogów (lore §4)
    for loc in ("kamienny_grod", "karawanseraj_na_trakcie", "wyrobisko_srebrnej_zyly",
                "posterunek_linii_soli", "gorace_zrodla", "siarkowe_pola",
                "oboz_wygnancow_lodu", "lodowa_brama"):
        c = conn.execute("SELECT count(*) c FROM location_enemy_assignments "
                         "WHERE location_key=? AND is_active=1", (loc,)).fetchone()["c"]
        if c:
            problems.append(f"{loc}: ma {c} przypisań wrogów, a mieć nie powinna")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    res = apply(conn)
    print(f"  frakcje (rody) nowe:      {res['factions']}")
    print(f"  NPC-ikony nowe:           {res['npcs']}")
    print(f"  przypisania NPC nowe:     {res['npc_assignments']}")
    print(f"  przypisania wrogów nowe:  {res['enemy_assignments']}")

    rows = conn.execute("""
        SELECT a.location_key, gl.label AS loc, a.npc_key, n.label AS npc, a.assignment_type
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs n ON n.key = a.npc_key
        WHERE gl.region = 'siwe_granie' AND a.is_active = 1
        ORDER BY gl.label, n.label""").fetchall()
    print(f"\n  obsada krainy ({len(rows)} przypisań):")
    for r in rows:
        print(f"    {r['loc']:42s} ← {r['npc']} ({r['assignment_type']})")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
