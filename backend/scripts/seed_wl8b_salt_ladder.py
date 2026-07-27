#!/usr/bin/env python3
"""WL-8b (#1504) — dopięcie drabiny soli: sól górska (Granie) + sól z blizny (Pustkowia).

Domyka gradację handlową z lore §3: Pustkowia > Granie > Wybrzeże = trzy klasy tego
samego towaru. Sól morska (Wybrzeże) była już w WL-8; tu dochodzą dwa górne szczeble
jako REALNE towary. Ceny sprzedaży w Nizinach: blizna > górska > morska (patrz
smuggling_service.TRADE_GOODS). Każda sól najtańsza w swoim regionie rodowym.

Źródła (istniejące sklepy krain):
  * sól górska  → Helga Solnobroda @ grod_targ_solny (Targ Solny, Siwe Granie),
  * sól z blizny → Nadira Żniwiarka @ solne_zniwa / solny_prog_solne_magazyny (Pustkowia).

Idempotentny (MERGE po kluczu). URUCHOMIENIE w kontenerze backendu:
    docker cp scripts/seed_wl8b_salt_ladder.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_wl8b_salt_ladder.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

# price_gp = uczciwa wartość „z Nizin"; narzut per-sklep daje tanie kupno u źródła.
ITEMS = [
    dict(key="sol_gorska", kind="item", label="Sól górska", price_gp=14,
         description="Sól kopalniana z żył Siwych Grań — czystsza i droższa od morskiej "
                     "z Wybrzeża, tańsza od blizny Pustkowi. Średni szczebel drabiny soli."),
    dict(key="sol_blizny", kind="item", label="Sól z blizny", price_gp=24,
         description="Sól wyskrobana z solnej blizny Martwych Pustkowi — najczystsza i "
                     "najdroższa klasa soli świata. Górny szczebel drabiny."),
]

SHOP_ADDS = [
    dict(npc_key="helga_solnobroda", add=[{"type": "item", "key": "sol_gorska", "price": 5}]),
    dict(npc_key="nadira_zniwiarka", add=[{"type": "item", "key": "sol_blizny", "price": 9}]),
]


def seed_items(conn):
    n = 0
    for it in ITEMS:
        conn.execute(
            """INSERT INTO game_items (key, kind, label, description, price_gp, location_tags,
                                       min_level, rarity, created_by, approved, is_active, item_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET kind=excluded.kind, label=excluded.label,
                 description=excluded.description, price_gp=excluded.price_gp, is_active=1,
                 updated_at=datetime('now')""",
            (it["key"], it["kind"], it["label"], it["description"], float(it["price_gp"]),
             "[]", 1, 1, "seed", 1, 1, "{}"),
        )
        n += 1
    return n


def merge_shop(conn, npc_key, add):
    rows = conn.execute("SELECT id, shop_inventory_json FROM npcs WHERE key=?", (npc_key,)).fetchall()
    if not rows:
        raise SystemExit(f"BŁĄD: brak NPC {npc_key}")
    changed = 0
    for row in rows:  # NPC może mieć wiele przypisań/wierszy — ale klucz jest UNIQUE; pętla defensywna
        try:
            cur = json.loads(row["shop_inventory_json"] or "[]")
            if not isinstance(cur, list):
                cur = []
        except Exception:
            cur = []
        have = {(str(e.get("type")), str(e.get("key"))) for e in cur if isinstance(e, dict)}
        for entry in add:
            sig = (str(entry.get("type")), str(entry.get("key")))
            if sig in have:
                continue
            cur.append(dict(entry))
            changed += 1
        conn.execute(
            "UPDATE npcs SET shop_inventory_json=?, is_shop=1, is_active=1, updated_at=datetime('now') WHERE id=?",
            (json.dumps(cur, ensure_ascii=False), int(row["id"])),
        )
    return changed


def verify(conn):
    problems = []
    for it in ITEMS:
        r = conn.execute("SELECT price_gp FROM game_items WHERE key=? AND is_active=1", (it["key"],)).fetchone()
        if not r or float(r["price_gp"] or 0) <= 0:
            problems.append(f"katalog: {it['key']} brak/cena0")
    for shop in SHOP_ADDS:
        r = conn.execute("SELECT shop_inventory_json FROM npcs WHERE key=?", (shop["npc_key"],)).fetchone()
        keys = {str(e.get("key")) for e in json.loads(r["shop_inventory_json"] or "[]")} if r else set()
        for entry in shop["add"]:
            if entry["key"] not in keys:
                problems.append(f"{shop['npc_key']}: nie dodano {entry['key']}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    ni = seed_items(conn)
    ns = sum(merge_shop(conn, s["npc_key"], s["add"]) for s in SHOP_ADDS)
    conn.commit()
    print(f"  przedmioty: {ni}   wpisy sklepowe: {ns}")
    problems = verify(conn)
    conn.close()
    print("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
