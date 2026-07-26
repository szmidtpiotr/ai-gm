#!/usr/bin/env python3
"""MP-7 (#1494) — dowód na żywym silniku: odpoczynek na hexie `sol`.

Bez bukłaka = częściowy (leczy o połowę); z bukłakiem = pełny (bukłak zużyty).
Uruchamiane na KOPII bazy DEV (nie rusza żywych danych).

    docker cp scripts/verify_mp7_rest.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 sh -c 'cp /data/ai_gm.db /tmp/mp7.db && python /app/verify_mp7_rest.py /tmp/mp7.db'
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.rest_service import perform_long_rest


def _pick_sol_hex(conn):
    row = conn.execute(
        "SELECT q, r FROM world_hexes WHERE hex_type = 'sol' AND is_active = 1 LIMIT 1"
    ).fetchone()
    return (row["q"], row["r"]) if row else (None, None)


def _pick_character(conn):
    row = conn.execute(
        """SELECT c.id AS cid, s.campaign_id AS camp
           FROM characters c JOIN game_sessions s ON s.campaign_id = c.campaign_id
           LIMIT 1"""
    ).fetchone()
    return (row["cid"], row["camp"]) if row else (None, None)


def _setup(conn, cid, camp, q, r, *, with_skin):
    # bohater: mało HP/many, wysoki max — leczenie będzie dobrze widoczne
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (cid,)).fetchone()
    sheet = json.loads(row["sheet_json"] or "{}")
    sheet["current_hp"] = 1
    sheet["max_hp"] = 30
    sheet["current_mana"] = 0
    sheet["max_mana"] = 10
    sheet.setdefault("archetype", "warrior")
    sheet.setdefault("stats", {}).setdefault("CON", 10)
    sheet["conditions"] = []
    conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                 (json.dumps(sheet, ensure_ascii=False), cid))
    # pozycja: hex sol, brak lokacji-źródła wody, ale odpoczynek dozwolony (safe loc)
    safe = conn.execute(
        "SELECT id FROM game_locations WHERE safe_for_rest = 1 AND is_active = 1 "
        "AND key NOT LIKE 'solny_prog%' AND key != 'misja_swiatla' LIMIT 1"
    ).fetchone()
    loc_id = safe["id"] if safe else None
    sess = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ?", (camp,)
    ).fetchone()
    flags = json.loads(sess["session_flags"] or "{}")
    flags["current_hex"] = {"q": q, "r": r}
    flags.pop("fatigue_last_rest_day", None)   # skasuj bramkę „raz na dzień"
    flags.pop("camp_encounter_boost", None)    # bez losowego spotkania
    conn.execute(
        "UPDATE game_sessions SET session_flags = ?, current_location_id = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), loc_id, camp),
    )
    conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (camp,))
    conn.execute("DELETE FROM character_inventory WHERE character_id = ? AND item_key = 'waterskin'", (cid,))
    if with_skin:
        conn.execute(
            "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?, 'waterskin', 1)",
            (cid,),
        )
    conn.commit()


def _has_skin(conn, cid):
    r = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) n FROM character_inventory "
        "WHERE character_id = ? AND item_key = 'waterskin'", (cid,)
    ).fetchone()
    return int(r["n"])


def main(dbpath):
    conn = sqlite3.connect(dbpath)
    conn.row_factory = sqlite3.Row
    q, r = _pick_sol_hex(conn)
    cid, camp = _pick_character(conn)
    print(f"hex sol = ({q},{r}); bohater id={cid}, kampania={camp}")
    if q is None or cid is None:
        print("BRAK danych do testu"); return 1

    print("\n--- BEZ BUKŁAKA (oczekiwane: częściowy, ~połowa) ---")
    _setup(conn, cid, camp, q, r, with_skin=False)
    res = perform_long_rest(conn, cid, camp)
    print(f"  hp {res.get('hp_before')} -> {res.get('hp_after')} (z 30) | "
          f"mana {res.get('mana_before')} -> {res.get('mana_after')} (z 10)")
    print(f"  waterless_partial = {res.get('waterless_partial')} | teren = {res.get('water',{}).get('terrain')}")

    print("\n--- Z BUKŁAKIEM (oczekiwane: pełny, bukłak zużyty) ---")
    _setup(conn, cid, camp, q, r, with_skin=True)
    print(f"  bukłaki przed: {_has_skin(conn, cid)}")
    res = perform_long_rest(conn, cid, camp)
    print(f"  hp {res.get('hp_before')} -> {res.get('hp_after')} (z 30) | "
          f"mana {res.get('mana_before')} -> {res.get('mana_after')} (z 10)")
    print(f"  waterskin_consumed = {res.get('waterskin_consumed')} | bukłaki po: {_has_skin(conn, cid)}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mp7.db"))
