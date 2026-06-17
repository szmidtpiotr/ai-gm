"""Seed LB3 — re-spec krypta_probna jako ONBOARDING loch.

Decyzja LB-3 (z override Piotra 2026-06-17): tile_count=4 (entry + 2 komnaty
walki + boss), boss = undead_champion (~20 PŻ at D1), rest_heal_pct=100,
rest_charges=0 (unlimited), min_level=1. Cel clear ~78-85% solo lvl1.

undead_champion przy D1 (boss_factor=0.45, boss_lvl=3, CON 10):
  HP = max(1, round(45 * 0.45)) + con_mod(0) * 3 = 20 PŻ
  attack = round(7 * 0.45) + 3//2 = 3 + 1 = 4
  damage = 1d8 (count round(1*0.45)=1), damage_bonus = round(1*0.45) + 0 = 0
  AC = min(16, 10 + round((16-10)*0.45)) = 13

Run inside dev backend container:
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_lb3_krypta_probna_onboarding.py

Idempotent: warunkowy UPDATE; ponowne uruchomienie nie zmienia stanu.
Konwencja FAZY LB: legacy dezaktywujemy is_active=0, nie kasujemy.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")

BOSS_ENEMY_KEY = "undead_champion"

BOSS_TILE = {
    "category_key": "krypta",
    "label": "Komnata Strażnika",
    "doors_json": json.dumps(["N", "S", "E", "W"]),
    "enemies_json": json.dumps([{"enemy_key": BOSS_ENEMY_KEY, "count": 1}]),
    "items_json": json.dumps([]),
    "active_states_json": json.dumps([]),
    "exit_conditions_json": json.dumps([{"type": "enemies_cleared"}]),
    "room_description": (
        "Starożytna komnata strażnika. Spoczywający tu od wieków upiorny czempion "
        "budzi się na dźwięk waszych kroków — ostatnia linia obrony tego grobowca."
    ),
    "is_boss_tile": 1,
    "is_active": 1,
}

KRYPTA_PROBNA_UPDATE = {
    "tile_count": 4,
    "rest_heal_pct": 100,
    "rest_charges": 0,
    "min_level": 1,
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def seed(conn: sqlite3.Connection) -> None:
    # ── 0. Sanity: boss enemy istnieje ───────────────────────────────────────────
    enemy = conn.execute(
        "SELECT key, hp_base FROM game_config_enemies WHERE key = ?", (BOSS_ENEMY_KEY,)
    ).fetchone()
    if not enemy:
        print(f"[ERROR] Enemy '{BOSS_ENEMY_KEY}' nie istnieje w game_config_enemies")
        return

    # ── 1. Boss tile "Komnata Strażnika" (upsert + switch na undead_champion) ────
    existing_tile = conn.execute(
        "SELECT id, enemies_json FROM dungeon_tiles WHERE category_key = ? AND label = ?",
        (BOSS_TILE["category_key"], BOSS_TILE["label"]),
    ).fetchone()
    if existing_tile:
        boss_tile_id = existing_tile["id"]
        if existing_tile["enemies_json"] == BOSS_TILE["enemies_json"]:
            print(f"[SKIP] Boss tile '{BOSS_TILE['label']}' już ma {BOSS_ENEMY_KEY} (id={boss_tile_id})")
        else:
            conn.execute(
                """UPDATE dungeon_tiles SET
                    enemies_json = ?, room_description = ?, is_boss_tile = 1, is_active = 1
                   WHERE id = ?""",
                (BOSS_TILE["enemies_json"], BOSS_TILE["room_description"], boss_tile_id),
            )
            conn.commit()
            print(f"[OK] Boss tile id={boss_tile_id} przepięty na {BOSS_ENEMY_KEY}")
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
        print(f"[OK] Boss tile '{BOSS_TILE['label']}' utworzony (id={boss_tile_id})")

    # ── 2. Dezaktywuj nieużywany legacy enemy krypta_opiekun (LB3 v1) ────────────
    legacy = conn.execute(
        "SELECT key, is_active FROM game_config_enemies WHERE key = 'krypta_opiekun'"
    ).fetchone()
    if legacy and int(legacy["is_active"] or 0) == 1:
        conn.execute("UPDATE game_config_enemies SET is_active = 0 WHERE key = 'krypta_opiekun'")
        conn.commit()
        print("[OK] Legacy enemy 'krypta_opiekun' dezaktywowany (is_active=0)")
    elif legacy:
        print("[SKIP] Legacy enemy 'krypta_opiekun' już nieaktywny")

    # ── 3. Update krypta_probna → ONBOARDING config ─────────────────────────────
    current = conn.execute(
        "SELECT tile_count, rest_heal_pct, rest_charges, min_level, boss_tile_id, boss_enemy "
        "FROM game_dungeons WHERE key = 'krypta_probna'",
    ).fetchone()
    if not current:
        print("[ERROR] krypta_probna nie istnieje — uruchom seed_l16_krypta_probna.py najpierw")
        return

    needs_update = (
        int(current["tile_count"] or 0) != KRYPTA_PROBNA_UPDATE["tile_count"]
        or int(current["rest_heal_pct"] or 20) != KRYPTA_PROBNA_UPDATE["rest_heal_pct"]
        or int(current["rest_charges"] or 2) != KRYPTA_PROBNA_UPDATE["rest_charges"]
        or int(current["min_level"] or 1) != KRYPTA_PROBNA_UPDATE["min_level"]
        or int(current["boss_tile_id"] or 0) != boss_tile_id
        or (current["boss_enemy"] or "") != BOSS_ENEMY_KEY
    )
    if not needs_update:
        print("[SKIP] krypta_probna już zgodna z LB3")
    else:
        conn.execute(
            """UPDATE game_dungeons SET
                tile_count = ?, rest_heal_pct = ?, rest_charges = ?,
                min_level = ?, boss_tile_id = ?, boss_enemy = ?
               WHERE key = 'krypta_probna'""",
            (
                KRYPTA_PROBNA_UPDATE["tile_count"], KRYPTA_PROBNA_UPDATE["rest_heal_pct"],
                KRYPTA_PROBNA_UPDATE["rest_charges"], KRYPTA_PROBNA_UPDATE["min_level"],
                boss_tile_id, BOSS_ENEMY_KEY,
            ),
        )
        conn.commit()
        print(
            f"[OK] krypta_probna: tile_count=4, rest_heal_pct=100, rest_charges=0, "
            f"boss_tile_id={boss_tile_id}, boss_enemy={BOSS_ENEMY_KEY}"
        )

    # ── 4. Verify ─────────────────────────────────────────────────────────────────
    row = conn.execute(
        "SELECT tile_count, rest_heal_pct, rest_charges, min_level, boss_tile_id, boss_enemy "
        "FROM game_dungeons WHERE key = 'krypta_probna'"
    ).fetchone()
    print(
        f"\n[VERIFY] krypta_probna: tile_count={row['tile_count']}, min_level={row['min_level']}, "
        f"rest_heal_pct={row['rest_heal_pct']}, rest_charges={row['rest_charges']}, "
        f"boss_tile_id={row['boss_tile_id']}, boss_enemy={row['boss_enemy']}"
    )
    tile = conn.execute(
        "SELECT id, label, is_boss_tile, is_active, enemies_json FROM dungeon_tiles WHERE id = ?",
        (row["boss_tile_id"],),
    ).fetchone()
    if tile:
        print(f"[VERIFY] Boss tile: id={tile['id']} '{tile['label']}' "
              f"is_boss={tile['is_boss_tile']} is_active={tile['is_active']} "
              f"enemies={tile['enemies_json']}")
    else:
        print(f"[WARN] Boss tile id={row['boss_tile_id']} nie znaleziony!")

    print("\nDone. LB3 complete.")


if __name__ == "__main__":
    with _conn() as conn:
        seed(conn)
