"""TDD: Issue #429 (E14) — encounters scale to player level (level_min/level_max gate)."""
import sys, os

sys.path.insert(0, "/app")

import pytest


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_level_in_range_matches():
    """Hero level inside [level_min, level_max] → encounter eligible."""
    from app.services.encounter_service import encounter_matches
    enc = {"trigger_types": ["hex_enter"], "level_min": 5, "level_max": 10}
    assert encounter_matches(enc, trigger="hex_enter", hex_type=None, hero_level=7) is True


def test_level_below_min_excluded():
    """Hero too weak (below level_min) → encounter NOT eligible."""
    from app.services.encounter_service import encounter_matches
    enc = {"trigger_types": ["hex_enter"], "level_min": 5, "level_max": 10}
    assert encounter_matches(enc, trigger="hex_enter", hex_type=None, hero_level=1) is False


def test_level_above_max_excluded():
    """Hero too strong (above level_max) → encounter NOT eligible (no trivial fights)."""
    from app.services.encounter_service import encounter_matches
    enc = {"trigger_types": ["hex_enter"], "level_min": 1, "level_max": 3}
    assert encounter_matches(enc, trigger="hex_enter", hex_type=None, hero_level=10) is False


def test_no_level_bounds_matches_any_level():
    """An encounter without level bounds is eligible for any hero level."""
    from app.services.encounter_service import encounter_matches
    enc = {"trigger_types": ["hex_enter"]}
    assert encounter_matches(enc, trigger="hex_enter", hex_type=None, hero_level=1) is True
    assert encounter_matches(enc, trigger="hex_enter", hex_type=None, hero_level=20) is True


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_trigger_and_biome_still_gate():
    """The existing trigger + biome gating must still apply (no regression)."""
    from app.services.encounter_service import encounter_matches
    enc = {"trigger_types": ["n_turns"], "biomes": ["forest"]}
    # wrong trigger
    assert encounter_matches(enc, trigger="hex_enter", hex_type="forest", hero_level=1) is False
    # wrong biome
    assert encounter_matches(enc, trigger="n_turns", hex_type="city", hero_level=1) is False
    # right trigger + biome
    assert encounter_matches(enc, trigger="n_turns", hex_type="forest", hero_level=1) is True
