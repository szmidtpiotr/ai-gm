"""TDD: Issue #580 — `game_sessions.ingame_hours` column stays in sync with session_flags.

The authoritative clock lives in `session_flags.ingame_hours`; the legacy column was never
written, so a direct column reader saw a stale time-of-day. After advancing the clock the
column must equal the flags value.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import clock_service


def _conn(start_hours: int = 9) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, "
        "session_flags TEXT, ingame_hours INTEGER)"
    )
    c.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags, ingame_hours) VALUES (1, 77, ?, ?)",
        (json.dumps({"ingame_hours": start_hours}), start_hours),
    )
    c.commit()
    return c


def _col(c) -> int:
    return c.execute("SELECT ingame_hours FROM game_sessions WHERE campaign_id=77").fetchone()[0]


def _flag(c) -> int:
    row = c.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=77").fetchone()
    return int(json.loads(row["session_flags"])["ingame_hours"])


def test_column_syncs_after_advance():
    """Advancing the clock writes both the flags AND the legacy column."""
    c = _conn(9)
    clock_service.advance_clock(77, hours=3, reason="travel", conn=c)
    assert _flag(c) == 12
    assert _col(c) == 12  # was the bug: column stuck at 9


def test_column_matches_flags_on_partial_minutes():
    """Sub-hour ticks that promote to a full hour also sync the column."""
    c = _conn(9)
    clock_service.advance_clock(77, minutes=90, reason="turn_narrative", conn=c)  # +1h, 30 leftover
    assert _col(c) == _flag(c)
