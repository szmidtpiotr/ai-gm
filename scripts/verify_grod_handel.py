#!/usr/bin/env python3
"""SG-5b (#1481) — twarda weryfikacja handlu w Kamiennym Grodzie.

Nie sprawdza „czy dane są w bazie" tylko PRZEPUSZCZA REALNE TRANSAKCJE przez
silnik sklepu (shop_service.get_shop_inventory / buy_item / sell_item — te same
funkcje, które wołają endpointy /api/shop/*), dla dwóch bohaterów o identycznych
statystykach różniących się wyłącznie rasą. Na końcu sprząta po sobie.

    docker cp scripts/verify_grod_handel.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/verify_grod_handel.py
"""
from __future__ import annotations

import json
import sqlite3
import sys

sys.path.insert(0, "/app")

DB = "/data/ai_gm.db"
CAMP_ID = 77779901
HERO_DWARF = 99990901
HERO_HUMAN = 99990902

SHEET = json.dumps(
    {
        "level": 1,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "hp": {"current": 20, "max": 20},
        "archetype": "warrior",
        "__sg5b_test__": True,
    },
    ensure_ascii=False,
)


def cleanup(conn: sqlite3.Connection) -> None:
    for hid in (HERO_DWARF, HERO_HUMAN):
        conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (hid,))
        conn.execute("DELETE FROM characters WHERE id = ?", (hid,))
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (CAMP_ID,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (CAMP_ID,))
    conn.commit()


def setup(conn: sqlite3.Connection, location_key: str) -> None:
    cleanup(conn)
    conn.execute(
        "INSERT INTO campaigns (id, title, status, system_id, model_id, owner_user_id) "
        "VALUES (?, ?, 'active', 'fantasy', 'test', 1)",
        (CAMP_ID, "[TEST] SG-5b handel Grodu"),
    )
    loc_id = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (location_key,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, current_location_id, session_flags) "
        "VALUES (?, ?, ?)",
        (CAMP_ID, loc_id, json.dumps({"ingame_hours": 12})),
    )
    for hid, race, name in (
        (HERO_DWARF, "dwarf", "[TEST] Krasnolud"),
        (HERO_HUMAN, "human", "[TEST] Człowiek"),
    ):
        conn.execute(
            "INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, "
            "gold_gp, race, status, is_active) "
            "VALUES (?, ?, 1, ?, 'fantasy', ?, 2000, ?, 'in_campaign', 1)",
            (hid, CAMP_ID, name, SHEET, race),
        )
    conn.commit()


def move_to(conn: sqlite3.Connection, location_key: str) -> None:
    loc_id = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (location_key,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
        (loc_id, CAMP_ID),
    )
    conn.commit()


def run_shop(conn: sqlite3.Connection, npc_key: str, location_key: str, test_key: str,
             test_type: str) -> list[str]:
    from app.services import shop_service

    problems: list[str] = []
    npc = conn.execute("SELECT id, label, faction_key FROM npcs WHERE key = ?", (npc_key,)).fetchone()
    npc_id = int(npc["id"])

    print(f"\n=== {npc['label']} @ {location_key} (frakcja: {npc['faction_key'] or '—'})")

    prices = {}
    for hid, race in ((HERO_HUMAN, "człowiek"), (HERO_DWARF, "krasnolud")):
        inv = shop_service.get_shop_inventory(npc_id, hid, location_key=location_key)
        if not inv["items"]:
            problems.append(f"{npc_key}: pusty asortyment w podglądzie")
            return problems
        row = next((i for i in inv["items"] if i["key"] == test_key), None)
        if row is None:
            problems.append(f"{npc_key}: {test_key} nie widoczny w sklepie")
            return problems
        print(f"  widok sklepu ({race:9s}): pozycji {len(inv['items']):2d} | "
              f"{row['label']} = {row['buy_price_gp']} gp (bazowo {row['value_gp']}) | "
              f"mnożnik {inv['buy_multiplier']}")
        prices[race] = row["buy_price_gp"]

    # Realne kupno + sprzedaż tego samego przedmiotu, oba bohaterowie.
    for hid, race in ((HERO_HUMAN, "człowiek"), (HERO_DWARF, "krasnolud")):
        g0 = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (hid,)).fetchone()[0]
        bought = shop_service.buy_item(hid, npc_id, test_type, test_key)
        if bought["paid_gp"] != prices[race]:
            problems.append(
                f"{npc_key}/{race}: podgląd {prices[race]} gp ≠ zapłacono {bought['paid_gp']} gp"
            )
        inv_row = conn.execute(
            "SELECT id FROM character_inventory WHERE character_id = ? "
            "ORDER BY id DESC LIMIT 1", (hid,),
        ).fetchone()
        sold = shop_service.sell_item(hid, int(inv_row["id"]), npc_id=npc_id)
        g1 = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (hid,)).fetchone()[0]
        print(f"  transakcja ({race:9s}): kupno −{bought['paid_gp']} gp, "
              f"sprzedaż +{sold['earned_gp']} gp | złoto {g0} → {g1}")
        if sold["earned_gp"] >= bought["paid_gp"]:
            problems.append(f"{npc_key}/{race}: sprzedaż ≥ kupno (arbitraż!)")

    if prices["krasnolud"] >= prices["człowiek"]:
        problems.append(f"{npc_key}: krasnolud nie ma taniej ({prices})")
    else:
        pct = 100 * (1 - prices["krasnolud"] / prices["człowiek"])
        print(f"  ZNIŻKA KRASNOLUDA: {prices['człowiek']} → {prices['krasnolud']} gp "
              f"({pct:.1f}% taniej)")
    return problems


