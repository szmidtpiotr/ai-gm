#!/usr/bin/env python3
"""Seed buff conditions for buff potions to apply via add_condition.
Then backfill effect_json on buff potions + magical passive items.
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# ── Buff conditions ────────────────────────────────────────────────────────
# Schema: key, label, effect_json (mechanic blob), description, stackable, auto_remove
BUFF_CONDITIONS = [
    {
        "key": "strength_boost",
        "label": "Wzmocnienie siły",
        "description": "Mięśnie pieką ogniem, każdy cios pada cięższy. STR +2 na 5 rund.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "STR", "value": 2,
                 "expires": "duration_rounds:5"}
            ]
        },
        "auto_remove": "duration_rounds:5",
    },
    {
        "key": "giant_strength",
        "label": "Siła olbrzyma",
        "description": "Bohater podnosi wozy i wyrywa wrota z zawiasów. STR +4 na 3 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "STR", "value": 4,
                 "expires": "duration_rounds:3"}
            ]
        },
        "auto_remove": "duration_rounds:3",
    },
    {
        "key": "haste_boost",
        "label": "Pośpiech",
        "description": "Refleks wyostrzony, krok lekki. DEX +2 na 5 rund.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "DEX", "value": 2,
                 "expires": "duration_rounds:5"}
            ]
        },
        "auto_remove": "duration_rounds:5",
    },
    {
        "key": "stealth_boost",
        "label": "Cienie",
        "description": "Cienie garną się do bohatera, kroki są bezgłośne. DEX +2 na 5 rund.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "DEX", "value": 2,
                 "expires": "duration_rounds:5"}
            ]
        },
        "auto_remove": "duration_rounds:5",
    },
    {
        "key": "damage_resistance",
        "label": "Odporność",
        "description": "Skóra twardnieje, ciosy ślizgają się po niej. CON +2 na 5 rund.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "CON", "value": 2,
                 "expires": "duration_rounds:5"}
            ]
        },
        "auto_remove": "duration_rounds:5",
    },
]

# ── Items to backfill with effect_json ─────────────────────────────────────
# Buff potions (consumables) → apply_condition pointing at the new conditions.
ITEM_EFFECT_BACKFILL = {
    "potion_strength":       {"type": "apply_condition", "condition_key": "strength_boost"},
    "potion_giant_strength": {"type": "apply_condition", "condition_key": "giant_strength"},
    "potion_haste":          {"type": "apply_condition", "condition_key": "haste_boost"},
    "potion_stealth":        {"type": "apply_condition", "condition_key": "stealth_boost"},
    "potion_resistance":     {"type": "apply_condition", "condition_key": "damage_resistance"},
}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        # Insert/update conditions
        n_cond = 0
        for c in BUFF_CONDITIONS:
            conn.execute(
                """
                INSERT INTO game_config_conditions (key, label, effect_json, description, stackable, auto_remove, is_active)
                VALUES (?, ?, ?, ?, 0, ?, 1)
                ON CONFLICT(key) DO UPDATE SET
                    label = excluded.label,
                    effect_json = excluded.effect_json,
                    description = excluded.description,
                    auto_remove = excluded.auto_remove,
                    updated_at = datetime('now')
                """,
                (c["key"], c["label"], json.dumps(c["effect_json"], ensure_ascii=False),
                 c["description"], c["auto_remove"]),
            )
            n_cond += 1
        print(f"✓ Conditions seeded: {n_cond}")

        # Backfill effect_json on the buff potions
        n_item = 0
        for key, effect in ITEM_EFFECT_BACKFILL.items():
            payload = json.dumps({
                "schema_version": 1,
                "effect_category": "consumable_immediate",
                "effects": [effect],
            }, ensure_ascii=False)
            cur = conn.execute(
                "UPDATE game_config_items SET effect_json = ?, updated_at = datetime('now') WHERE key = ?",
                (payload, key),
            )
            if cur.rowcount:
                n_item += 1
        print(f"✓ Buff potions updated with effect_json: {n_item}")

        conn.commit()

        # Sanity
        for k in ITEM_EFFECT_BACKFILL.keys():
            row = conn.execute(
                "SELECT key, effect_json FROM game_config_items WHERE key = ?", (k,)
            ).fetchone()
            if row:
                print(f"  {row[0]:24s} → {row[1]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
