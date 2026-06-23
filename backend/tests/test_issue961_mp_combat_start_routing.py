"""TDD #961: MP combat start endpoint must route to start_mp_combat, not solo initiate_combat.

POST /api/campaigns/{id}/combat/start with a multiplayer campaign currently hits the solo
router (registered first in main.py), which does character lookup by campaign_id — MP chars
have campaign_id=NULL and always fail with 'character not found'.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN = {"username": "demo", "password": "demo"}


def _admin_token():
    r = client.post("/api/admin/dev-login", json=ADMIN)
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return r.json()["token"]


def _create_user(token, suffix):
    uname = f"test961_{suffix}"
    r = client.post(
        "/api/admin/accounts/create",
        json={"username": uname, "password": "pw_961_ok!", "display_name": f"T961 {suffix}", "is_admin": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    r2 = client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    body = r2.json()
    accounts = body if isinstance(body, list) else body.get("items", body.get("accounts", []))
    user = next((a for a in accounts if a.get("username") == uname), None)
    assert user, f"user {uname} not found (create status={r.status_code}: {r.text})"
    return user["id"]


def _create_hero(uid, suffix=""):
    r = client.post(
        "/api/characters",
        json={
            "user_id": uid,
            "name": f"[961]Hero{suffix}",
            "system_id": "fantasy",
            "sheet_json": {"archetype": "warrior"},
        },
    )
    assert r.status_code == 200, f"create hero: {r.text}"
    return r.json()["id"]


def _setup_mp_lobby(h_id, g_id, h_hero, g_hero, g_username):
    """Create MP lobby, both players accept, return campaign_id."""
    r = client.post(
        "/api/multiplayer/campaigns",
        params={"user_id": h_id},
        json={"title": "[961test]", "system_id": "fantasy", "round_timer_minutes": 1, "max_players": 2},
    )
    assert r.status_code == 200, f"create lobby: {r.text}"
    cid = r.json()["campaign_id"]

    r = client.post(f"/api/multiplayer/campaigns/{cid}/accept",
                    params={"user_id": h_id}, json={"character_id": h_hero})
    assert r.status_code == 200, f"host accept: {r.text}"

    r = client.post(f"/api/multiplayer/campaigns/{cid}/invite/username",
                    params={"user_id": h_id}, json={"username": g_username})
    assert r.status_code == 200, f"invite: {r.text}"

    r = client.post(f"/api/multiplayer/campaigns/{cid}/accept",
                    params={"user_id": g_id}, json={"character_id": g_hero})
    assert r.status_code == 200, f"guest accept: {r.text}"
    return cid


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_mp_combat_start_routes_to_mp_service():
    """POST /combat/start for MP campaign must succeed and include ALL players in turn_order.

    Currently FAILS: solo router wins → 'character not found' (MP chars have campaign_id=NULL).
    After fix: must return MP combat state with both heroes in turn_order.
    """
    token = _admin_token()
    h_id = _create_user(token, "host")
    g_id = _create_user(token, "guest")
    h_hero = _create_hero(h_id, "H")
    g_hero = _create_hero(g_id, "G")

    # get guest username for invite
    r = client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    accounts = r.json() if isinstance(r.json(), list) else r.json().get("items", r.json().get("accounts", []))
    g_uname = next(a["username"] for a in accounts if a["id"] == g_id)

    cid = _setup_mp_lobby(h_id, g_id, h_hero, g_hero, g_uname)

    # This is the call that currently fails with 'character not found'
    r = client.post(
        f"/api/campaigns/{cid}/combat/start",
        json={"enemy_keys": ["goblin"]},
        params={"user_id": h_id},
    )
    assert r.status_code == 200, (
        f"MP combat start must return 200, got {r.status_code}: {r.text}"
    )

    body = r.json()
    assert "turn_order" in body, f"MP combat state must have turn_order, got: {body}"
    player_slots = [t for t in body["turn_order"] if str(t).startswith("player:")]
    assert len(player_slots) >= 2, (
        f"MP combat must include both heroes in turn_order, got: {body['turn_order']}"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_solo_combat_start_still_works_after_mp_routing_fix():
    """Solo campaign combat start must still work after the MP routing fix.

    Uses the existing demo campaign (ID=1, mode='solo') — always present in DEV.
    Verifies solo path is not broken by the MP mode-check branch.
    """
    # Demo campaign 1 has a character attached. Start combat then clean up.
    # 409 means combat already active — also acceptable (means routing worked, not crashed).
    r = client.post(
        "/api/campaigns/1/combat/start",
        json={"enemy_keys": ["goblin"]},
    )
    assert r.status_code in (200, 409, 400), (
        f"Solo combat start must not 404/500, got {r.status_code}: {r.text}"
    )
    # Key assertion: must NOT be 'character not found' (that would mean routing is broken)
    if r.status_code == 400:
        assert "character not found" not in r.text.lower(), (
            f"Solo must not fail with 'character not found' — got: {r.text}"
        )


# ─── _maybe_start_combat_from_gm_tag MP routing ──────────────────────────────

def test_maybe_start_combat_gm_tag_calls_mp_service_for_mp_campaign():
    """_maybe_start_combat_from_gm_tag must use start_mp_combat for MP campaigns.

    Patches HF-7 validation to pass + mocks the DB mode query so a fake MP campaign_id works.
    After fix: start_mp_combat called; solo initiate_combat NOT called.
    """
    from unittest.mock import patch, MagicMock, call
    import sqlite3

    from app.api.turns import _maybe_start_combat_from_gm_tag

    mock_mp_result = {
        "id": 9991,
        "campaign_id": 99991,
        "turn_order": ["player:1", "goblin_01", "player:2"],
        "current_turn": "player:1",
        "active": True,
    }

    # sqlite3.connect mock: returns mode='multiplayer' for the campaign mode query.
    # Use a plain dict so ["mode"] access works without MagicMock dunder tricks.
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"mode": "multiplayer"}

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_cursor
    mock_db.row_factory = None
    mock_db.__enter__ = lambda s: s
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("app.services.multiplayer_round_service.start_mp_combat", return_value=mock_mp_result) as mock_mp, \
         patch("app.services.combat_service.get_active_combat", return_value=None), \
         patch("app.services.combat_service.initiate_combat") as mock_solo, \
         patch("app.api.turns._validate_combat_start_target", return_value=(True, None)), \
         patch("sqlite3.connect", return_value=mock_db):

        result = _maybe_start_combat_from_gm_tag(
            campaign_id=99991,
            character_id=1,
            assistant_text="Goblin atakuje! [COMBAT_START:goblin]",
        )

    # After fix: mp service called, solo NOT called
    assert mock_mp.called, "_maybe_start_combat_from_gm_tag must call start_mp_combat for MP campaigns"
    assert not mock_solo.called, "initiate_combat (solo) must NOT be called for MP campaigns"
