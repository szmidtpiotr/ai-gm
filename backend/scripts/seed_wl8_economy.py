#!/usr/bin/env python3
"""WL-8 (#1504) — ekonomia Wybrzeża Łez: sól morska + kontrabanda + papiery Nizin.

Źródło prawdy: docs/world/regions/wybrzeze_lez.md §3/§6, koronne_niziny.md §6.
Wzorzec: seed_martwe_pustkowia_handel.py (MP-5) — jawny asortyment bije domyślny.

Co robi (idempotentnie):
  1. Dodaje 6 przedmiotów do katalogu ``game_items``:
       - sol_morska            (LEGALNY towar — najtańsza klasa soli, warzelnie),
       - perla_glebin          (KONTRABANDA „z głębin"),
       - zywica_topielcow      (KONTRABANDA),
       - glejt_kupiecki        (papier Nizin — mniejsza czujność na rogatce),
       - list_zelazny          (papier Nizin — przejście bez pytań),
       - falszywe_papiery      (papier łotrzyka — test na rogatce).
  2. Dokłada towar do sklepów (MERGE — istniejący asortyment zostaje):
       - nakea_przemytniczka (Czarnogród, Czarny Targ) = ŹRÓDŁO: sól + kontrabanda
         z tanim narzutem (price) — tu się kupuje,
       - kupiec_vilnograd (Vilnograd, Rynek) = glejt + list żelazny (legalne papiery),
       - merchant_aldric (Volhynia, Targowisko) = fałszywe papiery (paser „z Nizin").

Ceny SPRZEDAŻY towarów są region-zależne w ``smuggling_service`` — Niziny płacą
drogo, Wybrzeże tanio; loop domyka się: kup w Czarnogrodzie → sprzedaj w Nizinach.

URUCHOMIENIE (w kontenerze backendu):
    docker cp scripts/seed_wl8_economy.py ai-gm-dev-backend-1:/tmp/
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_wl8_economy.py
    docker exec ai-gm-dev-backend-1 python3 /tmp/seed_wl8_economy.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

# ── Katalog: 6 nowych przedmiotów (klucz, kind, label, price_gp, opis) ────────
# price_gp = uczciwa wartość „z Nizin"; tanie kupno u źródła daje narzut per-sklep.
ITEMS: list[dict] = [
    dict(key="sol_morska", kind="item", label="Sól morska", price_gp=6,
         description="Warzona na mieliznach Wybrzeża Łez — najtańsza sól świata, "
                     "gorsza od górskiej z Grań i od blizny Pustkowi. Prosty, legalny towar."),
    dict(key="perla_glebin", kind="item", label="Perła z Głębin", price_gp=140,
         description="Morze wyrzuca je na wrakach przy rafach. Kupcy Nizin płacą krocie "
                     "i nie pytają, skąd. Prawo Korony nie lubi „towaru z głębin”."),
    dict(key="zywica_topielcow", kind="item", label="Żywica topielców", price_gp=80,
         description="Ciemna, słodkawa żywica z podmorskich grot. Zakazana w Nizinach — "
                     "i dlatego tam najdroższa. Kontrabanda pełną gębą."),
    dict(key="glejt_kupiecki", kind="item", label="Glejt kupiecki", price_gp=60,
         description="Pieczętowana licencja handlowa Korony. Na rogatce celnik patrzy "
                     "łaskawszym okiem — mniej węszy w jukach."),
    dict(key="list_zelazny", kind="item", label="List żelazny", price_gp=120,
         description="Pismo z pieczęcią, przed którym rogatki otwierają szlaban bez pytań. "
                     "Drogie, ale przejście gwarantowane."),
    dict(key="falszywe_papiery", kind="item", label="Fałszywe papiery", price_gp=40,
         description="Podrobione glejty spod ciemnej gwiazdy z Nizin. Działają — dopóki "
                     "celnik nie przyjrzy się pieczęci. Wtedy jest gorzej niż bez nich."),
]

# ── Domieszki do sklepów (MERGE po kluczu; „price" = narzut per-sklep) ────────
SHOP_ADDS: list[dict] = [
    dict(npc_key="nakea_przemytniczka", add=[
        {"type": "item", "key": "sol_morska", "price": 2},       # tanio u źródła
        {"type": "item", "key": "perla_glebin", "price": 40},    # kontrabanda tania tu
        {"type": "item", "key": "zywica_topielcow", "price": 20},
    ]),
    dict(npc_key="kupiec_vilnograd", add=[
        {"type": "item", "key": "glejt_kupiecki"},
        {"type": "item", "key": "list_zelazny"},
    ]),
    dict(npc_key="merchant_aldric", add=[
        {"type": "item", "key": "falszywe_papiery"},
    ]),
]


def seed_items(conn: sqlite3.Connection) -> int:
    n = 0
    for it in ITEMS:
        row = conn.execute("SELECT price_gp, label FROM game_items WHERE key=?", (it["key"],)).fetchone()
        if row and float(row["price_gp"] or 0) == float(it["price_gp"]) and (row["label"] or "") == it["label"]:
            continue
        conn.execute(
            """INSERT INTO game_items (key, kind, label, description, price_gp, location_tags,
                                       min_level, rarity, created_by, approved, is_active, item_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                 kind=excluded.kind, label=excluded.label, description=excluded.description,
                 price_gp=excluded.price_gp, is_active=1, updated_at=datetime('now')""",
            (it["key"], it["kind"], it["label"], it["description"], float(it["price_gp"]),
             "[]", 1, 1, "seed", 1, 1, "{}"),
        )
        n += 1
    return n


def merge_shop(conn: sqlite3.Connection, npc_key: str, add: list[dict]) -> int:
    row = conn.execute("SELECT id, shop_inventory_json FROM npcs WHERE key=?", (npc_key,)).fetchone()
    if not row:
        raise SystemExit(f"BŁĄD: brak NPC {npc_key} — najpierw obsada WL-6 / Nizin")
    try:
        cur = json.loads(row["shop_inventory_json"] or "[]")
        if not isinstance(cur, list):
            cur = []
    except Exception:
        cur = []
    have = {(str(e.get("type")), str(e.get("key"))) for e in cur if isinstance(e, dict)}
    changed = 0
    for entry in add:
        sig = (str(entry.get("type")), str(entry.get("key")))
        if sig in have:
            # aktualizuj narzut, jeśli inny
            for e in cur:
                if isinstance(e, dict) and (str(e.get("type")), str(e.get("key"))) == sig:
                    if entry.get("price") is not None and e.get("price") != entry.get("price"):
                        e["price"] = entry["price"]
                        changed += 1
            continue
        cur.append(dict(entry))
        changed += 1
    if changed:
        conn.execute(
            "UPDATE npcs SET shop_inventory_json=?, is_shop=1, is_active=1, updated_at=datetime('now') WHERE id=?",
            (json.dumps(cur, ensure_ascii=False), int(row["id"])),
        )
    return changed


def verify(conn: sqlite3.Connection) -> list[str]:
    problems: list[str] = []
    for it in ITEMS:
        r = conn.execute("SELECT price_gp, is_active FROM game_items WHERE key=?", (it["key"],)).fetchone()
        if not r:
            problems.append(f"brak w katalogu: {it['key']}")
        elif int(r["is_active"] or 0) != 1:
            problems.append(f"nieaktywny: {it['key']}")
        elif float(r["price_gp"] or 0) <= 0:
            problems.append(f"cena 0: {it['key']}")
    for shop in SHOP_ADDS:
        row = conn.execute("SELECT shop_inventory_json FROM npcs WHERE key=?", (shop["npc_key"],)).fetchone()
        if not row:
            problems.append(f"brak NPC: {shop['npc_key']}")
            continue
        keys = {str(e.get("key")) for e in json.loads(row["shop_inventory_json"] or "[]") if isinstance(e, dict)}
        for entry in shop["add"]:
            if entry["key"] not in keys:
                problems.append(f"{shop['npc_key']}: nie dodano {entry['key']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    n_items = seed_items(conn)
    n_shops = 0
    for shop in SHOP_ADDS:
        n_shops += merge_shop(conn, shop["npc_key"], shop["add"])
    conn.commit()

    print(f"  przedmioty dodane/zmienione: {n_items}")
    print(f"  wpisy sklepowe dodane/zmienione: {n_shops}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
