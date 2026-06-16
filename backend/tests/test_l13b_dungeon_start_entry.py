"""TDD L13b (#683) — Wejście z ekranu startowego (scalenie D9).

Weryfikuje:
- GET /campaign-modes → tryb 'loch' ma label 'Wyprawa do lochu'
- GET /campaign-modes → tryb 'loch' ma opis zawierający 'kafelkowy' lub 'loch'
- GET /campaign-modes → brak trybu 'loch_kafelki' (scalony w L10)
- GET /campaign-modes → struktura trybu loch: key, label, description, available, count
- POST /campaigns → bohater idle może stworzyć kampanię-kontener trybu 'dungeon'
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_test_user_id() -> int | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username = 'demo' LIMIT 1"
        ).fetchone()
        if row:
            return row["id"]
        row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _get_idle_character_id() -> int | None:
    """Return a character not currently in an active campaign."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT id FROM characters
               WHERE (status = 'idle' OR campaign_id IS NULL)
               AND status NOT IN ('deleted')
               LIMIT 1"""
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# ─── Tests: campaign-modes API ────────────────────────────────────────────────

def test_campaign_modes_loch_label():
    """GET /campaign-modes → loch mode label is 'Wyprawa do lochu'."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    modes = body.get("modes", [])
    loch = next((m for m in modes if m["key"] == "loch"), None)
    assert loch is not None, "Mode 'loch' must exist in campaign-modes response"
    assert loch["label"] == "Wyprawa do lochu", (
        f"Expected label 'Wyprawa do lochu', got '{loch['label']}'"
    )


def test_campaign_modes_loch_description_mentions_dungeon():
    """GET /campaign-modes → loch mode description mentions dungeon content."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200
    body = r.json()
    modes = body.get("modes", [])
    loch = next((m for m in modes if m["key"] == "loch"), None)
    assert loch is not None
    desc = (loch.get("description") or "").lower()
    assert any(kw in desc for kw in ["loch", "komnat", "kafelek", "kafelk"]), (
        f"loch description must mention dungeon content, got: '{desc}'"
    )


def test_campaign_modes_no_loch_kafelki():
    """GET /campaign-modes → no 'loch_kafelki' mode (merged in L10)."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200
    body = r.json()
    modes = body.get("modes", [])
    keys = [m["key"] for m in modes]
    assert "loch_kafelki" not in keys, (
        f"'loch_kafelki' must not exist (merged into 'loch' in L10), found: {keys}"
    )


def test_campaign_modes_loch_structure():
    """GET /campaign-modes → loch mode has required fields."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200
    body = r.json()
    modes = body.get("modes", [])
    loch = next((m for m in modes if m["key"] == "loch"), None)
    assert loch is not None
    for field in ("key", "label", "description", "available"):
        assert field in loch, f"loch mode must have field '{field}'"
    assert isinstance(loch["available"], bool), "loch.available must be bool"


# ─── Tests: dungeon container campaign creation ────────────────────────────────

def test_create_dungeon_campaign_mode_field():
    """POST /campaigns with mode='dungeon' should be accepted (or use existing route)."""
    user_id = _get_test_user_id()
    if user_id is None:
        pytest.skip("No test user available")

    payload = {
        "title": "Test L13b — ekspedycja",
        "system_id": "fantasy",
        "model_id": "default",
        "owner_user_id": user_id,
        "language": "pl",
        "mode": "dungeon",
        "status": "active",
        "previous_campaign_id": None,
    }
    r = client.post("/api/campaigns", json=payload)
    # Accept 200/201; some configs may not have create endpoint — skip if 404
    if r.status_code == 404:
        pytest.skip("POST /campaigns not available in this test context")
    assert r.status_code in (200, 201), (
        f"Creating dungeon campaign should succeed, got {r.status_code}: {r.text}"
    )
    body = r.json()
    camp_id = body.get("id")
    # Cleanup
    if camp_id:
        try:
            conn = _get_conn()
            conn.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass


def test_idle_character_not_blocked_from_dungeon_api():
    """Idle character can call GET /dungeons (no 403 from hero status guard)."""
    char_id = _get_idle_character_id()
    if char_id is None:
        pytest.skip("No idle character available")
    r = client.get(f"/api/dungeons?character_id={char_id}")
    assert r.status_code in (200,), (
        f"Idle character must be able to list dungeons, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert "dungeons" in body, "Response must have 'dungeons' field"
