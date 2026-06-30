"""TDD: Issue #1038 — Adaptacyjna długość narracji (resolver B+C, słownik A, zdjęcie floora D).

Silnik wstrzykuje dyrektywę [DŁUGOŚĆ: poziom] do kontekstu narratora wg macierzy:
walka > nowa lokacja > examine > akcja > mechaniczne.
"""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/app")

from app.services.context_injector import ContextInjector


def _ci():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return ContextInjector(conn)


# ─── Test główny: resolver per-sytuacja (macierz pierwszeństwa) ───────────────

def test_combat_active_yields_walka_level():
    """Walka aktywna (combat_roster) → poziom WALKA, najwyższy priorytet (nawet w nowej lokacji)."""
    ci = _ci()
    sf = {"turns_at_location": 0, "combat_roster": [{"key": "goblin", "hp": 5}]}
    level, _ = ci._resolve_narration_length(sf, "ATTACK", {}, "atakuję goblina")
    assert level == "WALKA"


def test_new_location_yields_pelny_level():
    """turns_at_location==0 (nowa lokacja) → poziom PEŁNY (opis sensoryczny)."""
    ci = _ci()
    sf = {"turns_at_location": 0, "combat_roster": []}
    level, _ = ci._resolve_narration_length(sf, "MOVEMENT", {}, "idę do lasu")
    assert level == "PEŁNY"


def test_same_location_examine_yields_sredni_level():
    """Ta sama lokacja + intencja examine (rozejrzyj się/zbadaj) → poziom ŚREDNI."""
    ci = _ci()
    sf = {"turns_at_location": 3, "combat_roster": []}
    level, _ = ci._resolve_narration_length(sf, "EXAMINE", {}, "rozglądam się")
    assert level == "ŚREDNI"


def test_same_location_plain_action_yields_zwiezly_level():
    """Ta sama lokacja + zwykła akcja → poziom ZWIĘZŁY (bez re-opisu miejsca)."""
    ci = _ci()
    sf = {"turns_at_location": 4, "combat_roster": []}
    level, _ = ci._resolve_narration_length(sf, "DIALOGUE", {}, "pytam karczmarza o drogę")
    assert level == "ZWIĘZŁY"


def test_mechanical_action_yields_mechaniczny_level():
    """Prosta/mechaniczna akcja w znanej lokacji → poziom MECHANICZNY."""
    ci = _ci()
    sf = {"turns_at_location": 2, "combat_roster": []}
    level, _ = ci._resolve_narration_length(sf, "ITEM_PICKUP", {}, "podnoszę miecz")
    assert level == "MECHANICZNY"


def test_directive_block_emits_dlugosc_marker():
    """Blok dyrektywy zawiera marker [DŁUGOŚĆ: ...] z poziomem."""
    ci = _ci()
    sf = {"turns_at_location": 0, "combat_roster": []}
    block = ci._build_length_directive_block(sf, "MOVEMENT", {}, "idę dalej")
    assert "[DŁUGOŚĆ:" in block
    assert "PEŁNY" in block


# ─── Konfigurowalność progów (Acceptance: progi do strojenia) ────────────────

def test_levels_are_configurable():
    """Poziomy długości żyją w konfigurowalnej strukturze klasy (strojenie)."""
    assert hasattr(ContextInjector, "_NARRATION_LEVELS")
    levels = ContextInjector._NARRATION_LEVELS
    for key in ("WALKA", "PEŁNY", "ŚREDNI", "ZWIĘZŁY", "MECHANICZNY"):
        assert key in levels


# ─── D: zdjęcie twardego floora 4-6 zdań z promptu ───────────────────────────

def test_system_prompt_has_no_hard_floor():
    """system_prompt.txt nie zawiera twardego floora 'minimum 4-6 zdań'."""
    path = "/app/prompts/system_prompt.txt"
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    assert "minimum 4-6 zdań" not in txt


def test_system_prompt_has_adaptive_levels():
    """system_prompt.txt zawiera słownik poziomów (A) i marker dyrektywy [DŁUGOŚĆ]."""
    path = "/app/prompts/system_prompt.txt"
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    assert "[DŁUGOŚĆ" in txt
