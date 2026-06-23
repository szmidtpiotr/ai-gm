"""TDD: Issue #963 — whisper_to username auto-normalizes to character name."""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

DB_PATH = "/data/ai_gm.db"

# High-range IDs to avoid collisions
_U1 = 999_963_01
_U2 = 999_963_02
_CAMP = 999_963
_CHAR1_ID = 999_963_01
_CHAR2_ID = 999_963_02
_CHAR1_NAME = "[TEST-963] Wojownik"
_CHAR2_NAME = "[TEST-963] Uczony"
_U2_USERNAME = "test963_mp2"


def _setup():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(f"""
            INSERT OR REPLACE INTO users (id, username, password_hash, display_name)
                VALUES ({_U1}, 'test963_mp1', '', 'MP1 963');
            INSERT OR REPLACE INTO users (id, username, password_hash, display_name)
                VALUES ({_U2}, '{_U2_USERNAME}', '', 'MP2 963');
            INSERT OR REPLACE INTO campaigns (id, title, owner_user_id, mode, status, system_id, model_id)
                VALUES ({_CAMP}, 'TestCamp963', {_U1}, 'multiplayer', 'active', 'fantasy', 'gpt-4');
            INSERT OR REPLACE INTO campaign_members (campaign_id, user_id, role, status, character_id)
                VALUES ({_CAMP}, {_U1}, 'player', 'accepted', {_CHAR1_ID});
            INSERT OR REPLACE INTO campaign_members (campaign_id, user_id, role, status, character_id)
                VALUES ({_CAMP}, {_U2}, 'player', 'accepted', {_CHAR2_ID});
            INSERT OR REPLACE INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
                VALUES ({_CHAR1_ID}, {_CAMP}, {_U1}, '{_CHAR1_NAME}', 'fantasy', '{{}}');
            INSERT OR REPLACE INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
                VALUES ({_CHAR2_ID}, {_CAMP}, {_U2}, '{_CHAR2_NAME}', 'fantasy', '{{}}');
        """)
        conn.commit()
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DELETE FROM party_messages WHERE campaign_id={_CAMP}")
        conn.execute(f"DELETE FROM campaign_round_actions WHERE campaign_id={_CAMP}")
        conn.execute(f"DELETE FROM campaign_members WHERE campaign_id={_CAMP}")
        conn.execute(f"DELETE FROM characters WHERE id IN ({_CHAR1_ID}, {_CHAR2_ID})")
        conn.execute(f"DELETE FROM campaigns WHERE id={_CAMP}")
        conn.execute(f"DELETE FROM users WHERE id IN ({_U1}, {_U2})")
        conn.commit()
    finally:
        conn.close()


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def db_fixtures():
    _setup()
    yield
    _cleanup()


# ─── Test główny: username auto-normalizes to char name ───────────────────────

def test_whisper_username_normalized_to_char_name():
    """POST whisper_to username → stored as char name → GET odbiorca widzi szept."""
    client = _client()

    # MP1 sends whisper with username of MP2
    resp = client.post(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        json={
            "message": "Tajny szept przez username",
            "character_name": _CHAR1_NAME,
            "whisper_to": _U2_USERNAME,  # username, not char name
        },
        params={"user_id": _U1},
    )
    assert resp.status_code == 201, f"POST failed: {resp.status_code} {resp.text}"

    # MP2 fetches chat — should see the whisper (filtered by char name)
    resp2 = client.get(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        params={"user_id": _U2},
    )
    assert resp2.status_code == 200, f"GET failed: {resp2.status_code}"
    messages = resp2.json()["messages"]
    whispers = [m for m in messages if m.get("whisper_to") is not None]
    assert len(whispers) == 1, (
        f"MP2 powinien widzieć 1 szept, widzi {len(whispers)}. "
        f"Bug: whisper_to '{_U2_USERNAME}' (username) nie znormalizowany do '{_CHAR2_NAME}'"
    )
    assert whispers[0]["message"] == "Tajny szept przez username"

    # Also verify that whisper_to was stored as char name (not username)
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            f"SELECT whisper_to FROM party_messages WHERE campaign_id={_CAMP} LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == _CHAR2_NAME, (
            f"DB powinien przechowywać char name '{_CHAR2_NAME}', "
            f"ale trzyma '{row[0]}'"
        )
    finally:
        conn.close()


# ─── Char name jako whisper_to działa bez zmian ───────────────────────────────

def test_whisper_char_name_stored_as_is():
    """POST whisper_to char name → stored unchanged → GET odbiorca widzi szept."""
    client = _client()

    resp = client.post(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        json={
            "message": "Szept przez char name",
            "character_name": _CHAR1_NAME,
            "whisper_to": _CHAR2_NAME,  # already char name
        },
        params={"user_id": _U1},
    )
    assert resp.status_code == 201, f"POST failed: {resp.status_code} {resp.text}"

    resp2 = client.get(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        params={"user_id": _U2},
    )
    messages = resp2.json()["messages"]
    whispers = [m for m in messages if m.get("whisper_to") is not None]
    assert len(whispers) == 1, f"MP2 powinien widzieć szept po char name. Widzi: {len(whispers)}"
    assert whispers[0]["message"] == "Szept przez char name"


# ─── Backward compat: wiadomość bez whisper ───────────────────────────────────

def test_public_message_no_whisper():
    """POST bez whisper_to → publik widzi, logika normalizacji nie odpala się."""
    client = _client()

    resp = client.post(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        json={
            "message": "Publiczna wiadomość",
            "character_name": _CHAR1_NAME,
        },
        params={"user_id": _U1},
    )
    assert resp.status_code == 201

    resp2 = client.get(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        params={"user_id": _U2},
    )
    messages = resp2.json()["messages"]
    public = [m for m in messages if m.get("whisper_to") is None]
    assert len(public) == 1
    assert public[0]["message"] == "Publiczna wiadomość"


# ─── Nieznany whisper_to → 400 ────────────────────────────────────────────────

def test_whisper_unknown_recipient_returns_400():
    """POST whisper_to nieznany user/char → 400, nie cichy przepadek."""
    client = _client()

    resp = client.post(
        f"/api/multiplayer/campaigns/{_CAMP}/chat",
        json={
            "message": "Szept do nikogo",
            "character_name": _CHAR1_NAME,
            "whisper_to": "nieistniejacy_user_xyz999",
        },
        params={"user_id": _U1},
    )
    assert resp.status_code == 400, (
        f"Nieznany whisper_to powinien dać 400, dostał {resp.status_code}"
    )
