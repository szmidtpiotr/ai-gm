#!/usr/bin/env python3
"""Issue #1376 — spójny power-curve wrogów (bez inwersji tierów) + spójny loot.

Follow-up balansowy do #1346. Audyt bazy (64 global/permanent) wykrył:
  • inwersję elite/standard: 4 elity słabsze niż najsilniejszy standard (56.5),
  • cave_bear: standard L3-5 threat 56 = outlier pasma (leży w L6-10),
  • 28 wrogów z zaśmieconym loot_tier (poor/rich/treasure — słowa lochowe),
  • 6 wrogów dropiących 0 zł (per-enemy gold_max=0; złoto leci TYLKO z tabeli
    per-wróg, nie tierowej).

Ten seed:
  1. Podnosi 4 elity nad pasmo standard (stat bumpy zgodne z motywem),
  2. Rebanduje cave_bear L3-5 -> L6-10 standard,
  3. Zeruje (NULL) zaśmiecony loot_tier -> tier enum jedynym źródłem tabeli #1333,
  4. Ustawia gold na 6 zero-gold tabelach per-wróg.

Wartości = STARTING VALUES (Numbers Policy), strojlne w Sandboxie. Idempotentny.

Run inside dev backend container:
    docker exec -i ai-gm-dev-backend-1 python3 - < scripts/seed_powercurve_loot_1376.py
"""
from __future__ import annotations

import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# ── 1. Elity nad pasmo standard (threat >=60; motyw zachowany) ──
#   key: {kolumna: nowa_wartość}  (threat po zmianie w komentarzu)
ELITE_BUMPS = {
    "dark_priest":    {"hp_base": 42, "damage_die": "1d8", "damage_bonus": 1},  # 49.5 -> 60.5
    "witch":          {"hp_base": 42, "damage_bonus": 1},                       # 52.0 -> 61.0
    "troll":          {"hp_base": 45},                                          # 54.5 -> 64.5 (regen-tank)
    "shadow_stalker": {"attacks_per_turn": 2},                                  # 55.0 -> 66.0 (podwójny cios)
}

# ── 2. Reband cave_bear (duża bestia z L3-5 -> pasmo L6-10) ──
CAVE_BEAR = {"min_level": 6, "max_level": 10}

# ── 4. Gold na zero-gold tabelach per-wróg (gold leci tylko stąd) ──
#   loot_<key> : (gold_min, gold_max)  — per tier band
GOLD_FIX = {
    "loot_giant_rat":    (1, 5),    # weak
    "loot_skeleton":     (5, 15),   # standard
    "loot_wolf":         (5, 15),   # standard
    "loot_giant_spider": (5, 15),   # standard
    "loot_lizardman":    (5, 15),   # standard
    "loot_cave_bear":    (5, 15),   # standard (po rebandzie L6-10)
}

VALID_TIER = ("weak", "standard", "elite", "boss")


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. Elite bumps
    for key, cols in ELITE_BUMPS.items():
        sets = ", ".join(f"{c}=?" for c in cols)
        conn.execute(
            f"UPDATE game_config_enemies SET {sets}, updated_at=datetime('now') WHERE key=?",
            (*cols.values(), key),
        )
        print(f"  ~ elite bump {key:16s} {dict(cols)}")

    # 2. cave_bear reband
    conn.execute(
        "UPDATE game_config_enemies SET min_level=?, max_level=?, updated_at=datetime('now') WHERE key='cave_bear'",
        (CAVE_BEAR["min_level"], CAVE_BEAR["max_level"]),
    )
    print(f"  ~ reband cave_bear L3-5 -> L{CAVE_BEAR['min_level']}-{CAVE_BEAR['max_level']}")

    # 3. NULL zaśmiecony loot_tier (zachowaj poprawne tier-band słowa)
    cur = conn.execute(
        f"""UPDATE game_config_enemies SET loot_tier=NULL, updated_at=datetime('now')
            WHERE loot_tier IS NOT NULL
              AND LOWER(TRIM(loot_tier)) NOT IN ({",".join("?" * len(VALID_TIER))})""",
        VALID_TIER,
    )
    print(f"  ~ loot_tier NULL na {cur.rowcount} wrogach (zaśmiecone poor/rich/treasure)")

    # 4. Gold na zero-gold tabelach
    for lt_key, (gmin, gmax) in GOLD_FIX.items():
        cur = conn.execute(
            "UPDATE game_config_loot_tables SET gold_min=?, gold_max=?, updated_at=datetime('now') "
            "WHERE key=? AND (gold_max IS NULL OR gold_max=0)",
            (gmin, gmax, lt_key),
        )
        if cur.rowcount:
            print(f"  ~ gold {lt_key:20s} -> {gmin}-{gmax}")

    conn.commit()
    print("\nOK: power-curve + loot dostrojony (#1376).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
