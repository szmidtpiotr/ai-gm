"""TDD: Issue #925 — GF5 MP frontend sections (my-lobbies, my-active-games, my-invites).

Verifies that the three MP list endpoints return correct shapes and data
for an invited/accepted user.
"""
import pytest
import sqlite3
import sys, os
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DB_PATH = "/data/ai_gm.db"


def _get_username(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row["username"] if row else None


# ─── helpers ──────────────────────────────────────────────────────────────────

def _create_mp_campaign(host_user_id: int, title: str = "Test MP Game") -> int:
    """Create a multiplayer campaign directly in DB (bypasses create_lobby model_id bug)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """INSERT INTO campaigns
           (title, system_id, owner_user_id, model_id, mode, status,
            round_timer_hours, round_timer_minutes, max_players, host_user_id, lobby_status)
           VALUES (?, 'fantasy', ?, 'default', 'multiplayer', 'active', 24, 1440, 4, ?, 'open')""",
        (title, host_user_id, host_user_id),
    )
    campaign_id = cur.lastrowid
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status) VALUES (?, ?, 'owner', 'accepted')",
        (campaign_id, host_user_id),
    )
    conn.commit()
    conn.close()
    return campaign_id


def _invite_user(campaign_id: int, host_user_id: int, target_username: str):
    resp = client.post(
        f"/api/multiplayer/campaigns/{campaign_id}/invite/username",
        json={"username": target_username},
        params={"user_id": host_user_id},
    )
    return resp


def _cleanup_campaign(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM campaign_members WHERE campaign_id=?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id=?", (campaign_id,))
    conn.commit()
    conn.close()


# ─── Test 1: my-invites returns pending invites ────────────────────────────────

def test_my_invites_returns_pending_for_invited_user():
    """A user who has been invited sees the invite in /multiplayer/my-invites."""
    host_id = 1
    guest_id = 2
    guest_username = _get_username(guest_id)
    if not guest_username:
        pytest.skip("guest user 2 not found in DB")

    campaign_id = _create_mp_campaign(host_id, "GF5 Invite Test")

    # Invite the guest
    inv_resp = _invite_user(campaign_id, host_id, guest_username)
    assert inv_resp.status_code in (200, 409), f"invite failed: {inv_resp.text}"

    # Now guest should see the invite
    resp = client.get("/api/multiplayer/my-invites", params={"user_id": guest_id})
    assert resp.status_code == 200, f"my-invites failed: {resp.text}"

    body = resp.json()
    assert "invites" in body, "response missing 'invites' key"

    # Find our campaign in the list
    ids = [i["campaign_id"] for i in body["invites"]]
    assert campaign_id in ids, f"campaign {campaign_id} not in my-invites: {ids}"

    _cleanup_campaign(campaign_id)


# ─── Test 2: my-lobbies returns open lobby for accepted member ─────────────────

def test_my_lobbies_returns_open_lobby_for_member():
    """After accepting an invite, the campaign appears in /multiplayer/my-lobbies."""
    host_id = 1
    guest_id = 2
    guest_username = _get_username(guest_id)
    if not guest_username:
        pytest.skip("guest user 2 not found in DB")

    campaign_id = _create_mp_campaign(host_id, "GF5 Lobby Test")

    # Invite guest
    _invite_user(campaign_id, host_id, guest_username)

    # Guest accepts (without character — spectator path)
    accept_resp = client.post(
        f"/api/multiplayer/campaigns/{campaign_id}/accept",
        json={"as_spectator": True},
        params={"user_id": guest_id},
    )
    assert accept_resp.status_code == 200, f"accept failed: {accept_resp.text}"

    # Guest should now see lobby
    resp = client.get("/api/multiplayer/my-lobbies", params={"user_id": guest_id})
    assert resp.status_code == 200
    body = resp.json()
    assert "lobbies" in body

    ids = [l["campaign_id"] for l in body["lobbies"]]
    assert campaign_id in ids, f"campaign {campaign_id} not in my-lobbies: {ids}"

    _cleanup_campaign(campaign_id)


# ─── Test 3: my-active-games returns started game for member ──────────────────

def test_my_active_games_returns_started_game_for_member():
    """After lobby is started, campaign appears in /multiplayer/my-active-games."""
    host_id = 1
    guest_id = 2
    guest_username = _get_username(guest_id)
    if not guest_username:
        pytest.skip("guest user 2 not found in DB")

    campaign_id = _create_mp_campaign(host_id, "GF5 Active Game Test")

    # Invite + accept as spectator
    _invite_user(campaign_id, host_id, guest_username)
    client.post(
        f"/api/multiplayer/campaigns/{campaign_id}/accept",
        json={"as_spectator": True},
        params={"user_id": guest_id},
    )

    # Host starts the game
    start_resp = client.post(
        f"/api/multiplayer/campaigns/{campaign_id}/start",
        params={"user_id": host_id},
    )
    assert start_resp.status_code == 200, f"start failed: {start_resp.text}"

    # Guest should see active game
    resp = client.get("/api/multiplayer/my-active-games", params={"user_id": guest_id})
    assert resp.status_code == 200
    body = resp.json()
    assert "games" in body

    ids = [g["campaign_id"] for g in body["games"]]
    assert campaign_id in ids, f"campaign {campaign_id} not in my-active-games: {ids}"

    _cleanup_campaign(campaign_id)


# ─── Test 4: decline removes invite from my-invites ──────────────────────────

def test_decline_invite_removes_from_my_invites():
    """After declining, the invite no longer appears in /multiplayer/my-invites."""
    host_id = 1
    guest_id = 2
    guest_username = _get_username(guest_id)
    if not guest_username:
        pytest.skip("guest user 2 not found in DB")

    campaign_id = _create_mp_campaign(host_id, "GF5 Decline Test")
    _invite_user(campaign_id, host_id, guest_username)

    # Verify invite exists
    before = client.get("/api/multiplayer/my-invites", params={"user_id": guest_id})
    before_ids = [i["campaign_id"] for i in before.json().get("invites", [])]
    assert campaign_id in before_ids, "invite not created — test setup failed"

    # Decline
    dec_resp = client.post(
        f"/api/multiplayer/campaigns/{campaign_id}/decline",
        params={"user_id": guest_id},
    )
    assert dec_resp.status_code == 200

    # Should be gone
    after = client.get("/api/multiplayer/my-invites", params={"user_id": guest_id})
    after_ids = [i["campaign_id"] for i in after.json().get("invites", [])]
    assert campaign_id not in after_ids, f"invite still in list after decline: {after_ids}"

    _cleanup_campaign(campaign_id)
