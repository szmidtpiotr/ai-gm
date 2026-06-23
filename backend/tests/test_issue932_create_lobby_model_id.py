"""TDD: Issue #932 — POST /multiplayer/campaigns HTTP 500 (missing model_id in INSERT).

Verifies that create_lobby endpoint returns 200 and campaign has model_id='default'.
"""
import sqlite3
import sys
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DB_PATH = "/data/ai_gm.db"

HOST_USER_ID = 1  # demo user


def _cleanup_lobby(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM campaign_members WHERE campaign_id=?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id=?", (campaign_id,))
    conn.commit()
    conn.close()


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_create_lobby_returns_200():
    """POST /multiplayer/campaigns powinno zwrócić 200 + campaign_id."""
    resp = client.post(
        f"/api/multiplayer/campaigns?user_id={HOST_USER_ID}",
        json={"title": "Test932 Lobby", "max_players": 2, "round_timer_minutes": 60},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "campaign_id" in body, f"campaign_id missing from response: {body}"
    assert body["campaign_id"] > 0

    _cleanup_lobby(body["campaign_id"])


def test_create_lobby_campaign_has_model_id_default():
    """Kampania MP stworzona przez create_lobby ma model_id='default' w DB."""
    resp = client.post(
        f"/api/multiplayer/campaigns?user_id={HOST_USER_ID}",
        json={"title": "Test932 ModelId", "max_players": 2, "round_timer_minutes": 60},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    campaign_id = resp.json()["campaign_id"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT model_id, mode FROM campaigns WHERE id=?", (campaign_id,)
    ).fetchone()
    conn.close()

    assert row is not None, "Campaign not found in DB"
    assert row["model_id"] == "default", f"model_id={row['model_id']!r}, expected 'default'"
    assert row["mode"] == "multiplayer"

    _cleanup_lobby(campaign_id)


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_create_lobby_with_max_players_4():
    """Tworzenie lobby z max_players=4 nadal działa po fixie."""
    resp = client.post(
        f"/api/multiplayer/campaigns?user_id={HOST_USER_ID}",
        json={"title": "Test932 4P", "max_players": 4, "round_timer_minutes": 1440},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("lobby_status") == "open"

    _cleanup_lobby(body["campaign_id"])
