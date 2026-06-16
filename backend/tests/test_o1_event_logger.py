"""O1 — Tests for event_logger.py and observability table indices."""
import json
import sqlite3
import tempfile
import os
import pytest


def make_db():
    """Create in-memory DB with the O1 schema (tables + indices)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            campaign_id INTEGER,
            character_id INTEGER,
            user_id INTEGER,
            event_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            call_type TEXT,
            model TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER,
            cache_hit INTEGER DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_game_events_type_date ON game_events (event_type, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_game_events_campaign ON game_events (campaign_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_game_events_severity ON game_events (severity, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_log_type_date ON llm_call_log (call_type, created_at)")
    conn.commit()
    return conn


def test_write_game_event_inserts_row():
    from app.services.event_logger import write_game_event
    conn = make_db()
    write_game_event("combat_victory", 1, 2, 3, {"enemies_killed": 2, "xp_awarded": 30}, conn=conn)
    row = conn.execute("SELECT * FROM game_events").fetchone()
    assert row is not None
    assert row[1] == "combat_victory"
    assert row[2] == "info"
    assert row[3] == 1   # campaign_id
    assert row[4] == 2   # character_id
    assert row[5] == 3   # user_id
    payload = json.loads(row[6])
    assert payload["enemies_killed"] == 2
    conn.close()


def test_write_game_event_custom_severity():
    from app.services.event_logger import write_game_event
    conn = make_db()
    write_game_event("player_death", 1, 2, 3, {"cause": "goblin"}, severity="warning", conn=conn)
    row = conn.execute("SELECT severity FROM game_events").fetchone()
    assert row[0] == "warning"
    conn.close()


def test_write_game_event_never_raises():
    from app.services.event_logger import write_game_event
    # Pass a broken connection — must not raise
    write_game_event("x", None, None, None, {}, conn=None)  # DB_PATH doesn't matter in test context


def test_write_llm_log_inserts_row():
    from app.services.event_logger import write_llm_log
    conn = make_db()
    write_llm_log("narrator", "claude-sonnet-4-6", 1240,
                  campaign_id=5, prompt_tokens=850, completion_tokens=120,
                  cache_hit=True, conn=conn)
    row = conn.execute("SELECT * FROM llm_call_log").fetchone()
    assert row is not None
    assert row[2] == "narrator"        # call_type
    assert row[3] == "claude-sonnet-4-6"  # model
    assert row[4] == 850               # prompt_tokens
    assert row[5] == 120               # completion_tokens
    assert row[6] == 1240              # latency_ms
    assert row[7] == 1                 # cache_hit (True→1)
    conn.close()


def test_write_llm_log_with_error():
    from app.services.event_logger import write_llm_log
    conn = make_db()
    write_llm_log("intent_parser", "gpt-4.1-mini", 5000,
                  error="timeout", conn=conn)
    row = conn.execute("SELECT error FROM llm_call_log").fetchone()
    assert row[0] == "timeout"
    conn.close()


def test_indices_exist_on_dev_db():
    """Verify the 4 required indices exist in the DEV database via env path."""
    db_path = os.environ.get("DB_PATH", "/data/ai_gm.db")
    if not os.path.exists(db_path):
        pytest.skip(f"DB not found at {db_path}")
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN ('game_events','llm_call_log')"
    ).fetchall()
    names = {r[0] for r in rows}
    conn.close()
    assert "idx_game_events_type_date" in names
    assert "idx_game_events_campaign" in names
    assert "idx_game_events_severity" in names
    assert "idx_llm_log_type_date" in names
