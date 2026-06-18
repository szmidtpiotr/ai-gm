"""TDD: Issue #779 — GET /api/admin/campaigns/{id}/quests-xp (zakładka Questy+XP)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_ADMIN_TOKEN = None


def _get_token():
    global _ADMIN_TOKEN
    if _ADMIN_TOKEN:
        return _ADMIN_TOKEN
    for creds in [("admin", "admin"), ("demo", "demo")]:
        r = client.post("/api/admin/dev-login",
                        json={"username": creds[0], "password": creds[1]})
        if r.status_code == 200:
            _ADMIN_TOKEN = r.json()["token"]
            return _ADMIN_TOKEN
    raise RuntimeError("Cannot obtain admin token")


def _auth():
    return {"Authorization": f"Bearer {_get_token()}"}


def _find_campaign_with_quests():
    """Find a campaign_id that has character_quests rows AND exists in campaigns table."""
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT cq.campaign_id FROM character_quests cq
               JOIN campaigns c ON c.id = cq.campaign_id LIMIT 1"""
        ).fetchone()
        return row["campaign_id"] if row else None
    finally:
        conn.close()


def _find_campaign_with_xp():
    """Find a campaign_id that has character_xp_grants rows AND exists in campaigns table."""
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT g.campaign_id FROM character_xp_grants g
               JOIN campaigns c ON c.id = g.campaign_id LIMIT 1"""
        ).fetchone()
        return row["campaign_id"] if row else None
    finally:
        conn.close()


def _any_campaign_id():
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns LIMIT 1").fetchone()
        return row["id"] if row else 1
    finally:
        conn.close()


# ─── Test 1: endpoint istnieje i zwraca poprawny kształt ────────────────────

def test_quests_xp_endpoint_returns_correct_shape():
    """GET /api/admin/campaigns/{id}/quests-xp zwraca quests + xp_grants."""
    cid = _any_campaign_id()
    r = client.get(f"/api/admin/campaigns/{cid}/quests-xp", headers=_auth())
    assert r.status_code == 200, f"Endpoint brakuje lub error: {r.status_code} {r.text}"
    body = r.json()
    assert "quests" in body, "Brak klucza 'quests' w odpowiedzi"
    assert "xp_grants" in body, "Brak klucza 'xp_grants' w odpowiedzi"
    assert isinstance(body["quests"], list)
    assert isinstance(body["xp_grants"], list)


# ─── Test 2: pola questów są kompletne ───────────────────────────────────────

def test_quest_fields_present():
    """Każdy quest ma wymagane pola."""
    cid = _find_campaign_with_quests()
    if cid is None:
        pytest.skip("Brak questów w DB")

    r = client.get(f"/api/admin/campaigns/{cid}/quests-xp", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    quests = body["quests"]
    assert len(quests) > 0, f"Kampania {cid} ma questy w DB ale endpoint zwrócił pustą listę"
    for q in quests:
        for field in ("id", "title", "status", "quest_type", "created_turn", "campaign_id"):
            assert field in q, f"Quest brakuje pola '{field}': {q}"


# ─── Test 3: pola grantów XP są kompletne ────────────────────────────────────

def test_xp_grant_fields_present():
    """Każdy grant XP ma wymagane pola."""
    cid = _find_campaign_with_xp()
    if cid is None:
        pytest.skip("Brak xp_grants w DB")

    r = client.get(f"/api/admin/campaigns/{cid}/quests-xp", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    grants = body["xp_grants"]
    assert len(grants) > 0, f"Kampania {cid} ma XP grants w DB ale endpoint zwrócił pustą listę"
    for g in grants:
        for field in ("id", "amount", "reason", "source", "turn_number", "campaign_id"):
            assert field in g, f"XP grant brakuje pola '{field}': {g}"


# ─── Test 4: 401 bez tokena ───────────────────────────────────────────────────

def test_quests_xp_requires_auth():
    """Endpoint bez tokena → 401."""
    cid = _any_campaign_id()
    r = client.get(f"/api/admin/campaigns/{cid}/quests-xp")
    assert r.status_code == 401, f"Oczekiwano 401, dostałem {r.status_code}"


# ─── Test 5: 404 dla nieistniejącej kampanii ─────────────────────────────────

def test_quests_xp_404_for_missing_campaign():
    """Kampania 999999999 → 404."""
    r = client.get("/api/admin/campaigns/999999999/quests-xp", headers=_auth())
    assert r.status_code == 404, f"Oczekiwano 404, dostałem {r.status_code}"


# ─── Test 6: backward compat — istniejące endpointy kampanii działają ────────

def test_existing_campaign_endpoints_unaffected():
    """Istniejący /turns nie jest naruszony przez nowe endpointy."""
    cid = _any_campaign_id()
    r = client.get(f"/api/admin/campaigns/{cid}/turns", headers=_auth())
    assert r.status_code == 200
    assert "items" in r.json()
