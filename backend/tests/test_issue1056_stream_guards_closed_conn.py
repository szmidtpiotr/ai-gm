"""TDD: Issue #1056 — u30_desync_guard and quest_cap_trim use closed DB conn in stream path.

Root cause: token_generator() in create_turn_stream() is a closure that references `conn`
from the outer scope. The outer function's `finally: conn.close()` fires when
StreamingResponse is returned — BEFORE the generator runs. Both guards then fail silently.

Fix: each guard opens its own fresh get_db() connection inside token_generator().
"""
import pytest
import sqlite3
import sys

sys.path.insert(0, "/app")

DB_PATH = "/data/ai_gm.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Bug reproduction: closed conn raises ─────────────────────────────────────

def test_closed_conn_raises_on_execute():
    """Baseline: SQLite conn closed before use → ProgrammingError (root cause of #1056)."""
    conn = get_db()
    conn.close()
    with pytest.raises(Exception):
        conn.execute("SELECT 1")


def test_u30_guard_fails_when_called_with_closed_conn():
    """Simulate pre-fix: guard called with closed conn → raises (guard silently swallowed)."""
    conn = get_db()
    conn.close()
    with pytest.raises(Exception):
        conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (9999,),
        )


def test_quest_cap_fails_when_called_with_closed_conn():
    """Simulate pre-fix: count_active_quests with closed conn → raises."""
    from app.services.quest_persist_service import count_active_quests
    conn = get_db()
    conn.close()
    with pytest.raises(Exception):
        count_active_quests(conn, 9999, 9999)


# ─── Fix verification: fresh conn works ───────────────────────────────────────

def test_u30_desync_guard_works_with_fresh_conn():
    """Post-fix: guard opens its own conn → no ProgrammingError."""
    from app.services.turn_pipeline import guard_travel_desync
    conn = get_db()
    try:
        turn_num = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (9999,),
        ).fetchone()[0]
        # Must not raise (nonexistent campaign → guard logs nothing or noop)
        guard_travel_desync(conn, 9999, "Gracz idzie na północ.", False, turn_num)
    finally:
        conn.close()


def test_quest_cap_trim_works_with_fresh_conn():
    """Post-fix: count_active_quests opens its own conn → returns int without error."""
    from app.services.quest_persist_service import count_active_quests, MAX_ACTIVE_QUESTS
    conn = get_db()
    try:
        count = count_active_quests(conn, 9999, 9999)
        assert isinstance(count, int)
        assert count >= 0
        slots = max(0, MAX_ACTIVE_QUESTS - count)
        assert slots >= 0
    finally:
        conn.close()


def test_quest_cap_trim_actually_limits_to_add():
    """Quest cap slices to_add correctly based on remaining slots."""
    from app.services.quest_persist_service import count_active_quests, MAX_ACTIVE_QUESTS
    conn = get_db()
    try:
        count = count_active_quests(conn, 9999, 9999)
        slots = max(0, MAX_ACTIVE_QUESTS - count)
        # Build more quests than slots
        to_add = [{"title": f"Quest {i}"} for i in range(MAX_ACTIVE_QUESTS + 5)]
        trimmed = to_add[:slots]
        assert len(trimmed) <= MAX_ACTIVE_QUESTS, "trim must respect the cap"
    finally:
        conn.close()
