"""TDD: Issue #416 — Player HUD quest bar loaded on campaign entry."""
import sys, os, json, sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ─── Helpers ────────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")

def _get_campaign_quests(campaign_id: int):
    """Call the player-facing quests endpoint."""
    return client.get(f"/api/campaigns/{campaign_id}/quests")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_campaign_quests_endpoint_exists():
    """GET /campaigns/{id}/quests must exist and return active_quests list."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns LIMIT 1").fetchone()
    finally:
        conn.close()

    if not row:
        pytest.skip("No campaigns in DB")

    campaign_id = row["id"]
    r = _get_campaign_quests(campaign_id)

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "active_quests" in body, f"Response missing 'active_quests': {body}"
    assert isinstance(body["active_quests"], list), f"active_quests must be list, got: {type(body['active_quests'])}"


def test_campaign_quests_returns_stored_quests():
    """#999: active quests from character_quests (source of truth) must be returned.

    Updated from the old contract (seeded game_sessions.active_quests) — the endpoint
    now reads character_quests directly, so world_state can no longer drift the bar.
    """
    seed_title = "Znajdź artefakt #999test"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns LIMIT 1").fetchone()
        if not row:
            pytest.skip("No campaigns in DB")
        campaign_id = row["id"]

        # Seed a known ACTIVE quest into the source of truth: character_quests
        conn.execute(
            """INSERT INTO character_quests
                   (character_id, campaign_id, quest_type, title, narrative, status, created_turn)
               VALUES (?,?,?,?,?,?,?)""",
            (999001, campaign_id, "main", seed_title, "Pobierz artefakt ze skrzynki", "active", 9999),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        r = _get_campaign_quests(campaign_id)
        assert r.status_code == 200
        body = r.json()
        quests = body["active_quests"]
        assert len(quests) >= 1, "Expected at least 1 quest in response"
        titles = [q["title"] for q in quests]
        assert seed_title in titles, f"Seeded quest not found in response: {quests}"
        # narrative mapped to objective for the HUD
        seeded = next(q for q in quests if q["title"] == seed_title)
        assert seeded["objective"] == "Pobierz artefakt ze skrzynki"
    finally:
        # cleanup — don't pollute the shared DEV DB
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM character_quests WHERE title = ?", (seed_title,))
        conn.commit()
        conn.close()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_campaign_detail_endpoint_still_works():
    """GET /campaigns/{id} must still work (no regression)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns LIMIT 1").fetchone()
    finally:
        conn.close()

    if not row:
        pytest.skip("No campaigns in DB")

    r = client.get(f"/api/campaigns/{row['id']}")
    assert r.status_code == 200
    body = r.json()
    assert "id" in body, "Campaign detail endpoint broken"
