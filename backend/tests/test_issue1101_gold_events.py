"""TDD: Issue #1101 — service payments emit visible gold_events (💰 dymek).

Bug: [SPEND_GOLD:key] deducts gold but the deduction is invisible to the player —
the tag is stripped from narration and nothing is surfaced in the turn response.

Fix: apply_spend_gold_to_narrative(text, conn, character_id, collect_events=list)
appends a {delta, label, source, service_key} record per successful charge so the
turn pipeline can put them in done_payload["gold_events"] → frontend 💰 bubble.

Backward compat: called WITHOUT collect_events, behaviour is byte-for-byte unchanged.
"""
import sys
sys.path.insert(0, "/app")

import sqlite3
import pytest
from app.services.spend_gold_service import apply_spend_gold_to_narrative


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_services (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            cost_gp INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("tavern_meal", "Gospoda: posiłek", 2, 1))
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("inn_night", "Gospoda: jedna noc", 5, 1))
    conn.execute("INSERT INTO characters VALUES (?, ?)", (1, 100))
    conn.commit()
    yield conn
    conn.close()


# ─── Main behaviour: collect_events out-param ────────────────────────────────

def test_collect_events_records_successful_charge(test_db):
    """On success, collect_events gets one record with delta/label/source/service_key."""
    events = []
    narrative = "Siadasz i jesz. [SPEND_GOLD:tavern_meal]"
    apply_spend_gold_to_narrative(narrative, test_db, 1, collect_events=events)
    assert len(events) == 1
    ev = events[0]
    assert ev["delta"] == -2
    assert ev["label"] == "Gospoda: posiłek"
    assert ev["source"] == "service"
    assert ev["service_key"] == "tavern_meal"


def test_collect_events_multiple_charges(test_db):
    """Two affordable tags → two event records, in order."""
    events = []
    narrative = "[SPEND_GOLD:tavern_meal] Jesz. [SPEND_GOLD:inn_night] Śpisz."
    apply_spend_gold_to_narrative(narrative, test_db, 1, collect_events=events)
    assert [e["service_key"] for e in events] == ["tavern_meal", "inn_night"]
    assert [e["delta"] for e in events] == [-2, -5]


def test_collect_events_empty_on_insufficient(test_db):
    """No charge (can't afford) → no event recorded."""
    test_db.execute("UPDATE characters SET gold_gp = 0 WHERE id = 1")
    test_db.commit()
    events = []
    narrative = "Czekasz na nocleg. [SPEND_GOLD:inn_night]"
    apply_spend_gold_to_narrative(narrative, test_db, 1, collect_events=events)
    assert events == []


def test_collect_events_ignores_unknown_service(test_db):
    """Unknown service key → no event (nothing charged)."""
    events = []
    narrative = "Robisz coś. [SPEND_GOLD:nonexistent_key]"
    apply_spend_gold_to_narrative(narrative, test_db, 1, collect_events=events)
    assert events == []


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_without_collect_events_returns_string(test_db):
    """Old call signature (no collect_events) still returns cleaned string."""
    narrative = "Siadasz i jesz. [SPEND_GOLD:tavern_meal] Smacznego."
    result = apply_spend_gold_to_narrative(narrative, test_db, 1)
    assert isinstance(result, str)
    assert "[SPEND_GOLD:" not in result
    assert "Smacznego" in result


def test_without_collect_events_still_deducts(test_db):
    """Old call signature still deducts gold."""
    narrative = "Płacisz. [SPEND_GOLD:inn_night]"
    apply_spend_gold_to_narrative(narrative, test_db, 1)
    test_db.commit()
    row = test_db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 95  # 100 - 5, unchanged behaviour
