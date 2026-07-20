#!/usr/bin/env python3
"""SG-5c — twarda weryfikacja WSZYSTKICH sklepów w grze.

Dla każdego aktywnego kupca: stawia bohatera testowego w JEGO lokacji, otwiera
okno sklepu przez silnik (`get_shop_inventory`), po czym realnie KUPUJE pierwszą
pozycję i sprzedaje ją z powrotem. Wyłapuje dokładnie te awarie, których raport
statyczny nie zobaczy:
  * rozjazd podgląd ↔ kupno (`item_not_in_shop`) — kluczowe po zmianie doboru
    towaru, bo obie ścieżki liczą listę osobno,
  * pusty sklep po filtrach poziomu/lokacji,
  * cena z podglądu inna niż pobrana.

Kupcy gildyjni (#1342) mają własny silnik komponentów i są pomijani (raportowane).
Po teście sprząta bohatera i kampanię.

    docker cp scripts/verify_all_shops.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/verify_all_shops.py
"""
from __future__ import annotations

import json
import sqlite3
import sys

sys.path.insert(0, "/app")

DB = "/data/ai_gm.db"
CAMP_ID = 77779902
HERO = 99990903

SHEET = json.dumps(
    {
        "level": 10,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "hp": {"current": 60, "max": 60},
        "archetype": "warrior",
        "__sg5c_test__": True,
    },
    ensure_ascii=False,
)


def cleanup(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (HERO,))
    conn.execute("DELETE FROM characters WHERE id = ?", (HERO,))
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (CAMP_ID,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (CAMP_ID,))
    conn.commit()


def setup(conn: sqlite3.Connection) -> None:
    cleanup(conn)
    conn.execute(
        "INSERT INTO campaigns (id, title, status, system_id, model_id, owner_user_id) "
        "VALUES (?, '[TEST] SG-5c sklepy', 'active', 'fantasy', 'test', 1)",
        (CAMP_ID,),
    )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, current_location_id, session_flags) "
        "VALUES (?, NULL, ?)",
        (CAMP_ID, json.dumps({"ingame_hours": 12})),
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, "
        "gold_gp, race, status, is_active) "
        "VALUES (?, ?, 1, '[TEST] Kupujacy', 'fantasy', ?, 200000, 'human', 'in_campaign', 1)",
        (HERO, CAMP_ID, SHEET),
    )
    conn.commit()


def npc_home(conn: sqlite3.Connection, npc: sqlite3.Row) -> str | None:
    row = conn.execute(
        "SELECT a.location_key FROM location_npc_assignments a "
        "JOIN game_locations gl ON gl.key = a.location_key "
        "WHERE a.npc_key = ? AND COALESCE(a.is_active, 1) = 1 "
        "ORDER BY CASE gl.location_type WHEN 'sub' THEN 0 ELSE 1 END, a.rowid LIMIT 1",
        (str(npc["key"]),),
    ).fetchone()
    return str(row[0]) if row else None


def main() -> int:
    from app.services import shop_service

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    ok = skipped = 0
    problems: list[str] = []
    try:
        setup(conn)
        npcs = conn.execute(
            "SELECT id, key, label, COALESCE(is_guild_merchant, 0) AS guild "
            "FROM npcs WHERE is_shop = 1 AND is_active = 1 ORDER BY key"
        ).fetchall()
        print(f"{'kupiec':34s} {'lokacja':26s} {'poz':>3s} kupno/sprzedaż")
        print("-" * 92)
        for npc in npcs:
            name = (npc["label"] or npc["key"])[:33]
            if int(npc["guild"] or 0) == 1:
                skipped += 1
                print(f"{name:34s} {'—':26s}   —  pominięty (silnik gildii #1342)")
                continue
            loc = npc_home(conn, npc)
            if not loc:
                problems.append(f"{npc['key']}: kupiec nieprzypisany do żadnej lokacji")
                print(f"{name:34s} {'(brak przypisania)':26s}   —  BŁĄD")
                continue
            loc_id = conn.execute("SELECT id FROM game_locations WHERE key = ?", (loc,)).fetchone()[0]
            conn.execute(
                "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                (loc_id, CAMP_ID),
            )
            conn.commit()

            view = shop_service.get_shop_inventory(int(npc["id"]), HERO, location_key=loc)
            items = view["items"]
            if not items:
                problems.append(f"{npc['key']}: pusty sklep w {loc}")
                print(f"{name:34s} {loc[:25]:26s}   0  PUSTY")
                continue
            pick = items[0]
            try:
                bought = shop_service.buy_item(HERO, int(npc["id"]), pick["type"], pick["key"])
            except Exception as e:  # noqa: BLE001 — chcemy dokładny powód w raporcie
                problems.append(f"{npc['key']}: kupno {pick['key']} → {e}")
                print(f"{name:34s} {loc[:25]:26s} {len(items):3d}  BŁĄD KUPNA: {e}")
                continue
            if bought["paid_gp"] != pick["buy_price_gp"]:
                problems.append(
                    f"{npc['key']}: podgląd {pick['buy_price_gp']} ≠ zapłacono {bought['paid_gp']}"
                )
            inv_id = conn.execute(
                "SELECT id FROM character_inventory WHERE character_id = ? ORDER BY id DESC LIMIT 1",
                (HERO,),
            ).fetchone()[0]
            sold = shop_service.sell_item(HERO, int(inv_id), npc_id=int(npc["id"]))
            if sold["earned_gp"] >= bought["paid_gp"]:
                problems.append(f"{npc['key']}: sprzedaż ≥ kupno (arbitraż)")
            ok += 1
            print(f"{name:34s} {loc[:25]:26s} {len(items):3d}  "
                  f"{pick['label'][:22]:23s} −{bought['paid_gp']}/+{sold['earned_gp']} gp")
    finally:
        cleanup(conn)
        conn.close()
    print("-" * 92)
    print(f"sklepów przetestowanych transakcją: {ok} | pominiętych (gildia): {skipped} | "
          f"problemów: {len(problems)}")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
