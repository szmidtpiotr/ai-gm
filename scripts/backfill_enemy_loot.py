#!/usr/bin/env python3
"""Backfill tier-based loot for enemies that were approved before the
tier-loot autogen feature (commit 38f8b9b) and ended up with an empty
loot table.

Targets: enemies where review_status='permanent' AND loot_table_key IS
NOT NULL AND the assigned loot table has zero entries.

Idempotent — re-running on an already-populated table is a no-op.

Run inside the dev backend container:

    docker exec -i ai-gm-dev-backend-1 python3 - < scripts/backfill_enemy_loot.py

Or with --dry-run to just print what would change:

    docker exec -i ai-gm-dev-backend-1 python3 - --dry-run < scripts/backfill_enemy_loot.py
"""

from __future__ import annotations

import os
import sys
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
DRY_RUN = "--dry-run" in sys.argv

sys.path.insert(0, "/app")
from app.services.world_service import (  # noqa: E402
    _TIER_LOOT_RECIPES,
    roll_loot_preview_for_tier,
    _populate_loot_table_for_tier,
)


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    candidates = conn.execute(
        """
        SELECT e.key, e.label, e.tier, e.drop_chance, e.loot_table_key,
               (SELECT COUNT(*) FROM game_config_loot_entries
                WHERE loot_table_key = e.loot_table_key) AS entries
        FROM game_config_enemies e
        WHERE e.review_status = 'permanent'
          AND e.loot_table_key IS NOT NULL
        ORDER BY e.tier, e.key
        """
    ).fetchall()

    empty_tables = [dict(r) for r in candidates if int(r["entries"] or 0) == 0]

    print(f"Found {len(empty_tables)} enemy(ies) with empty loot tables "
          f"(out of {len(candidates)} approved enemies with loot tables).")
    if not empty_tables:
        return 0

    for r in empty_tables:
        print(f"  [{r['tier']:<8}] {r['key']:<40} (label='{r['label']}', "
              f"drop_chance={r['drop_chance']}, table={r['loot_table_key']})")

    if DRY_RUN:
        print("\n--dry-run: would populate the tables above. No changes made.")
        return 0

    print()
    populated = 0
    drop_chance_set = 0
    gold_set = 0
    populated_tables: set[str] = set()  # dedup: multiple enemies can share a loot_table_key
    for r in empty_tables:
        tier = (r["tier"] or "standard").lower()
        recipe = _TIER_LOOT_RECIPES.get(tier, _TIER_LOOT_RECIPES["standard"])
        lt_key = r["loot_table_key"]

        # 1) Populate entries via the same helper the on-approve path uses.
        # Skip if we already populated this table for an earlier enemy
        # sharing the same loot_table_key (use that enemy's tier).
        if lt_key not in populated_tables:
            _populate_loot_table_for_tier(conn, lt_key, tier)
            entries_after = conn.execute(
                "SELECT COUNT(*) AS n FROM game_config_loot_entries WHERE loot_table_key = ?",
                (lt_key,),
            ).fetchone()["n"]
            if entries_after > 0:
                populated += 1
                populated_tables.add(lt_key)
                print(f"  ✓ {r['key']:<40}  +{entries_after} entries → {lt_key}")
            else:
                print(f"  ⚠ {r['key']:<40}  recipe produced 0 picks (catalog?)")
        else:
            print(f"  · {r['key']:<40}  (shares {lt_key}, already populated)")

        # 2) Update drop_chance from tier if still at default 1.0
        if r["drop_chance"] is not None and abs(float(r["drop_chance"]) - 1.0) < 1e-6:
            conn.execute(
                "UPDATE game_config_enemies SET drop_chance = ? WHERE key = ?",
                (float(recipe["drop_chance"]), r["key"]),
            )
            drop_chance_set += 1

        # 3) Set gold range on the loot table if it's still at default 0/0
        lt_row = conn.execute(
            "SELECT gold_min, gold_max FROM game_config_loot_tables WHERE key = ?", (lt_key,),
        ).fetchone()
        if lt_row and int(lt_row["gold_min"] or 0) == 0 and int(lt_row["gold_max"] or 0) == 0:
            gmin, gmax = recipe["gold"]
            conn.execute(
                "UPDATE game_config_loot_tables SET gold_min = ?, gold_max = ?, "
                "updated_at = datetime('now') WHERE key = ?",
                (int(gmin), int(gmax), lt_key),
            )
            gold_set += 1

    conn.commit()
    conn.close()

    print()
    print(f"Done. Populated {populated} loot tables, "
          f"set drop_chance on {drop_chance_set} enemies, "
          f"set gold range on {gold_set} tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
