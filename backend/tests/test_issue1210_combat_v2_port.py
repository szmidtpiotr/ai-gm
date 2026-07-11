"""TDD: Issue #1210 — port 4 mechanik walki z prototypu combat_v2_service.py
do żywej combat_service.py (model #826).

Mechaniki (warstwa deterministyczna — silnik decyduje, LLM narruje):
1. Strach/Groza  — resolve_fear_outcome (3-stopniowa eskalacja)
2. Hit-location  — crit_location_from_d6 + crit_condition_for_location
3. Death-save DC ladder — get_death_save_dc + resolve_death_save_outcome
4. Flee opposed DEX — resolve_flee_outcome + flee_penalty_from_conditions
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import combat_service as cs  # noqa: E402


# ─── 3. Death-save DC ladder ─────────────────────────────────────────────────

def test_death_save_dc_ladder_progression():
    """Kolejne padnięcie na 0 HP w tej samej walce → rosnące DC 10/13/16/19."""
    assert cs.get_death_save_dc(1) == 10
    assert cs.get_death_save_dc(2) == 13
    assert cs.get_death_save_dc(3) == 16
    assert cs.get_death_save_dc(4) == 19


def test_death_save_dc_ladder_caps_at_last_rung():
    """Po wyczerpaniu drabiny DC zostaje na maksimum (19), nie rośnie dalej ani nie crashuje."""
    assert cs.get_death_save_dc(5) == 19
    assert cs.get_death_save_dc(99) == 19
    # count < 1 nie może wyjść poza pierwszy szczebel
    assert cs.get_death_save_dc(0) == 10


def test_death_save_outcome_success_restores():
    """d20 >= DC → SURVIVED, brak dodanych porażek."""
    out = cs.resolve_death_save_outcome(d20=15, dc=13, current_failures=0)
    assert out["success"] is True
    assert out["outcome"] == "SURVIVED"
    assert out["failures_added"] == 0
    assert out["dead"] is False


def test_death_save_outcome_nat1_adds_two_failures():
    """Nat 1 = auto-porażka warta 2 porażki (śmierć przy 3)."""
    out = cs.resolve_death_save_outcome(d20=1, dc=10, current_failures=1)
    assert out["success"] is False
    assert out["failures_added"] == 2
    assert out["total_failures"] == 3
    assert out["dead"] is True
    assert out["outcome"] == "DEAD"


def test_death_save_outcome_nat20_survives_below_dc():
    """Nat 20 zawsze ratuje, nawet gdy DC wyższe niż 20."""
    out = cs.resolve_death_save_outcome(d20=20, dc=19, current_failures=2)
    assert out["success"] is True
    assert out["dead"] is False


def test_death_save_outcome_plain_fail_one_failure():
    """Zwykła porażka (nie Nat1) dodaje 1 porażkę; 3. porażka = śmierć."""
    out = cs.resolve_death_save_outcome(d20=5, dc=16, current_failures=2)
    assert out["success"] is False
    assert out["failures_added"] == 1
    assert out["total_failures"] == 3
    assert out["dead"] is True


# ─── 2. Hit-location (krytyk) ────────────────────────────────────────────────

def test_hit_location_table_covers_d6():
    """d6 → 6 lokacji, deterministycznie."""
    locs = {cs.crit_location_from_d6(i) for i in range(1, 7)}
    assert locs == {"head", "torso", "right_arm", "left_arm", "right_leg", "left_leg"}


def test_enemy_crit_leg_gives_hobbled():
    """Krytyk gracza w nogę wroga → hobbled (nie może uciec)."""
    cond, dur = cs.crit_condition_for_location("right_leg", on_player=False)
    assert cond == "hobbled"
    assert dur == 3


def test_player_crit_leg_gives_leg_wound():
    """Krytyk wroga w nogę gracza → leg_wound (kara do ucieczki, 3 rundy)."""
    cond, dur = cs.crit_condition_for_location("left_leg", on_player=True)
    assert cond == "leg_wound"
    assert dur == 3


def test_enemy_crit_head_stuns():
    """Krytyk gracza w głowę wroga → stunned 1 rundę."""
    cond, dur = cs.crit_condition_for_location("head", on_player=False)
    assert cond == "stunned"
    assert dur == 1


# ─── 1. Strach / Groza (3-stopniowa eskalacja) ───────────────────────────────

def test_fear_success_no_condition():
    """Zdany rzut WIS (d20 >= DC) → brak stanu strachu."""
    out = cs.resolve_fear_outcome(d20=14, dc=12, current_fear=None)
    assert out["outcome"] == "SUCCESS"
    assert out["condition"] is None


def test_fear_first_fail_frightened():
    """Pierwsza porażka bez wcześniejszego strachu → frightened."""
    out = cs.resolve_fear_outcome(d20=5, dc=12, current_fear=None)
    assert out["outcome"] == "FAILURE"
    assert out["condition"] == "frightened"


def test_fear_escalates_frightened_to_panicked():
    """Porażka gdy już frightened → panicked (drugi stopień)."""
    out = cs.resolve_fear_outcome(d20=5, dc=12, current_fear="frightened")
    assert out["condition"] == "panicked"


def test_fear_escalates_panicked_to_break():
    """Porażka gdy już panicked → break (trzeci, najwyższy stopień)."""
    out = cs.resolve_fear_outcome(d20=5, dc=12, current_fear="panicked")
    assert out["condition"] == "break"


def test_fear_nat1_double_escalates():
    """Nat 1 przeskakuje dwa stopnie: brak → panicked."""
    out = cs.resolve_fear_outcome(d20=1, dc=12, current_fear=None)
    assert out["outcome"] == "FAILURE"
    assert out["condition"] == "panicked"


def test_fear_nat20_always_succeeds():
    """Nat 20 zdaje nawet przy bardzo wysokim DC."""
    out = cs.resolve_fear_outcome(d20=20, dc=25, current_fear="frightened")
    assert out["outcome"] == "SUCCESS"
    assert out["condition"] is None


# ─── 4. Flee (opposed DEX + modyfikacja warunkami) ───────────────────────────

def test_flee_success_when_player_beats_enemy():
    """Wyższy rzut gracza → ucieczka."""
    out = cs.resolve_flee_outcome(player_total=18, enemy_total=12)
    assert out["fled"] is True
    assert out["outcome"] == "SUCCESS"


def test_flee_tie_goes_to_enemy():
    """Remis przegrywa gracz (obrońca wygrywa remis) — brak ucieczki."""
    out = cs.resolve_flee_outcome(player_total=12, enemy_total=12)
    assert out["fled"] is False


def test_flee_penalty_leg_wound():
    """leg_wound → -2 do rzutu na ucieczkę, nie blokuje."""
    penalty, blocked = cs.flee_penalty_from_conditions([{"key": "leg_wound"}])
    assert penalty == -2
    assert blocked is False


def test_flee_blocked_by_hobbled():
    """hobbled → całkowicie blokuje ucieczkę."""
    penalty, blocked = cs.flee_penalty_from_conditions([{"key": "hobbled"}])
    assert blocked is True


def test_flee_no_conditions_no_penalty():
    """Brak warunków → zero kary, brak blokady."""
    penalty, blocked = cs.flee_penalty_from_conditions([])
    assert penalty == 0
    assert blocked is False


# ─── Backward compat: istniejące API #826 nietknięte ─────────────────────────

def test_existing_defense_model_unchanged():
    """Port nie rusza modelu obrony #826 — apply_defense_model działa jak wcześniej."""
    dm = cs.apply_defense_model(
        base_damage=6, attack_total=20, defense_stat=12, ignore_armor=False
    )
    assert dm["final"] >= 1
    assert "margin_bonus" in dm


