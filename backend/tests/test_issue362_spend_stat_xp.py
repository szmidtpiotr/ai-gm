"""TDD: Issue #362 — C8 XP Spend: endpoint spend_stat (wszystkie archetypy)."""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

DB_PATH = "/data/ai_gm.db"
_TEST_CHAR_BASE = 999_362


def _make_sheet(archetype: str, xp: int = 500, stats: dict | None = None, hp: int = 20) -> str:
    base_stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}
    if stats:
        base_stats.update(stats)
    return json.dumps({
        "archetype": archetype,
        "level": 3,
        "current_hp": hp,
        "max_hp": hp,
        "xp_available": xp,
        "xp_lifetime_earned": xp + 200,
        "stats": base_stats,
        "skills": {},
    })


def _insert_char(char_id: int, archetype: str, xp: int = 500, stats: dict | None = None, hp: int = 20):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, sheet_json)
               VALUES (?, NULL, 1, ?, 'v1', ?)""",
            (char_id, f"[TEST_C8] {archetype}", _make_sheet(archetype, xp, stats, hp)),
        )
        conn.commit()
    finally:
        conn.close()


def _get_sheet(char_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
        return json.loads(row[0]) if row else {}
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


# ─── Test 1: nowy URL /spend-xp/stat istnieje ────────────────────────────────

def test_new_url_spend_xp_stat_exists():
    """POST /api/characters/{id}/spend-xp/stat musi istnieć (nie 404)."""
    char_id = _TEST_CHAR_BASE + 1
    _insert_char(char_id, "warrior", xp=500)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/spend-xp/stat",
            json={"stat_key": "STR"},
        )
        assert resp.status_code != 404, (
            f"Endpoint /spend-xp/stat nie istnieje — dostaliśmy 404. "
            f"Istniejący URL to /xp/spend-stat — potrzeba aliasu per game_mechanics.md."
        )
    finally:
        _cleanup(char_id)


# ─── Test 2: koszt za STR 8-10 = 50 XP ──────────────────────────────────────

def test_stat_cost_low_tier_50xp():
    """Podniesienie STR z 10 do 11 kosztuje 50 XP (tier 8-10 w game_mechanics.md)."""
    char_id = _TEST_CHAR_BASE + 2
    _insert_char(char_id, "warrior", xp=49, stats={"STR": 10})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "STR"},
        )
        assert resp.status_code == 400, (
            f"Z 49 XP i kosztem 50 (STR=10→11) oczekiwano 400 insufficient_xp, "
            f"dostaliśmy {resp.status_code}. Obecny koszt jest inny niż 50 XP."
        )
    finally:
        _cleanup(char_id)


# ─── Test 3: koszt za stat 11-13 = 100 XP ────────────────────────────────────

def test_stat_cost_mid_tier_100xp():
    """Podniesienie INT z 13 do 14 kosztuje 100 XP (tier 11-13 w game_mechanics.md)."""
    char_id = _TEST_CHAR_BASE + 3
    _insert_char(char_id, "scholar", xp=99, stats={"INT": 13})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "INT"},
        )
        assert resp.status_code == 400, (
            f"Z 99 XP i kosztem 100 (INT=13→14) oczekiwano 400, "
            f"dostaliśmy {resp.status_code}. Obecny koszt mid-tier jest inny niż 100 XP."
        )
    finally:
        _cleanup(char_id)


# ─── Test 4: koszt za stat 14-16 = 200 XP ────────────────────────────────────

def test_stat_cost_high_tier_200xp():
    """Podniesienie STR z 16 do 17 kosztuje 200 XP (tier 14-16)."""
    char_id = _TEST_CHAR_BASE + 4
    _insert_char(char_id, "warrior", xp=199, stats={"STR": 16})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "STR"},
        )
        assert resp.status_code == 400, (
            f"Z 199 XP i kosztem 200 (STR=16→17) oczekiwano 400, "
            f"dostaliśmy {resp.status_code}. Obecny koszt high-tier jest inny niż 200 XP."
        )
    finally:
        _cleanup(char_id)


# ─── Test 5: koszt za stat 17-18 = 400 XP ────────────────────────────────────

def test_stat_cost_elite_tier_400xp():
    """Podniesienie DEX z 18 do 19 kosztuje 400 XP (tier 17-18)."""
    char_id = _TEST_CHAR_BASE + 5
    _insert_char(char_id, "rogue", xp=399, stats={"DEX": 18})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "DEX"},
        )
        assert resp.status_code == 400, (
            f"Z 399 XP i kosztem 400 (DEX=18→19) oczekiwano 400, "
            f"dostaliśmy {resp.status_code}. Obecny koszt elite-tier jest inny niż 400 XP."
        )
    finally:
        _cleanup(char_id)


# ─── Test 6: stat 19+ = sufit (niedostępne) ──────────────────────────────────

def test_stat_19_is_ceiling():
    """Stat na 19 = sufit — spend_stat zwraca 400 (game_mechanics.md: 19+ Niedostępne)."""
    char_id = _TEST_CHAR_BASE + 6
    _insert_char(char_id, "warrior", xp=9999, stats={"STR": 19})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "STR"},
        )
        assert resp.status_code == 400, (
            f"Stat=19 powinien być sufitem (niedostępne per game_mechanics.md), "
            f"dostaliśmy {resp.status_code}. Obecny ceiling to 20 — trzeba zmienić na 19."
        )
    finally:
        _cleanup(char_id)


# ─── Test 7: CON +1 przelicza hp_max ─────────────────────────────────────────

def test_con_increase_recalculates_hp_max():
    """CON 11→12 zmienia modyfikator 0→1; hp_max musi wzrosnąć o level (=3)."""
    char_id = _TEST_CHAR_BASE + 7
    # CON=11 → mod=0; CON=12 → mod=1; level=3 → hp_max += 3
    _insert_char(char_id, "warrior", xp=500, stats={"CON": 11}, hp=20)
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "CON"},
        )
        if resp.status_code == 200:
            sheet = _get_sheet(char_id)
            new_max_hp = sheet.get("max_hp", 20)
            assert new_max_hp > 20, (
                f"CON 11→12 (mod 0→1, level 3) powinno zwiększyć max_hp z 20 do ≥23, "
                f"dostaliśmy max_hp={new_max_hp}. CON modifier nie przelicza HP."
            )
        else:
            pytest.fail(f"spend-stat CON zwróciło {resp.status_code}: {resp.text}")
    finally:
        _cleanup(char_id)


# ─── Test 8: Scholar wydaje XP na INT ────────────────────────────────────────

def test_scholar_spends_on_int():
    """Scholar może wydać XP na INT."""
    char_id = _TEST_CHAR_BASE + 8
    _insert_char(char_id, "scholar", xp=500, stats={"INT": 10})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "INT"},
        )
        assert resp.status_code == 200, (
            f"Scholar nie może wydać XP na INT: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("new_value") == 11
    finally:
        _cleanup(char_id)


# ─── Test 9: Warrior wydaje XP na STR ────────────────────────────────────────

def test_warrior_spends_on_str():
    """Warrior może wydać XP na STR."""
    char_id = _TEST_CHAR_BASE + 9
    _insert_char(char_id, "warrior", xp=500, stats={"STR": 10})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "STR"},
        )
        assert resp.status_code == 200, (
            f"Warrior nie może wydać XP na STR: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("new_value") == 11
    finally:
        _cleanup(char_id)


# ─── Test 10: wynik zawiera nowy stan ────────────────────────────────────────

def test_spend_stat_returns_new_state():
    """Endpoint zwraca stat_key, new_value, xp_spent, xp_available."""
    char_id = _TEST_CHAR_BASE + 10
    _insert_char(char_id, "warrior", xp=500, stats={"STR": 10})
    try:
        resp = _client().post(
            f"/api/characters/{char_id}/xp/spend-stat",
            json={"stat_key": "STR"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "new_value" in data, f"Brak new_value: {data}"
            assert "xp_spent" in data, f"Brak xp_spent: {data}"
            assert "xp_available" in data, f"Brak xp_available: {data}"
    finally:
        _cleanup(char_id)
