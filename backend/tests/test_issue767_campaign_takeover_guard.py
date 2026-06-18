"""TDD: Issue #767 — Hero B must not be able to take over active campaign owned by Hero A.

Bug: assign_hero_to_campaign() blindly frees the existing hero from a campaign
when assigning a new hero — no check whether the existing hero belongs to a
different user. This allowed Hero B (SMOKE test character) to hijack Mizel's
active campaign, evict Mizel, and play turns there.

Fix:
- assign_hero_to_campaign: if existing hero.user_id != requester user_id → 409
- create_character (POST /campaigns/{id}/characters): same guard
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout = 30000")
    return c


def _make_user(conn, username):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, role) VALUES (?,?,?,?)",
        (username, "x", username, "player"),
    )
    conn.commit()
    return cur.lastrowid


def _make_campaign(conn, owner_user_id, title="TestCamp767"):
    cur = conn.execute(
        """INSERT INTO campaigns
               (title, system_id, status, owner_user_id, gm_plan_json, model_id)
           VALUES (?,?,?,?,?,?)""",
        (title, "default", "active", owner_user_id, "{}", "gpt-4o-mini"),
    )
    conn.commit()
    return cur.lastrowid


def _make_hero(conn, user_id, campaign_id=None, status="idle", name="Hero767"):
    cur = conn.execute(
        """INSERT INTO characters
               (user_id, campaign_id, name, system_id, sheet_json, is_active, status)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, campaign_id, name, "default", "{}", 1, status),
    )
    conn.commit()
    return cur.lastrowid


def _cleanup(conn, chars, camps, users):
    if chars:
        conn.execute(
            "DELETE FROM characters WHERE id IN ({})".format(",".join("?" * len(chars))),
            chars,
        )
    if camps:
        conn.execute(
            "DELETE FROM campaigns WHERE id IN ({})".format(",".join("?" * len(camps))),
            camps,
        )
    if users:
        conn.execute(
            "DELETE FROM users WHERE id IN ({})".format(",".join("?" * len(users))),
            users,
        )
    conn.commit()


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.fixture
def scenario():
    """Create two users, one campaign (owned by user A + hero A in it), one idle hero B."""
    conn = _db()
    chars, camps, users = [], [], []

    import os
    pid = os.getpid()
    user_a = _make_user(conn, f"test767_userA_{pid}")
    users.append(user_a)
    user_b = _make_user(conn, f"test767_userB_{pid}")
    users.append(user_b)

    camp = _make_campaign(conn, user_a, "Camp767_A")
    camps.append(camp)

    hero_a = _make_hero(conn, user_a, campaign_id=camp, status="in_campaign", name="HeroA_767")
    chars.append(hero_a)

    hero_b = _make_hero(conn, user_b, name="HeroB_767")
    chars.append(hero_b)

    # Same-user second hero — the real Mizel/[SMOKE] incident: both heroes user A
    hero_a2 = _make_hero(conn, user_a, name="HeroA2_767")
    chars.append(hero_a2)

    empty_camp = _make_campaign(conn, user_b, "Camp767_empty")
    camps.append(empty_camp)

    conn.close()

    yield {
        "user_a": user_a,
        "user_b": user_b,
        "camp": camp,
        "hero_a": hero_a,
        "hero_a2": hero_a2,
        "hero_b": hero_b,
        "empty_camp": empty_camp,
    }

    conn2 = _db()
    _cleanup(conn2, chars, camps, users)
    conn2.close()


def test_assign_different_user_hero_returns_409(scenario):
    """Hero B cannot take over Hero A's active campaign — must get 409."""
    resp = client.post(
        f"/api/characters/{scenario['hero_b']}/assign-campaign",
        json={"campaign_id": scenario["camp"], "user_id": scenario["user_b"]},
    )
    assert resp.status_code == 409, (
        f"Expected 409, got {resp.status_code}: {resp.text}"
    )


def test_hero_a_not_evicted_after_failed_takeover(scenario):
    """Hero A must still be in_campaign after a blocked takeover attempt."""
    client.post(
        f"/api/characters/{scenario['hero_b']}/assign-campaign",
        json={"campaign_id": scenario["camp"], "user_id": scenario["user_b"]},
    )
    conn = _db()
    row = conn.execute(
        "SELECT status, campaign_id FROM characters WHERE id = ?", (scenario["hero_a"],)
    ).fetchone()
    conn.close()
    assert row["status"] == "in_campaign"
    assert row["campaign_id"] == scenario["camp"]


def test_same_user_other_hero_cannot_take_over(scenario):
    """The real incident: a SECOND hero of the SAME user must NOT hijack the campaign.

    Mizel (user 1) and [SMOKE] Wojownik (user 1) — same user, different heroes.
    Assigning hero_a2 to hero_a's campaign must 409, not evict hero_a.
    """
    resp = client.post(
        f"/api/characters/{scenario['hero_a2']}/assign-campaign",
        json={"campaign_id": scenario["camp"], "user_id": scenario["user_a"]},
    )
    assert resp.status_code == 409, (
        f"Same-user takeover must 409, got {resp.status_code}: {resp.text}"
    )
    conn = _db()
    row = conn.execute(
        "SELECT status, campaign_id FROM characters WHERE id = ?", (scenario["hero_a"],)
    ).fetchone()
    conn.close()
    assert row["status"] == "in_campaign", "hero_a was evicted by same-user hero"
    assert row["campaign_id"] == scenario["camp"]


def test_same_user_reassign_still_works(scenario):
    """Hero A's own user can re-assign Hero A to the same campaign (idempotent)."""
    resp = client.post(
        f"/api/characters/{scenario['hero_a']}/assign-campaign",
        json={"campaign_id": scenario["camp"], "user_id": scenario["user_a"]},
    )
    assert resp.status_code == 200, (
        f"Expected 200 for same-user reassign, got {resp.status_code}: {resp.text}"
    )


def test_assign_to_empty_campaign_still_works(scenario):
    """Assigning a hero to a campaign with no existing hero should succeed."""
    resp = client.post(
        f"/api/characters/{scenario['hero_b']}/assign-campaign",
        json={"campaign_id": scenario["empty_camp"], "user_id": scenario["user_b"]},
    )
    assert resp.status_code == 200, (
        f"Expected 200 for empty campaign assign, got {resp.status_code}: {resp.text}"
    )
