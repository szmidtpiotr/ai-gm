"""TDD: Issue #1016 — end screen shows side-quest counter (X/Y done).

`campaign_run_stats` must break out side quests:
  side_quests_completed = side WHERE status='completed'   (X)
  side_quests_total     = ALL side (completed+skipped+active) (Y)
  side_quests_skipped   = side WHERE status='skipped'       (for the "pominąłeś" list)
Skipped counts toward Y, never toward X.
"""
import sqlite3
import pytest

from app.services.solo_death_service import campaign_run_stats


def _conn_with_quests(rows):
    """rows = list of (quest_type, status). Build minimal schema + a hero."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0)"
    )
    conn.execute("INSERT INTO characters (id, gold_gp) VALUES (1, 0)")
    conn.execute(
        """CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, campaign_id INTEGER,
            quest_type TEXT DEFAULT 'main', status TEXT DEFAULT 'active',
            completed_turn INTEGER DEFAULT NULL
        )"""
    )
    for qtype, status in rows:
        completed_turn = 5 if status == "completed" else None
        conn.execute(
            "INSERT INTO character_quests "
            "(character_id, campaign_id, quest_type, status, completed_turn) "
            "VALUES (1, 99, ?, ?, ?)",
            (qtype, status, completed_turn),
        )
    conn.commit()
    return conn


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_side_quest_counter_breakdown():
    """X = side completed, Y = all side, skipped counts to Y not X."""
    conn = _conn_with_quests([
        ("side", "completed"),
        ("side", "completed"),
        ("side", "skipped"),
        ("side", "active"),
        ("main", "completed"),   # main never counted as side
    ])
    stats = campaign_run_stats(conn, campaign_id=99, character_id=1)
    assert stats["side_quests_completed"] == 2      # X
    assert stats["side_quests_total"] == 4          # Y (2 completed + 1 skipped + 1 active)
    assert stats["side_quests_skipped"] == 1


def test_skipped_not_counted_as_completed():
    """A purely-skipped side quest → 0/1, never 1/1."""
    conn = _conn_with_quests([("side", "skipped")])
    stats = campaign_run_stats(conn, campaign_id=99, character_id=1)
    assert stats["side_quests_completed"] == 0
    assert stats["side_quests_total"] == 1


def test_no_side_quests_is_zero_zero():
    """No side quests → 0/0 (frontend decides to hide)."""
    conn = _conn_with_quests([("main", "completed"), ("main", "active")])
    stats = campaign_run_stats(conn, campaign_id=99, character_id=1)
    assert stats["side_quests_completed"] == 0
    assert stats["side_quests_total"] == 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_stats_keys_still_present():
    """Old keys (turn_count, gold, npcs_met, quests_completed) unchanged."""
    conn = _conn_with_quests([("main", "completed")])
    stats = campaign_run_stats(conn, campaign_id=99, character_id=1)
    for key in ("turn_count", "gold", "npcs_met", "quests_completed"):
        assert key in stats
    # main completed still counted in the overall quests_completed
    assert stats["quests_completed"] == 1
