"""TDD: Issue #1121 (PT11) — wspólny rdzeń ruchu (movement_service).

Jeden silnik sekwencji kroków konsumowany przez profile world/local.
Ruch = sekwencja kroków; każdy krok ma koszt czasu i (opcjonalnie) koszt
budżetu, może być już wyczyszczony (skip ryzyka), może wywołać encounter
(ryzyko) lub przerwanie budżetowe. Sekwencję można wznowić od start_index.

Te testy opisują TYLKO czysty rdzeń (bez DB). Zgodność z zachowaniem
world/local weryfikują istniejące testy PT6-PT10 (regres).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.movement_service import (  # noqa: E402
    MovementStep,
    MovementProfile,
    MovementOutcome,
    run_step_sequence,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _steps(costs, **overrides):
    """Build a step list where steps[0] is the start position (cost 0)."""
    out = [MovementStep(key=0, cost=0.0)]
    for i, c in enumerate(costs, start=1):
        out.append(MovementStep(key=i, cost=c, **overrides))
    return out


def _never_risk(step):
    return None


# ─── Test główny — pełny przejazd bez przerwania ───────────────────────────────

def test_full_traversal_no_interrupt():
    """3 kroki, brak ryzyka i budżetu → dochodzi do ostatniego kroku."""
    steps = _steps([1.0, 2.0, 3.0])  # 4 pozycje: start + 3 kroki
    profile = MovementProfile(name="test", roll_risk=_never_risk)
    out = run_step_sequence(steps, profile)
    assert isinstance(out, MovementOutcome)
    assert out.arrived_index == 3
    assert out.total_cost == pytest.approx(6.0)
    assert out.completed is True
    assert out.encounter is None
    assert out.interrupt_reason is None


# ─── Ryzyko / encounter przerywa na kroku ──────────────────────────────────────

def test_encounter_interrupt_stops_at_step():
    """Ryzyko na 2. kroku → dojście = ten krok, encounter ustawiony, reason='encounter'."""
    steps = _steps([1.0, 1.0, 1.0])

    def risk_on_step2(step):
        return {"enemy_key": "bandit"} if step.key == 2 else None

    profile = MovementProfile(name="test", roll_risk=risk_on_step2)
    out = run_step_sequence(steps, profile)
    assert out.arrived_index == 2
    assert out.total_cost == pytest.approx(2.0)  # kroki 1 + 2 policzone
    assert out.completed is False
    assert out.interrupt_reason == "encounter"
    assert out.encounter == {"enemy_key": "bandit"}


# ─── Przerwanie budżetowe (dusk / forced_camp) ─────────────────────────────────

def test_budget_interrupt_stops_and_reports_reason():
    """budget_interrupt zwraca powód → sekwencja staje na tym kroku."""
    steps = _steps([4.0, 4.0, 4.0])  # budżet narasta 4/8/12

    def budget(acc, step):
        if acc >= 12.0:
            return "forced_camp"
        if acc >= 8.0:
            return "dusk"
        return None

    profile = MovementProfile(name="world", roll_risk=_never_risk, budget_interrupt=budget)
    out = run_step_sequence(steps, profile)
    # po 2. kroku acc=8 → dusk
    assert out.arrived_index == 2
    assert out.interrupt_reason == "dusk"
    assert out.completed is False
    assert out.budget_total == pytest.approx(8.0)


def test_budget_start_carries_into_threshold():
    """Wcześniej przemaszerowane godziny liczą się do progu (wznowienie dnia)."""
    steps = _steps([2.0, 2.0])

    def budget(acc, step):
        return "forced_camp" if acc >= 12.0 else None

    profile = MovementProfile(name="world", roll_risk=_never_risk, budget_interrupt=budget)
    out = run_step_sequence(steps, profile, budget_start=10.0)
    # 10 + 2 = 12 na 1. kroku → forced_camp
    assert out.arrived_index == 1
    assert out.interrupt_reason == "forced_camp"
    assert out.budget_total == pytest.approx(12.0)


# ─── Wznowienie od start_index (travel_plan resume-after-combat) ───────────────

def test_resume_from_start_index():
    """start_index=2 pomija już przebyte kroki, liczy tylko pozostałe."""
    steps = _steps([1.0, 1.0, 1.0, 1.0])  # start + 4
    profile = MovementProfile(name="test", roll_risk=_never_risk)
    out = run_step_sequence(steps, profile, start_index=2)
    # przebywa kroki 3 i 4
    assert out.arrived_index == 4
    assert out.total_cost == pytest.approx(2.0)
    assert out.completed is True


# ─── Wyczyszczony krok pomija ryzyko, ale liczy koszt ──────────────────────────

def test_cleared_step_skips_risk_but_counts_cost():
    """Krok z cleared=True nie roluje ryzyka, lecz koszt/budżet nadal narasta."""
    steps = [
        MovementStep(key=0, cost=0.0),
        MovementStep(key=1, cost=1.0, cleared=True),  # ryzyko pominięte
        MovementStep(key=2, cost=1.0),
    ]

    def always_risk(step):
        return {"enemy_key": "goblin"}

    profile = MovementProfile(name="test", roll_risk=always_risk)
    out = run_step_sequence(steps, profile)
    # krok 1 pominął ryzyko (cleared), krok 2 zaryzykował → stop na 2
    assert out.arrived_index == 2
    assert out.interrupt_reason == "encounter"
    assert out.total_cost == pytest.approx(2.0)  # oba kroki policzone


# ─── Dwa koszty: trip (teleport-aware) vs budżet (teren) ───────────────────────

def test_dual_cost_trip_vs_budget():
    """budget_cost może różnić się od cost (krok teleportu: 8h czasu, 1h budżetu)."""
    steps = [
        MovementStep(key=0, cost=0.0),
        MovementStep(key=1, cost=8.0, budget_cost=1.0),  # teleport
    ]
    seen = {}

    def budget(acc, step):
        seen["acc"] = acc
        return None

    profile = MovementProfile(name="world", roll_risk=_never_risk, budget_interrupt=budget)
    out = run_step_sequence(steps, profile)
    assert out.total_cost == pytest.approx(8.0)     # czas podróży
    assert out.budget_total == pytest.approx(1.0)   # obciążenie budżetu marszu
    assert seen["acc"] == pytest.approx(1.0)


def test_budget_cost_defaults_to_cost():
    """Gdy budget_cost=None, do budżetu liczy się cost (zwykły krok terenowy)."""
    steps = _steps([3.0])
    seen = {}

    def budget(acc, step):
        seen["acc"] = acc
        return None

    profile = MovementProfile(name="world", roll_risk=_never_risk, budget_interrupt=budget)
    out = run_step_sequence(steps, profile)
    assert out.budget_total == pytest.approx(3.0)
    assert seen["acc"] == pytest.approx(3.0)


# ─── Profil local — pojedynczy krok (backward-compat kształt) ──────────────────

def test_single_step_local_profile():
    """Local = sekwencja długości 1; encounter na jedynym kroku przerywa."""
    steps = [MovementStep(key=0, cost=0.0), MovementStep(key=1, cost=15.0)]

    def local_risk(step):
        return {"enemy_key": "bandit", "hex_label": "Zaułek"}

    profile = MovementProfile(name="local", roll_risk=local_risk)
    out = run_step_sequence(steps, profile)
    assert out.arrived_index == 1
    assert out.total_cost == pytest.approx(15.0)
    assert out.interrupt_reason == "encounter"
    assert out.encounter["enemy_key"] == "bandit"


def test_empty_or_singleton_sequence_completes():
    """Sekwencja bez kroków (sam start) kończy się natychmiast, bez ruchu."""
    profile = MovementProfile(name="test", roll_risk=_never_risk)
    out = run_step_sequence([MovementStep(key=0, cost=0.0)], profile)
    assert out.arrived_index == 0
    assert out.total_cost == pytest.approx(0.0)
    assert out.completed is True
