"""TDD: Issue #535 — HF-6: Gate ATTACK regex catches negation 'nic nie atakuję'."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def _classify(text: str) -> str:
    from app.services.gate_service import classify_intent_stub
    return classify_intent_stub(text)["action_type"]


# ─── Tests: negation bypass (must FAIL before fix) ───────────────────────────

def test_nie_atakuje_not_classified_as_attack():
    """'nic nie atakuję' must NOT be ATTACK."""
    result = _classify("Wchodzę do gospody i szukam Marty. Nic nie atakuję.")
    assert result != "ATTACK", f"Expected not ATTACK, got {result!r}"


def test_nie_atakuje_nikogo_not_attack():
    """'nie atakuję nikogo' must NOT be ATTACK."""
    result = _classify("Nie atakuję nikogo, tylko obserwuję okolicę.")
    assert result != "ATTACK", f"Expected not ATTACK, got {result!r}"


def test_nie_walcze_not_attack():
    """'Nie walczę z nimi' must NOT be ATTACK."""
    result = _classify("Nie walczę z nimi, chcę porozmawiać.")
    assert result != "ATTACK", f"Expected not ATTACK, got {result!r}"


def test_nie_strzelam_not_attack():
    """'nie strzelam' must NOT be ATTACK."""
    result = _classify("Uspokajam się, nie strzelam do goblina.")
    assert result != "ATTACK", f"Expected not ATTACK, got {result!r}"


# ─── Tests: positive cases (must still work after fix) ───────────────────────

def test_atakuje_goblina_is_attack():
    """'atakuję goblina' must remain ATTACK."""
    result = _classify("Atakuję goblina mieczem!")
    assert result == "ATTACK", f"Expected ATTACK, got {result!r}"


def test_uderz_go_is_attack():
    """'uderz go' must remain ATTACK."""
    result = _classify("Uderz go w głowę!")
    assert result == "ATTACK", f"Expected ATTACK, got {result!r}"


def test_strzelam_do_celu_is_attack():
    """'strzelam do celu' must remain ATTACK."""
    result = _classify("Strzelam do celu z łuku.")
    assert result == "ATTACK", f"Expected ATTACK, got {result!r}"


def test_walcze_is_attack():
    """'walczę' without negation must remain ATTACK."""
    result = _classify("Walczę z orkiem całą siłą.")
    assert result == "ATTACK", f"Expected ATTACK, got {result!r}"
