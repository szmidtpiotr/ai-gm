#!/usr/bin/env python3
"""SG-6b (#1481) — twarda weryfikacja treści bojowej i plotek Siwych Grań.

Nie sprawdza „czy wiersz jest w bazie" tylko PRZEPUSZCZA REALNE LOSOWANIA przez
oba tory silnika spotkań (kompozytor + katalog scen) na prawdziwych hexach mapy,
a plotkę wyciąga tą samą funkcją, której używa gra w karczmie.

Kontrolowane:
  1. każdy teren krainy oddaje spotkanie i jest ono z KRAINY (nie generyczny wilk),
  2. wrogowie krainy NIE pojawiają się na hexach innych krain (próba na Kresach),
  3. zamarznięci pielgrzymi wychodzą WYŁĄCZNIE na hexach sanktuarium,
  4. plotka z puli regionu realnie trafia do bohatera w szynku.

    docker cp scripts/verify_siwe_granie_bestia.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/verify_siwe_granie_bestia.py
"""
from __future__ import annotations

import json
import sqlite3
import sys

sys.path.insert(0, "/app")

DB = "/data/ai_gm.db"
REGION = "siwe_granie"
CAMP_ID = 77779903
HERO = 99990904
DRAWS = 40

SHEET = json.dumps(
    {"level": 5, "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10,
                           "CHA": 10, "LCK": 10},
     "hp": {"current": 40, "max": 40}, "archetype": "warrior", "__sg6b_test__": True},
    ensure_ascii=False,
)


def cleanup(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM character_rumors WHERE character_id = ?", (HERO,))
    conn.execute("DELETE FROM characters WHERE id = ?", (HERO,))
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (CAMP_ID,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (CAMP_ID,))
    conn.commit()


def setup(conn: sqlite3.Connection) -> None:
    cleanup(conn)
    conn.execute(
        "INSERT INTO campaigns (id, title, status, system_id, model_id, owner_user_id) "
        "VALUES (?, '[TEST] SG-6b bestia', 'active', 'fantasy', 'test', 1)", (CAMP_ID,))
    loc = conn.execute(
        "SELECT id FROM game_locations WHERE key = 'grod_pod_rdzawym_mlotem'").fetchone()[0]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, current_location_id, session_flags) "
        "VALUES (?, ?, ?)", (CAMP_ID, loc, json.dumps({"ingame_hours": 20})))
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, "
        "gold_gp, race, status, is_active) VALUES (?, ?, 1, '[TEST] Wedrowiec', 'fantasy', "
        "?, 500, 'dwarf', 'in_campaign', 1)", (HERO, CAMP_ID, SHEET))
    conn.commit()


def sample_hex(conn: sqlite3.Connection, region: str, hex_type: str):
    return conn.execute(
        "SELECT q, r, hex_type, region, encounter_pool FROM world_hexes "
        "WHERE region = ? AND hex_type = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
        (region, hex_type),
    ).fetchone()


