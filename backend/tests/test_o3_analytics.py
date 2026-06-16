"""TDD: Issue #705 O3 — Panel admina „Statystyki i Logi".

Tests for new analytics service functions:
  get_dashboard, get_players, get_errors
And extended params for get_events (filters) and get_llm (period alias).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.admin_analytics import (  # noqa: E402
    get_dashboard,
    get_errors,
    get_events,
    get_llm,
    get_players,
)


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT, display_name TEXT,
            password_hash TEXT NOT NULL DEFAULT 'x',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active',
            owner_user_id INTEGER,
            system_id TEXT DEFAULT 'default', model_id TEXT DEFAULT 'm',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER,
            status TEXT DEFAULT 'idle',
            system_id TEXT DEFAULT 'warrior',
            sheet_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, character_id INTEGER,
            user_text TEXT DEFAULT 'x', route TEXT DEFAULT 'narrative',
            turn_number INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE game_events (
            id INTEGER PRIMARY KEY, event_type TEXT, severity TEXT DEFAULT 'info',
            campaign_id INTEGER, character_id INTEGER, user_id INTEGER,
            event_data TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE llm_call_log (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, call_type TEXT,
            model TEXT DEFAULT 'gpt-4.1-mini',
            prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 500,
            cache_hit INTEGER DEFAULT 0, error TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.execute("INSERT INTO users (id, username, display_name) VALUES (1,'demo','Demo Player')")
    conn.execute(
        "INSERT INTO campaigns (id, title, status, owner_user_id) VALUES (1,'Kampania 1','active',1)"
    )
    conn.execute(
        "INSERT INTO characters (id, name, user_id, campaign_id) VALUES (1,'Aldric',1,1)"
    )
    conn.execute(
        "INSERT INTO campaign_turns (id, campaign_id, character_id) VALUES (1,1,1)"
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data)"
        " VALUES ('combat_victory','info',1,1,1,'{\"xp\":45}')"
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data)"
        " VALUES ('player_death','warning',1,1,1,'{\"cause\":\"goblin\"}')"
    )
    conn.execute(
        "INSERT INTO game_events (event_type, severity, campaign_id, character_id, user_id, event_data)"
        " VALUES ('llm_error','error',1,1,1,'{\"msg\":\"timeout\"}')"
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, latency_ms, cache_hit)"
        " VALUES (1,'narrator',1200,0)"
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, latency_ms, cache_hit)"
        " VALUES (1,'narrator',800,1)"
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, latency_ms, cache_hit, error)"
        " VALUES (1,'intent_parser',300,0,'timeout')"
    )
    conn.commit()
    return conn


# ── get_dashboard ─────────────────────────────────────────────────────────────

def test_dashboard_keys_present():
    out = get_dashboard(conn=_make_db())
    assert set(out.keys()) == {"active_campaigns", "turns_today", "avg_latency_ms", "errors_24h"}


def test_dashboard_active_campaigns():
    out = get_dashboard(conn=_make_db())
    assert out["active_campaigns"] == 1


def test_dashboard_errors_24h_merges_sources():
    out = get_dashboard(conn=_make_db())
    # 1 game_event severity=error + 1 llm_call_log with error
    assert out["errors_24h"] == 2


def test_dashboard_no_crash_empty():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaigns (id INTEGER, status TEXT);
        CREATE TABLE campaign_turns (id INTEGER, created_at TEXT);
        CREATE TABLE game_events (id INTEGER, severity TEXT, created_at TEXT);
        CREATE TABLE llm_call_log (id INTEGER, error TEXT, latency_ms INTEGER, created_at TEXT);
    """)
    out = get_dashboard(conn=conn)
    assert out["active_campaigns"] == 0
    assert out["errors_24h"] == 0


# ── get_players ────────────────────────────────────────────────────────────────

def test_players_returns_list():
    out = get_players(conn=_make_db())
    assert "players" in out
    assert len(out["players"]) >= 1


def test_players_fields():
    p = get_players(conn=_make_db())["players"][0]
    assert p["username"] == "demo"
    assert p["character_name"] == "Aldric"
    assert p["campaign_title"] == "Kampania 1"
    assert isinstance(p["turns_count"], int)


def test_players_sandbox_clones_excluded():
    conn = _make_db()
    conn.execute(
        "INSERT INTO characters (id, name, user_id, campaign_id) VALUES (2,'[SBX] Aldric',1,1)"
    )
    conn.commit()
    names = [p["character_name"] for p in get_players(conn=conn)["players"]]
    assert "[SBX] Aldric" not in names


def test_players_no_crash_empty():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE users (id INTEGER, username TEXT, display_name TEXT);
        CREATE TABLE campaigns (id INTEGER, title TEXT);
        CREATE TABLE characters (id INTEGER, name TEXT, user_id INTEGER, campaign_id INTEGER);
        CREATE TABLE campaign_turns (id INTEGER, campaign_id INTEGER, character_id INTEGER, created_at TEXT);
        CREATE TABLE game_events (id INTEGER, event_type TEXT, user_id INTEGER, created_at TEXT);
    """)
    out = get_players(conn=conn)
    assert out["players"] == []


# ── get_errors ────────────────────────────────────────────────────────────────

def test_errors_returns_list():
    out = get_errors(conn=_make_db())
    assert "errors" in out


def test_errors_merges_both_sources():
    out = get_errors(conn=_make_db())
    sources = {e["source"] for e in out["errors"]}
    assert "game_event" in sources
    assert "llm_error" in sources


def test_errors_limit():
    out = get_errors(limit=1, conn=_make_db())
    assert len(out["errors"]) == 1


def test_errors_no_crash_empty():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_events (id INTEGER, severity TEXT, event_type TEXT,
                                   campaign_id INTEGER, event_data TEXT, created_at TEXT);
        CREATE TABLE llm_call_log (id INTEGER, call_type TEXT, campaign_id INTEGER,
                                    error TEXT, created_at TEXT);
    """)
    out = get_errors(conn=conn)
    assert out["errors"] == []


# ── get_events extended params ────────────────────────────────────────────────

def test_events_filter_event_type():
    out = get_events(30, conn=_make_db(), event_type="combat_victory")
    assert len(out["events"]) == 1
    assert out["events"][0]["event_type"] == "combat_victory"


def test_events_filter_severity():
    out = get_events(30, conn=_make_db(), severity="warning")
    assert all(e["severity"] == "warning" for e in out["events"])
    assert len(out["events"]) == 1


def test_events_filter_campaign_id():
    out = get_events(30, conn=_make_db(), campaign_id=1)
    assert all(e["campaign_id"] == 1 for e in out["events"])


def test_events_no_filter_returns_all():
    out = get_events(30, conn=_make_db())
    assert len(out["events"]) == 3


def test_events_filter_combined():
    out = get_events(30, conn=_make_db(), event_type="player_death", severity="warning")
    assert len(out["events"]) == 1
    e = out["events"][0]
    assert e["event_type"] == "player_death"
    assert e["severity"] == "warning"


# ── get_llm period alias ──────────────────────────────────────────────────────

def test_llm_period_aliases_accepted():
    conn = _make_db()
    for period in ("24h", "7d", "30d"):
        out = get_llm(days=30, period=period, conn=conn)
        assert "by_type" in out, f"period={period} failed"
        assert "slowest" in out


def test_llm_period_unknown_falls_back_to_days():
    conn = _make_db()
    out = get_llm(days=30, period="BOGUS", conn=conn)
    assert "by_type" in out
