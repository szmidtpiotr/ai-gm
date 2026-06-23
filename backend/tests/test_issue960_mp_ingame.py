"""TDD #960: MP in-game harness — backend API contracts for Playwright helpers.

Verifies create→accept→invite→accept→start flow (mirrors setupMpViaApi in mp.js)
and party-chat POST/GET. These APIs must hold so Playwright mp_ingame.spec.js
can rely on them without mocking.
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
    uname = f"test960_{suffix}"
    r = client.post(
        "/api/admin/accounts/create",
        json={"username": uname, "password": "pw_960_ok", "display_name": f"T960 {suffix}", "is_admin": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 409 = already exists (idempotent), 200 = created
    if r.status_code not in (200, 409):
        # Try to get existing user anyway
        pass
    r2 = client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    body = r2.json()
    accounts = body if isinstance(body, list) else body.get("items", body.get("accounts", []))
    user = next((a for a in accounts if a.get("username") == uname), None)
    assert user, f"user {uname} not found after create (create status={r.status_code}: {r.text})"
    return user["id"]


def _create_hero(uid, arch="warrior", suffix=""):
    r = client.post(
        "/api/characters",
        json={
            "user_id": uid,
            "name": f"[960]Hero{suffix}",
            "system_id": "fantasy",
            "sheet_json": {"archetype": arch},
        },
    )
    assert r.status_code == 200, f"create hero: {r.text}"
    return r.json()["id"]


def _setup_lobby(h_id, g_id, h_hero, g_hero, g_username, title="[960test]"):
    """Create lobby, both players accept, return campaign_id."""
    r = client.post(
        "/api/multiplayer/campaigns",
        params={"user_id": h_id},
        json={"title": title, "system_id": "fantasy", "round_timer_minutes": 1, "max_players": 2},
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

def test_mp_lobby_flow_create_to_start():
    """setupMpViaApi flow: create → 2 accept → start → lobby_status=started."""
    token = _admin_token()
    h_id = _create_user(token, "h1")
    g_id = _create_user(token, "g1")
    h_hero = _create_hero(h_id, "warrior", "h1")
    g_hero = _create_hero(g_id, "scholar", "g1")

    cid = _setup_lobby(h_id, g_id, h_hero, g_hero, "test960_g1", "[960test] lobby")

    r = client.post(f"/api/multiplayer/campaigns/{cid}/start", params={"user_id": h_id})
    assert r.status_code == 200, f"start: {r.text}"
    body = r.json()
    assert body.get("campaign_id") == cid, f"campaign_id missing: {body}"
    assert body.get("lobby_status") == "started", f"expected started: {body}"
    assert body.get("players") == 2, f"expected 2 players: {body}"


def test_party_chat_send_and_receive():
    """POST /chat stores a message; GET returns it to all accepted members (CP11 backend)."""
    token = _admin_token()
    h_id = _create_user(token, "ch1")
    g_id = _create_user(token, "cg1")
    h_hero = _create_hero(h_id, "warrior", "ch1")
    g_hero = _create_hero(g_id, "scholar", "cg1")

    cid = _setup_lobby(h_id, g_id, h_hero, g_hero, "test960_cg1", "[960chat]")
    client.post(f"/api/multiplayer/campaigns/{cid}/start", params={"user_id": h_id})

    # Post public message
    r = client.post(
        f"/api/multiplayer/campaigns/{cid}/chat",
        params={"user_id": h_id},
        json={"message": "Cześć drużyno!", "character_name": "[960]Heroch1"},
    )
    assert r.status_code == 201, f"post chat: {r.text}"

    # Host sees own message
    r = client.get(f"/api/multiplayer/campaigns/{cid}/chat", params={"user_id": h_id})
    assert r.status_code == 200, f"get chat host: {r.text}"
    msgs = r.json().get("messages", [])
    assert any("Cześć drużyno!" in m.get("message", "") for m in msgs), \
        f"host can't see own msg: {msgs}"

    # Guest sees public message (CP11 — public visible to all)
    r = client.get(f"/api/multiplayer/campaigns/{cid}/chat", params={"user_id": g_id})
    assert r.status_code == 200, f"get chat guest: {r.text}"
    msgs = r.json().get("messages", [])
    assert any("Cześć drużyno!" in m.get("message", "") for m in msgs), \
        f"guest can't see public msg: {msgs}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_lobby_get_returns_round_timer_minutes():
    """GET /lobby returns round_timer_minutes — required by enterMpGame fix (#960)."""
    token = _admin_token()
    h_id = _create_user(token, "lt1")
    g_id = _create_user(token, "lt2")
    h_hero = _create_hero(h_id, suffix="lt1")
    g_hero = _create_hero(g_id, suffix="lt2")

    cid = _setup_lobby(h_id, g_id, h_hero, g_hero, "test960_lt2", "[960timer]")

    r = client.get(f"/api/multiplayer/campaigns/{cid}/lobby", params={"user_id": h_id})
    assert r.status_code == 200, f"get lobby: {r.text}"
    body = r.json()
    assert "round_timer_minutes" in body, f"missing round_timer_minutes: {body}"
    assert body["round_timer_minutes"] == 1, f"expected 1 min timer: {body}"
    # members list with role — used by enterMpGame to detect spectator
    assert "members" in body, f"missing members: {body}"
    members = body["members"]
    assert any(m.get("role") in ("owner", "player") for m in members), \
        f"no owner/player in members: {members}"
