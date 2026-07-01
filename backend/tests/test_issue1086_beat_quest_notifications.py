"""TDD: Issue #1086 — Beat/quest completion notifications in player chat."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            campaign_id INTEGER,
            character_id INTEGER,
            user_id INTEGER,
            event_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT
        );
        CREATE TABLE game_config_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    return conn


def _insert_beat_event(conn, campaign_id, beat_key, turn, act=1):
    conn.execute(
        "INSERT INTO game_events (event_type, campaign_id, event_data) VALUES (?,?,?)",
        ("beat_complete", campaign_id, json.dumps({"beat_key": beat_key, "act": act, "turn": turn})),
    )
    conn.commit()


def _insert_quest_event(conn, campaign_id, title, xp, turn):
    conn.execute(
        "INSERT INTO game_events (event_type, campaign_id, event_data) VALUES (?,?,?)",
        ("quest_complete", campaign_id, json.dumps({"quest_title": title, "xp": xp, "turn": turn})),
    )
    conn.commit()


def _set_plan(conn, campaign_id, beats):
    """beats = list of (key, summary) tuples."""
    plan = {"acts": [{"key_beats": [{"beat_key": k, "summary": s} for k, s in beats]}]}
    conn.execute(
        "INSERT OR REPLACE INTO campaigns (id, gm_plan_json) VALUES (?,?)",
        (campaign_id, json.dumps(plan)),
    )
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_collect_includes_completed_beat():
    """completed_beats returned when beat_complete event exists for campaign+turn."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _set_plan(conn, 1, [("beat_abc", "Spotkaj Yarla w tawernie")])
    _insert_beat_event(conn, campaign_id=1, beat_key="beat_abc", turn=5)

    result = collect_turn_notifications(campaign_id=1, turn_number=5, conn=conn)

    assert "completed_beats" in result, "completed_beats missing from result"
    beats = result["completed_beats"]
    assert len(beats) == 1
    assert beats[0]["key"] == "beat_abc"
    assert beats[0]["label"] == "Spotkaj Yarla w tawernie"


def test_collect_includes_completed_quest():
    """completed_quests returned when quest_complete event exists for campaign+turn."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _insert_quest_event(conn, campaign_id=2, title="Ochrona karawany", xp=50, turn=10)

    result = collect_turn_notifications(campaign_id=2, turn_number=10, conn=conn)

    assert "completed_quests" in result, "completed_quests missing from result"
    quests = result["completed_quests"]
    assert len(quests) == 1
    assert quests[0]["title"] == "Ochrona karawany"
    assert quests[0]["xp"] == 50


def test_collect_empty_for_other_turn():
    """Events from a different turn are NOT included."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _insert_beat_event(conn, campaign_id=3, beat_key="beat_xyz", turn=7)

    result = collect_turn_notifications(campaign_id=3, turn_number=99, conn=conn)

    assert result == {}, "Should be empty for a different turn number"


def test_collect_empty_when_disabled():
    """When enabled=False, no notifications returned regardless of events."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _insert_beat_event(conn, campaign_id=4, beat_key="beat_x", turn=1)
    _insert_quest_event(conn, campaign_id=4, title="Some quest", xp=20, turn=1)

    result = collect_turn_notifications(campaign_id=4, turn_number=1, conn=conn, enabled=False)

    assert result == {}, "Notifications must be empty when disabled"


def test_collect_beat_and_quest_together():
    """Both beat and quest completed in same turn → both in result."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _set_plan(conn, 5, [("beat_a", "Znajdź skarb"), ("beat_b", "Zabij smoka")])
    _insert_beat_event(conn, campaign_id=5, beat_key="beat_a", turn=3)
    _insert_quest_event(conn, campaign_id=5, title="Misja nr 1", xp=30, turn=3)

    result = collect_turn_notifications(campaign_id=5, turn_number=3, conn=conn)

    assert "completed_beats" in result
    assert "completed_quests" in result
    assert result["completed_beats"][0]["label"] == "Znajdź skarb"
    assert result["completed_quests"][0]["title"] == "Misja nr 1"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_collect_returns_empty_when_no_events():
    """No events → empty dict, no crash."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    result = collect_turn_notifications(campaign_id=99, turn_number=1, conn=conn)
    assert result == {}


def test_beat_label_falls_back_to_key_when_plan_missing():
    """Beat key used as label when campaign has no gm_plan_json."""
    from app.services.turn_notifications import collect_turn_notifications

    conn = _make_db()
    _insert_beat_event(conn, campaign_id=6, beat_key="orphan_beat", turn=2)

    result = collect_turn_notifications(campaign_id=6, turn_number=2, conn=conn)

    assert result["completed_beats"][0]["label"] == "orphan_beat"
