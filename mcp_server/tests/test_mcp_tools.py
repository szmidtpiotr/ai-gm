"""
Tests for mcp_server/server.py tools.
Run inside the mcp-server container:
    python -m pytest tests/ -v
"""
import json
import os
import sqlite3
import sys

# server.py lives one level up from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server


# ---------------------------------------------------------------------------
# Helper function tests (no DB needed)
# ---------------------------------------------------------------------------


def test_ts_cutoff_24h():
    ts = server.ts_cutoff(period="24h")
    assert len(ts) == 19  # "YYYY-MM-DD HH:MM:SS"
    assert ts[:4].isdigit()


def test_ts_cutoff_7d():
    ts = server.ts_cutoff(period="7d")
    assert len(ts) == 19


def test_ts_cutoff_hours():
    ts = server.ts_cutoff(hours_back=1)
    assert len(ts) == 19


def test_parse_json_safe_valid():
    result = server.parse_json_safe('{"key": "value"}')
    assert result == {"key": "value"}


def test_parse_json_safe_invalid():
    result = server.parse_json_safe("not json", default={})
    assert result == {}


def test_parse_json_safe_none():
    result = server.parse_json_safe(None, default=None)
    assert result is None


def test_hero_level_from_level():
    sheet = {"level": 5}
    assert server.hero_level(sheet) == 5


def test_hero_level_from_xp():
    sheet = {"xp_lifetime_earned": 250}
    assert server.hero_level(sheet) == 3  # 250//100 + 1 = 3


def test_hero_level_clamped():
    sheet = {"xp_lifetime_earned": 99999}
    assert server.hero_level(sheet) == 10


def test_hero_level_empty():
    assert server.hero_level({}) == 1


# ---------------------------------------------------------------------------
# DB integration tests (require /data/ai_gm_dev.db to be mounted)
# ---------------------------------------------------------------------------


DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm_dev.db")
DB_AVAILABLE = os.path.exists(DB_PATH)


def test_db_path_exists():
    assert DB_AVAILABLE, f"DB not mounted at {DB_PATH} — run inside mcp-server container"


def test_get_system_health():
    if not DB_AVAILABLE:
        return
    result = server.get_system_health()
    assert result["status"] == "ok"
    assert result["db_size_mb"] > 0
    assert isinstance(result["total_campaigns"], int)
    assert isinstance(result["total_users"], int)


def test_query_game_events_returns_list():
    if not DB_AVAILABLE:
        return
    result = server.query_game_events(limit=5)
    assert isinstance(result, list)
    for item in result:
        assert "event_type" in item
        assert "created_at" in item
        assert "data" in item


def test_query_game_events_filtered():
    if not DB_AVAILABLE:
        return
    result = server.query_game_events(event_type="combat_victory", limit=10)
    assert isinstance(result, list)
    for item in result:
        assert item["event_type"] == "combat_victory"


def test_get_llm_performance():
    if not DB_AVAILABLE:
        return
    result = server.get_llm_performance(period="7d")
    assert "total_calls" in result
    assert "avg_latency_ms" in result
    assert "by_call_type" in result
    assert isinstance(result["by_call_type"], list)


def test_get_error_log():
    if not DB_AVAILABLE:
        return
    result = server.get_error_log(hours=168, limit=10)
    assert isinstance(result, list)


def test_get_world_analytics():
    if not DB_AVAILABLE:
        return
    result = server.get_world_analytics()
    assert "total_locations" in result
    assert "pending_review_count" in result
    assert isinstance(result["most_visited"], list)


def test_get_player_stats_all():
    if not DB_AVAILABLE:
        return
    result = server.get_player_stats()
    assert isinstance(result, list)
    if result:
        assert "user_id" in result[0]
        assert "characters" in result[0]


def test_search_events_returns_list():
    if not DB_AVAILABLE:
        return
    result = server.search_events(query="goblin")
    assert isinstance(result, list)
    for item in result:
        assert "event_type" in item
        assert "data" in item


def test_search_events_no_match():
    if not DB_AVAILABLE:
        return
    result = server.search_events(query="ZZZNONEXISTENTQUERY999")
    assert isinstance(result, list)
    assert len(result) == 0


def test_query_action_log_returns_list():
    if not DB_AVAILABLE:
        return
    # Query for any campaign that has turns
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT campaign_id FROM campaign_turns ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row:
        result = server.query_action_log(campaign_id=row[0], limit=5)
        assert isinstance(result, list)