def draw_both_tracks(conn, hex_row, level: int) -> dict[str, int]:
    """Losuj wielokrotnie OBA tory (kompozytor + katalog) dla danego hexa."""
    from app.services import encounter_service as es
    from app.services import encounter_catalog_service as cat

    hex_data = dict(hex_row)
    try:
        hex_data["encounter_pool"] = json.loads(hex_row["encounter_pool"] or "[]")
    except Exception:
        hex_data["encounter_pool"] = []
    seen: dict[str, int] = {}
    for _ in range(DRAWS):
        enc = es.compose_travel_encounter(conn, CAMP_ID, hex_data)
        for e in (enc or {}).get("enemies", []):
            seen[e["enemy_key"]] = seen.get(e["enemy_key"], 0) + 1
        row = cat.draw_combat(conn, hex_row["hex_type"], level,
                              region=hex_row["region"])
        if row:
            for e in (row.get("payload") or {}).get("enemies", []):
                seen[e["enemy_key"]] = seen.get(e["enemy_key"], 0) + 1
    return seen


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    problems: list[str] = []
    try:
        setup(conn)
        region_enemies = {
            r[0] for r in conn.execute(
                "SELECT key FROM game_config_enemies WHERE region_tag = ?", (REGION,))
        }
        print(f"wrogowie krainy: {', '.join(sorted(region_enemies))}\n")

        # 1 — każdy teren krainy oddaje spotkanie i to KRAINOWE
        print(f"{'teren':14s} {'hex':12s} {'spotkani wrogowie (x razy na %d losowań)' % DRAWS}")
        print("-" * 96)
        for hex_type in ("grania", "przelecz", "tundra", "lodowiec", "siarka",
                         "hills", "heath", "road", "bridge", "ruins"):
            hx = sample_hex(conn, REGION, hex_type)
            if not hx:
                print(f"{hex_type:14s} {'—':12s} brak takiego hexa w krainie")
                continue
            seen = draw_both_tracks(conn, hx, 5)
            if not seen:
                problems.append(f"{hex_type}: ZERO spotkań na {DRAWS} losowań")
                print(f"{hex_type:14s} ({hx['q']},{hx['r']})".ljust(27) + "PUSTO")
                continue
            regional = sum(v for k, v in seen.items() if k in region_enemies)
            share = 100 * regional / sum(seen.values())
            top = ", ".join(f"{k}×{v}" for k, v in
                            sorted(seen.items(), key=lambda kv: -kv[1])[:4])
            print(f"{hex_type:14s} ({hx['q']},{hx['r']})".ljust(27) +
                  f"{top}   [krainowe {share:.0f}%]")
            # Próg to OBECNOŚĆ, nie dominacja: globalny bestiariusz (orki, bandyci,
            # wyverny) ma prawo pojawiać się wszędzie — kraina ma dokładać swoje,
            # nie wypierać reszty. Udział wypisujemy do oceny klimatu przez człowieka.
            if regional == 0:
                problems.append(f"{hex_type}: ZERO spotkań z treści krainy")

        # 2 — szczelność: wrogowie Grań NIE mogą wyjść na Kresy
        print("\nkontrola szczelności (te same terenowo hexy, ale region 'kresy'):")
        for hex_type in ("hills", "road", "heath", "ruins"):
            hx = sample_hex(conn, "kresy", hex_type)
            if not hx:
                continue
            seen = draw_both_tracks(conn, hx, 5)
            leaked = sorted(k for k in seen if k in region_enemies)
            print(f"  {hex_type:8s} ({hx['q']},{hx['r']}): "
                  f"{'WYCIEK ' + ', '.join(leaked) if leaked else 'czysto'} "
                  f"({len(seen)} różnych wrogów)")
            if leaked:
                problems.append(f"kresy/{hex_type}: wyciekli {leaked}")

        # 3 — pielgrzymi tylko przy sanktuarium
        print("\nzamarznięci pielgrzymi (world_scope='pool'):")
        sanct = conn.execute(
            "SELECT q, r, hex_type, region, encounter_pool FROM world_hexes "
            "WHERE q = 36 AND r = -65 AND map_level = 0").fetchone()
        far = conn.execute(
            "SELECT q, r, hex_type, region, encounter_pool FROM world_hexes "
            "WHERE region = ? AND hex_type = 'lodowiec' AND map_level = 0 "
            "AND (q - 36) * (q - 36) + (r + 65) * (r + 65) > 400 LIMIT 1", (REGION,)).fetchone()
        s_seen = draw_both_tracks(conn, sanct, 4) if sanct else {}
        f_seen = draw_both_tracks(conn, far, 4) if far else {}
        print(f"  hex sanktuarium ({sanct['q']},{sanct['r']}): "
              f"pielgrzym ×{s_seen.get('zamarzniety_pielgrzym', 0)}")
        print(f"  lodowiec z dala ({far['q']},{far['r']}): "
              f"pielgrzym ×{f_seen.get('zamarzniety_pielgrzym', 0)}")
        if not s_seen.get("zamarzniety_pielgrzym"):
            problems.append("pielgrzymi nie pojawiają się przy sanktuarium")
        if f_seen.get("zamarzniety_pielgrzym"):
            problems.append("pielgrzymi wyciekli poza sanktuarium")

        # 4 — plotka z puli regionu w szynku
        print("\nplotki w szynku (pula regionu ma 60% pierwszeństwa):")
        from app.services import rumor_service
        from app.services.reputation_service import resolve_region
        print(f"  region rozpoznany w szynku: {resolve_region(conn, CAMP_ID)}")
        from_pool = 0
        for _ in range(10):
            r = rumor_service.eavesdrop_rumor(CAMP_ID, HERO, conn=conn)
            if not r:
                continue
            row = conn.execute(
                "SELECT source_type, rumor_text FROM character_rumors WHERE id = ?",
                (r["rumor_id"],)).fetchone()
            if row and row["source_type"] == "world":
                from_pool += 1
                if from_pool <= 2:
                    print(f"    „{row['rumor_text'][:88]}…”")
        print(f"  plotek z puli krainy: {from_pool}/10 podsłuchów")
        if from_pool == 0:
            problems.append("żadna plotka nie przyszła z puli regionu")
    finally:
        cleanup(conn)
        conn.close()
    print("\n" + ("WERYFIKACJA OK" if not problems
                  else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
