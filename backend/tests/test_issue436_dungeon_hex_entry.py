"""TDD: Issue #436 — E21 Wejście do lochu z mapy hex kampanii.

Backend: hex-travel do dungeon hexu powinien zwracać dungeon_prompt=True
żeby frontend mógł automatycznie otworzyć picker lochów.
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Helper ──────────────────────────────────────────────────────────────────

def _get_dungeon_hex_coords():
    """Return (q, r) of a dungeon hex from world_hexes, or None."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT q, r FROM world_hexes WHERE hex_type='dungeon' AND is_active=1 LIMIT 1"
        ).fetchone()
        return (row["q"], row["r"]) if row else None
    finally:
        conn.close()


def _get_demo_campaign_with_character():
    """Return (campaign_id, character_id) for demo user's first active campaign."""
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT c.id, ch.id AS char_id
               FROM campaigns c
               JOIN characters ch ON ch.campaign_id = c.id
               WHERE c.owner_user_id = 1 AND c.status = 'active'
                 AND c.mode != 'dungeon'
               LIMIT 1"""
        ).fetchone()
        if row:
            return row["id"], row["char_id"]
        return None, None
    finally:
        conn.close()


# ─── Test główny — dungeon_prompt w odpowiedzi hex-travel ────────────────────

def test_hex_travel_to_dungeon_hex_returns_dungeon_prompt():
    """hex-travel do hexu z hex_type='dungeon' powinno zwrócić dungeon_prompt=True."""
    coords = _get_dungeon_hex_coords()
    if coords is None:
        pytest.skip("Brak dungeon hexów w world_hexes")

    campaign_id, character_id = _get_demo_campaign_with_character()
    if campaign_id is None:
        pytest.skip("Brak aktywnej kampanii demo")

    from app.main import app
    client = TestClient(app)

    q, r = coords
    resp = client.post(
        f"/api/campaigns/{campaign_id}/hex-travel",
        json={"character_id": character_id, "destination_q": q, "destination_r": r},
    )
    # endpoint musi istnieć (może zwrócić 200 lub 422 — interesuje nas shape)
    assert resp.status_code in (200, 207), f"Nieoczekiwany status: {resp.status_code}"
    body = resp.json()

    # NOWE pole — musi być w odpowiedzi gdy docelowy hex_type='dungeon'
    assert "dungeon_prompt" in body, (
        "hex-travel do dungeon hexu powinno zwracać 'dungeon_prompt' w odpowiedzi. "
        "Frontend używa tego do auto-otwierania pickera lochów."
    )
    assert body["dungeon_prompt"] is True, (
        f"dungeon_prompt powinno być True dla hex_type='dungeon', got: {body.get('dungeon_prompt')}"
    )


# ─── Test — hex-travel do NIE-dungeon hexu NIE zwraca dungeon_prompt ─────────

def test_hex_travel_to_non_dungeon_hex_no_dungeon_prompt():
    """hex-travel do zwykłego hexu (las, równiny) nie powinno zwracać dungeon_prompt."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT q, r FROM world_hexes WHERE hex_type != 'dungeon' AND is_active=1 LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("Brak nie-dungeon hexów")
        q, r = row["q"], row["r"]
    finally:
        conn.close()

    campaign_id, character_id = _get_demo_campaign_with_character()
    if campaign_id is None:
        pytest.skip("Brak aktywnej kampanii demo")

    from app.main import app
    client = TestClient(app)

    resp = client.post(
        f"/api/campaigns/{campaign_id}/hex-travel",
        json={"character_id": character_id, "destination_q": q, "destination_r": r},
    )
    assert resp.status_code in (200, 207)
    body = resp.json()

    # Dla nie-dungeon hexu: dungeon_prompt powinno być False lub nie istnieć
    dungeon_prompt = body.get("dungeon_prompt", False)
    assert not dungeon_prompt, (
        f"Nie-dungeon hex nie powinien zwracać dungeon_prompt=True, got: {dungeon_prompt}"
    )


# ─── Test — world-map zwraca dungeon hexes z hex_type='dungeon' ───────────────

def test_world_map_includes_dungeon_hex_type():
    """GET /api/campaigns/{id}/world-map powinno zwracać hexes z hex_type='dungeon'."""
    campaign_id, character_id = _get_demo_campaign_with_character()
    if campaign_id is None:
        pytest.skip("Brak aktywnej kampanii demo")

    from app.main import app
    client = TestClient(app)

    resp = client.get(f"/api/campaigns/{campaign_id}/world-map?character_id={character_id}")
    assert resp.status_code == 200
    body = resp.json()

    hexes = body.get("hexes", [])
    assert isinstance(hexes, list), "hexes powinno być listą"

    # Każdy hex musi mieć pole hex_type (potrzebne do E21 frontend detection)
    for h in hexes:
        assert "hex_type" in h, f"Brak hex_type w hexie {h.get('q')},{h.get('r')}"
