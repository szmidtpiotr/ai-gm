"""TDD: Issue #390 — advance_clock nie przyjmuje minutes= keyword argument.

Root cause: advance_clock(campaign_id, hours, reason, conn) przyjmuje
`hours` pozycyjnie. turns.py:2138 woła go z `minutes=effective_min` →
TypeError silently caught → zegar nigdy nie tyka.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.clock_service import advance_clock, get_clock_state, START_HOUR_DEFAULT


@pytest.fixture
def test_conn():
    from app.core.db_runtime import resolve_db_path
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture
def campaign_id(test_conn):
    row = test_conn.execute(
        "SELECT id FROM campaigns WHERE status != 'deleted' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No campaign found")
    return row["id"]


@pytest.fixture
def ensure_session(test_conn, campaign_id):
    """Ensure game_session exists for campaign and reset clock to START_HOUR_DEFAULT."""
    row = test_conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        pytest.skip("No game_session for campaign")

    flags = json.loads(row["session_flags"] or "{}")
    original_hours = flags.get("ingame_hours", START_HOUR_DEFAULT)
    original_pending = flags.get("pending_clock_minutes", 0)

    # Reset to known state
    flags["ingame_hours"] = START_HOUR_DEFAULT
    flags["pending_clock_minutes"] = 0
    test_conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    test_conn.commit()

    yield

    # Restore original
    flags2 = json.loads(test_conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    flags2["ingame_hours"] = original_hours
    flags2["pending_clock_minutes"] = original_pending
    test_conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags2, ensure_ascii=False), campaign_id),
    )
    test_conn.commit()


# ─── Test główny: minutes= keyword działa ───────────────────────────────────

def test_advance_clock_accepts_minutes_keyword(campaign_id, ensure_session, test_conn):
    """advance_clock must accept minutes= keyword argument without TypeError."""
    # This used to raise TypeError: unexpected keyword argument 'minutes'
    result = advance_clock(campaign_id, minutes=60, reason="test", conn=test_conn)
    assert result is not None, "advance_clock must return a dict"
    assert "ingame_hours" in result


def test_advance_clock_60_minutes_advances_one_hour(campaign_id, ensure_session, test_conn):
    """60 minutes → 1 hour advance."""
    state_before = get_clock_state(campaign_id, conn=test_conn)
    advance_clock(campaign_id, minutes=60, reason="test", conn=test_conn)
    test_conn.commit()
    state_after = get_clock_state(campaign_id, conn=test_conn)
    assert state_after["ingame_hours"] == state_before["ingame_hours"] + 1


def test_advance_clock_sub_hour_accumulates(campaign_id, ensure_session, test_conn):
    """15 min × 4 turns = 60 min accumulated → 1 hour advance."""
    state_before = get_clock_state(campaign_id, conn=test_conn)
    for _ in range(4):
        advance_clock(campaign_id, minutes=15, reason="narrative_turn", conn=test_conn)
    test_conn.commit()
    state_after = get_clock_state(campaign_id, conn=test_conn)
    assert state_after["ingame_hours"] == state_before["ingame_hours"] + 1, (
        f"Expected 1 hour advance after 4×15min, got {state_after['ingame_hours'] - state_before['ingame_hours']}"
    )


def test_advance_clock_sub_hour_no_advance_until_60(campaign_id, ensure_session, test_conn):
    """15 min × 3 turns = 45 min → no hour advance yet."""
    state_before = get_clock_state(campaign_id, conn=test_conn)
    for _ in range(3):
        advance_clock(campaign_id, minutes=15, reason="narrative_turn", conn=test_conn)
    test_conn.commit()
    state_after = get_clock_state(campaign_id, conn=test_conn)
    assert state_after["ingame_hours"] == state_before["ingame_hours"], (
        "3×15min should NOT advance clock (only 45min accumulated)"
    )


def test_advance_clock_hours_positional_still_works(campaign_id, ensure_session, test_conn):
    """Existing callers using positional hours must still work."""
    state_before = get_clock_state(campaign_id, conn=test_conn)
    advance_clock(campaign_id, 1, "long_rest", conn=test_conn)
    test_conn.commit()
    state_after = get_clock_state(campaign_id, conn=test_conn)
    assert state_after["ingame_hours"] == state_before["ingame_hours"] + 1
