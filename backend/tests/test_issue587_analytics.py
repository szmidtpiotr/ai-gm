"""TDD: Issue #587 — Overview → Zdarzenia: analytics events + llm endpoints.

overview.js calls GET /api/admin/analytics/events and /llm — backing functions
(get_events/get_llm) + their source tables did not exist → 404/500.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.admin_analytics import get_events, get_llm  # noqa: E402


def _conn_with_tables() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_events (
            id INTEGER PRIMARY KEY, event_type TEXT, severity TEXT,
            campaign_id INTEGER, character_id INTEGER, user_id INTEGER,
            event_data TEXT, created_at TEXT DEFAULT (datetime('now')))"""
    )
    conn.execute(
        """CREATE TABLE llm_call_log (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, call_type TEXT, model TEXT,
            prompt_tokens INTEGER, completion_tokens INTEGER, latency_ms INTEGER,
            cache_hit INTEGER, error TEXT, created_at TEXT DEFAULT (datetime('now')))"""
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, event_data) "
        "VALUES ('combat_start','info',7,'{\"foe\":\"goblin\"}')"
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, model, latency_ms, cache_hit) "
        "VALUES (7,'narration','gpt-4.1-mini',1200,0)"
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, model, latency_ms, cache_hit) "
        "VALUES (7,'narration','gpt-4.1-mini',800,1)"
    )
    conn.commit()
    return conn


# ─── #587 events feed ────────────────────────────────────────────────────────

def test_get_events_returns_feed():
    conn = _conn_with_tables()
    out = get_events(30, conn=conn)
    assert "events" in out
    assert len(out["events"]) == 1
    e = out["events"][0]
    assert e["event_type"] == "combat_start"
    assert e["severity"] == "info"
    assert e["campaign_id"] == 7


# ─── #587 llm usage ──────────────────────────────────────────────────────────

def test_get_llm_aggregates_by_type():
    conn = _conn_with_tables()
    out = get_llm(30, conn=conn)
    assert "by_type" in out and "slowest" in out
    narr = next(r for r in out["by_type"] if r["call_type"] == "narration")
    assert narr["n"] == 2
    assert narr["cache_hits"] == 1
    assert narr["avg_ms"] == 1000  # (1200+800)/2


def test_get_llm_slowest_first():
    conn = _conn_with_tables()
    out = get_llm(30, conn=conn)
    assert out["slowest"][0]["latency_ms"] == 1200


# ─── backward-compat: empty tables don't crash ───────────────────────────────

def test_get_events_empty_ok():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE game_events (event_type TEXT, severity TEXT, campaign_id INTEGER, "
        "event_data TEXT, created_at TEXT)"
    )
    conn.commit()
    out = get_events(30, conn=conn)
    assert out["events"] == []
