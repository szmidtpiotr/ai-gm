"""TDD: Issue #781 — GET /api/campaigns/{id}/game-events per-campaign viewer.

Red: endpoint route does not exist → query helper / response shape missing.
Green: endpoint returns game_events for the campaign, newest first, filterable.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient


_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    campaign_id INTEGER,
    character_id INTEGER,
    user_id INTEGER,
    event_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _seed(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data) "
        "VALUES (?,?,?,?,?,?)",
        ("quest_complete", "info", 555, 1, 1, json.dumps({"quest_title": "Uratuj wieś", "xp": 50})),
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data) "
        "VALUES (?,?,?,?,?,?)",
        ("gold_grant", "info", 555, 1, 1, json.dumps({"amount": 30, "new_total_gp": 80})),
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data) "
        "VALUES (?,?,?,?,?,?)",
        ("combat_victory", "info", 999, 2, 1, json.dumps({"enemy": "goblin"})),  # other campaign
    )
    conn.commit()
    conn.close()


def _client(tmp_db):
    import app.api.campaigns as campaigns_mod
    campaigns_mod.DB_PATH = tmp_db
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(campaigns_mod.router, prefix="/api")
    return TestClient(app)


# ── Test 1: endpoint returns events for the campaign ─────────────────────────

def test_game_events_endpoint_returns_campaign_events(tmp_path):
    """GET /campaigns/{id}/game-events returns only that campaign's events."""
    db = str(tmp_path / "t781.db")
    _seed(db)
    client = _client(db)

    r = client.get("/api/campaigns/555/game-events")
    assert r.status_code == 200, f"endpoint missing or errored: {r.status_code}"
    body = r.json()
    assert body["campaign_id"] == 555
    assert body["count"] == 2, f"expected 2 events for campaign 555, got {body['count']}"
    types = {e["event_type"] for e in body["game_events"]}
    assert types == {"quest_complete", "gold_grant"}, f"unexpected types: {types}"


# ── Test 2: event_data parsed to dict under 'data' key ───────────────────────

def test_game_events_data_parsed_to_dict(tmp_path):
    """event_data JSON must be returned as parsed dict (key 'data')."""
    db = str(tmp_path / "t781b.db")
    _seed(db)
    client = _client(db)

    r = client.get("/api/campaigns/555/game-events")
    body = r.json()
    qc = next(e for e in body["game_events"] if e["event_type"] == "quest_complete")
    assert isinstance(qc["data"], dict), "data must be a parsed dict"
    assert qc["data"].get("quest_title") == "Uratuj wieś"
    assert qc["data"].get("xp") == 50


# ── Test 3: event_type filter ────────────────────────────────────────────────

def test_game_events_event_type_filter(tmp_path):
    """?event_type=gold_grant returns only gold_grant rows."""
    db = str(tmp_path / "t781c.db")
    _seed(db)
    client = _client(db)

    r = client.get("/api/campaigns/555/game-events?event_type=gold_grant")
    body = r.json()
    assert body["count"] == 1
    assert body["game_events"][0]["event_type"] == "gold_grant"


# ── Test 4: empty campaign returns empty list, not error ─────────────────────

def test_game_events_empty_campaign(tmp_path):
    """Campaign with no events returns count=0, empty list — not 500."""
    db = str(tmp_path / "t781d.db")
    _seed(db)
    client = _client(db)

    r = client.get("/api/campaigns/12345/game-events")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["game_events"] == []


# ── Test 5: newest first ordering ────────────────────────────────────────────

def test_game_events_newest_first(tmp_path):
    """Events ordered by id DESC (newest first)."""
    db = str(tmp_path / "t781e.db")
    _seed(db)
    client = _client(db)

    r = client.get("/api/campaigns/555/game-events")
    body = r.json()
    ids = [e["id"] for e in body["game_events"]]
    assert ids == sorted(ids, reverse=True), f"not newest-first: {ids}"
