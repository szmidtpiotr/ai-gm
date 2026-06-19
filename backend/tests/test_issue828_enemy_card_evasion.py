"""TDD: Issue #828 — narrative ataku wroga musi zawierać player_evasion, nie tylko target_ac.

#828 follow-up po #826: backend oblicza pasywny unik gracza (d20+DEX) ale NIE wpisuje go
do narrative w combat_turns. Frontend widzi tylko target_ac → karta pokazuje 'vs AC' mimo
że trafienie liczyło się przez rzut uniku.

Testy (bez DB) oparte na czystym helperze _enemy_attack_narrative_dict.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.combat_service import _enemy_attack_narrative_dict  # noqa: E402


# ─── Test główny: pasywny unik wpisany do narrative ───────────────────────────

def test_narrative_includes_player_evasion_when_passive_evasion():
    """Pasywny unik (brak reakcji) → narrative musi mieć player_evasion z pełnym rozbiorem."""
    evasion = {"raw": 13, "dex_mod": 3, "total": 16}
    out = {"player_evasion": evasion}
    result = _enemy_attack_narrative_dict(
        out=out, raw=8, attack_roll=14, pac=11,
        enemy={"name": "Golem Kamienny"}, atk_b=6,
    )
    assert "player_evasion" in result, (
        "narrative brakuje player_evasion — frontend nie może pokazać rzutu uniku zamiast AC"
    )
    assert result["player_evasion"]["total"] == 16
    assert result["player_evasion"]["raw"] == 13
    assert result["player_evasion"]["dex_mod"] == 3


def test_narrative_includes_attack_bonus():
    """Narrative musi mieć attack_bonus żeby UI mogło pokazać pełne równanie d20+bonus=total."""
    out = {"player_evasion": {"raw": 10, "dex_mod": 2, "total": 12}}
    result = _enemy_attack_narrative_dict(
        out=out, raw=15, attack_roll=21, pac=11,
        enemy={"enemy_key": "skeleton"}, atk_b=6,
    )
    assert "attack_bonus" in result
    assert result["attack_bonus"] == 6


def test_narrative_always_has_target_ac_for_damage_reduction_context():
    """target_ac nadal w narrative (potrzebny do opisu redukcji pancerza, nie trafienia)."""
    out = {"player_evasion": {"raw": 5, "dex_mod": 1, "total": 6}}
    result = _enemy_attack_narrative_dict(
        out=out, raw=12, attack_roll=18, pac=14,
        enemy={"name": "Rycerz"}, atk_b=4,
    )
    assert result["target_ac"] == 14


# ─── Backward compat: okno reakcji — brak player_evasion w narrative ─────────

def test_narrative_no_player_evasion_when_reaction_window():
    """Okno reakcji (out bez player_evasion) → narrative ma player_evasion=None lub go brak."""
    out = {}  # brak player_evasion — bo gracz miał dostępną reakcję
    result = _enemy_attack_narrative_dict(
        out=out, raw=18, attack_roll=24, pac=11,
        enemy={"name": "Szkielet"}, atk_b=3,
    )
    # player_evasion może być None lub nieobecne — ale nie może być dict z total
    pev = result.get("player_evasion")
    assert pev is None or pev == {}, (
        "okno reakcji: player_evasion nie powinno zawierać rzutu (nie było rzutu)"
    )


def test_narrative_enemy_name_fallback_to_enemy_key():
    """Wróg bez 'name' → fallback do 'enemy_key'."""
    out = {}
    result = _enemy_attack_narrative_dict(
        out=out, raw=5, attack_roll=8, pac=11,
        enemy={"enemy_key": "rat"}, atk_b=0,
    )
    assert result["enemy_name"] == "rat"
