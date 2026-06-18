"""TDD: Issue #767 (part 2) — dungeon-leave relink must not hijack another hero's campaign.

Real recurrence: [SMOKE] Wojownik (999409) had a stale dungeon snapshot pointing at
Mizel's campaign 99791. On leaving the dungeon, `_relink_hero_to_previous` blindly
freed the campaign's existing hero (Mizel) and relinked Wojownik → Mizel evicted to
idle again, even AFTER the assign_hero_to_campaign guard was added.

Model (Piotr): each hero owns its OWN campaigns/dungeons. No other hero of the same
user may take over. `_relink_hero_to_previous` must:
- NEVER evict a different active hero from the target campaign
- only relink when the campaign is free AND its play-history belongs to this hero
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app")

from app.api.dungeons import _relink_hero_to_previous

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def _db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout = 30000")
    return c


def _mk_user(conn, name):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, role) VALUES (?,?,?,?)",
        (name, "x", name, "player"),
    )
    conn.commit()
    return cur.lastrowid


def _mk_campaign(conn, owner, title, mode="solo", status="active"):
    cur = conn.execute(
        """INSERT INTO campaigns (title, system_id, status, owner_user_id, gm_plan_json, model_id, mode)
           VALUES (?,?,?,?,?,?,?)""",
        (title, "default", status, owner, "{}", "gpt-4o-mini", mode),
    )
    conn.commit()
    return cur.lastrowid


def _mk_hero(conn, user_id, campaign_id, status, name):
    cur = conn.execute(
        """INSERT INTO characters (user_id, campaign_id, name, system_id, sheet_json, is_active, status)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, campaign_id, name, "default", "{}", 1, status),
    )
    conn.commit()
    return cur.lastrowid


def _mk_turn(conn, campaign_id, character_id, n):
    conn.execute(
        """INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, turn_number)
           VALUES (?,?,?,?,?)""",
        (campaign_id, character_id, f"turn {n}", "narrative", n),
    )
    conn.commit()


@pytest.fixture
def scenario():
    conn = _db()
    pid = os.getpid()
    chars, camps, users = [], [], []

    user = _mk_user(conn, f"t767dr_{pid}")
    users.append(user)

    # Mizel-like campaign: owned + played by hero_a
    camp_a = _mk_campaign(conn, user, "PierwszeKroki767")
    camps.append(camp_a)
    hero_a = _mk_hero(conn, user, camp_a, "in_campaign", "Mizel767")
    chars.append(hero_a)
    _mk_turn(conn, camp_a, hero_a, 1)
    _mk_turn(conn, camp_a, hero_a, 2)

    # Wojownik-like intruder: same user, currently parked elsewhere
    camp_b = _mk_campaign(conn, user, "Wojownik767own")
    camps.append(camp_b)
    hero_b = _mk_hero(conn, user, camp_b, "in_campaign", "Wojownik767")
    chars.append(hero_b)

    # Empty campaign with no turns/heroes (claimable)
    camp_empty = _mk_campaign(conn, user, "Empty767")
    camps.append(camp_empty)

    conn.close()
    yield {"user": user, "camp_a": camp_a, "hero_a": hero_a,
           "camp_b": camp_b, "hero_b": hero_b, "camp_empty": camp_empty}

    c2 = _db()
    c2.execute("DELETE FROM campaign_turns WHERE campaign_id IN ({})".format(
        ",".join("?" * len(camps))), camps)
    c2.execute("DELETE FROM characters WHERE id IN ({})".format(
        ",".join("?" * len(chars))), chars)
    c2.execute("DELETE FROM campaigns WHERE id IN ({})".format(
        ",".join("?" * len(camps))), camps)
    c2.execute("DELETE FROM users WHERE id IN ({})".format(
        ",".join("?" * len(users))), users)
    c2.commit()
    c2.close()


def test_relink_does_not_evict_other_hero(scenario):
    """Wojownik leaving a dungeon with stale snapshot → must NOT evict Mizel from camp_a."""
    result = _relink_hero_to_previous(scenario["hero_b"], scenario["camp_a"])
    assert result is None, "relink must refuse — camp_a belongs to another hero"

    conn = _db()
    row = conn.execute(
        "SELECT campaign_id, status FROM characters WHERE id = ?", (scenario["hero_a"],)
    ).fetchone()
    conn.close()
    assert row["campaign_id"] == scenario["camp_a"], "Mizel was evicted!"
    assert row["status"] == "in_campaign"


def test_relink_refuses_foreign_play_history(scenario):
    """Even if camp_a's hero were momentarily idle, foreign turn-history blocks takeover."""
    # Free hero_a so no active hero is parked (race window)
    conn = _db()
    conn.execute("UPDATE characters SET campaign_id = NULL, status = 'idle' WHERE id = ?",
                 (scenario["hero_a"],))
    conn.commit()
    conn.close()

    result = _relink_hero_to_previous(scenario["hero_b"], scenario["camp_a"])
    assert result is None, "relink must refuse — camp_a has hero_a's play history"


def test_relink_to_empty_campaign_works(scenario):
    """A hero may relink to a campaign with no other hero and no foreign history."""
    result = _relink_hero_to_previous(scenario["hero_b"], scenario["camp_empty"])
    assert result == scenario["camp_empty"], "relink to empty campaign should succeed"
    conn = _db()
    row = conn.execute(
        "SELECT campaign_id, status FROM characters WHERE id = ?", (scenario["hero_b"],)
    ).fetchone()
    conn.close()
    assert row["campaign_id"] == scenario["camp_empty"]
    assert row["status"] == "in_campaign"
