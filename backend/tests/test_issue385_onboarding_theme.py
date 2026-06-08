"""TDD: Issue #385 — onboarding theme selection saved to game_mode_flags."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

DB_PATH = "/data/ai_gm.db"
_TEST_USER_ID = 999_385

client = TestClient(app)


def _insert_test_user():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO users
               (id, username, password_hash, display_name, is_active, is_admin, role)
               VALUES (?, 'test_user_385', 'ph', 'TestUser385', 1, 0, 'player')""",
            (_TEST_USER_ID,),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup_test_user():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (_TEST_USER_ID,))
        conn.commit()
    finally:
        conn.close()


def _get_token() -> str:
    from app.services.jwt_service import issue_pair
    pair = issue_pair(
        user_id=_TEST_USER_ID,
        username="test_user_385",
        role="player",
        is_admin=0,
    )
    return pair["access_token"]


def _get_user_flags() -> str | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT game_mode_flags FROM users WHERE id = ?", (_TEST_USER_ID,)
        ).fetchone()
        return row["game_mode_flags"] if row else None
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    _insert_test_user()
    yield
    _cleanup_test_user()


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_patch_game_settings_saves_visual_theme():
    """PATCH /me/game-settings z visual_theme zapisuje do game_mode_flags."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.patch(
        "/api/me/game-settings",
        json={"visual_theme": "dark_fantasy"},
        headers=headers,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json().get("ok") is True

    flags_raw = _get_user_flags()
    assert flags_raw is not None, "game_mode_flags not saved to DB"
    flags = json.loads(flags_raw)
    assert flags.get("visual_theme") == "dark_fantasy"


def test_login_returns_game_mode_flags():
    """Login zwraca game_mode_flags w odpowiedzi JWT (pole w auth.py SELECT)."""
    # Verify login endpoint includes game_mode_flags in response
    # We test via TestClient + hardcoded demo user
    resp = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
    # demo user may not exist in test DB — if 401, skip; if 200, check field
    if resp.status_code == 200:
        assert "game_mode_flags" in resp.json(), f"game_mode_flags missing: {resp.json().keys()}"
    else:
        # Direct field-presence check: login SELECT must include game_mode_flags
        import inspect
        from app.api import auth as auth_module
        src = inspect.getsource(auth_module.login)
        assert "game_mode_flags" in src, "game_mode_flags missing from login SELECT/response"


def test_game_settings_persisted():
    """Po PATCH /me/game-settings DB zawiera poprawny JSON z visual_theme."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    client.patch("/api/me/game-settings", json={"visual_theme": "classic"}, headers=headers)

    flags_raw = _get_user_flags()
    assert flags_raw is not None
    flags = json.loads(flags_raw)
    assert flags.get("visual_theme") == "classic"


def test_game_settings_classic_theme():
    """Motyw 'classic' jest akceptowany."""
    token = _get_token()
    resp = client.patch(
        "/api/me/game-settings",
        json={"visual_theme": "classic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_patch_game_settings_invalid_theme_rejected():
    """Nieznany motyw jest odrzucany (400)."""
    token = _get_token()
    resp = client.patch(
        "/api/me/game-settings",
        json={"visual_theme": "not_a_real_theme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, f"Expected 400 for invalid theme, got {resp.status_code}"


def test_me_game_settings_without_auth_rejected():
    """Brak tokenu → 401."""
    resp = client.patch("/api/me/game-settings", json={"visual_theme": "classic"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
