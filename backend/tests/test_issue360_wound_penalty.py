"""TDD: Issue #360 — C4 wound_penalty utility: hp_current/hp_max → roll penalty.

REBALANSOWANE G1 #1459 (2026-07-19) na WARIANT A (łagodny). Progi:
  > 50% → 0 · 26–50% → 0 (Ranny, klimat) · 11–25% → -1 · 1–10% → -2.
Poprzednio wariant B (75/50/25 → 0/-1/-2/-4) — superseded decyzją Piotra.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─── Thresholds (wariant A): >50% → 0, >25% → 0, >10% → -1, ≤10% → -2 ─────────

def test_healthy_no_penalty():
    """HP > 50% → zero penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(81, 100) == 0
    assert wound_penalty(60, 100) == 0


def test_minor_wound_is_climate_only():
    """26% < HP ≤ 50% → 0 (Ranny — tylko narracja, brak kary)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(35, 100) == 0


def test_serious_wound_minus1():
    """11% < HP ≤ 25% → -1 penalty (pierwsza realna kara)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(20, 100) == -1


def test_near_death_minus2():
    """HP ≤ 10% → -2 penalty."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(8, 100) == -2


# ─── Boundary values ─────────────────────────────────────────────────────────

def test_exactly_50pct_is_zero():
    """Exactly 50% is NOT >50%, so falls to minor tier → 0 (klimat)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(50, 100) == 0


def test_exactly_25pct_is_minus1():
    """Exactly 25% is NOT >25%, so falls to serious tier → -1."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(25, 100) == -1


def test_exactly_10pct_is_minus2():
    """Exactly 10% is NOT >10%, so falls to near_death tier → -2."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(10, 100) == -2


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_zero_hp_is_minus2():
    """HP=0 → -2 (na skraju śmierci)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(0, 100) == -2


def test_full_hp_no_penalty():
    """HP=max → 0."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(100, 100) == 0


def test_zero_max_hp_returns_zero():
    """max_hp=0 → no penalty (division guard)."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(0, 0) == 0