def test_existing_death_ladder_constant_present():
    """Stała drabiny DC dostępna na module (Sandbox-tunable)."""
    assert cs.DEATH_SAVE_DC_LADDER == [10, 13, 16, 19]


# ─── Integracja: warunki ran krytycznych z katalogu (wymaga seedu #1210) ──────

def test_crit_condition_inplace_applies_from_catalog():
    """`_apply_crit_condition_inplace` dokłada leg_wound z katalogu do combatanta."""
    with cs._conn() as conn:
        comb = {"id": "player", "type": "player", "conditions": []}
        added = cs._apply_crit_condition_inplace(conn, comb, "leg_wound")
        assert added is True
        keys = [c.get("key") for c in comb["conditions"]]
        assert "leg_wound" in keys


def test_crit_condition_inplace_no_duplicate():
    """Ponowne nałożenie tego samego warunku nie duplikuje wpisu."""
    with cs._conn() as conn:
        comb = {"id": "e1", "type": "enemy", "conditions": []}
        assert cs._apply_crit_condition_inplace(conn, comb, "hobbled") is True
        assert cs._apply_crit_condition_inplace(conn, comb, "hobbled") is False
        assert sum(1 for c in comb["conditions"] if c.get("key") == "hobbled") == 1


def test_roll_crit_hit_location_returns_valid_condition():
    """Rzut lokacji na wrogu → jeden z warunków wroga, applied=True."""
    with cs._conn() as conn:
        enemy = {"id": "e1", "type": "enemy", "conditions": []}
        info = cs.roll_crit_hit_location(conn, enemy, on_player=False)
        assert info["location"] in cs.HIT_LOCATION_TABLE.values()
        assert info["condition"] in {"stunned", "bleeding", "disarmed", "hobbled"}
        assert info["applied"] is True


def test_seeded_wound_conditions_exist():
    """6 warunków ran (#1210) obecnych i aktywnych w katalogu."""
    with cs._conn() as conn:
        rows = conn.execute(
            "SELECT key FROM game_config_conditions WHERE is_active = 1 "
            "AND key IN ('dazed','winded','arm_wound','leg_wound','disarmed','hobbled')"
        ).fetchall()
        assert len(rows) == 6


# ─── Integracja: flee ────────────────────────────────────────────────────────

def test_resolve_player_flee_no_active_combat():
    """Ucieczka bez aktywnej walki → ok=False, no_active_combat (bez wyjątku)."""
    out = cs.resolve_player_flee(999_999_999)  # kampania bez walki
    assert out["ok"] is False
    assert out["reason"] == "no_active_combat"
