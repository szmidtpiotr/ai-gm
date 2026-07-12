"""#1313 — wpięcie death-save DC ladder do żywego przepływu 0 HP.

Testuje helper `_apply_death_save_ladder`, który zamienia natychmiastową
nieprzytomność na rzut drabiny (rosnące DC). Liczniki żyją na combatancie (`p`)
→ per-postać, MP-safe. Pure d20 wstrzykiwany przez `d20=` (bez losowości).
"""
import app.services.combat_service as cs


def test_ladder_increments_count_and_escalates_dc():
    p = {"death_save_count": 0, "death_failures": 0}
    out = {}
    r1 = cs._apply_death_save_ladder(p, out, d20=10)  # 1. padnięcie → DC 10
    assert r1["death_save_count"] == 1
    assert r1["dc"] == 10
    assert p["death_save_count"] == 1
    assert out["death_save"] is r1

    r2 = cs._apply_death_save_ladder(p, out, d20=13)  # 2. padnięcie → DC 13
    assert r2["death_save_count"] == 2
    assert r2["dc"] == 13
    assert p["death_save_count"] == 2


def test_survive_leaves_player_alive_no_failure():
    p = {"death_save_count": 0, "death_failures": 0}
    r = cs._apply_death_save_ladder(p, {}, d20=15)  # DC 10 → sukces
    assert r["success"] is True
    assert r["dead"] is False
    assert p["death_failures"] == 0
    assert r["hp_restored"] == 1


def test_plain_fail_records_failure_but_not_dead():
    p = {"death_save_count": 0, "death_failures": 0}
    r = cs._apply_death_save_ladder(p, {}, d20=3)  # DC 10 → porażka
    assert r["success"] is False
    assert r["dead"] is False           # 1 porażka < 3 → gracz „dying", zostaje na 1 HP
    assert p["death_failures"] == 1


def test_three_failures_kills():
    p = {"death_save_count": 0, "death_failures": 0}
    cs._apply_death_save_ladder(p, {}, d20=2)   # fail #1
    cs._apply_death_save_ladder(p, {}, d20=2)   # fail #2
    r3 = cs._apply_death_save_ladder(p, {}, d20=2)  # fail #3 → śmierć
    assert p["death_failures"] == 3
    assert r3["dead"] is True
    assert r3["outcome"] == "DEAD"


def test_nat1_two_failures_then_dead():
    p = {"death_save_count": 0, "death_failures": 0}
    cs._apply_death_save_ladder(p, {}, d20=2)    # fail #1
    r = cs._apply_death_save_ladder(p, {}, d20=1)  # Nat 1 → +2 → 3 porażki → śmierć
    assert r["nat1"] is True
    assert p["death_failures"] == 3
    assert r["dead"] is True


def test_nat20_survives_regardless_of_dc():
    p = {"death_save_count": 4, "death_failures": 2}  # DC 19, na krawędzi
    r = cs._apply_death_save_ladder(p, {}, d20=20)
    assert r["nat20"] is True
    assert r["success"] is True
    assert r["dead"] is False
    assert p["death_failures"] == 2   # sukces nie dodaje porażki


def test_mp_counters_are_per_combatant():
    p1 = {"death_save_count": 0, "death_failures": 0}
    p2 = {"death_save_count": 0, "death_failures": 0}
    cs._apply_death_save_ladder(p1, {}, d20=2)  # p1 pada
    cs._apply_death_save_ladder(p1, {}, d20=2)  # p1 pada znów
    cs._apply_death_save_ladder(p2, {}, d20=15)  # p2 przeżywa
    assert p1["death_save_count"] == 2
    assert p1["death_failures"] == 2
    assert p2["death_save_count"] == 1   # niezależny licznik
    assert p2["death_failures"] == 0
