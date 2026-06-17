"""Seed LB3 — re-spec krypta_probna jako ONBOARDING loch.

Decyzja LB-3: tile_count=3, 2 komnaty walki (1 wróg/komnata), boss ~18 PŻ,
rest_heal_pct=100, rest_charges=0 (unlimited). Cel clear ~78-85% solo lvl1.

Run inside dev backend container:
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_lb3_krypta_probna_onboarding.py

Idempotent: INSERT OR IGNORE dla nowych rekordów, warunkowy UPDATE dungeonu.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


# Boss designed for D1 scaling:
#   HP = max(1, round(40 * 0.45)) + con_mod(0) * 3 = 18 PŻ
#   attack = round(4 * 0.45) + 3//2 = 2 + 1 = 3
#   damage = 1d6 (unchanged at D1)
#   AC = min(14, 10 + round((14-10)*0.45)) = 12
BOSS_ENEMY = {
    "key": "krypta_opiekun",
    "label": "Strażnik Grobowca",
    "hp_base": 40,
    "ac_base": 14,
    "attack_bonus": 4,
    "damage_die": "1d6",
    "damage_bonus": 1,
    "dex_modifier": 0,
    "tier": "boss",
    "attacks_per_turn": 1,
    "damage_type": "physical",
    "xp_award": 30,
    "stats_json": json.dumps({"STR": 12, "DEX": 10, "CON": 10, "INT": 8, "WIS": 10, "CHA": 8, "LCK": 10}),
    "description": "Prastary opiekun grobowca — upiór w zbroi, budzący się na dźwięk intruzów.",
    "review_status": "permanent",
}

BOSS_TILE = {
    "category_key": "krypta",
    "label": "Komnata Strażnika",
    "doors_json": json.dumps(["N", "S", "E", "W"]),
    "enemies_json": json.dumps([{"enemy_key": "krypta_opiekun", "count": 1}]),
    "items_json": json.dumps([]),
    "active_states_json": json.dumps([]),
    "exit_conditions_json": json.dumps([{"type": "enemies_cleared"}]),
    "room_description": (
        "Starożytna komnata strażnika. Spoczywający tu od wieków upiór budzi się "
        "na dźwięk waszych kroków — ostatnia linia obrony tego grobowca."
    ),
    "is_boss_tile": 1,
    "is_active": 1,
}

# New krypta_probna config (LB3)
KRYPTA_PROBNA_UPDATE = {
    "tile_count": 3,
    "rest_heal_pct": 100,
    "rest_charges": 0,
    "min_level": 1,
}


def seed(conn: sqlite3.Connection) -> None:
    # ── 1. krypta_opiekun enemy ──────────────────────────────────────────────────
    existing_enemy = conn.execute(
        "SELECT key FROM game_config_enemies WHERE key = ?", (BOSS_ENEMY["key"],)
    ).fetchone()
    if existing_enemy:
        print(f"[SKIP] Enemy '{BOSS_ENEMY['key']}' already exists")
    else:
        conn.execute(
            """INSERT INTO game_config_enemies
               (key, label, hp_base, ac_base, attack_bonus, damage_die, damage_bonus,
                dex_modifier, tier, attacks_per_turn, damage_type, xp_award,
                stats_json, description, review_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                BOSS_ENEMY["key"], BOSS_ENEMY["label"], BOSS_ENEMY["hp_base"],
                BOSS_ENEMY["ac_base"], BOSS_ENEMY["attack_bonus"], BOSS_ENEMY["damage_die"],
                BOSS_ENEMY["damage_bonus"], BOSS_ENEMY["dex_modifier"], BOSS_ENEMY["tier"],
                BOSS_ENEMY["attacks_per_turn"], BOSS_ENEMY["damage_type"], BOSS_ENEMY["xp_award"],
                BOSS_ENEMY["stats_json"], BOSS_ENEMY["description"], BOSS_ENEMY["review_status"],
            ),
        )
        conn.commit()
        print(f"[OK] Enemy '{BOSS_ENEMY['key']}' created (hp_base=40 → ~18 HP at D1)")

    # ── 2. Boss tile "Komnata Strażnika" ────────────────────────────────────────
    existing_tile = conn.execute(
        "SELECT id FROM dungeon_tiles WHERE category_key = ? AND label = ? AND is_boss_tile = 1",
        (BOSS_TILE["category_key"], BOSS_TILE["label"]),
    ).fetchone()
    if existing_tile:
        boss_tile_id = existing_tile["id"]
        print(f"[SKIP] Boss tile '{BOSS_TILE['label']}' already exists (id={boss_tile_id})")
    else:
        conn.execute(
            """INSERT INTO dungeon_tiles
               (category_key, label, doors_json, enemies_json, items_json,
                active_states_json, exit_conditions_json, room_description,
                is_boss_tile, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                BOSS_TILE["category_key"], BOSS_TILE["label"], BOSS_TILE["doors_json"],
                BOSS_TILE["enemies_json"], BOSS_TILE["items_json"],
                BOSS_TILE["active_states_json"], BOSS_TILE["exit_conditions_json"],
                BOSS_TILE["room_description"], BOSS_TILE["is_boss_tile"], BOSS_TILE["is_active"],
            ),
        )
        conn.commit()
        boss_tile_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        print(f"[OK] Boss tile '{BOSS_TILE['label']}' created (id={boss_tile_id})")

    # ── 3. Update krypta_probna → ONBOARDING config ─────────────────────────────
    current = conn.execute(
        "SELECT tile_count, rest_heal_pct, rest_charges, min_level, boss_tile_id "
        "FROM game_dungeons WHERE key = 'krypta_probna'",
    ).fetchone()

    if not current:
        print("[ERROR] krypta_probna not found in game_dungeons — run seed_l16_krypta_probna.py first")
        return

    needs_update = (
        int(current["tile_count"] or 0) != KRYPTA_PROBNA_UPDATE["tile_count"]
        or int(current["rest_heal_pct"] or 20) != KRYPTA_PROBNA_UPDATE["rest_heal_pct"]
        or int(current["rest_charges"] or 2) != KRYPTA_PROBNA_UPDATE["rest_charges"]
        or int(current["boss_tile_id"] or 0) != boss_tile_id
    )

    if not needs_update:
        print("[SKIP] krypta_probna already up-to-date (LB3)")
    else:
        conn.execute(
            """UPDATE game_dungeons SET
                tile_count = ?,
                rest_heal_pct = ?,
                rest_charges = ?,
                min_level = ?,
                boss_tile_id = ?,
                boss_enemy = ?
               WHERE key = 'krypta_probna'""",
            (
                KRYPTA_PROBNA_UPDATE["tile_count"],
                KRYPTA_PROBNA_UPDATE["rest_heal_pct"],
                KRYPTA_PROBNA_UPDATE["rest_charges"],
                KRYPTA_PROBNA_UPDATE["min_level"],
                boss_tile_id,
                BOSS_ENEMY["key"],
            ),
        )
        conn.commit()
        print(
            f"[OK] krypta_probna updated: tile_count=3, rest_heal_pct=100, "
            f"rest_charges=0, boss_tile_id={boss_tile_id}, boss_enemy='krypta_opiekun'"
        )

    # ── 4. Verify ─────────────────────────────────────────────────────────────────
    row = conn.execute(
        "SELECT tile_count, rest_heal_pct, rest_charges, min_level, boss_tile_id, boss_enemy "
        "FROM game_dungeons WHERE key = 'krypta_probna'"
    ).fetchone()
    print(
        f"\n[VERIFY] krypta_probna: tile_count={row['tile_count']}, "
        f"min_level={row['min_level']}, rest_heal_pct={row['rest_heal_pct']}, "
        f"rest_charges={row['rest_charges']}, boss_tile_id={row['boss_tile_id']}, "
        f"boss_enemy={row['boss_enemy']}"
    )

    tile = conn.execute(
        "SELECT id, label, is_boss_tile, enemies_json FROM dungeon_tiles WHERE id = ?",
        (row["boss_tile_id"],),
    ).fetchone()
    if tile:
        print(f"[VERIFY] Boss tile: id={tile['id']} '{tile['label']}' "
              f"is_boss={tile['is_boss_tile']} enemies={tile['enemies_json']}")
    else:
        print(f"[WARN] Boss tile id={row['boss_tile_id']} not found!")

    print("\nDone. LB3 complete.")


if __name__ == "__main__":
    with _conn() as conn:
        seed(conn)
