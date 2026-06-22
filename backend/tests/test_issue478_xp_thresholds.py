"""TDD: Issue #478 — F18 non-linear XP thresholds configurable from Admin.

Design contract:
  - level_from_xp(lifetime_xp, thresholds) determines character level
  - thresholds = dict {level_str: cumulative_xp_needed} e.g. {"2": 100, "3": 250}
  - Backward compat: when thresholds is None/empty, falls back to flat 100-XP-per-level
  - get_xp_level_thresholds(conn) reads from game_config_meta.xp_level_thresholds
  - Migration seeds default non-linear thresholds
  - resurrection_service and solo_death_service use level_from_xp

Default non-linear thresholds (see game design rationale):
  L2:  100 XP  (new player ramp: first level fast)
  L3:  250 XP  (need 150 more)
  L4:  450 XP  (need 200 more)
  L5:  700 XP  (need 250 more)
  L6: 1000 XP  (need 300 more)
  L7: 1350 XP  (need 350 more)
  L8: 1750 XP  (need 400 more)
  L9: 2200 XP  (need 450 more)
  L10:2700 XP  (need 500 more, cap)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _fixtures_schema import table_sql

import sqlite3
import pytest

from app.services.xp_service import level_from_xp, get_xp_level_thresholds


FLAT_THRESHOLDS = {str(i): (i - 1) * 100 for i in range(2, 11)}  # {"2":100,"3":200,...}

NON_LINEAR_THRESHOLDS = {
    "2": 100, "3": 250, "4": 450, "5": 700,
    "6": 1000, "7": 1350, "8": 1750, "9": 2200, "10": 2700,
}


# ─── In-memory DB fixture ────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_meta") + """
    """)
    conn.commit()
    return conn


# ─── level_from_xp logic ─────────────────────────────────────────────────────

def test_level_from_xp_level1_at_zero(db):
    """0 XP = level 1 (no thresholds crossed)."""
    assert level_from_xp(0, NON_LINEAR_THRESHOLDS) == 1


def test_level_from_xp_level2_at_threshold(db):
    """Exactly at level-2 threshold = level 2."""
    assert level_from_xp(100, NON_LINEAR_THRESHOLDS) == 2


def test_level_from_xp_below_level2(db):
    """99 XP = still level 1."""
    assert level_from_xp(99, NON_LINEAR_THRESHOLDS) == 1


def test_level_from_xp_level3(db):
    """250 XP = level 3."""
    assert level_from_xp(250, NON_LINEAR_THRESHOLDS) == 3


def test_level_from_xp_between_levels(db):
    """200 XP (between L2=100 and L3=250) = level 2."""
    assert level_from_xp(200, NON_LINEAR_THRESHOLDS) == 2


def test_level_from_xp_max_level(db):
    """At or above max threshold = max level."""
    assert level_from_xp(2700, NON_LINEAR_THRESHOLDS) == 10
    assert level_from_xp(9999, NON_LINEAR_THRESHOLDS) == 10


def test_level_from_xp_flat_backward_compat(db):
    """Flat 100-per-level thresholds reproduce old formula exactly."""
    for xp, expected_level in [(0, 1), (100, 2), (200, 3), (500, 6), (900, 10)]:
        assert level_from_xp(xp, FLAT_THRESHOLDS) == expected_level, (
            f"Flat compat fail at xp={xp}: expected {expected_level}"
        )


def test_level_from_xp_empty_thresholds_fallback(db):
    """None or empty thresholds falls back to flat 100-XP-per-level."""
    assert level_from_xp(100, None) == 2
    assert level_from_xp(200, {}) == 3


# ─── get_xp_level_thresholds from DB ─────────────────────────────────────────

def test_get_xp_level_thresholds_reads_config(db):
    """get_xp_level_thresholds reads game_config_meta.xp_level_thresholds."""
    import json
    db.execute(
        "INSERT INTO game_config_meta (key, value) VALUES ('xp_level_thresholds', ?)",
        (json.dumps(NON_LINEAR_THRESHOLDS),),
    )
    db.commit()
    thresholds = get_xp_level_thresholds(db)
    assert thresholds["2"] == 100
    assert thresholds["3"] == 250
    assert thresholds["10"] == 2700


def test_get_xp_level_thresholds_returns_default_when_missing(db):
    """When no config in DB, returns flat 100-per-level defaults."""
    thresholds = get_xp_level_thresholds(db)
    # Should return something sensible (not crash)
    assert isinstance(thresholds, dict)
    assert "2" in thresholds


# ─── Design target: faster early levels ──────────────────────────────────────

def test_non_linear_thresholds_level2_faster_than_flat(db):
    """Level 2 threshold must be same or lower in non-linear vs flat (100 = same)."""
    assert NON_LINEAR_THRESHOLDS["2"] <= FLAT_THRESHOLDS["2"]


def test_non_linear_thresholds_high_levels_require_more_xp(db):
    """Level 10 threshold must be higher in non-linear (2700 vs flat 900)."""
    assert NON_LINEAR_THRESHOLDS["10"] > FLAT_THRESHOLDS["10"]