def run_reputation(conn: sqlite3.Connection) -> list[str]:
    """#1103 — mnożnik reputacji per frakcja MUSI wchodzić w cenę u Helgi."""
    from app.services import shop_service, reputation_service

    problems: list[str] = []
    npc_id = int(conn.execute("SELECT id FROM npcs WHERE key='helga_solnobroda'").fetchone()[0])
    region = reputation_service.resolve_region(conn, CAMP_ID)
    print(f"\n=== reputacja (region rozpoznany jako: {region})")

    base = shop_service.combined_buy_multiplier(conn, HERO_HUMAN, npc_id, "item")
    reputation_service.adjust_reputation(
        conn, HERO_HUMAN, "solnobrodzi", 60, scope_type="faction", reason="test SG-5b"
    )
    conn.commit()
    after = shop_service.combined_buy_multiplier(conn, HERO_HUMAN, npc_id, "item")
    fac_mult = reputation_service.get_faction_shop_multiplier(conn, HERO_HUMAN, "solnobrodzi")
    print(f"  mnożnik ceny przed: {base} → po +60 rep u Solnobrodych: {after} "
          f"(sam mnożnik frakcji: {fac_mult})")
    if after >= base:
        problems.append("reputacja frakcji NIE obniża ceny")
    conn.execute(
        "DELETE FROM character_reputation WHERE character_id = ? AND scope_key = 'solnobrodzi'",
        (HERO_HUMAN,),
    )
    conn.commit()
    return problems


def run_services(conn: sqlite3.Connection) -> list[str]:
    from app.services.location_services import get_services_catalog, buy_service

    problems: list[str] = []
    print("\n=== usługi (naprawa / nocleg)")
    for loc, must in (("grod_wielka_kuznia", "blacksmith_repair"),
                      ("grod_pod_rdzawym_mlotem", "inn_night")):
        cat = get_services_catalog(conn, loc, HERO_DWARF)
        keys = [i["key"] for i in cat["items"]]
        print(f"  {loc:26s} → {', '.join(keys) or '(brak)'}")
        if must not in keys:
            problems.append(f"{loc}: brak usługi {must}")
    g0 = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (HERO_DWARF,)).fetchone()[0]
    res = buy_service(conn, HERO_DWARF, "blacksmith_repair")
    print(f"  zakup naprawy u kowala: −{res['paid_gp']} gp ({g0} → {res['gold_gp']})")
    if res["gold_gp"] != g0 - res["paid_gp"]:
        problems.append("naprawa: złoto nie zgadza się po zakupie")
    return problems


def run_dwarf_repair(conn: sqlite3.Connection) -> list[str]:
    """#969 „kowalskie oko" — akcja Reperuj: przywraca trwałość za 20 gp."""
    problems: list[str] = []
    print("\n=== naprawa krasnoluda (akcja Reperuj, #969)")
    conn.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, quantity, source, "
        "durability_current, durability_max) VALUES (?, 'warhammer', 1, 'test', 3, 20)",
        (HERO_DWARF,),
    )
    conn.commit()
    from app.api.characters import DWARF_REPAIR_COST_GP
    from fastapi.testclient import TestClient
    from app.main import app

    before = conn.execute(
        "SELECT durability_current FROM character_inventory WHERE character_id = ? "
        "ORDER BY id DESC LIMIT 1", (HERO_DWARF,),
    ).fetchone()[0]
    client = TestClient(app)
    # Prawdziwa ścieżka gracza: logowanie demo/demo → Bearer token → akcja Reperuj.
    login = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
    token = (login.json() or {}).get("access_token") if login.status_code == 200 else None
    if not token:
        problems.append(f"logowanie demo nieudane: HTTP {login.status_code}")
        return problems
    r = client.post(
        f"/api/characters/{HERO_DWARF}/dwarf-repair",
        json={}, headers={"Authorization": f"Bearer {token}"},
    )
    after_row = conn.execute(
        "SELECT durability_current, durability_max FROM character_inventory "
        "WHERE character_id = ? ORDER BY id DESC LIMIT 1", (HERO_DWARF,),
    ).fetchone()
    print(f"  HTTP {r.status_code} | trwałość {before} → {after_row['durability_current']}"
          f"/{after_row['durability_max']} | koszt {DWARF_REPAIR_COST_GP} gp")
    if r.status_code != 200:
        problems.append(f"dwarf-repair: HTTP {r.status_code} — {r.text[:200]}")
    elif after_row["durability_current"] != after_row["durability_max"]:
        problems.append("dwarf-repair: trwałość nie wróciła do maksimum")
    else:
        print(f"  odpowiedź: {r.json().get('message') or r.json()}")
    return problems


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    problems: list[str] = []
    try:
        setup(conn, "grod_wielka_kuznia")
        problems += run_shop(conn, "torvin_mistrz_kuzni", "grod_wielka_kuznia",
                             "warhammer", "weapon")
        move_to(conn, "grod_targ_solny")
        problems += run_shop(conn, "helga_solnobroda", "grod_targ_solny",
                             "climbing_kit", "item")
        problems += run_reputation(conn)
        move_to(conn, "grod_pod_rdzawym_mlotem")
        problems += run_shop(conn, "grimm_rdzawy", "grod_pod_rdzawym_mlotem",
                             "sobering_draught", "consumable")
        problems += run_services(conn)
        problems += run_dwarf_repair(conn)
    finally:
        cleanup(conn)
        conn.close()
    print("\n" + ("WERYFIKACJA OK" if not problems
                  else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
