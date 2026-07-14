"""TDD: Issue #1382 — per-skill, per-rank tunable XP upgrade cost.

Cost resolution precedence:
  per-skill `game_config_skills.rank_cost_json` → global `xp_skill_rank_costs` → DEFAULT_RANK_UP_COSTS.
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"
_TEST_CHAR_BASE = 999_1382
_SKILL_OVERRIDE = "test_costtune_override"
_SKILL_NULL = "test_costtune_null"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _make_sheet(xp: int, skills: dict | None = None) -> str:
    return json.dumps({
        "archetype": "warrior",
        "level": 3,
        "current_hp": 20,
        "max_hp": 20,
        "xp_available": xp,
        "xp_lifetime_earned": xp + 500,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": skills or {},
    })


def _insert_char(char_id: int, xp: int, skills: dict | None = None):
    conn = _conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, sheet_json)
               VALUES (?, NULL, 1, ?, 'v1', ?)""",
            (char_id, "[TEST_1382]", _make_sheet(xp, skills)),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_skill(key: str, rank_cost_json: str | None):
    conn = _conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO game_config_skills
               (key, label, linked_stat, rank_ceiling, sort_order, rank_cost_json)
               VALUES (?, ?, 'STR', 5, 900, ?)""",
            (key, f"[TEST] {key}", rank_cost_json),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _fixtures():
    _insert_skill(_SKILL_OVERRIDE, json.dumps({"1": 250, "2": 500}))
    _insert_skill(_SKILL_NULL, None)
    yield
    conn = _conn()
    try:
        conn.execute("DELETE FROM game_config_skills WHERE key IN (?, ?)", (_SKILL_OVERRIDE, _SKILL_NULL))
        for i in range(1, 10):
            conn.execute("DELETE FROM characters WHERE id = ?", (_TEST_CHAR_BASE + i,))
        conn.commit()
    finally:
        conn.close()


# ── Test 1: per-skill override cost deducted, not global ─────────────────────
def test_override_cost_deducted():
    from app.services.xp_service import spend_skill_rank_up
    char_id = _TEST_CHAR_BASE + 1
    _insert_char(char_id, xp=300, skills={_SKILL_OVERRIDE: 0})
    conn = _conn()
    try:
        res = spend_skill_rank_up(conn, char_id, _SKILL_OVERRIDE)
        conn.commit()
        assert res["xp_spent"] == 250, f"Oczekiwano kosztu 250 (override rank1), dostaliśmy {res['xp_spent']}"
        assert res["xp_available"] == 50
        assert res["new_rank"] == 1
    finally:
        conn.close()


# ── Test 2: override respects insufficient XP boundary ───────────────────────
def test_override_insufficient_xp():
    from app.services.xp_service import spend_skill_rank_up
    char_id = _TEST_CHAR_BASE + 2
    _insert_char(char_id, xp=249, skills={_SKILL_OVERRIDE: 0})
    conn = _conn()
    try:
        with pytest.raises(ValueError, match="insufficient_xp"):
            spend_skill_rank_up(conn, char_id, _SKILL_OVERRIDE)
    finally:
        conn.close()


# ── Test 3: second rank uses its own override (rank2 = 500) ──────────────────
def test_override_rank2_cost():
    from app.services.xp_service import spend_skill_rank_up
    char_id = _TEST_CHAR_BASE + 3
    _insert_char(char_id, xp=600, skills={_SKILL_OVERRIDE: 1})
    conn = _conn()
    try:
        res = spend_skill_rank_up(conn, char_id, _SKILL_OVERRIDE)
        conn.commit()
        assert res["xp_spent"] == 500, f"Oczekiwano kosztu 500 (override rank2), dostaliśmy {res['xp_spent']}"
        assert res["new_rank"] == 2
    finally:
        conn.close()


# ── Test 4: NULL rank_cost_json → falls back to global/default (regression) ──
def test_null_falls_back_to_global():
    from app.services.xp_service import spend_skill_rank_up, _load_rank_costs, DEFAULT_RANK_UP_COSTS
    char_id = _TEST_CHAR_BASE + 4
    _insert_char(char_id, xp=5000, skills={_SKILL_NULL: 0})
    conn = _conn()
    try:
        expected = int(_load_rank_costs(conn).get(1) or DEFAULT_RANK_UP_COSTS[1])
        res = spend_skill_rank_up(conn, char_id, _SKILL_NULL)
        conn.commit()
        assert res["xp_spent"] == expected, (
            f"NULL override powinien użyć globalnego kosztu {expected}, dostaliśmy {res['xp_spent']}"
        )
    finally:
        conn.close()


# ── Test 5: snapshot exposes per-skill overrides ────────────────────────────
def test_snapshot_includes_overrides():
    from app.services.xp_service import get_xp_snapshot
    char_id = _TEST_CHAR_BASE + 5
    _insert_char(char_id, xp=100)
    conn = _conn()
    try:
        snap = get_xp_snapshot(conn, char_id)
        overrides = snap.get("skill_rank_cost_overrides") or {}
        assert _SKILL_OVERRIDE in overrides, f"Brak override w snapshot: {overrides}"
        assert overrides[_SKILL_OVERRIDE] == {"1": 250, "2": 500}
        assert _SKILL_NULL not in overrides, "Skill z NULL nie powinien być w override map"
    finally:
        conn.close()
