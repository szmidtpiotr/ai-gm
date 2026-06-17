"""Seed LB4 — nowy głębszy loch katakumby_mroku.

Decyzja LB-4 (game_mechanics.md → CZĘŚĆ AJ → FAZA LB):
  Obecna trudna treść (5 walk + Lisz ~40 PŻ, absolutna skala D1) trafia do
  oddzielnego lochu `katakumby_mroku`. Wymagany poziom 3, rest ograniczony:
  20% HP / 2 ładunki. Cel clear ~60-70% @ min_level=3.

  lich przy D1 (boss_factor=0.45, boss_lvl=3, CON 10):
    HP = max(1, round(90 * 0.45)) + con_mod(0) * 3 = 41 PŻ ≈ "40 PŻ" z opisu LB4
    attack = round(base * 0.45), damage 1d8+bonus, AC = min(16, 10 + round(...))

Run inside dev backend container:
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_lb4_katakumby_mroku.py

Idempotent: warunkowy INSERT/UPDATE; ponowne uruchomienie nie zmienia stanu.
Konwencja FAZY LB: created_by='seed', legacy dezaktywujemy is_active=0, nie kasujemy.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")

DUNGEON_KEY = "katakumby_mroku"
BOSS_ENEMY_KEY = "lich"
BOSS_TILE_LABEL = "Tron Lisza"
BOSS_TILE_CATEGORY = "krypta"

KATAKUMBY_CONFIG = {
    "key": DUNGEON_KEY,
    "label": "Katakumby Mroku",
    "location_key": "krypta_grobowiec_hrabiego",
    "rooms": 7,
    "enemy_pool": json.dumps(["skeleton", "zombie", "ghoul", "ghost", "wraith"]),
    "boss_enemy": BOSS_ENEMY_KEY,
    "loot_tier": "rich",
    "atmosphere": (
        "Głębsze poziomy grobowca, sięgające mrocznej starożytności. "
        "Zimno tu jest nie od ziemi lecz od czegoś starszego — magii, "
        "która przeżyła swoich twórców. Pięć komnat pełnych nieumarłych "
        "stoi między tobą a Liszem, władcą tych katakumb. Bez odpowiedniego "
        "przygotowania i wytrzymałości nie masz tu czego szukać."
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
    "dungeon_difficulty": 1,
    "tile_category_key": "krypta",
    "tile_count": 7,   # entry + 5 combat + boss = 7 (middle_count = tile_count - 2 = 5)
    "endless_growth_n": 0,
    "rest_heal_pct": 20,
    "rest_charges": 2,
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def seed(conn: sqlite3.Connection) -> None:
    # ── 0. Sanity: boss enemy lich istnieje ─────────────────────────────────────
    enemy = conn.execute(
        "SELECT key, hp_base, is_active FROM game_config_enemies WHERE key = ?",
        (BOSS_ENEMY_KEY,),
    ).fetchone()
    if not enemy:
        print(f"[ERROR] Enemy '{BOSS_ENEMY_KEY}' nie istnieje w game_config_enemies")
        return
    if not int(enemy["is_active"] or 1):
        print(f"[WARN] Enemy '{BOSS_ENEMY_KEY}' jest nieaktywny (is_active=0)")
    print(f"[OK] Boss enemy '{BOSS_ENEMY_KEY}' znaleziony: hp_base={enemy['hp_base']}")

    # ── 1. Znajdź boss tile "Tron Lisza" ────────────────────────────────────────
    boss_tile = conn.execute(
        "SELECT id, enemies_json, is_boss_tile, is_active FROM dungeon_tiles "
        "WHERE category_key = ? AND label = ?",
        (BOSS_TILE_CATEGORY, BOSS_TILE_LABEL),
    ).fetchone()
    if not boss_tile:
        print(f"[ERROR] Boss tile '{BOSS_TILE_LABEL}' nie istnieje w dungeon_tiles")
        return
    boss_tile_id = boss_tile["id"]
    enemies_in_tile = json.loads(boss_tile["enemies_json"] or "[]")
    has_lich = any(e.get("enemy_key") == BOSS_ENEMY_KEY for e in enemies_in_tile)
    if not has_lich:
        print(f"[ERROR] Boss tile '{BOSS_TILE_LABEL}' (id={boss_tile_id}) nie ma lich w enemies_json: {enemies_in_tile}")
        return
    print(f"[OK] Boss tile '{BOSS_TILE_LABEL}' id={boss_tile_id}, is_boss={boss_tile['is_boss_tile']}, enemies={enemies_in_tile}")

    # ── 2. Upsert katakumby_mroku ────────────────────────────────────────────────
    existing = conn.execute(
        "SELECT key, tile_count, min_level, rest_heal_pct, rest_charges, boss_tile_id "
        "FROM game_dungeons WHERE key = ?",
        (DUNGEON_KEY,),
    ).fetchone()

    target_tile_count = KATAKUMBY_CONFIG["tile_count"]
    target_min_level = KATAKUMBY_CONFIG["min_level"]
    target_rest_heal = KATAKUMBY_CONFIG["rest_heal_pct"]
    target_rest_charges = KATAKUMBY_CONFIG["rest_charges"]

    if existing:
        needs_update = (
            int(existing["tile_count"] or 0) != target_tile_count
            or int(existing["min_level"] or 1) != target_min_level
            or int(existing["rest_heal_pct"] or 20) != target_rest_heal
            or int(existing["rest_charges"] or 2) != target_rest_charges
            or int(existing["boss_tile_id"] or 0) != boss_tile_id
        )
        if not needs_update:
            print(f"[SKIP] {DUNGEON_KEY} już zgodny z LB4")
        else:
            conn.execute(
                """UPDATE game_dungeons SET
                    label=?, location_key=?, rooms=?, enemy_pool=?, boss_enemy=?,
                    loot_tier=?, atmosphere=?, cooldown_hours=?, min_level=?, is_active=?,
                    chest_loot_table_key=?, boss_loot_table_key=?, room_loot_chance=?,
                    room_types_json=?, riddle_source=?, riddle_max_hints=?,
                    dungeon_difficulty=?, tile_category_key=?, tile_count=?, boss_tile_id=?,
                    endless_growth_n=?, rest_heal_pct=?, rest_charges=?
                   WHERE key=?""",
                (
                    KATAKUMBY_CONFIG["label"], KATAKUMBY_CONFIG["location_key"],
                    KATAKUMBY_CONFIG["rooms"], KATAKUMBY_CONFIG["enemy_pool"],
                    KATAKUMBY_CONFIG["boss_enemy"], KATAKUMBY_CONFIG["loot_tier"],
                    KATAKUMBY_CONFIG["atmosphere"], KATAKUMBY_CONFIG["cooldown_hours"],
                    KATAKUMBY_CONFIG["min_level"], KATAKUMBY_CONFIG["is_active"],
                    KATAKUMBY_CONFIG["chest_loot_table_key"], KATAKUMBY_CONFIG["boss_loot_table_key"],
                    KATAKUMBY_CONFIG["room_loot_chance"], KATAKUMBY_CONFIG["room_types_json"],
                    KATAKUMBY_CONFIG["riddle_source"], KATAKUMBY_CONFIG["riddle_max_hints"],
                    KATAKUMBY_CONFIG["dungeon_difficulty"], KATAKUMBY_CONFIG["tile_category_key"],
                    KATAKUMBY_CONFIG["tile_count"], boss_tile_id,
                    KATAKUMBY_CONFIG["endless_growth_n"], KATAKUMBY_CONFIG["rest_heal_pct"],
                    KATAKUMBY_CONFIG["rest_charges"],
                    DUNGEON_KEY,
                ),
            )
            conn.commit()
            print(f"[OK] {DUNGEON_KEY} zaktualizowany do LB4 config")
    else:
        conn.execute(
            """INSERT INTO game_dungeons (
                key, label, location_key, rooms, enemy_pool, boss_enemy,
                loot_tier, atmosphere, cooldown_hours, min_level, is_active,
                chest_loot_table_key, boss_loot_table_key, room_loot_chance,
                room_types_json, riddle_source, riddle_max_hints,
                dungeon_difficulty, tile_category_key, tile_count, boss_tile_id,
                endless_growth_n, rest_heal_pct, rest_charges
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                KATAKUMBY_CONFIG["key"], KATAKUMBY_CONFIG["label"],
                KATAKUMBY_CONFIG["location_key"], KATAKUMBY_CONFIG["rooms"],
                KATAKUMBY_CONFIG["enemy_pool"], KATAKUMBY_CONFIG["boss_enemy"],
                KATAKUMBY_CONFIG["loot_tier"], KATAKUMBY_CONFIG["atmosphere"],
                KATAKUMBY_CONFIG["cooldown_hours"], KATAKUMBY_CONFIG["min_level"],
                KATAKUMBY_CONFIG["is_active"], KATAKUMBY_CONFIG["chest_loot_table_key"],
                KATAKUMBY_CONFIG["boss_loot_table_key"], KATAKUMBY_CONFIG["room_loot_chance"],
                KATAKUMBY_CONFIG["room_types_json"], KATAKUMBY_CONFIG["riddle_source"],
                KATAKUMBY_CONFIG["riddle_max_hints"], KATAKUMBY_CONFIG["dungeon_difficulty"],
                KATAKUMBY_CONFIG["tile_category_key"], KATAKUMBY_CONFIG["tile_count"],
                boss_tile_id, KATAKUMBY_CONFIG["endless_growth_n"],
                KATAKUMBY_CONFIG["rest_heal_pct"], KATAKUMBY_CONFIG["rest_charges"],
            ),
        )
        conn.commit()
        print(f"[OK] {DUNGEON_KEY} utworzony (LB4 seed)")

    # ── 3. Verify ─────────────────────────────────────────────────────────────────
    row = conn.execute(
        "SELECT key, label, tile_count, min_level, rest_heal_pct, rest_charges, "
        "boss_tile_id, boss_enemy, is_active "
        "FROM game_dungeons WHERE key = ?",
        (DUNGEON_KEY,),
    ).fetchone()
    print(
        f"\n[VERIFY] {DUNGEON_KEY}: tile_count={row['tile_count']}, min_level={row['min_level']}, "
        f"rest_heal_pct={row['rest_heal_pct']}, rest_charges={row['rest_charges']}, "
        f"boss_tile_id={row['boss_tile_id']}, boss_enemy={row['boss_enemy']}, "
        f"is_active={row['is_active']}"
    )
    tile = conn.execute(
        "SELECT id, label, is_boss_tile, is_active, enemies_json FROM dungeon_tiles WHERE id = ?",
        (row["boss_tile_id"],),
    ).fetchone()
    if tile:
        print(
            f"[VERIFY] Boss tile: id={tile['id']} '{tile['label']}' "
            f"is_boss={tile['is_boss_tile']} is_active={tile['is_active']} "
            f"enemies={tile['enemies_json']}"
        )
    else:
        print(f"[WARN] Boss tile id={row['boss_tile_id']} nie znaleziony!")

    print("\nDone. LB4 complete.")


if __name__ == "__main__":
    with _conn() as conn:
        seed(conn)
