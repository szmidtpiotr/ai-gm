"""TDD: Issue #737 (LB3) — krypta_probna jako ONBOARDING loch.

Niezmienniki config:
- tile_count=4 (entry + 2 komnaty walki + boss = 4 kafle)
- min_level=1 (dostępny od poziomu 1)
- rest_heal_pct=100 (pełne leczenie — onboarding)
- rest_charges=0 (unlimited — onboarding)
- boss_tile_id wskazuje na aktywny is_boss_tile=1 z undead_champion (1 wróg, ~20 HP at D1)

Tests:
- T1: krypta_probna.tile_count == 4
- T2: krypta_probna.min_level == 1
- T3: krypta_probna.rest_heal_pct == 100
- T4: krypta_probna.rest_charges == 0 (unlimited)
- T5: boss tile ma 1 wroga undead_champion, HP at D1 ~= 20
"""
from __future__ import annotations

import json
import math
import sqlite3

import pytest

DB_PATH = "/data/ai_gm.db"


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _get_krypta(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM game_dungeons WHERE key = 'krypta_probna'"
    ).fetchone()
    assert row is not None, "krypta_probna nie istnieje w game_dungeons"
    return row


# ─── T1: tile_count == 3 ─────────────────────────────────────────────────────

def test_krypta_probna_tile_count(db):
    """krypta_probna powinna mieć tile_count=4 (entry + 2 combat + boss)."""
    row = _get_krypta(db)
    assert int(row["tile_count"]) == 4, (
        f"krypta_probna.tile_count powinno być 4, got {row['tile_count']}"
    )


# ─── T2: min_level == 1 ──────────────────────────────────────────────────────

def test_krypta_probna_min_level(db):
    """krypta_probna powinna być dostępna od poziomu 1."""
    row = _get_krypta(db)
    assert int(row["min_level"]) == 1, (
        f"krypta_probna.min_level powinno być 1, got {row['min_level']}"
    )


# ─── T3: rest_heal_pct == 100 ────────────────────────────────────────────────

def test_krypta_probna_rest_heal_pct(db):
    """krypta_probna to onboarding — pełne leczenie (100%) przy odpoczynku."""
    row = _get_krypta(db)
    assert int(row["rest_heal_pct"]) == 100, (
        f"krypta_probna.rest_heal_pct powinno być 100 (onboarding), got {row['rest_heal_pct']}"
    )


# ─── T4: rest_charges == 0 (unlimited) ───────────────────────────────────────

def test_krypta_probna_rest_charges_unlimited(db):
    """krypta_probna to onboarding — rest_charges=0 (unlimited, wg konwencji <=0)."""
    row = _get_krypta(db)
    charges = int(row["rest_charges"])
    assert charges <= 0, (
        f"krypta_probna.rest_charges powinno być 0 (unlimited), got {charges}"
    )


# ─── T5: Boss tile ma krypta_opiekun (~18 HP at D1) ─────────────────────────

def test_krypta_probna_boss_tile_onboarding_enemy(db):
    """Boss tile krypta_probna ma undead_champion, 1 egzemplarz. HP at D1 ~= 20."""
    row = _get_krypta(db)
    boss_tile_id = row["boss_tile_id"]
    assert boss_tile_id, "krypta_probna musi mieć boss_tile_id"

    tile = db.execute(
        "SELECT * FROM dungeon_tiles WHERE id = ? AND is_boss_tile = 1 AND is_active = 1",
        (boss_tile_id,)
    ).fetchone()
    assert tile is not None, (
        f"dungeon_tiles id={boss_tile_id} nie istnieje lub nie ma is_boss_tile=1"
    )

    enemies = json.loads(tile["enemies_json"] or "[]")
    assert len(enemies) == 1, f"Boss tile powinien mieć 1 wróg, got {len(enemies)}: {enemies}"
    e = enemies[0]
    assert e["enemy_key"] == "undead_champion", (
        f"Boss tile powinien mieć undead_champion, got {e['enemy_key']}"
    )
    assert int(e.get("count", 1)) == 1, f"Boss powinien być 1 sztuka, got {e}"

    # Sprawdź hp_base: przy D1 boss_factor=0.45 → HP = round(hp_base * 0.45)
    enemy = db.execute(
        "SELECT hp_base, stats_json FROM game_config_enemies WHERE key = 'undead_champion'"
    ).fetchone()
    assert enemy is not None, "Enemy 'undead_champion' nie istnieje w game_config_enemies"

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

    # Cel: ~20 PŻ (undead_champion hp_base=45 → round(45*0.45)=20; tolerancja na zaokrąglenia)
    assert 17 <= hp_at_d1 <= 23, (
        f"Boss undead_champion przy D1 powinien mieć ~20 HP (17-23), "
        f"got hp_base={hp_base}, hp_at_d1={hp_at_d1}"
    )
