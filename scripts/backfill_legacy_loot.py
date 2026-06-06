#!/usr/bin/env python3
"""Backfill loot tables + tier for 9 legacy enemies that pre-date the new seed.
Idempotent."""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# Retiering + loot composition for legacy enemies based on their HP/role.
# (tier, gold_min, gold_max, drop_chance, [(slot, key, weight, qmin, qmax), ...])
LEGACY_LOOT = {
    "wolf": ("weak", 0, 2, 0.4, [
        ("consumables", "dried_meat", 35, 1, 1),
        ("items",       "wolf_pelt", 50, 1, 1),
        ("items",       "rope_hemp", 15, 1, 1),
    ]),
    "old_man": ("weak", 0, 3, 0.5, [
        ("consumables", "bread_loaf", 30, 1, 1),
        ("consumables", "apple", 25, 1, 1),
        ("items",       "pipeweed_pouch", 20, 1, 1),
        ("items",       "wax_candle", 25, 1, 2),
    ]),
    "skeleton": ("standard", 1, 6, 0.6, [
        ("weapons",     "dagger", 25, 1, 1),
        ("weapons",     "shortsword", 20, 1, 1),
        ("items",       "leather_cap", 15, 1, 1),
        ("consumables", "bandage", 10, 1, 1),
        ("items",       "silver_chalice", 5, 1, 1),
    ]),
    "bandit": ("standard", 2, 10, 0.75, [
        ("weapons",     "dagger", 25, 1, 1),
        ("weapons",     "shortsword", 20, 1, 1),
        ("weapons",     "handaxe", 15, 1, 1),
        ("consumables", "potion_healing_small", 20, 1, 1),
        ("consumables", "wineskin", 10, 1, 1),
        ("items",       "lockpicks", 8, 1, 1),
        ("items",       "belt_pouch", 12, 1, 1),
    ]),
    "guard": ("standard", 3, 12, 0.7, [
        ("weapons",     "longsword", 20, 1, 1),
        ("weapons",     "spear", 18, 1, 1),
        ("items",       "chainmail_shirt", 15, 1, 1),
        ("items",       "iron_helm", 18, 1, 1),
        ("items",       "kite_shield", 12, 1, 1),
        ("consumables", "potion_healing_small", 15, 1, 1),
    ]),
    "enemy": ("standard", 1, 8, 0.6, [
        ("weapons",     "club", 25, 1, 1),
        ("weapons",     "dagger", 20, 1, 1),
        ("consumables", "bandage", 20, 1, 1),
        ("items",       "torch", 20, 1, 1),
        ("consumables", "hardtack", 15, 1, 1),
    ]),
    "unknown_attacker": ("standard", 1, 8, 0.65, [
        ("weapons",     "dagger", 30, 1, 1),
        ("items",       "hooded_cloak", 20, 1, 1),
        ("consumables", "potion_stealth", 12, 1, 1),
        ("consumables", "smoke_bomb", 15, 1, 1),
        ("items",       "lockpicks", 13, 1, 1),
        ("items",       "silk_scarf", 10, 1, 1),
    ]),
    "orc": ("elite", 8, 30, 0.85, [
        ("weapons",     "battleaxe", 25, 1, 1),
        ("weapons",     "greataxe", 15, 1, 1),
        ("weapons",     "warhammer", 15, 1, 1),
        ("items",       "scale_mail", 15, 1, 1),
        ("items",       "round_shield", 15, 1, 1),
        ("consumables", "potion_healing_medium", 10, 1, 1),
        ("consumables", "dried_meat", 5, 1, 2),
    ]),
    "troll": ("elite", 12, 40, 0.9, [
        ("weapons",     "greataxe", 25, 1, 1),
        ("weapons",     "maul", 20, 1, 1),
        ("items",       "hide_armor", 15, 1, 1),
        ("items",       "demon_skull", 8, 1, 1),
        ("consumables", "potion_healing_medium", 15, 1, 1),
        ("consumables", "alchemist_fire", 10, 1, 1),
        ("items",       "golden_idol", 7, 1, 1),
    ]),
}

COL_BY_SLOT = {"items": "item_key", "consumables": "consumable_key", "weapons": "weapon_key"}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        n_tier = 0
        n_table = 0
        n_entries = 0
        for enemy_key, (tier, gmin, gmax, drop_chance, drops) in LEGACY_LOOT.items():
            # Retier + drop_chance
            cur = conn.execute(
                "UPDATE game_config_enemies SET tier = ?, drop_chance = ? WHERE key = ?",
                (tier, drop_chance, enemy_key),
            )
            if cur.rowcount:
                n_tier += 1

            # Loot table
            table_key = f"loot_{enemy_key}"
            conn.execute(
                """
                INSERT INTO game_config_loot_tables (key, label, description, gold_min, gold_max, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(key) DO UPDATE SET
                    gold_min = excluded.gold_min,
                    gold_max = excluded.gold_max,
                    description = excluded.description,
                    updated_at = datetime('now')
                """,
                (table_key, f"Łupy: {enemy_key}",
                 f"Tabela łupów dla {enemy_key} (tier {tier}, retiered).",
                 int(gmin), int(gmax)),
            )
            # Ensure enemy linked
            conn.execute(
                "UPDATE game_config_enemies SET loot_table_key = ? WHERE key = ?",
                (table_key, enemy_key),
            )
            # Wipe existing entries + reseed
            conn.execute(
                "DELETE FROM game_config_loot_entries WHERE loot_table_key = ?",
                (table_key,),
            )
            for slot, item_key, weight, qmin, qmax in drops:
                col = COL_BY_SLOT[slot]
                conn.execute(
                    f"""
                    INSERT INTO game_config_loot_entries
                        (loot_table_key, {col}, weight, qty_min, qty_max)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (table_key, item_key, int(weight), int(qmin), int(qmax)),
                )
                n_entries += 1
            n_table += 1
        conn.commit()
        print(f"✓ Retiered {n_tier} enemies, refreshed {n_table} loot tables ({n_entries} entries)")

        # Verification
        rows = conn.execute(
            """
            SELECT e.key, e.tier, e.loot_table_key,
                   (SELECT COUNT(*) FROM game_config_loot_entries le WHERE le.loot_table_key = e.loot_table_key) AS entries,
                   t.gold_min, t.gold_max
            FROM game_config_enemies e
            LEFT JOIN game_config_loot_tables t ON t.key = e.loot_table_key
            WHERE e.key IN %s
            ORDER BY e.tier, e.key
            """ % (str(tuple(LEGACY_LOOT.keys())),)
        ).fetchall()
        for r in rows:
            print(f"  {r[0]:18s} tier={r[1]:8s} table={r[2]:24s} entries={r[3]} gold={r[4]}-{r[5]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
