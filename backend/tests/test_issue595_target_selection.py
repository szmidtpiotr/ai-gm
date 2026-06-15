"""TDD: Issue #595 — gracz może wybrać cel ataku w walce z wieloma wrogami.

Bug: frontend wysyła `target_id`, ale backend go ignoruje — `resolve_attack` zawsze
bije pierwszego żywego wroga w turn_order. Fix: czysty helper `_select_player_target`
honoruje wskazany cel (jeśli to żywy wróg), inaczej zachowuje stare auto-wybieranie.
Melee dalej bramkowane strefą (out_of_range), dystans/czar celuje dowolną strefę.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.combat_service import (
    _select_player_target,
    ZONE_ENGAGED,
    ZONE_RANGED,
)


def _combatants():
    return [
        {"id": "player", "type": "player", "hp_current": 20, "zone": ZONE_ENGAGED},
        {"id": "e1", "type": "enemy", "hp_current": 10, "zone": ZONE_ENGAGED},
        {"id": "e2", "type": "enemy", "hp_current": 3, "zone": ZONE_ENGAGED},
        {"id": "e3", "type": "enemy", "hp_current": 8, "zone": ZONE_RANGED},
    ]


ORDER = ["player", "e1", "e2", "e3"]


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_player_targets_chosen_living_enemy_ranged():
    """Dystans: wskazany żywy wróg (e2, ranny) jest celem zamiast pierwszego (e1)."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=False, requested_target_id="e2",
    )
    assert tid == "e2", f"powinien wybrać wskazany cel e2, dostał {tid}"
    assert block is None


def test_player_targets_chosen_living_enemy_melee_same_zone():
    """Melee: wskazany wróg w tej samej strefie (zwarcie) jest celem."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=True, requested_target_id="e2",
    )
    assert tid == "e2", f"melee w tej samej strefie powinno trafić e2, dostało {tid}"
    assert block is None


def test_player_targets_chosen_enemy_other_zone_melee_blocked():
    """Melee: wskazany wróg w innej strefie (dystans) → out_of_range, brak celu."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=True, requested_target_id="e3",
    )
    assert tid is None
    assert block == "out_of_range", f"e3 jest w dystansie — melee ma blokować, dostało {block}"


def test_dead_requested_target_falls_back_to_first_living():
    """Wskazany cel martwy/nieobecny → fallback do pierwszego żywego (stare zachowanie)."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=False, requested_target_id="nieistnieje",
    )
    assert tid == "e1", f"nieprawidłowy cel → fallback do e1, dostał {tid}"
    assert block is None


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_no_request_ranged_picks_first_in_order():
    """Brak wskazania (dystans): pierwszy żywy w turn_order — bez zmian."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=False, requested_target_id=None,
    )
    assert tid == "e1"
    assert block is None


def test_no_request_melee_picks_first_same_zone():
    """Brak wskazania (melee): pierwszy żywy w tej samej strefie — bez zmian."""
    cs = _combatants()
    living = ["e1", "e2", "e3"]
    tid, block = _select_player_target(
        cs, ORDER, living, ZONE_ENGAGED, is_melee=True, requested_target_id=None,
    )
    assert tid == "e1"
    assert block is None


def test_no_request_melee_all_enemies_other_zone_blocked():
    """Brak wskazania (melee): wszyscy żywi w innej strefie → out_of_range."""
    cs = [
        {"id": "player", "type": "player", "hp_current": 20, "zone": ZONE_ENGAGED},
        {"id": "e1", "type": "enemy", "hp_current": 10, "zone": ZONE_RANGED},
    ]
    tid, block = _select_player_target(
        cs, ["player", "e1"], ["e1"], ZONE_ENGAGED, is_melee=True, requested_target_id=None,
    )
    assert tid is None
    assert block == "out_of_range"
