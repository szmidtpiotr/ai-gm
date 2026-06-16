"""Seed L16 — game_dungeons record 'krypta_probna' + world_hexes dungeon entry.

Run inside dev backend container:
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_l16_krypta_probna.py

Idempotent: skips records that already exist.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


DUNGEON = {
    "key": "krypta_probna",
    "label": "Krypta Próbna",
    "location_key": "krypta_grobowiec_hrabiego",
    "rooms": 6,
    "enemy_pool": json.dumps(["skeleton", "zombie", "ghoul", "ghost", "wraith"]),
    "boss_enemy": "lich",
    "loot_tier": "rich",
    "atmosphere": (
        "Starożytne katakumby wykute w litej skale. Fosforyzujące kości świecą w mroku, "
        "lodowate zimno przenika do szpiku. Echa kroków odbijają się od kamiennych ścian "
        "ozdobionych sarkofagami. Idealne miejsce na pierwsze starcie z nieumarłymi."
    ),
    "cooldown_hours": 72,
    "min_level": 3,
    "is_active": 1,
    "chest_loot_table_key": "loot_rich",
    "boss_loot_table_key": "loot_treasure",
    "room_loot_chance": 0.15,
    "room_types_json": json.dumps({"combat": 50, "chest": 15, "trap": 15, "riddle": 10, "rest": 10}),
    "riddle_source": "database",
    "riddle_max_hints": 2,
    "dungeon_difficulty": 2,   # D2 tier (stored as int; code does int(dungeon_difficulty))
    "tile_category_key": "krypta",
    "tile_count": 6,
    "boss_tile_id": 24,   # Tron Lisza (is_boss_tile=1)
    "endless_growth_n": 0,
}

# Hex coordinates for dungeon on world map
# Use q=-35, r=-7 (existing dungeon hex with no location_key)
HEX_Q = -35
HEX_R = -7


def seed(conn: sqlite3.Connection) -> None:
    # ── 1. game_dungeons record ────────────────────────────────────────────────
    existing = conn.execute(
        "SELECT key FROM game_dungeons WHERE key = ?", (DUNGEON["key"],)
    ).fetchone()
    if existing:
        print(f"[SKIP] Dungeon '{DUNGEON['key']}' already exists")
    else:
        conn.execute(
            """INSERT INTO game_dungeons
               (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier,
                atmosphere, cooldown_hours, min_level, is_active,
                chest_loot_table_key, boss_loot_table_key, room_loot_chance,
                room_types_json, riddle_source, riddle_max_hints,
                dungeon_difficulty, tile_category_key, tile_count,
                boss_tile_id, endless_growth_n)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                DUNGEON["key"],
                DUNGEON["label"],
                DUNGEON["location_key"],
                DUNGEON["rooms"],
                DUNGEON["enemy_pool"],
                DUNGEON["boss_enemy"],
                DUNGEON["loot_tier"],
                DUNGEON["atmosphere"],
                DUNGEON["cooldown_hours"],
                DUNGEON["min_level"],
                DUNGEON["is_active"],
                DUNGEON["chest_loot_table_key"],
                DUNGEON["boss_loot_table_key"],
                DUNGEON["room_loot_chance"],
                DUNGEON["room_types_json"],
                DUNGEON["riddle_source"],
                DUNGEON["riddle_max_hints"],
                DUNGEON["dungeon_difficulty"],
                DUNGEON["tile_category_key"],
                DUNGEON["tile_count"],
                DUNGEON["boss_tile_id"],
                DUNGEON["endless_growth_n"],
            ),
        )
        conn.commit()
        print(f"[OK] Dungeon '{DUNGEON['key']}' created (D2, krypta, tile_count=6, boss_tile_id=24)")

    # ── 2. world_hexes dungeon entry ──────────────────────────────────────────
    existing_hex = conn.execute(
        "SELECT id, location_key FROM world_hexes WHERE q = ? AND r = ?", (HEX_Q, HEX_R)
    ).fetchone()
    if existing_hex:
        if existing_hex["location_key"] == DUNGEON["location_key"]:
            print(f"[SKIP] Hex ({HEX_Q},{HEX_R}) already has location_key='{DUNGEON['location_key']}'")
        else:
            conn.execute(
                "UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ?",
                (DUNGEON["location_key"], HEX_Q, HEX_R),
            )
            conn.commit()
            print(f"[OK] Hex ({HEX_Q},{HEX_R}) location_key updated to '{DUNGEON['location_key']}'")
    else:
        conn.execute(
            """INSERT INTO world_hexes
               (q, r, hex_type, label, atmosphere, location_key, is_active)
               VALUES (?, ?, 'dungeon', ?, ?, ?, 1)""",
            (
                HEX_Q,
                HEX_R,
                DUNGEON["label"],
                DUNGEON["atmosphere"][:200],
                DUNGEON["location_key"],
            ),
        )
        conn.commit()
        print(f"[OK] Hex ({HEX_Q},{HEX_R}) created (dungeon, location_key='{DUNGEON['location_key']}')")

    # ── 3. Verify boss tile exists ────────────────────────────────────────────
    boss = conn.execute(
        "SELECT id, label FROM dungeon_tiles WHERE id = ? AND is_boss_tile = 1",
        (DUNGEON["boss_tile_id"],),
    ).fetchone()
    if boss:
        print(f"[OK] Boss tile verified: id={boss['id']} '{boss['label']}'")
    else:
        print(f"[WARN] Boss tile id={DUNGEON['boss_tile_id']} not found or not is_boss_tile=1!")

    print("\nDone.")


if __name__ == "__main__":
    with _conn() as conn:
        seed(conn)
