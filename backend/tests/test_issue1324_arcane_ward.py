"""TDD: Issue #1324 — Arkanowa Bariera (arcane_ward): reakcja instant maga w oknie SF10.

Odpowiednik Uniku: test d20+INT+rank+prof vs attack_roll, koszt 1 mana/próba (schodzi
ZAWSZE, niezależnie od wyniku), sukces = 0 obrażeń, krytyczna porażka = lockout następnej
rundy. Gate: skill `arcane_ward` rank ≥ 1 ORAZ current_mana ≥ koszt. Limity parytet #1322.
"""
import importlib

import pytest

cs = importlib.import_module("app.services.combat_service")


# ─── Helper _try_arcane_ward_reaction ────────────────────────────────────────

def _mk(mana=10, rank=1, declared="arcane_ward"):
    """Combatant gracza + sheet ze skillem arcane_ward i pulą many."""
    p = {"id": "player", "hp_current": 20, "stats": {"INT": 14}}
    if declared:
        p["reaction_declared"] = declared
    sheet = {"stats": {"INT": 14}, "skills": {"arcane_ward": rank}, "current_mana": mana}
    return p, sheet


def test_arcane_ward_success_negates_damage_and_spends_mana(monkeypatch):
    """Sukces testu INT → 0 obrażeń, mana −1 (koszt startowy)."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 20)  # wysoki rzut → pewny sukces
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_arcane_ward_reaction(p, sheet, attack_roll=12, round_n=1)
    assert res is not None and res.get("available") is True
    assert res.get("warded") is True
    assert int(sheet["current_mana"]) == 9  # koszt 1 many


def test_arcane_ward_failure_spends_mana_anyway(monkeypatch):
    """Porażka testu → NIE warded (pełne obrażenia dalej), mana i tak −1 (hazard)."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 1)  # niski rzut → porażka
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_arcane_ward_reaction(p, sheet, attack_roll=25, round_n=1)
    assert res is not None and res.get("available") is True
    assert res.get("warded") is False
    assert int(sheet["current_mana"]) == 9  # mana schodzi mimo porażki


def test_arcane_ward_critical_failure_locks_next_round(monkeypatch):
    """Krytyczna porażka (margines ≤ −5) → reaction_locked_round = round + 1 (parytet Uniku)."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 1)
    p, sheet = _mk(mana=10, rank=1)
    cs._try_arcane_ward_reaction(p, sheet, attack_roll=30, round_n=2)
    assert int(p.get("reaction_locked_round") or 0) == 3


def test_arcane_ward_no_mana_unavailable(monkeypatch):
    """0 many → reakcja niedostępna (available=False), pula nie schodzi poniżej zera."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 20)
    p, sheet = _mk(mana=0, rank=1)
    res = cs._try_arcane_ward_reaction(p, sheet, attack_roll=12, round_n=1)
    assert res is None or res.get("available") is False
    assert int(sheet["current_mana"]) == 0


def test_arcane_ward_no_skill_returns_none(monkeypatch):
    """Brak skilla arcane_ward → helper zwraca None (nie ma reakcji), mana nietknięta."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 20)
    p, sheet = _mk(mana=10, rank=0)
    res = cs._try_arcane_ward_reaction(p, sheet, attack_roll=12, round_n=1)
    assert res is None
    assert int(sheet["current_mana"]) == 10


# ─── _reaction_options gate ──────────────────────────────────────────────────

def test_reaction_options_includes_arcane_ward_when_skill_and_mana(monkeypatch):
    """Okno reakcji pokazuje 'arcane_ward' gdy skill ≥ 1 i mana ≥ koszt."""
    p = {"id": "player"}
    sheet = {"skills": {"arcane_ward": 1}, "current_mana": 5}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "arcane_ward" in opts


def test_reaction_options_excludes_arcane_ward_without_mana():
    """Brak many → 'arcane_ward' nie pojawia się w oknie."""
    p = {"id": "player"}
    sheet = {"skills": {"arcane_ward": 1}, "current_mana": 0}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "arcane_ward" not in opts


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_dodge_reaction_still_works(monkeypatch):
    """Stara reakcja uniku działa bez zmian (nie zepsuliśmy toru DEX)."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 20)
    p = {"id": "player", "reaction_declared": "dodge", "stats": {"DEX": 14}}
    sheet = {"stats": {"DEX": 14}, "skills": {"dodge": 1}}
    res = cs._try_dodge_reaction(p, sheet, attack_roll=12, round_n=1)
    assert res is not None and res.get("dodged") is True


def test_reaction_options_warrior_no_ward():
    """Wojownik bez skilla arcane_ward nie widzi bariery w oknie."""
    p = {"id": "player"}
    sheet = {"skills": {"dodge": 1}, "current_mana": 0}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "arcane_ward" not in opts
    assert "dodge" in opts
