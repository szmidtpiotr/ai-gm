"""TDD: Issue #861 — render dual-wield (drugi atak off-hand + parowanie) w UI walki.

Frontend rysuje karty walki z META wiersza `combat_turns` (DB), NIE z live response.
Dlatego meta MUSI nieść sygnały, których UI potrzebuje, żeby narysować:
  • atak OFF-HAND  → flaga `offhand: true` na karcie ataku gracza (label „drugi cios")
  • atak WROGA sparowany → `parry_bonus` w meta ataku wroga (badge „Parujesz +N")

#598 zapisuje off-hand jako osobny `combat_turn`, ale bez flagi — UI nie odróżnia go
od głównego ciosu. `_enemy_attack_narrative_dict` w ogóle gubił `parry_bonus`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.combat_service import (  # noqa: E402
    _enemy_attack_narrative_dict,
    _player_attack_narrative_dict,
)

_ATK = {
    "test": "melee_attack", "attack_stat": "DEX", "modifier": 3, "total": 16,
    "weapon_key": "dagger", "weapon_label": "Sztylet", "weapon_type": "melee",
}


# ─── off-hand flag (drugi cios) ──────────────────────────────────────────────

def test_offhand_attack_meta_flagged():
    """Atak off-hand (weapon_override) → meta.offhand == True (UI: 'drugi cios')."""
    meta = _player_attack_narrative_dict(_ATK, 13, 16, {"key": "dagger"}, offhand=True)
    assert meta["offhand"] is True


def test_main_attack_meta_not_offhand():
    """Główny atak → meta.offhand == False (UI: karta jak dotąd)."""
    meta = _player_attack_narrative_dict(_ATK, 13, 16, {"key": "dagger"}, offhand=False)
    assert meta["offhand"] is False


def test_player_attack_meta_keeps_existing_keys():
    """Backward compat — wszystkie pola sprzed #861 nadal obecne i poprawne."""
    meta = _player_attack_narrative_dict(_ATK, 13, 16, {"key": "dagger"})
    for k in ("raw_d20", "attack_test", "attack_stat", "attack_label",
              "modifier", "total", "weapon_key", "weapon_label", "weapon_type"):
        assert k in meta, f"brak pola {k}"
    assert meta["attack_label"] == "ATAK WRĘCZ"
    assert meta["weapon_label"] == "Sztylet"
    assert meta["offhand"] is False   # default = główny cios


# ─── parry badge (parowanie) ─────────────────────────────────────────────────

def test_enemy_attack_meta_includes_parry_bonus():
    """Atak wroga sparowany (out.parry_bonus) → meta niesie parry_bonus dla badge."""
    out = {"player_evasion": None, "parry_bonus": 2}
    d = _enemy_attack_narrative_dict(out, 14, 18, 15, {"name": "Bandyta"}, 2)
    assert d["parry_bonus"] == 2


def test_enemy_attack_meta_zero_parry_when_absent():
    """Brak parowania → parry_bonus == 0 (UI: bez badge, zero regresji)."""
    out = {"player_evasion": None}
    d = _enemy_attack_narrative_dict(out, 14, 18, 15, {"name": "Bandyta"}, 2)
    assert d["parry_bonus"] == 0


def test_enemy_attack_meta_keeps_existing_keys():
    """Backward compat — pola ataku wroga sprzed #861 nietknięte."""
    out = {"player_evasion": {"raw": 5, "dex_mod": 2, "total": 7}}
    d = _enemy_attack_narrative_dict(out, 14, 18, 15, {"name": "Bandyta"}, 2)
    for k in ("raw_d20", "attack_bonus", "attack_roll", "target_ac",
              "enemy_name", "player_evasion"):
        assert k in d, f"brak pola {k}"
