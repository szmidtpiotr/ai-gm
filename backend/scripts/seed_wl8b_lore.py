#!/usr/bin/env python3
"""WL-8b (#1504) — lokacje/obsada: kantor (enklawa krasnoludzka) + Rogatka Wschodnia.

Domyka smaczki #1500/#1501 Koronnych Nizin warstwą treści:
  * ``vilnograd_enklawa_krasnoludzka`` — kantor (weksle), bankier **Gundrik Złota Waga**.
    kantor_service.kantor_available rozpoznaje tę lokację po kluczu/subtypie.
  * ``rogatka_wschodnia`` — komora celna, celniczka **Berta Twarda Pieczęć**
    (twarz mechaniki rogatki z WL-8; kontrola i tak działa regionowo z execute_travel).

Wyłącznie hexless sub-lokacje (parent = istniejące huby Nizin) — NIE dotyka mapy
świata (world_hexes map_level=0 = własność Piotra). Idempotentny (ON CONFLICT/klucz).

URUCHOMIENIE w kontenerze backendu:
    docker cp scripts/seed_wl8b_lore.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_wl8b_lore.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

LOCATIONS = [
    dict(key="vilnograd_enklawa_krasnoludzka",
         label="Vilnograd: Enklawa Krasnoludzka",
         description="Ciasna dzielnica kantorów, jubilerów i wag. Za kratą Gundrik Złota "
                     "Waga zamienia złoto na weksle na okaziciela — kradzież ani śmierć "
                     "nie zabiorą papieru, tylko kruszec.",
         region="koronne_niziny", parent_key="vilnograd_stolica",
         location_type="sub", location_subtype="kantor", tier=2, safe_for_rest=1),
    dict(key="rogatka_wschodnia",
         label="Rogatka Wschodnia",
         description="Komora celna na trakcie z Wybrzeża. Szlaban, waga i rejestr. "
                     "Berta Twarda Pieczęć sprawdza glejty i juki — kto wiezie „towar z "
                     "głębin” bez papierów, ten go tu zostawia.",
         region="koronne_niziny", parent_key="volhynia_kupiecka",
         location_type="sub", location_subtype="rogatka", tier=1, safe_for_rest=1),
]

NPCS = [
    dict(key="gundrik_zlota_waga", label="Gundrik Złota Waga", npc_type="merchant",
         description="Bankier enklawy krasnoludzkiej. Wystawia i wykupuje weksle kantorów. "
                     "Prowizję liczy co do miedziaka, ale słowa dotrzymuje.",
         faction_key=None, location_key="vilnograd_enklawa_krasnoludzka"),
    dict(key="berta_twarda_pieczec", label="Berta Twarda Pieczęć", npc_type="neutral",
         description="Celniczka Rogatki Wschodniej. Germańska twardość, koronna pieczęć. "
                     "Glejt przepuści, fałszywkę wywęszy, kontrabandę skonfiskuje.",
         faction_key="korona", location_key="rogatka_wschodnia"),
]


def seed_locations(conn) -> int:
    n = 0
    for loc in LOCATIONS:
        conn.execute(
            """INSERT INTO game_locations
                 (key, label, description, region, parent_key, location_type,
                  location_subtype, tier, safe_for_rest, canonical, is_active, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,1,1,'seed')
               ON CONFLICT(key) DO UPDATE SET
                 label=excluded.label, description=excluded.description, region=excluded.region,
                 parent_key=excluded.parent_key, location_subtype=excluded.location_subtype,
                 tier=excluded.tier, safe_for_rest=excluded.safe_for_rest, is_active=1,
                 updated_at=datetime('now')""",
            (loc["key"], loc["label"], loc["description"], loc["region"], loc["parent_key"],
             loc["location_type"], loc["location_subtype"], loc["tier"], loc["safe_for_rest"]),
        )
        n += 1
    return n


def seed_npcs(conn) -> int:
    n = 0
    for npc in NPCS:
        conn.execute(
            """INSERT INTO npcs (key, label, npc_type, description, faction_key, is_shop, is_active)
               VALUES (?,?,?,?,?,0,1)
               ON CONFLICT(key) DO UPDATE SET
                 label=excluded.label, npc_type=excluded.npc_type, description=excluded.description,
                 faction_key=excluded.faction_key, is_active=1, updated_at=datetime('now')""",
            (npc["key"], npc["label"], npc["npc_type"], npc["description"], npc["faction_key"]),
        )
        # przypisanie do lokacji (bez duplikatu)
        exists = conn.execute(
            "SELECT 1 FROM location_npc_assignments WHERE location_key=? AND npc_key=?",
            (npc["location_key"], npc["key"]),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
                "VALUES (?,?,'resident',1)",
                (npc["location_key"], npc["key"]),
            )
        n += 1
    return n


def verify(conn) -> list[str]:
    problems = []
    for loc in LOCATIONS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc["key"],)).fetchone():
            problems.append(f"lokacja brak: {loc['key']}")
    for npc in NPCS:
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc["key"],)).fetchone():
            problems.append(f"NPC brak: {npc['key']}")
        if not conn.execute(
            "SELECT 1 FROM location_npc_assignments WHERE location_key=? AND npc_key=? AND COALESCE(is_active,1)=1",
            (npc["location_key"], npc["key"])).fetchone():
            problems.append(f"przypisanie brak: {npc['key']}→{npc['location_key']}")
    # kantor rozpoznawalny?
    try:
        sys.path.insert(0, "/app")
        from app.services import kantor_service
        row = conn.execute("SELECT key,label,location_subtype FROM game_locations WHERE key='vilnograd_enklawa_krasnoludzka'").fetchone()
        hay = f"{row['key']} {row['label']} {row['location_subtype']}".lower()
        if not any(k in hay for k in kantor_service.KANTOR_KEYWORDS):
            problems.append("enklawa NIE rozpoznana jako kantor (keywords)")
    except Exception as e:
        problems.append(f"kantor_service import: {e}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    nl = seed_locations(conn)
    nn = seed_npcs(conn)
    conn.commit()
    print(f"  lokacje: {nl}   NPC+przypisania: {nn}")
    problems = verify(conn)
    conn.close()
    print("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
