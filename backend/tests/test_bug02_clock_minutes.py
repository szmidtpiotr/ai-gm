"""BUG-02 — clock_service minute resolution + per-turn auto-advance."""

import json
import sqlite3

import pytest

from app.services import clock_service
from app.services.clock_config_service import (
    DEFAULT_COMBAT_MIN,
    DEFAULT_NARRATIVE_MIN,
    DEFAULT_TRAVEL_MIN,
    get_clock_config,
    set_clock_config,
)


@pytest.fixture
def clean_session():
    """Insert a fresh game_sessions row for an isolated campaign id."""
    campaign_id = 99902
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, '{}')",
            (f"bug02-{campaign_id}", campaign_id),
        )
        conn.commit()
    finally:
        conn.close()
    yield campaign_id
    # Teardown — keep cleanup minimal; row is harmless.


def test_clock_state_defaults_to_morning(clean_session):
    state = clock_service.get_clock_state(clean_session)
    assert state["ingame_hours"] == 9
    assert state["ingame_minutes"] == 0
    assert state["display"].startswith("Dzień 1, 09:00")


def test_advance_clock_minutes_only(clean_session):
    state = clock_service.advance_clock(clean_session, minutes=15, reason="turn_narrative")
    assert state["delta_minutes"] == 15
    assert state["ingame_minutes"] == 15
    assert state["ingame_hours"] == 9  # no rollover yet
    assert "09:15" in state["display"]


def test_advance_clock_rolls_over_to_next_hour(clean_session):
    clock_service.advance_clock(clean_session, minutes=45)
    state = clock_service.advance_clock(clean_session, minutes=20)
    # 0 + 45 + 20 = 65 → 1h 5m → 9:00 + 1h05 = 10:05
    assert state["ingame_hours"] == 10
    assert state["ingame_minutes"] == 5
    assert "10:05" in state["display"]


def test_advance_clock_legacy_hours_kwarg_still_works(clean_session):
    state = clock_service.advance_clock(clean_session, 8, "long_rest")
    # 9:00 + 8h = 17:00
    assert state["ingame_hours"] == 17
    assert state["ingame_minutes"] == 0
    assert state["delta_minutes"] == 480
    assert "17:00" in state["display"]


def test_advance_clock_hours_and_minutes_combined(clean_session):
    state = clock_service.advance_clock(clean_session, hours=1, minutes=30, reason="travel")
    assert state["ingame_hours"] == 10
    assert state["ingame_minutes"] == 30
    assert state["delta_minutes"] == 90


def test_advance_clock_clamps_to_max(clean_session):
    # 168h cap = 10080 min
    state = clock_service.advance_clock(clean_session, hours=1000, reason="bug")
    assert state["delta_minutes"] == 168 * 60


def test_clock_config_defaults_round_trip():
    cfg = get_clock_config()
    # If the row hasn't been seeded, we get defaults; otherwise we get whatever's there.
    assert cfg["narrative_min"] >= 0
    assert cfg["combat_min"] >= 0
    assert cfg["travel_min"] >= 0


def test_clock_config_set_and_read_back():
    set_clock_config(narrative_min=20, combat_min=3, travel_min=45)
    cfg = get_clock_config()
    assert cfg["narrative_min"] == 20
    assert cfg["combat_min"] == 3
    assert cfg["travel_min"] == 45
    # Restore defaults so other tests aren't affected.
    set_clock_config(
        narrative_min=DEFAULT_NARRATIVE_MIN,
        combat_min=DEFAULT_COMBAT_MIN,
        travel_min=DEFAULT_TRAVEL_MIN,
    )


def test_clock_config_rejects_out_of_range():
    with pytest.raises(ValueError):
        set_clock_config(narrative_min=999)
    with pytest.raises(ValueError):
        set_clock_config(combat_min=-1)
