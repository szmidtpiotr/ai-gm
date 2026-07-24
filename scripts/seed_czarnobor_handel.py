#!/usr/bin/env python3
"""CB-5 (#1489/#1490) — handel Czarnoboru: asortyment 3 punktów wymiany.

Źródło prawdy: docs/world/regions/czarnobor.md §4 (lokacje), §6 (dziegieć/futra),
§8 (obsada). Wzorzec: scripts/seed_grod_handel.py (SG-5b) — ta sama mechanika.

DLACZEGO JAWNY ASORTYMENT (read-path silnika):
  `shop_service._effective_shop_entries()`: jawny `npcs.shop_inventory_json`
  wygrywa zawsze; puste pole → `_default_stock_for_npc()` dobiera NAJTAŃSZE śmieci
  z całej gry wg roli. Trzy punkty Czarnoboru dostają JAWNY, krainowy towar:
    1) Cathel @ Targ Wymienny — asortyment elficki: łuki, strzały, skóry, zioła,
    2) Sylvar @ Łukodzielnia — warsztat łuczniczy: łuki, kusza, strzały, tandeta cieśli,
    3) Bartel @ Ostęp Graniczny — towary ludzkie + futra (dziegieć: patrz TODO).

Ceny NIE są tu zapisywane — biorą się z `game_items.price_gp` × `combined_buy_multiplier()`.
Usługi (nocleg/naprawa) NIE tutaj — `location_services.py` wnioskuje je z podtypu
lokacji: Gościnne Drzewo ('guest-inn' → 'inn' → nocleg), Łukodzielnia ('bowyer-forge'
→ 'forge' → naprawa). Suby dostają podtypy w seed_szept_koron.py; verify() to sprawdza.

TODO (dziegieć/sól-analog): §6 opisuje dziegieć czarnodrzewny i futra jako filar
ekonomii krainy. Futra są w katalogu (fur_mantle, wolf_hide_cloak, bear_hide,
wolf_pelt) — dziegieć jeszcze NIE (0 trafień na 'dziegie'/'tar-consumable'). Gdy
przyszła fala doda przedmiot dziegieć — dopisać klucz do BARTEL i puścić seeder.

Idempotentny: UPDATE po kluczu NPC. Każdy klucz walidowany względem katalogu.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_czarnobor_handel.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_handel.py
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_handel.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

SHOPS: list[dict] = [
    dict(
        npc_key="cathel_zwiadowca",
        location_key="szept_targ_wymienny",
        # Targ Wymienny: asortyment elficki — to, co bór rodzi i czym się wymienia.
        # Łuki i strzały (broń dystansowa elfów), skóry i futra kniei, zioła, sprzęt
        # leśny. Ciężkiego żelastwa TU NIE MA — od tego są ludzie za granicą.
        stock=[
            ("weapon", "shortbow"),
            ("weapon", "longbow"),
            ("consumable", "arrows"),
            ("item", "bear_hide"),
            ("item", "wolf_pelt"),
            ("armor", "hide_armor"),
            ("armor", "studded_leather"),
            ("armor", "leather_armor"),
            ("armor", "travelers_cloak"),
            ("consumable", "healing_herb"),
            ("consumable", "bandage"),
            ("item", "waterskin"),
            ("item", "bedroll"),
            ("item", "rope_hemp"),
        ],
    ),
    dict(
        npc_key="sylvar_lukmistrz",
        location_key="szept_lukodzielnia",
        # Łukodzielnia: warsztat łuczniczy — pełny przekrój broni dystansowej,
        # amunicja i drobiazgi rzemiosła (naciągi = rope_hemp, konserwacja = oil/whetstone).
        stock=[
            ("weapon", "shortbow"),
            ("weapon", "longbow"),
            ("weapon", "crossbow"),
            ("consumable", "arrows"),
            ("armor", "studded_leather"),
            ("item", "rope_hemp"),
            ("item", "whetstone"),
            ("item", "oil_flask"),
        ],
    ),
    dict(
        npc_key="bartel_kupiec",
        location_key="ostep_graniczny",
        # Ostęp Graniczny: okno handlu z Kresami — towary ludzkie na drogę,
        # futra na przełęcze, jedno ludzkie ostrze. Dziegieć: patrz TODO w nagłówku.
        stock=[
            ("item", "torch"),
            ("item", "tinderbox"),
            ("item", "oil_flask"),
            ("item", "rope_hemp"),
            ("item", "waterskin"),
            ("item", "bedroll"),
            ("consumable", "bandage"),
            ("consumable", "healing_herb"),
            ("armor", "fur_mantle"),
            ("armor", "wolf_hide_cloak"),
            ("armor", "hooded_cloak"),
            ("item", "bear_hide"),
            ("item", "wolf_pelt"),
            ("weapon", "dagger"),
        ],
    ),
]

# Podtyp lokacji → usługi, których oczekujemy po `location_services.py`.
EXPECTED_SERVICES: dict[str, tuple[str, ...]] = {
    "szept_goscinne_drzewo": ("inn_night", "tavern_meal"),
    "szept_lukodzielnia": ("blacksmith_repair",),
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
            raise SystemExit(f"BŁĄD: brak NPC {shop['npc_key']} — najpierw obsada CB-5")
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
