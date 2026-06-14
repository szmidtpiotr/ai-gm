"""TDD: Issue #616 — hazard musi deterministycznie odpalać mechanikę stawki.

Bug (smoke-defect FAZA S #615): w swobodnej grze gracz deklaruje "stawiam 10 złota
i gram w kości", ale silnik nigdy nie rusza złotem, bo intencja hazardu nie dociera
do toru [GAMBLE] (pre-LLM skaner/U7 zżera turę generycznym testem). Fix: czysty,
deterministyczny detektor intencji hazardu ze stawką, który pozwala zsyntetyzować
tag [GAMBLE:<stawka>:DC:<n>] zanim cokolwiek zżre turę.

Detektor jest aktor-/silnik-agnostyczny i czysty (bez DB) — to RED/GREEN tej zmiany.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.skill_service import GAMBLE_RE, detect_gamble_intent


# ─── Test główny — wykrycie stawki z deklaracji hazardu ──────────────────────

def test_detect_gamble_intent_extracts_stake():
    """Gracz deklaruje grę w kości + kwotę → detektor zwraca stawkę (int gp)."""
    assert detect_gamble_intent("Siadam przy stole, stawiam 10 sztuk złota i gram w kości.") == 10


def test_detect_gamble_intent_various_phrasings():
    """Różne sformułowania hazardu ze stawką → poprawna kwota."""
    assert detect_gamble_intent("Obstawiam 25 złota w grze w kości.") == 25
    assert detect_gamble_intent("Zakładam się o 5 monet, rzucam kośćmi.") == 5
    assert detect_gamble_intent("Gram w kości o 100 gp.") == 100


# ─── Brak stawki → narracja, NIE auto-test (zgodnie z #616: brak stawki = brak karty) ──

def test_detect_gamble_intent_no_stake_returns_none():
    """Hazard bez podanej kwoty → None (mechanika nie zgaduje stawki; LLM narruje)."""
    assert detect_gamble_intent("Gram w kości z najemnikami.") is None


# ─── Backward compat / brak fałszywych trafień ───────────────────────────────

def test_detect_gamble_intent_non_gambling_returns_none():
    """Tekst niezwiązany z hazardem (nawet z liczbą złota) → None."""
    assert detect_gamble_intent("Idę do wioski tropiąc świeże ślady.") is None
    assert detect_gamble_intent("Kupuję miecz za 50 złota u kowala.") is None
    assert detect_gamble_intent("Wchodzę do kościoła i zapalam świecę za 3 złote.") is None


def test_detect_gamble_intent_empty():
    """Pusty/None tekst → None (bez wyjątku)."""
    assert detect_gamble_intent("") is None
    assert detect_gamble_intent(None) is None


# ─── Most intent→tag: zsyntetyzowany tag jest parsowalny przez istniejący tor S7 ──

def test_synthesized_gamble_tag_is_parseable_by_s7_path():
    """Stawka z detektora → [GAMBLE:<stawka>:DC:12] pasuje do GAMBLE_RE (tor S7)."""
    stake = detect_gamble_intent("Stawiam 10 złota i gram w kości.")
    synth = f"[GAMBLE:{stake}:DC:12]"
    m = GAMBLE_RE.search(synth)
    assert m is not None
    assert int(m.group(1)) == 10
    assert m.group(2).upper() == "DC"
