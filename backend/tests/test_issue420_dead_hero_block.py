"""TDD: Issue #420 (E5) — dead-hero campaign is blocked (regression lock).

E5 was already satisfied by prior work (HTTP 410 on ended campaigns via
get_active_campaign_or_gone). This test locks that behaviour so it cannot regress.
"""
import sys, os, sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def test_ended_campaign_turns_blocked_410():
    """Listing turns on an ended campaign must be rejected with HTTP 410 (Gone)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE status = 'ended' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no ended campaign in DB")
    r = client.post(
        f"/api/campaigns/{row['id']}/turns",
        json={"text": "spróbuję kontynuować", "character_id": 1},
    )
    assert r.status_code == 410, f"expected 410 Gone, got {r.status_code}: {r.text[:200]}"


def test_active_campaign_not_blocked():
    """An active campaign must NOT be 410 (guard is status-specific)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE status = 'active' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no active campaign in DB")
    # GET campaign detail should succeed for an active campaign
    r = client.get(f"/api/campaigns/{row['id']}")
    assert r.status_code == 200, f"active campaign detail failed: {r.status_code}"
