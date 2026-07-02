"""TDD: Issue #1109 — generate-plan nie może tworzyć orphan-beatów.

ensure_beats_closable(plan): każdy nieopcjonalny beat bez objective_type i bez
narrative_close dostaje narrative_close=True → validate_gm_plan zwraca 0 błędów.
"""
import sys
sys.path.insert(0, "/app")

from app.services.campaign_plan_runtime import ensure_beats_closable, validate_gm_plan


def _plan(beats):
    return {"acts": [{"number": 1, "key_beats": beats}]}


# ─── Test 1 (GŁÓWNY) — orphan non-optional beat dostaje narrative_close ───────

def test_orphan_beat_gets_narrative_close():
    plan = _plan([
        {"beat_key": "orphan", "optional": False, "summary": "Nocny sabotaż"},
    ])
    out = ensure_beats_closable(plan)
    beat = out["acts"][0]["key_beats"][0]
    assert beat.get("narrative_close") is True, \
        f"Orphan beat musi dostać narrative_close=True — {beat}"


def test_plan_with_orphan_passes_validation_after_fix():
    """Plan który miał 1 błąd orphan_beat — po ensure_beats_closable ma 0 błędów."""
    plan = _plan([
        {"beat_key": "start", "optional": False, "objective_type": "visit_location",
         "objective_value": "karczma"},
        {"beat_key": "nocna_proba_sabotazu", "optional": False, "summary": "Wyrostki nocą"},
    ])
    assert len(validate_gm_plan(plan)["errors"]) == 1, "Precondition: 1 orphan error"
    fixed = ensure_beats_closable(plan)
    assert validate_gm_plan(fixed)["errors"] == [], \
        "Po naprawie plan nie może mieć błędów walidacji"


# ─── Test 2 — nie ruszamy beatów już domykalnych ────────────────────────────

def test_beat_with_objective_type_untouched():
    plan = _plan([
        {"beat_key": "kill", "optional": False, "objective_type": "kill_enemy",
         "objective_value": "goblin"},
    ])
    out = ensure_beats_closable(plan)
    beat = out["acts"][0]["key_beats"][0]
    assert beat.get("narrative_close") in (None, False), \
        "Beat z objective_type nie potrzebuje narrative_close"


def test_beat_with_existing_narrative_close_untouched():
    plan = _plan([
        {"beat_key": "finale", "optional": False, "narrative_close": True,
         "summary": "Symboliczne zakończenie"},
    ])
    out = ensure_beats_closable(plan)
    assert out["acts"][0]["key_beats"][0]["narrative_close"] is True


def test_optional_orphan_beat_left_alone():
    """Opcjonalny beat bez celu jest legalny — nie dodajemy narrative_close."""
    plan = _plan([
        {"beat_key": "flavor", "optional": True, "summary": "Podsłuchane szepty"},
    ])
    out = ensure_beats_closable(plan)
    beat = out["acts"][0]["key_beats"][0]
    assert beat.get("narrative_close") in (None, False), \
        "Opcjonalny beat nie wymaga domknięcia — nie ruszamy"


# ─── Test 3 (backward compat / defensywność) ─────────────────────────────────

def test_non_dict_plan_returned_untouched():
    assert ensure_beats_closable(None) is None
    assert ensure_beats_closable({"foo": "bar"}) == {"foo": "bar"}


def test_idempotent():
    plan = _plan([{"beat_key": "orphan", "optional": False, "summary": "x"}])
    once = ensure_beats_closable(plan)
    twice = ensure_beats_closable(once)
    assert twice["acts"][0]["key_beats"][0]["narrative_close"] is True
