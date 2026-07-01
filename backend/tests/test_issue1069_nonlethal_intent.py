"""TDD: Issue #1069 — non-lethal intent detection (intimidate / capture / stun)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from api.turns import _subdue_intent, _intimidate_intent


# ─── _intimidate_intent — new function ───────────────────────────────────────

def test_intimidate_intent_zastrasz():
    """'zastraszam strażnika' — intimidate keyword detected."""
    assert _intimidate_intent("Zastraszam strażnika") is True


def test_intimidate_intent_groza_nozem():
    """'grożę mu nożem' — threat with weapon detected."""
    assert _intimidate_intent("Grożę mu nożem żeby się poddał") is True


def test_intimidate_intent_noz_do_gardla():
    """'przykładam nóż do gardła' — knife-to-throat gesture detected."""
    assert _intimidate_intent("Przykładam nóż do jego gardła") is True


def test_intimidate_intent_wez_zywcem():
    """'wziąć żywcem' — take-alive intent detected."""
    assert _intimidate_intent("Chcę go wziąć żywcem") is True


def test_intimidate_intent_pojmaj():
    """'pojmaj go' — capture intent detected."""
    assert _intimidate_intent("Pojmaj go, potrzebuję jeńca") is True


def test_intimidate_intent_negation_nie_zastraszam():
    """'nie zastraszam' — negated intimidate should return False."""
    assert _intimidate_intent("Nie zastraszam go, po prostu patrzę") is False


def test_intimidate_intent_normal_attack_no_hit():
    """Normal lethal attack text should NOT trigger intimidate intent."""
    assert _intimidate_intent("Atakuję go mieczem") is False


def test_intimidate_intent_dialogue_no_hit():
    """Dialogue text should NOT trigger intimidate intent."""
    assert _intimidate_intent("Rozmawiam z kupcem o towarach") is False


# ─── _subdue_intent expanded — ogłusz ────────────────────────────────────────

def test_subdue_intent_ogłusz():
    """'ogłusz go' — stun-intent now routes through subdue gate (#1069)."""
    assert _subdue_intent("Ogłusz go, nie chcę go zabijać") is True


def test_subdue_intent_ogłusz_variant():
    """'ogłuszam' conjugation also detected."""
    assert _subdue_intent("Ogłuszam wartownika od tyłu") is True


# ─── backward compat — existing subdue words unchanged ───────────────────────

def test_subdue_intent_obezwladniam_still_works():
    assert _subdue_intent("Obezwładniam go") is True


def test_subdue_intent_chwytam_still_works():
    assert _subdue_intent("Chwytam go za ramiona") is True


def test_subdue_intent_negation_still_works():
    assert _subdue_intent("Nie obezwładniam go") is False
