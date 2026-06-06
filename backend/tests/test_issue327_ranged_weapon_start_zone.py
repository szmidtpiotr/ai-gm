"""TDD: Issue #327 — Player with ranged weapon must start combat in ranged zone.

Bug: _default_zone_for_player() only checks archetype (Scholar → ranged, else engaged).
A Warrior with a bow still starts in ZONE_ENGAGED, losing ranged advantage entirely.

Fix: check equipped weapon_type first — if 'ranged', return ZONE_RANGED regardless of archetype.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.combat_service import _default_zone_for_player, ZONE_RANGED, ZONE_ENGAGED


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_warrior_with_ranged_weapon_starts_in_ranged_zone():
    """Warrior archetype carrying a ranged weapon must start in ZONE_RANGED."""
    sheet = {
        "archetype": "warrior",
        "equipped_weapon": "shortbow",   # ranged weapon key
    }
    # We need conn + character_id for full lookup — test the weapon_type path directly
    # by injecting weapon_type into sheet (post-resolution shortcut used in tests)
    sheet_with_weapon_type = {
        "archetype": "warrior",
        "_equipped_weapon_type": "ranged",   # injected resolved type
    }
    zone = _default_zone_for_player(sheet_with_weapon_type)
    assert zone == ZONE_RANGED, (
        f"Warrior with ranged weapon should start in '{ZONE_RANGED}', got '{zone}'"
    )


def test_rogue_with_ranged_weapon_starts_in_ranged_zone():
    """Rogue archetype with bow must also start ranged — not just Scholar."""
    sheet = {
        "archetype": "rogue",
        "_equipped_weapon_type": "ranged",
    }
    zone = _default_zone_for_player(sheet)
    assert zone == ZONE_RANGED, (
        f"Rogue with ranged weapon should start in '{ZONE_RANGED}', got '{zone}'"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_scholar_without_weapon_still_starts_ranged():
    """Scholar archetype default (no weapon override) must still start in ZONE_RANGED."""
    sheet = {"archetype": "scholar"}
    zone = _default_zone_for_player(sheet)
    assert zone == ZONE_RANGED, (
        f"Scholar should still start in '{ZONE_RANGED}' by archetype, got '{zone}'"
    )


def test_warrior_with_melee_weapon_starts_engaged():
    """Warrior with melee weapon must still start in ZONE_ENGAGED."""
    sheet = {
        "archetype": "warrior",
        "_equipped_weapon_type": "melee",
    }
    zone = _default_zone_for_player(sheet)
    assert zone == ZONE_ENGAGED, (
        f"Warrior with melee weapon should start in '{ZONE_ENGAGED}', got '{zone}'"
    )


def test_warrior_no_weapon_starts_engaged():
    """Warrior with no weapon info defaults to ZONE_ENGAGED (unchanged behavior)."""
    sheet = {"archetype": "warrior"}
    zone = _default_zone_for_player(sheet)
    assert zone == ZONE_ENGAGED, (
        f"Warrior with no weapon should default to '{ZONE_ENGAGED}', got '{zone}'"
    )
