"""TDD: Issue #738 (LB4) — katakumby_mroku jako głębszy loch.

Niezmienniki config:
- dungeon istnieje w game_dungeons z key='katakumby_mroku'
- tile_count=7 (entry + 5 komnat walki + boss = 7 kafli; middle_count=5)
- min_level=3 (dostępny od poziomu 3)
- rest_heal_pct=20 (ograniczone leczenie — głębszy loch)
- rest_charges=2 (2 ładunki odpoczynku na run)
- boss_tile_id → is_boss_tile=1 z lich (1 egzemplarz, HP at D1 ~= 41 ≈ "40 PŻ")

Tests:
- T1: katakumby_mroku.tile_count == 7
- T2: katakumby_mroku.min_level == 3
- T3: katakumby_mroku.rest_heal_pct == 20
- T4: katakumby_mroku.rest_charges == 2
- T5: boss tile ma 1 wroga lich, HP at D1 ~= 41 (38-44)
- T6: katakumby_mroku.is_active == 1
"""
from __future__ import annotations

import json
import sqlite3

import pytest

DB_PATH = "/data/ai_gm.db"

DUNGEON_KEY = "katakumby_mroku"
BOSS_ENEMY_KEY = "lich"


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _get_katakumby(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM game_dungeons WHERE key = ?", (DUNGEON_KEY,)
    ).fetchone()
    assert row is not None, f"{DUNGEON_KEY} nie istnieje w game_dungeons — uruchom seed_lb4"
    return row


# ─── T1: tile_count == 7 ─────────────────────────────────────────────────────

def test_katakumby_mroku_tile_count(db):
    """katakumby_mroku tile_count=7: entry + 5 komnat walki + boss."""
    row = _get_katakumby(db)
    assert int(row["tile_count"]) == 7, (
        f"katakumby_mroku.tile_count powinno być 7, got {row['tile_count']}"
    )


# ─── T2: min_level == 3 ──────────────────────────────────────────────────────

def test_katakumby_mroku_min_level(db):
    """katakumby_mroku dostępny od poziomu 3 (głębszy loch)."""
    row = _get_katakumby(db)
    assert int(row["min_level"]) == 3, (
        f"katakumby_mroku.min_level powinno być 3, got {row['min_level']}"
    )


# ─── T3: rest_heal_pct == 20 ─────────────────────────────────────────────────

def test_katakumby_mroku_rest_heal_pct(db):
    """katakumby_mroku to głębszy loch — ograniczone leczenie (20%) przy odpoczynku."""
    row = _get_katakumby(db)
    assert int(row["rest_heal_pct"]) == 20, (
        f"katakumby_mroku.rest_heal_pct powinno być 20, got {row['rest_heal_pct']}"
    )


# ─── T4: rest_charges == 2 ───────────────────────────────────────────────────

def test_katakumby_mroku_rest_charges(db):
    """katakumby_mroku — 2 ładunki odpoczynku na run (ograniczone)."""
    row = _get_katakumby(db)
    charges = int(row["rest_charges"])
    assert charges == 2, (
        f"katakumby_mroku.rest_charges powinno być 2, got {charges}"
    )


# ─── T5: Boss tile ma lich (~41 HP at D1) ────────────────────────────────────

def test_katakumby_mroku_boss_tile_lich(db):
    """Boss tile katakumby_mroku ma lich, 1 egzemplarz. HP at D1 ~= 41 (tolerancja 38-44)."""
    row = _get_katakumby(db)
    boss_tile_id = row["boss_tile_id"]
    assert boss_tile_id, "katakumby_mroku musi mieć boss_tile_id"

    tile = db.execute(
        "SELECT * FROM dungeon_tiles WHERE id = ? AND is_boss_tile = 1 AND is_active = 1",
        (boss_tile_id,),
    ).fetchone()
    assert tile is not None, (
        f"dungeon_tiles id={boss_tile_id} nie istnieje lub nie ma is_boss_tile=1"
    )

    enemies = json.loads(tile["enemies_json"] or "[]")
    assert len(enemies) == 1, f"Boss tile powinien mieć 1 wróg, got {len(enemies)}: {enemies}"
    e = enemies[0]
    assert e["enemy_key"] == BOSS_ENEMY_KEY, (
        f"Boss tile powinien mieć {BOSS_ENEMY_KEY}, got {e['enemy_key']}"
    )
    assert int(e.get("count", 1)) == 1, f"Boss powinien być 1 sztuka, got {e}"

    # HP at D1: boss_factor=0.45, boss_lvl=3, lich hp_base=90 CON=10
    enemy = db.execute(
        "SELECT hp_base, stats_json FROM game_config_enemies WHERE key = ?",
        (BOSS_ENEMY_KEY,),
    ).fetchone()
    assert enemy is not None, f"Enemy '{BOSS_ENEMY_KEY}' nie istnieje w game_config_enemies"

    boss_factor_d1 = 0.45
    boss_lvl_d1 = 3
    hp_base = int(enemy["hp_base"])
    try:
        stats = json.loads(enemy["stats_json"] or "{}")
        con = int(stats.get("CON", 10))
    except Exception:
        con = 10
    con_mod = max(0, (con - 10) // 2)
    scaled_hp_base = max(1, round(hp_base * boss_factor_d1))
    hp_at_d1 = scaled_hp_base + con_mod * boss_lvl_d1

    # Cel: ~41 PŻ (lich hp_base=90 → round(90*0.45)=41; tolerancja ±3)
    assert 38 <= hp_at_d1 <= 44, (
        f"Boss lich przy D1 powinien mieć ~41 HP (38-44), "
        f"got hp_base={hp_base}, hp_at_d1={hp_at_d1}"
    )


# ─── T6: is_active == 1 ──────────────────────────────────────────────────────

def test_katakumby_mroku_is_active(db):
    """katakumby_mroku musi być aktywny."""
    row = _get_katakumby(db)
    assert int(row["is_active"]) == 1, (
        f"katakumby_mroku.is_active powinno być 1, got {row['is_active']}"
    )
