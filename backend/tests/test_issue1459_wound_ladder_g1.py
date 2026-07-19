"""TDD: G1 #1459/#1458 — drabina ran WARIANT A (łagodny) + kara doliczana.

#1459: WOUND_TIERS = wariant A (kara startuje ≤25% HP, max -2, -1 DEX na skraju).
       Jedno źródło prawdy — wound_utils. (Księga + game_mechanics.md sync ręcznie.)
#1458: wound_penalty(hp_pct) doliczana do rzutu ataku gracza ORAZ do testów
       umiejętności — symetria z torem wroga (combat_service dolicza już wp).
"""
from app.services.wound_utils import (
    WOUND_TIERS,
    wound_dex_penalty,
    wound_penalty,
    wound_tier,
)
from app.services.weapon_rules import resolve_attack_roll_for_weapon
from app.services.skill_service import calc_skill_modifier_info


# ── #1459 — drabina zgodna ze specyfikacją wariantu A ─────────────────────────

def test_wound_tiers_match_spec():
    """WOUND_TIERS = wariant A łagodny (game_mechanics.md CZĘŚĆ AB + Księga).

    | HP %    | penalty | dex |
    | > 50%   |  0      |  0  |
    | 26–50%  |  0      |  0  |  (Ranny — tylko klimat)
    | 11–25%  | -1      |  0  |  (Poważnie ranny)
    | 1–10%   | -2      | -1  |  (Na skraju śmierci)
    """
    # Tabela ma dokładnie 4 tiery i pełny payload z dex_penalty.
    assert len(WOUND_TIERS) == 4
    for row in WOUND_TIERS:
        assert {"min_pct", "tier", "label", "penalty", "dex_penalty"} <= set(row)

    # Progi (EXCLUSIVE min_pct, malejąco): 50 / 25 / 10 / -1.
    assert [r["min_pct"] for r in WOUND_TIERS] == [50, 25, 10, -1]
    # Kary ATK: 0 / 0 / -1 / -2 (żadna nie sięga -4 jak w starym wariancie B).
    assert [r["penalty"] for r in WOUND_TIERS] == [0, 0, -1, -2]
    # Kara DEX tylko na skraju śmierci.
    assert [r["dex_penalty"] for r in WOUND_TIERS] == [0, 0, 0, -1]

    # Mapowanie HP% → kara (reprezentatywne punkty).
    assert wound_penalty(100, 100) == 0    # pełnia
    assert wound_penalty(60, 100) == 0     # 60% — brak kary (kluczowa różnica vs B)
    assert wound_penalty(40, 100) == 0     # 40% — Ranny, tylko klimat
    assert wound_penalty(20, 100) == -1    # 20% — Poważnie ranny
    assert wound_penalty(8, 100) == -2     # 8%  — Na skraju śmierci
    assert wound_penalty(10, 0) == 0       # guard: max_hp 0 → brak kary

    # DEX -1 wyłącznie na skraju śmierci.
    assert wound_dex_penalty(20, 100) == 0
    assert wound_dex_penalty(8, 100) == -1

    # Spójność: wound_penalty == tier['penalty'] dla każdego HP.
    for hp in (100, 80, 51, 50, 30, 25, 20, 11, 10, 5, 1):
        assert wound_penalty(hp, 100) == wound_tier(hp, 100)["penalty"]


# ── #1458 — kara za rany dolicza się do rzutu ataku gracza ────────────────────

def test_wound_penalty_applies_to_player_attack():
    """Ranny bohater trafia rzadziej — total ataku spada o wound_penalty, jako
    osobny człon (locked formuła d20+stat+skill+prof nietknięta)."""
    weapon = {"key": "sword", "label": "Miecz", "weapon_type": "melee"}
    healthy = {"stats": {"STR": 14}, "skills": {}, "conditions": [],
               "current_hp": 100, "max_hp": 100}
    wounded = {**healthy, "current_hp": 20}   # 20% HP → -1
    dying = {**healthy, "current_hp": 8}      # 8% HP  → -2

    base = resolve_attack_roll_for_weapon(healthy, raw_roll=10, weapon_row=weapon)
    w = resolve_attack_roll_for_weapon(wounded, raw_roll=10, weapon_row=weapon)
    d = resolve_attack_roll_for_weapon(dying, raw_roll=10, weapon_row=weapon)

    assert base.get("wound_penalty", 0) == 0
    assert w["wound_penalty"] == -1
    assert d["wound_penalty"] == -2
    assert w["total"] == base["total"] - 1, "total ataku musi spaść o karę za rany"
    assert d["total"] == base["total"] - 2
    # Stat modifier sam w sobie nietknięty (kara to circumstance, nie zmiana staty).
    assert w["stat_mod"] == base["stat_mod"]


# ── #1458 — kara za rany dolicza się do testów umiejętności ───────────────────

def test_wound_penalty_applies_to_skill_test():
    """Ranny bohater gorzej zdaje KAŻDY test — obok kar zmęczenia/choroby."""
    healthy = {"stats": {"DEX": 14}, "skills": {"skradanie": 2}, "conditions": [],
               "current_hp": 100, "max_hp": 100}
    wounded = {**healthy, "current_hp": 20}   # 20% → -1
    dying = {**healthy, "current_hp": 8}      # 8%  → -2

    base = calc_skill_modifier_info(healthy, "skradanie")
    w = calc_skill_modifier_info(wounded, "skradanie")
    d = calc_skill_modifier_info(dying, "skradanie")

    assert base["wound_penalty"] == 0
    assert w["wound_penalty"] == -1
    assert d["wound_penalty"] == -2
    assert w["total"] == base["total"] - 1, "suma testu musi spaść o karę za rany"
    assert d["total"] == base["total"] - 2


# ── #1458 — DEX -1 na skraju śmierci → -1 do obrony gracza (odrębny efekt) ─────

def test_wound_dex_penalty_wired_to_player_defense():
    """DEX -1 (≤10% HP) obniża obronę gracza w torze ataku wroga — odrębnie od
    kary -2 do ataku/testów. Wróg (ac_base bez DEX) nie dostaje tej kary."""
    import inspect
    import app.services.combat_service as cs

    # Drabina DEX: 0 powyżej skraju, -1 na skraju śmierci.
    assert wound_dex_penalty(100, 100) == 0
    assert wound_dex_penalty(20, 100) == 0
    assert wound_dex_penalty(8, 100) == -1
    assert wound_dex_penalty(0, 0) == 0  # guard

    # Tor ataku wroga faktycznie dolicza wound_dex_penalty do obrony gracza (pac).
    src = inspect.getsource(cs)
    assert "wound_dex_penalty" in src, "combat_service nie stosuje wound_dex_penalty"
    assert "pac += _wdex" in src, "kara DEX nie schodzi z obrony gracza (pac)"
