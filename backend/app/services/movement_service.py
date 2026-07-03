"""PT11 #1121 — Wspólny rdzeń ruchu (movement core).

Jeden silnik sekwencji kroków konsumowany przez dwa profile:
  - world  (hex_travel_service.resolve_chain_travel): heksy z kosztem terenu,
           dzienny budżet marszu (dusk/forced_camp), rolki encounterów.
  - local  (local_map.local_travel): kroki 15-min po sub-lokacjach, ryzyko wg
           safe_for_rest.

Ruch = sekwencja kroków. steps[0] to pozycja startowa (już zajęta, cost 0).
Każdy kolejny krok ma:
  - cost         — koszt czasu podróży (zwracany jako total_cost; teleport-aware),
  - budget_cost  — koszt obciążający dzienny budżet marszu (teren; None → = cost),
  - cleared      — czy encounter tu już wyczyszczony (pomiń ryzyko, licz koszt),
  - data         — dowolny payload (dane heksa), przekazywany do roll_risk.

Profil dostarcza:
  - roll_risk(step)              → payload encountera | None (przerwanie ryzykiem),
  - budget_interrupt(acc, step)  → powód ('dusk'/'forced_camp'/...) | None.

Sekwencję można wznowić od start_index (travel_plan resume-after-combat) oraz
z przeniesionym budżetem (budget_start = godziny już przemaszerowane dziś).

Rdzeń jest CZYSTY — bez DB, bez I/O. Konsumenci budują kroki z DB, wołają
run_step_sequence, a wynik mapują z powrotem na zapis pozycji / travel_plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Powód przerwania nadawany przy trafieniu ryzyka (encounter).
RISK_REASON = "encounter"


@dataclass
class MovementStep:
    """Pojedynczy krok sekwencji ruchu."""

    key: Any
    cost: float = 0.0
    budget_cost: Optional[float] = None
    data: dict = field(default_factory=dict)
    cleared: bool = False

    def effective_budget_cost(self) -> float:
        """Koszt obciążający budżet marszu — budget_cost, a gdy None: cost."""
        return self.cost if self.budget_cost is None else self.budget_cost


@dataclass
class MovementProfile:
    """Reguły profilu (world/local) wstrzykiwane do rdzenia."""

    name: str
    roll_risk: Callable[[MovementStep], Optional[dict]]
    budget_interrupt: Optional[Callable[[float, MovementStep], Optional[str]]] = None


@dataclass
class MovementOutcome:
    """Wynik przejścia sekwencji."""

    arrived_index: int
    total_cost: float
    budget_total: float
    encounter: Optional[dict] = None
    interrupt_reason: Optional[str] = None
    completed: bool = False


def run_step_sequence(
    steps: list[MovementStep],
    profile: MovementProfile,
    *,
    start_index: int = 0,
    budget_start: float = 0.0,
) -> MovementOutcome:
    """Przejdź sekwencję kroków wg profilu.

    Kolejność na każdym kroku (zgodna z world resolve_chain_travel):
      1. wejście w krok → akumuluj koszt czasu i budżetu,
      2. budget_interrupt(acc, step) → jeśli powód: stop na tym kroku,
      3. cleared → pomiń ryzyko (koszt już policzony), przejdź dalej,
      4. roll_risk(step) → jeśli encounter: stop na tym kroku.

    Zwraca MovementOutcome z indeksem dojścia, kosztem trip, sumą budżetu
    oraz — gdy przerwano — encounterem i powodem.
    """
    if not steps:
        return MovementOutcome(
            arrived_index=0, total_cost=0.0, budget_total=budget_start, completed=True
        )

    start_index = max(0, min(start_index, len(steps) - 1))
    arrived = start_index
    trip_total = 0.0
    budget_running = budget_start
    encounter: Optional[dict] = None
    reason: Optional[str] = None
    completed = True

    for idx in range(start_index + 1, len(steps)):
        step = steps[idx]

        # 1. wejście w krok — koszty zawsze narastają
        trip_total += step.cost
        budget_running += step.effective_budget_cost()
        arrived = idx

        # 2. przerwanie budżetowe (world: hard cap forced_camp / soft cap dusk)
        if profile.budget_interrupt is not None:
            b_reason = profile.budget_interrupt(budget_running, step)
            if b_reason:
                reason = b_reason
                completed = False
                break

        # 3. wyczyszczony encounter → nie roluj (koszt już policzony)
        if step.cleared:
            continue

        # 4. ryzyko / encounter
        risk = profile.roll_risk(step)
        if risk:
            encounter = risk
            reason = RISK_REASON
            completed = False
            break

    return MovementOutcome(
        arrived_index=arrived,
        total_cost=trip_total,
        budget_total=budget_running,
        encounter=encounter,
        interrupt_reason=reason,
        completed=completed,
    )
