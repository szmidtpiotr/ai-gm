"""TDD: Issue #1007 — Reperuj button for dwarf in frontend UI.

Backend endpoint /api/characters/{id}/dwarf-repair already exists.
These tests verify the endpoint contract that the new UI button relies on.
"""
import sqlite3
import json


# ─── Helpers ─────────────────────────────────────────────────────────────────

DB_PATH = "/data/ai_gm.db"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _create_test_char(name, race, gold=100):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO characters (name, race, system_id, user_id, gold_gp, status, sheet_json)
           VALUES (?, ?, 'test', 1, ?, 'idle', '{}')""",
        (name, race, gold),
    )
    conn.commit()
    char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return char_id


def _cleanup_char(char_id):
    conn = _get_conn()
    conn.execute("DELETE FROM character_inventory WHERE character_id=?", (char_id,))
    conn.execute("DELETE FROM characters WHERE id=?", (char_id,))
    conn.commit()
    conn.close()


def _add_weapon(char_id, dur_cur=10, dur_max=100):
    """Give the char a real weapon needing repair (#1448: dwarf-repair only
    charges when there's actually a weapon to fix)."""
    conn = _get_conn()
    wk = conn.execute("SELECT key FROM game_config_weapons LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, equipped, durability_current, durability_max) "
        "VALUES (?, ?, 1, ?, ?)",
        (char_id, wk, dur_cur, dur_max),
    )
    conn.commit()
    conn.close()


def _hdr(uid=1):
    # #1426/#1448: legacy ?user_id= auth is OFF — endpoints require a signed JWT.
    from app.services import jwt_service
    return {"Authorization": "Bearer " + jwt_service.issue_access_token(
        user_id=uid, username="u", role="player", is_admin=0)}


# ─── Test główny — endpoint zwraca ok dla krasnoludów ────────────────────────

def test_dwarf_repair_endpoint_exists_and_returns_ok():
    """POST /api/characters/{id}/dwarf-repair zwraca 200 dla krasnoludów z wystarczającym złotem."""
    import sys
    sys.path.insert(0, "/app")
    from fastapi.testclient import TestClient
    from app.main import app

    char_id = _create_test_char("[TEST] Gimli Reperuj", "dwarf", gold=100)
    _add_weapon(char_id)  # #1448: real weapon to repair → cost is charged
    try:
        client = TestClient(app)
        r = client.post(f"/api/characters/{char_id}/dwarf-repair", headers=_hdr())
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True, f"Expected ok=True, got: {body}"
        assert "cost_gp" in body, "Response must have cost_gp field"
        assert body["cost_gp"] == 20, f"Cost should be 20 gp, got {body['cost_gp']}"
        assert "message" in body, "Response must have message field"
    finally:
        _cleanup_char(char_id)


# ─── Test — endpoint odrzuca non-dwarf ────────────────────────────────────────

def test_dwarf_repair_forbidden_for_non_dwarf():
    """POST /api/characters/{id}/dwarf-repair zwraca 403 dla nie-krasnoludów."""
    import sys
    sys.path.insert(0, "/app")
    from fastapi.testclient import TestClient
    from app.main import app

    char_id = _create_test_char("[TEST] Human Reperuj", "human", gold=100)
    try:
        client = TestClient(app)
        r = client.post(f"/api/characters/{char_id}/dwarf-repair", headers=_hdr())
        assert r.status_code == 403, f"Expected 403 for non-dwarf, got {r.status_code}"
    finally:
        _cleanup_char(char_id)


# ─── Test — endpoint odrzuca przy braku złota ─────────────────────────────────

def test_dwarf_repair_insufficient_gold():
    """POST /api/characters/{id}/dwarf-repair zwraca 400 gdy za mało złota."""
    import sys
    sys.path.insert(0, "/app")
    from fastapi.testclient import TestClient
    from app.main import app

    char_id = _create_test_char("[TEST] Poor Dwarf", "dwarf", gold=0)
    _add_weapon(char_id)  # #1448: weapon present so the gold gate is actually reached
    try:
        client = TestClient(app)
        r = client.post(f"/api/characters/{char_id}/dwarf-repair", headers=_hdr())
        assert r.status_code == 400, f"Expected 400 for insufficient gold, got {r.status_code}"
    finally:
        _cleanup_char(char_id)
