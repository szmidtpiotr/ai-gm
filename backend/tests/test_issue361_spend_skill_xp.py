"""TDD: Issue #361 — C7 XP Spend: endpoint spend_skill (wszystkie archetypy)."""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"
_TEST_CHAR_BASE = 999_361


def _make_sheet(archetype: str, xp: int = 500, skills: dict | None = None) -> str:
    return json.dumps({
        "archetype": archetype,
        "level": 3,
        "current_hp": 20,
        "max_hp": 20,
        "xp_available": xp,
        "xp_lifetime_earned": xp + 200,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": skills or {},
    })


def _insert_char(char_id: int, archetype: str, xp: int = 500, skills: dict | None = None):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, sheet_json)
               VALUES (?, NULL, 1, ?, 'v1', ?)""",
            (char_id, f"[TEST_C7] {archetype}", _make_sheet(archetype, xp, skills)),
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


# ─── Test 1: nowy URL /spend-xp/skill istnieje ───────────────────────────────

def test_new_url_spend_xp_skill_exists():
    """POST /api/characters/{id}/spend-xp/skill musi istnieć (nie 404)."""
    char_id = _TEST_CHAR_BASE + 1
    _insert_char(char_id, "warrior", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/spend-xp/skill",
            json={"skill_key": "athletics"},
        )
        assert resp.status_code != 404, (
            f"Endpoint /spend-xp/skill nie istnieje — otrzymano 404. "
            f"Istniejący URL to /xp/spend-skill — potrzeba aliasu."
        )
    finally:
        _cleanup(char_id)


# ─── Test 2: koszt rank 1 = 100 XP ───────────────────────────────────────────

def test_rank1_costs_100xp():
    """Nauka nowej umiejętności (0→1) musi kosztować 100 XP (game_mechanics.md)."""
    char_id = _TEST_CHAR_BASE + 2
    _insert_char(char_id, "warrior", xp=500, skills={"athletics": 0})
    try:
        # Try to buy with only 99 XP → should get 400 insufficient_xp
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps({
                "archetype": "warrior", "level": 3,
                "current_hp": 20, "max_hp": 20,
                "xp_available": 99, "xp_lifetime_earned": 300,
                "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
                "skills": {"athletics": 0},
            }), char_id),
        )
        conn.commit()
        conn.close()

        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        # With 99 XP and cost=100 → should be 400 insufficient_xp
        assert resp.status_code == 400, (
            f"Z 99 XP i kosztem 100 XP oczekiwano 400, dostaliśmy {resp.status_code}. "
            f"Obecny koszt rank 1 to prawdopodobnie 50 XP (za mało)."
        )
    finally:
        _cleanup(char_id)


# ─── Test 3: koszt rank 2 = 75 XP ────────────────────────────────────────────

def test_rank2_costs_75xp():
    """Podniesienie rangi 1→2 musi kosztować 75 XP (game_mechanics.md)."""
    char_id = _TEST_CHAR_BASE + 3
    _insert_char(char_id, "warrior", xp=74, skills={"athletics": 1})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        # With 74 XP and cost=75 → should be 400 insufficient_xp
        assert resp.status_code == 400, (
            f"Z 74 XP i kosztem 75 XP (1→2) oczekiwano 400, dostaliśmy {resp.status_code}. "
            f"Obecny koszt rank 2 to 100 XP — nie zgadza się z game_mechanics.md."
        )
    finally:
        _cleanup(char_id)


# ─── Test 4: maksymalny rank = 3 ─────────────────────────────────────────────

def test_skill_rank3_is_ceiling():
    """Skill na rank 3 → spend_skill zwraca 400 (rank_ceiling=3)."""
    char_id = _TEST_CHAR_BASE + 4
    _insert_char(char_id, "warrior", xp=999, skills={"athletics": 3})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        assert resp.status_code == 400, (
            f"Skill na rank 3 powinien być zablokowany, dostaliśmy {resp.status_code}. "
            f"Obecny rank_ceiling={5} zamiast 3."
        )
    finally:
        _cleanup(char_id)


# ─── Test 5: wojownik może wydać XP na skill ─────────────────────────────────

def test_warrior_can_spend_skill_xp():
    """Archetype Warrior może wydać XP na umiejętność."""
    char_id = _TEST_CHAR_BASE + 5
    _insert_char(char_id, "warrior", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        assert resp.status_code == 200, (
            f"Warrior nie może wydać XP na skill: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("new_rank") == 1
    finally:
        _cleanup(char_id)


# ─── Test 6: uczony może wydać XP na skill ───────────────────────────────────

def test_scholar_can_spend_skill_xp():
    """Archetype Scholar może wydać XP na umiejętność."""
    char_id = _TEST_CHAR_BASE + 6
    _insert_char(char_id, "scholar", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "arcana"},
        )
        assert resp.status_code == 200, (
            f"Scholar nie może wydać XP na skill: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("ok") is True
    finally:
        _cleanup(char_id)


# ─── Test 7: łotr może wydać XP na skill ─────────────────────────────────────

def test_rogue_can_spend_skill_xp():
    """Archetype Rogue może wydać XP na umiejętność."""
    char_id = _TEST_CHAR_BASE + 7
    _insert_char(char_id, "rogue", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "stealth"},
        )
        assert resp.status_code == 200, (
            f"Rogue nie może wydać XP na skill: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("ok") is True
    finally:
        _cleanup(char_id)


# ─── Test 8: za mało XP → 400 ────────────────────────────────────────────────

def test_insufficient_xp_returns_400():
    """Za mało XP → HTTP 400."""
    char_id = _TEST_CHAR_BASE + 8
    _insert_char(char_id, "warrior", xp=0)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        assert resp.status_code == 400
    finally:
        _cleanup(char_id)


# ─── Test 9: wynik zawiera nowy stan (new_rank, xp_available) ─────────────────

def test_spend_skill_returns_new_state():
    """Endpoint zwraca new_rank i xp_available po zakupie."""
    char_id = _TEST_CHAR_BASE + 9
    _insert_char(char_id, "warrior", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-skill",
            json={"skill_key": "athletics"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "new_rank" in data, f"Brak new_rank w odpowiedzi: {data}"
            assert "xp_available" in data, f"Brak xp_available w odpowiedzi: {data}"
            assert "xp_spent" in data, f"Brak xp_spent w odpowiedzi: {data}"
    finally:
        _cleanup(char_id)
