"""Solo death save accumulation (Phase 7.6.7)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.solo_death_service import DEATH_SAVE_FAILURE_THRESHOLD, apply_death_save_outcome


def _roll(test: str, total: int, raw: int, nat20: bool = False, nat1: bool = False):
    return {
        "test": test,
        "total": total,
        "raw": raw,
        "is_nat20": nat20,
        "is_nat1": nat1,
        "stat_mod": 0,
        "skill_rank": 0,
        "proficiency": 0,
    }


def test_non_death_roll_ignored():
    s, died = apply_death_save_outcome({}, _roll("melee_attack", 15, 10))
    assert died is False
    assert "death_save_failures" not in s


def test_death_save_success_resets():
    sheet = {"death_save_failures": 2}
    s, died = apply_death_save_outcome(sheet, _roll("death_save", 12, 12))
    assert s["death_save_failures"] == 0
    assert died is False


def test_death_save_nat20_resets():
    sheet = {"death_save_failures": 2}
    s, died = apply_death_save_outcome(sheet, _roll("death_save", 5, 20, nat20=True))
    assert s["death_save_failures"] == 0
    assert died is False


def test_three_failures_triggers_death():
    sheet = {}
    for _ in range(DEATH_SAVE_FAILURE_THRESHOLD - 1):
        sheet, died = apply_death_save_outcome(sheet, _roll("death_save", 5, 5))
        assert died is False
    sheet, died = apply_death_save_outcome(sheet, _roll("death_save", 5, 8))
    assert died is True
    assert sheet["death_save_failures"] >= DEATH_SAVE_FAILURE_THRESHOLD


def test_nat1_counts_double():
    sheet = {"death_save_failures": 1}
    s, died = apply_death_save_outcome(sheet, _roll("death_save", 3, 1, nat1=True))
    assert s["death_save_failures"] == 3
    assert died is True


def test_resolve_test_name_death_save_variants():
    from app.services.dice import resolve_test_name

    assert resolve_test_name("death_save") == "death_save"
    assert resolve_test_name("Death Save") == "death_save"
    assert resolve_test_name("Death_Save") == "death_save"


def test_death_save_sequence_multiple_turns():
    """Failures accumulate across rolls; successes clear; repeats stay valid."""
    sheet = {}
    sheet, d = apply_death_save_outcome(sheet, _roll("death_save", 5, 5))
    assert d is False
    assert sheet["death_save_failures"] == 1
    sheet, d = apply_death_save_outcome(sheet, _roll("death_save", 5, 5))
    assert d is False
    assert sheet["death_save_failures"] == 2
    sheet, d = apply_death_save_outcome(sheet, _roll("death_save", 14, 14))
    assert d is False
    assert sheet["death_save_failures"] == 0
    sheet, d = apply_death_save_outcome(sheet, _roll("death_save", 3, 3))
    assert d is False
    assert sheet["death_save_failures"] == 1
