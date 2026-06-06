"""TDD: Issue #360 — C4 wound_penalty utility: hp_current/hp_max → roll penalty."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─── Thresholds: >75% → 0, >50% → -1, >25% → -2, ≤25% → -4 ─────────────────

def test_healthy_no_penalty():
    """HP > 75% → zero penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(81, 100) == 0


def test_lightly_wounded_minus1():
    """50% < HP ≤ 75% → -1 penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(60, 100) == -1


def test_moderately_wounded_minus2():
    """25% < HP ≤ 50% → -2 penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(35, 100) == -2


def test_critically_wounded_minus4():
    """HP ≤ 25% → -4 penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(20, 100) == -4


# ─── Boundary values ─────────────────────────────────────────────────────────

def test_exactly_75pct_is_minus1():
    """Exactly 75% is NOT >75%, so gets -1."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(75, 100) == -1


def test_exactly_50pct_is_minus2():
    """Exactly 50% is NOT >50%, so gets -2."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(50, 100) == -2


def test_exactly_25pct_is_minus4():
    """Exactly 25% is NOT >25%, so gets -4."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(25, 100) == -4


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_zero_hp_is_minus4():
    """HP=0 → -4."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(0, 100) == -4


def test_full_hp_no_penalty():
    """HP=max → 0."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(100, 100) == 0


def test_zero_max_hp_returns_zero():
    """max_hp=0 → no penalty (division guard)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(0, 0) == 0
