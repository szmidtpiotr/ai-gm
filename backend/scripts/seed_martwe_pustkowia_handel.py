#!/usr/bin/env python3
"""MP-5 (#1494) — handel Martwych Pustkowi: asortyment 4 punktów wymiany.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §4 (lokacje), §6 (sól premium,
kompas), §1/§7 (gorączka reliktów, obsada). Wzorzec: seed_czarnobor_handel.py (CB-5).

DLACZEGO JAWNY ASORTYMENT (read-path silnika):
  `shop_service._effective_shop_entries()`: jawny `npcs.shop_inventory_json`
  wygrywa zawsze; puste pole → `_default_stock_for_npc()` dobiera NAJTAŃSZE śmieci
  z całej gry wg roli. Cztery punkty MP dostają JAWNY, krainowy towar:
    1) Farid  @ Targ Przewodników — mapy, kompasy, relikty (przewodnictwo w ruiny),
    2) Nadira @ Solne Magazyny     — sól premium (Krąg/Klinga/Szczypta) + woda,
    3) Greta  @ Obóz Gorączki      — sprzęt kopacza + bukłaki,
    4) Fabian @ Obóz Gorączki      — SKUP reliktów: gracz SPRZEDAJE mu znaleziska
       (skup = zwykły sell_item do NPC); w sprzedaży trzyma tylko drobny towar pasera.

Ceny NIE są tu zapisywane — biorą się z `game_items.price_gp` × `combined_buy_multiplier()`.
Sól premium, kompas, relikt, kilof pochodzą z seed_martwe_pustkowia_smaczki.py — uruchom
go PRZED tym skryptem, inaczej walidacja „brak w katalogu" przerwie seed.

Usługi (nocleg) NIE tutaj — `location_services.py` wnioskuje je z podtypu lokacji:
Gospoda ('guest-inn' → 'inn' → nocleg). Podtyp nadaje seed_solny_prog.py.

Idempotentny: UPDATE po kluczu NPC. Każdy klucz walidowany względem katalogu.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_martwe_pustkowia_handel.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_handel.py
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_handel.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

SHOPS: list[dict] = [
    dict(
        npc_key="farid_kupiec",
        location_key="solny_prog_targ_przewodnikow",
        # Targ Przewodników: to, czego pustkowia najbardziej strzegą — mapy ruin,
        # kościane kompasy, relikty. Plus drobne zaopatrzenie na wyprawę.
        stock=[
            ("item", "treasure_map"),
            ("item", "kosciany_kompas"),
            ("item", "relikt_pradawnych"),
            ("item", "rope_hemp"),
            ("item", "torch"),
            ("item", "waterskin"),
            ("item", "bedroll"),
            ("consumable", "bandage"),
        ],
    ),
    dict(
        npc_key="nadira_zniwiarka",
        location_key="solny_prog_solne_magazyny",
        # Solne Magazyny: sól premium — trio Krąg / Klinga / Szczypta, najczystsza
        # ze wszystkich, bo powstała najbliżej pęknięć (§6). Woda dla wychodzących.
        stock=[
            ("item", "krag_soli"),
            ("consumable", "szczypta_soli"),
            ("weapon", "solona_klinga"),
            ("item", "waterskin"),
            ("consumable", "healing_herb"),
        ],
    ),
    dict(
        npc_key="greta_szefowa",
        location_key="oboz_goraczki",
        # Obóz Gorączki: sprzęt kopacza reliktów + bukłaki (§4). Kto kopie, kupuje
        # najpierw kilof i wodę — pustkowia są bezwodne (§5).
        stock=[
            ("item", "kilof_kopacza"),
            ("item", "shovel"),
            ("item", "waterskin"),
            ("item", "rope_hemp"),
            ("item", "torch"),
            ("item", "tinderbox"),
            ("item", "bedroll"),
            ("item", "oil_flask"),
            ("consumable", "healing_herb"),
            ("consumable", "bandage"),
        ],
    ),
    dict(
        npc_key="fabian_paser",
        location_key="oboz_goraczki",
        # Fabian = SKUP: gracz sprzedaje mu relikty (sell_item do NPC). W sprzedaży
        # trzyma tylko drobiazg pasera + odsprzedawane relikty i mapy.
        stock=[
            ("item", "relikt_pradawnych"),
            ("item", "treasure_map"),
            ("item", "torch"),
            ("item", "oil_flask"),
        ],
    ),
]

# Podtyp lokacji → usługi, których oczekujemy po `location_services.py`.
EXPECTED_SERVICES: dict[str, tuple[str, ...]] = {
    "solny_prog_gospoda": ("inn_night",),
}


def _validate_stock(conn) -> list[str]:
    problems: list[str] = []
    for shop in SHOPS:
        for kind, key in shop["stock"]:
            row = conn.execute(
                "SELECT kind, COALESCE(price_gp, 0) AS p FROM game_items "
                "WHERE key = ? AND is_active = 1", (key,),
            ).fetchone()
            if not row:
                problems.append(f"{shop['npc_key']}: brak w katalogu → {key}")
                continue
            if float(row["p"]) <= 0:
                problems.append(f"{shop['npc_key']}: cena 0 → {key}")
            if str(row["kind"]) != kind:
                problems.append(
                    f"{shop['npc_key']}: {key} ma kind='{row['kind']}', wpisano '{kind}'")
    return problems


def apply(conn) -> dict:
    res = {"updated": 0, "unchanged": 0}
    for shop in SHOPS:
        payload = json.dumps(
            [{"type": t, "key": k} for t, k in shop["stock"]], ensure_ascii=False)
        row = conn.execute(
            "SELECT id, shop_inventory_json FROM npcs WHERE key = ?", (shop["npc_key"],)
        ).fetchone()
        if not row:
            raise SystemExit(f"BŁĄD: brak NPC {shop['npc_key']} — najpierw obsada MP-5")
        if (row["shop_inventory_json"] or "") == payload:
            res["unchanged"] += 1
            continue
        conn.execute(
            "UPDATE npcs SET shop_inventory_json = ?, is_shop = 1, is_active = 1, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload, int(row["id"])))
        res["updated"] += 1
    return res


def verify(conn) -> list[str]:
    problems = _validate_stock(conn)
    for shop in SHOPS:
        npc = conn.execute(
            "SELECT is_shop, is_active, shop_inventory_json FROM npcs WHERE key = ?",
            (shop["npc_key"],)).fetchone()
        if not npc or int(npc["is_shop"] or 0) != 1 or int(npc["is_active"] or 0) != 1:
            problems.append(f"{shop['npc_key']}: nie jest aktywnym sklepem")
            continue
        if len(json.loads(npc["shop_inventory_json"] or "[]")) != len(shop["stock"]):
            problems.append(f"{shop['npc_key']}: asortyment nie zapisał się w całości")
        assigned = conn.execute(
            "SELECT 1 FROM location_npc_assignments "
            "WHERE npc_key = ? AND location_key = ? AND COALESCE(is_active, 1) = 1",
            (shop["npc_key"], shop["location_key"])).fetchone()
        if not assigned:
            problems.append(f"{shop['npc_key']}: brak przypisania do {shop['location_key']}")
    try:
        sys.path.insert(0, "/app")
        from app.services.location_services import get_available_service_keys
        for loc, expected in EXPECTED_SERVICES.items():
            keys = get_available_service_keys(conn, loc)
            missing = [s for s in expected if s not in keys]
            if missing:
                problems.append(f"{loc}: brak usług {missing} (podtyp lokacji?)")
    except ImportError:
        problems.append("nie udało się zaimportować location_services — usługi niesprawdzone")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    pre = _validate_stock(conn)
    if pre:
        print("PRZERWANE — asortyment nie zgadza się z katalogiem:")
        for p in pre:
            print("  " + p)
        print("  (uruchom seed_martwe_pustkowia_smaczki.py PRZED tym skryptem)")
        return 1

    res = apply(conn)
    conn.commit()
    print(f"  sklepy zaktualizowane:   {res['updated']}")
    print(f"  bez zmian (idempotent):  {res['unchanged']}")

    for shop in SHOPS:
        row = conn.execute(
            "SELECT n.label, n.faction_key, n.shop_inventory_json FROM npcs n WHERE n.key = ?",
            (shop["npc_key"],)).fetchone()
        entries = json.loads(row["shop_inventory_json"] or "[]")
        print(f"\n  {row['label']} @ {shop['location_key']} (frakcja: {row['faction_key'] or '—'})")
        print(f"    pozycji: {len(entries)}")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
