"""TDD: Issue #1053 — modal Awansuj nie zamyka się po wydaniu PD.

Backend: weryfikuje że wielokrotne wywołanie spend-skill w ramach jednej sesji
działa poprawnie (backend gotowy na 'pozostań otwarty' UX).
Bug był wyłącznie frontendowy — modal.style.display='none' po każdym commit.
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"
_CHAR_ID = 999_1053


def _make_sheet(xp: int = 200, skills: dict | None = None) -> str:
    return json.dumps({
        "archetype": "warrior",
        "level": 3,
        "current_hp": 20,
        "max_hp": 20,
        "xp_available": xp,
        "xp_lifetime_earned": xp + 200,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": skills or {"stealth": 0, "athletics": 0},
    })


def _insert_char(xp: int = 100, skills: dict | None = None):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO characters (id, campaign_id, user_id, name, system_id, sheet_json) "
            "VALUES (?, NULL, 1, '[TEST_1053] awansuj_modal', 'v1', ?)",
            (_CHAR_ID, _make_sheet(xp, skills)),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM characters WHERE id = ?", (_CHAR_ID,))
        conn.commit()
    finally:
        conn.close()


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


# ─── Test 1: backend zwraca xp_available po wydaniu PD ──────────────────────

def test_spend_skill_returns_xp_available():
    """Po spend-skill odpowiedź musi zawierać xp_available (frontend go wyświetla)."""
    _insert_char(xp=200, skills={"stealth": 0})
    client = _client()
    try:
        r = client.post(
            f"/api/characters/{_CHAR_ID}/xp/spend-skill",
            json={"skill_key": "stealth", "user_id": 1},
        )
        assert r.status_code == 200, f"spend-skill failed: {r.text}"
        data = r.json()
        assert "xp_available" in data, "Brak xp_available w odpowiedzi — frontend nie może zaktualizować wyświetlania PD"
        assert isinstance(data["xp_available"], int), "xp_available musi być liczbą całkowitą"
    finally:
        _cleanup()


# ─── Test 2: backend obsługuje dwa kolejne spend-skill bez błędu ─────────────

def test_two_consecutive_spends_both_succeed():
    """Modal ma zostać otwarty — znaczy gracz może wydać wiele PD z rzędu.
    Backend musi obsługiwać kolejne wywołania spend-skill poprawnie."""
    _insert_char(xp=200, skills={"stealth": 0, "athletics": 0})
    client = _client()
    try:
        # Pierwszy zakup
        r1 = client.post(
            f"/api/characters/{_CHAR_ID}/xp/spend-skill",
            json={"skill_key": "stealth", "user_id": 1},
        )
        assert r1.status_code == 200, f"Pierwszy spend-skill failed: {r1.text}"
        xp_after_first = r1.json().get("xp_available")
        assert xp_after_first is not None

        # Drugi zakup (bez zamykania i otwierania modala — to jest sedno buga)
        r2 = client.post(
            f"/api/characters/{_CHAR_ID}/xp/spend-skill",
            json={"skill_key": "athletics", "user_id": 1},
        )
        assert r2.status_code == 200, f"Drugi spend-skill failed: {r2.text}"
        xp_after_second = r2.json().get("xp_available")
        assert xp_after_second is not None
        assert xp_after_second < xp_after_first, (
            f"PD powinno zmaleć po drugim zakupie: {xp_after_first} → {xp_after_second}"
        )
    finally:
        _cleanup()


# ─── Test 3: backward compat — endpoint /xp/spend-skill nadal działa ────────

def test_spend_skill_endpoint_still_reachable():
    """Endpoint /xp/spend-skill musi nadal działać (backward compat)."""
    _insert_char(xp=200, skills={"stealth": 0})
    client = _client()
    try:
        r = client.post(
            f"/api/characters/{_CHAR_ID}/xp/spend-skill",
            json={"skill_key": "stealth", "user_id": 1},
        )
        assert r.status_code in (200, 400), (
            f"Endpoint niedostępny (404/500): {r.status_code} {r.text}"
        )
    finally:
        _cleanup()
