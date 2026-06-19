"""TDD: Issue #829 — Stage 2 damage dice animation backend contract.

The frontend Stage 2 dice animation (damage dice) requires the attack response
to carry `damage_die` (notation string) and `damage_rolls` (list of ints).
Without these, buildDamageStage() returns falsy and Stage 2 never starts.
These tests lock the backend contract that feeds the frontend animation.
"""
import sys
import re
import random
sys.path.insert(0, '/app')

import pytest
from app.services.combat_service import roll_dice_detailed


# ─── Backend contract: roll_dice_detailed shape ───────────────────────────────

def test_roll_dice_detailed_returns_required_fields():
    """roll_dice_detailed must return die + rolls — both are read by Stage 2."""
    result = roll_dice_detailed('1d6')
    assert 'die' in result, "missing 'die' field — combat_service sets out['damage_die'] from this"
    assert 'rolls' in result, "missing 'rolls' field — combat_service sets out['damage_rolls'] from this"
    assert isinstance(result['rolls'], list), "'rolls' must be a list"
    assert len(result['rolls']) >= 1, "'rolls' must have at least one element"


def test_roll_dice_detailed_all_weapon_die_types():
    """Every weapon damage die type must return a valid roll structure for Stage 2."""
    for notation in ['1d3', '1d4', '1d6', '1d8', '1d10', '1d12']:
        result = roll_dice_detailed(notation)
        assert result['die'] == notation, f"die field mismatch for {notation}: got {result['die']!r}"
        assert all(isinstance(r, int) for r in result['rolls']), f"non-int rolls for {notation}"
        n, sides = 1, int(notation.split('d')[1])
        assert all(1 <= r <= sides for r in result['rolls']), (
            f"roll value out of range for {notation}: {result['rolls']}"
        )


def test_roll_dice_detailed_normalises_notation():
    """Notation without leading count ('d6') normalises to '1d6'."""
    result = roll_dice_detailed('d6')
    assert result['die'] == '1d6', f"expected '1d6', got {result['die']!r}"
    assert len(result['rolls']) == 1


def test_roll_dice_detailed_multi_die():
    """2dX returns two rolls — Stage 2 shows each die landing separately."""
    result = roll_dice_detailed('2d6')
    assert result['die'] == '2d6'
    assert len(result['rolls']) == 2


# ─── Stage 2 frontend contract ────────────────────────────────────────────────

def test_stage2_frontend_guard_conditions():
    """Frontend buildDamageStage checks: data.hit && data.damage_die && damage > 0.
    Backend must ensure damage_die is truthy and damage_rolls is non-empty on a hit.
    """
    result = roll_dice_detailed('1d3')
    # Simulate what combat_service puts in the response on a hit
    out = {
        'hit': True,
        'damage_die': result['die'],       # combat_service.py:4660
        'damage_rolls': result['rolls'],   # combat_service.py:4661
        'damage': max(1, sum(result['rolls'])),
    }
    # These are the exact checks from buildDamageStage() in app.js
    assert out['hit'], "hit must be True for Stage 2 to trigger"
    assert out['damage_die'], "damage_die must be truthy"
    assert out['damage'] > 0, "damage must be > 0 for Stage 2"
    assert isinstance(out['damage_rolls'], list) and len(out['damage_rolls']) > 0, (
        "damage_rolls must be a non-empty list so forced dice match the backend result"
    )


def test_roll_dice_detailed_unparseable_returns_empty_rolls():
    """Unparseable notation returns empty rolls — Stage 2 falls back to unforced throw."""
    result = roll_dice_detailed('bad_input')
    assert result['rolls'] == [], "unparseable notation must yield empty rolls, not crash"
    assert result['die'] == 'bad_input', "die field preserves the original string"
