"""TDD: Issue #644 (B3) — Rogue dostaje własny budżet skilli (najwięcej skilli + bias złodzieja).

Łotrzyk = filar tożsamości: NAJWIĘCEJ skilli. Dziś brak klucza "rogue" w SKILL_BUDGET →
roll_creation_skills wpada w fallback na "warrior" (8 slotów / 7 aktywnych, bias wojownika).
Po fixie rogue ma slots=10 / active_skills=9 i bias złodzieja/zwiadowcy, a skille
złodziejskie (lockpick/acrobatics) istnieją w puli kreacji.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_creation_config import (  # noqa: E402
    ARCHETYPE_SKILL_WEIGHTS,
    CREATION_SKILL_POOL,
    SKILL_BUDGET,
    roll_creation_skills,
)

ROGUE_BIAS = {"stealth", "lockpick", "sleight_of_hand", "acrobatics", "awareness", "investigation"}


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_rogue_has_own_skill_budget():
    """Rogue ma własny wpis w SKILL_BUDGET: slots=10, active_skills=9 (nie fallback warrior)."""
    assert "rogue" in SKILL_BUDGET, "brak klucza 'rogue' — wpada w fallback warrior"
    assert SKILL_BUDGET["rogue"]["slots"] == 10
    assert SKILL_BUDGET["rogue"]["active_skills"] == 9


def test_rogue_has_more_active_skills_than_warrior():
    """Tożsamość: łotrzyk = NAJWIĘCEJ aktywnych skilli (> warrior, ≥ scholar)."""
    assert SKILL_BUDGET["rogue"]["active_skills"] > SKILL_BUDGET["warrior"]["active_skills"]
    assert SKILL_BUDGET["rogue"]["active_skills"] >= SKILL_BUDGET["scholar"]["active_skills"]


def test_rogue_bias_is_thief_kit():
    """ARCHETYPE_SKILL_WEIGHTS['rogue'] = pełny zestaw złodzieja/zwiadowcy z AK.2."""
    assert "rogue" in ARCHETYPE_SKILL_WEIGHTS
    assert set(ARCHETYPE_SKILL_WEIGHTS["rogue"]) == ROGUE_BIAS


def test_thief_skills_present_in_creation_pool():
    """lockpick + acrobatics muszą być w puli kreacji — inaczej bias jest martwy."""
    assert "lockpick" in CREATION_SKILL_POOL
    assert "acrobatics" in CREATION_SKILL_POOL


def test_rogue_roll_produces_nine_active_skills():
    """roll_creation_skills('rogue') daje 9 aktywnych skilli (rank ≥ 1)."""
    ranks = roll_creation_skills("rogue", rng=random.Random(42))
    active = [k for k, v in ranks.items() if v > 0]
    assert len(active) == 9, f"oczekiwano 9 aktywnych, jest {len(active)}: {active}"


def test_rogue_roll_biased_toward_thief_skills():
    """Przy wielu losowaniach łotrzyk statystycznie częściej dostaje skille złodziejskie niż wojownik."""
    rng = random.Random(7)
    rogue_hits = 0
    warrior_hits = 0
    runs = 200
    for _ in range(runs):
        r = roll_creation_skills("rogue", rng=rng)
        w = roll_creation_skills("warrior", rng=rng)
        rogue_hits += sum(1 for k in ROGUE_BIAS if r.get(k, 0) > 0)
        warrior_hits += sum(1 for k in ROGUE_BIAS if w.get(k, 0) > 0)
    assert rogue_hits > warrior_hits, (
        f"rogue powinien częściej trafiać skille złodziejskie: rogue={rogue_hits} vs warrior={warrior_hits}"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_warrior_budget_unchanged():
    """Wojownik niezmieniony: slots=8, active_skills=7."""
    assert SKILL_BUDGET["warrior"] == {"slots": 8, "active_skills": 7}


def test_scholar_budget_unchanged():
    """Uczony niezmieniony: slots=10, active_skills=8."""
    assert SKILL_BUDGET["scholar"] == {"slots": 10, "active_skills": 8}


def test_warrior_roll_still_seven_active():
    """roll_creation_skills('warrior') nadal daje 7 aktywnych skilli."""
    ranks = roll_creation_skills("warrior", rng=random.Random(1))
    active = [k for k, v in ranks.items() if v > 0]
    assert len(active) == 7
