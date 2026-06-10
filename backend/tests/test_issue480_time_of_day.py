"""TDD: Issue #480 — F20 time of day mechanical effects.

Phases derived from ingame_hours (mod 24):
  dawn:  06–11  (Rano)
  day:   12–17  (Popołudnie)
  dusk:  18–21  (Wieczór)
  night: 22–05  (Noc)

Effects stored in game_config_meta.time_of_day_effects as JSON dict:
  {"dawn": {...bonuses...}, "day": {...}, "dusk": {...}, "night": {...}}

Design:
  - get_time_of_day_phase(ingame_hours) → phase string
  - get_time_of_day_effects(conn) → full config dict
  - get_active_effects_for_phase(phase, effects_config) → effects for that phase
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import sqlite3
import pytest

from app.services.time_of_day_service import (
    get_time_of_day_phase,
    get_time_of_day_effects,
    get_active_effects_for_phase,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT);")
    conn.commit()
    return conn


DEFAULT_EFFECTS = {
    "dawn": {"initiative_bonus": 1},
    "day": {},
    "dusk": {"perception_dc_bonus": 1},
    "night": {"perception_dc_bonus": 2, "stealth_bonus": 2},
}


# ─── get_time_of_day_phase ────────────────────────────────────────────────────

def test_phase_dawn_morning(db):
    """06:00 → dawn."""
    assert get_time_of_day_phase(6) == "dawn"
    assert get_time_of_day_phase(11) == "dawn"


def test_phase_day_afternoon(db):
    """12:00 → day."""
    assert get_time_of_day_phase(12) == "day"
    assert get_time_of_day_phase(17) == "day"


def test_phase_dusk_evening(db):
    """18:00 → dusk."""
    assert get_time_of_day_phase(18) == "dusk"
    assert get_time_of_day_phase(21) == "dusk"


def test_phase_night(db):
    """22:00 and 00:00–05:59 → night."""
    assert get_time_of_day_phase(22) == "night"
    assert get_time_of_day_phase(0) == "night"
    assert get_time_of_day_phase(5) == "night"


def test_phase_wraps_with_mod24(db):
    """Works with total ingame_hours > 24 (mod 24 wrapping)."""
    assert get_time_of_day_phase(36) == "day"   # 36 % 24 = 12 → day
    assert get_time_of_day_phase(42) == "dusk"  # 42 % 24 = 18 → dusk
    assert get_time_of_day_phase(48) == "night"  # 48 % 24 = 0 → night


def test_phase_dawn_at_ingame_30(db):
    """30 hours ingame (mod 24 = 6) → dawn."""
    assert get_time_of_day_phase(30) == "dawn"


# ─── get_time_of_day_effects ─────────────────────────────────────────────────

def test_get_effects_reads_config(db):
    """get_time_of_day_effects reads from game_config_meta."""
    db.execute(
        "INSERT INTO game_config_meta (key, value) VALUES ('time_of_day_effects', ?)",
        (json.dumps(DEFAULT_EFFECTS),),
    )
    db.commit()
    effects = get_time_of_day_effects(db)
    assert "dawn" in effects
    assert effects["night"]["stealth_bonus"] == 2


def test_get_effects_returns_default_when_missing(db):
    """Returns default effects when config missing."""
    effects = get_time_of_day_effects(db)
    assert isinstance(effects, dict)
    assert "dawn" in effects and "night" in effects


# ─── get_active_effects_for_phase ────────────────────────────────────────────

def test_active_effects_dawn_returns_bonus(db):
    """Dawn has initiative_bonus: 1."""
    effects = get_active_effects_for_phase("dawn", DEFAULT_EFFECTS)
    assert effects.get("initiative_bonus") == 1


def test_active_effects_day_is_empty(db):
    """Day has no special bonuses (empty dict)."""
    effects = get_active_effects_for_phase("day", DEFAULT_EFFECTS)
    assert effects == {}


def test_active_effects_night_has_stealth(db):
    """Night gives stealth bonus."""
    effects = get_active_effects_for_phase("night", DEFAULT_EFFECTS)
    assert effects.get("stealth_bonus") == 2
    assert effects.get("perception_dc_bonus") == 2


def test_active_effects_unknown_phase(db):
    """Unknown phase returns empty dict (safe default)."""
    effects = get_active_effects_for_phase("apocalypse", DEFAULT_EFFECTS)
    assert effects == {}


def test_active_effects_empty_config(db):
    """Empty effects config returns empty dict for any phase."""
    assert get_active_effects_for_phase("night", {}) == {}
    assert get_active_effects_for_phase("night", None) == {}
