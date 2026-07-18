"""TDD: Issue #363 — C9 UI długiego odpoczynku: modal Ucz się (lista zakupów XP)."""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"
_TEST_CHAR_BASE = 999_363


def _make_sheet(archetype: str = "warrior", xp: int = 500) -> str:
    return json.dumps({
        "archetype": archetype,
        "level": 3,
        "current_hp": 20,
        "max_hp": 20,
        "xp_available": xp,
        "xp_lifetime_earned": xp + 200,
        "stats": {"STR": 12, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": {"athletics": 1, "stealth": 0},
    })


def _insert_char(char_id: int, archetype: str = "warrior", xp: int = 500):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, sheet_json)
               VALUES (?, NULL, 1, ?, 'v1', ?)""",
            (char_id, f"[TEST_C9] {archetype}", _make_sheet(archetype, xp)),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup(char_id: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
        conn.commit()
    finally:
        conn.close()


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


# ─── Test 1: /xp snapshot zawiera skill_rank_ceiling ─────────────────────────

def test_xp_snapshot_has_skill_rank_ceiling():
    """GET /characters/{id}/xp musi zwracać skill_rank_ceiling (potrzebne do UI)."""
    char_id = _TEST_CHAR_BASE + 1
    _insert_char(char_id)
    try:
        resp = _client().get(f"/api/characters/{char_id}/xp?user_id=1")
        assert resp.status_code == 200, f"Snapshot failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "skill_rank_ceiling" in data, (
            f"Brak skill_rank_ceiling w XP snapshot. "
            f"UI potrzebuje tej wartości żeby wiedzieć kiedy wyszarzyć przycisk Kup. "
            f"Obecne klucze: {list(data.keys())}"
        )
    finally:
        _cleanup(char_id)


# ─── Test 2: skill_rank_ceiling = 3 (per C7 migration) ───────────────────────

def test_xp_snapshot_skill_ceiling_is_3():
    """skill_rank_ceiling musi wynosić 3 (C7 ustawił rank_ceiling=3 dla wszystkich umiejętności)."""
    char_id = _TEST_CHAR_BASE + 2
    _insert_char(char_id)
    try:
        resp = _client().get(f"/api/characters/{char_id}/xp?user_id=1")
        data = resp.json()
        ceiling = data.get("skill_rank_ceiling")
        assert ceiling == 3, (
            f"skill_rank_ceiling powinno być 3 (game_mechanics.md), dostaliśmy {ceiling}. "
            f"UI wyświetla karty dla rang > 3 gdy to jest wyższe."
        )
    finally:
        _cleanup(char_id)


# ─── Test 3: stat_value_ceiling = 19 (per C8 migration) ──────────────────────

def test_xp_snapshot_stat_ceiling_is_19():
    """stat_value_ceiling musi wynosić 19 (C8: 19+ = Niedostępne)."""
    char_id = _TEST_CHAR_BASE + 3
    _insert_char(char_id)
    try:
        resp = _client().get(f"/api/characters/{char_id}/xp?user_id=1")
        data = resp.json()
        ceiling = data.get("stat_value_ceiling")
        assert ceiling == 19, (
            f"stat_value_ceiling powinno być 19 (game_mechanics.md), dostaliśmy {ceiling}. "
            f"UI wyszarza przycisk dopiero przy 20 — za późno."
        )
    finally:
        _cleanup(char_id)


# ─── Test 4: skill z rank=3 nie ma kosztu w rank_up_costs (sufit) ─────────────

def test_skill_at_ceiling_has_no_cost_card():
    """Umiejętność na rank 3 nie powinna mieć kosztu następnego awansu (brak klucza '4')."""
    char_id = _TEST_CHAR_BASE + 4
    _insert_char(char_id)
    try:
        resp = _client().get(f"/api/characters/{char_id}/xp?user_id=1")
        data = resp.json()
        rank_up_costs = data.get("rank_up_costs", {})
        # Per game_mechanics.md: max rank = 3. rank_up_costs nie powinien mieć klucza '4' ani '5'
        assert "4" not in rank_up_costs, (
            f"rank_up_costs zawiera klucz '4' — UI wyświetli przycisk Kup dla rang 4. "
            f"Obecne klucze: {list(rank_up_costs.keys())}"
        )
        assert "5" not in rank_up_costs, (
            f"rank_up_costs zawiera klucz '5' — UI wyświetli przycisk Kup dla rang 5. "
            f"Obecne klucze: {list(rank_up_costs.keys())}"
        )
    finally:
        _cleanup(char_id)


# Frontendowe testy statyczne (app.js/index.html starego UI) usunięte —
# legacy frontend/front/ skasowany 2026-07-18, ŻAR (front-v2) jest jedynym UI gracza.
