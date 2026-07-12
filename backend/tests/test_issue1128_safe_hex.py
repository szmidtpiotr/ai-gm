"""TDD: Issue #1128 follow-up — explicit 0 encounter_chance = safe zone.

Regression companion to the weather-march work. The world-travel encounter roll
(`_roll_encounter`) used `float(x or 0.15)` / `or base`, which treated an
explicit 0.0 as "unset" — so an authored safe hex, and settlement terrain types
(town/village/castle, base 0.0), still rolled ~15% and could ambush a hero
standing in a town. A 0 anywhere (hex-level or terrain type) now short-circuits
to no encounter; a genuinely missing/None value still defaults to 0.15.
"""
import sys
import random
import pytest

sys.path.insert(0, "/app")

from app.services.hex_travel_service import _roll_encounter


# hex_type_config mirror: settlements are explicit-0 safe types.
CFG = {
    "plains": {"encounter_base_chance": 0.15},
    "forest": {"encounter_base_chance": 0.30},
    "town": {"encounter_base_chance": 0.0},
    "village": {"encounter_base_chance": 0.0},
    "castle": {"encounter_base_chance": 0.0},
}


def _always_hit(monkeypatch):
    # random.random() == 0.0 < any positive chance → encounter always fires,
    # so a False result can only come from the safe-zone short-circuit.
    monkeypatch.setattr(random, "random", lambda: 0.0)


def test_hex_explicit_zero_is_safe(monkeypatch):
    _always_hit(monkeypatch)
    hexd = {"hex_type": "plains", "encounter_chance": 0.0}
    assert _roll_encounter(hexd, CFG) is False, "encounter_chance=0 must never fire"


def test_settlement_type_is_safe_despite_row_chance(monkeypatch):
    """The real-world bug: town/village hexes carry row chance 0.15 but their
    terrain type is base 0.0 — you should not be ambushed inside a town."""
    _always_hit(monkeypatch)
    for ht in ("town", "village", "castle"):
        hexd = {"hex_type": ht, "encounter_chance": 0.15}
        assert _roll_encounter(hexd, CFG) is False, f"{ht} must be safe (type base 0)"


def test_missing_chance_still_defaults_to_015(monkeypatch):
    """A genuinely absent value keeps the historical 0.15 default."""
    # miss just under 0.15 → fires; miss just over → does not. Proves default=0.15.
    monkeypatch.setattr(random, "random", lambda: 0.14)
    assert _roll_encounter({"hex_type": "plains"}, {}) is True
    monkeypatch.setattr(random, "random", lambda: 0.16)
    assert _roll_encounter({"hex_type": "plains"}, {}) is False


def test_positive_chance_still_rolls(monkeypatch):
    _always_hit(monkeypatch)
    hexd = {"hex_type": "forest", "encounter_chance": 0.30}
    assert _roll_encounter(hexd, CFG) is True, "non-zero hex must still roll encounters"


def test_type_raises_hex_chance_via_max(monkeypatch):
    """max(hex, type) preserved: forest type 0.30 lifts a low-row hex."""
    # miss at 0.25 → below forest 0.30 → fires (proves type raised it above hex 0.10).
    monkeypatch.setattr(random, "random", lambda: 0.25)
    hexd = {"hex_type": "forest", "encounter_chance": 0.10}
    assert _roll_encounter(hexd, CFG) is True
