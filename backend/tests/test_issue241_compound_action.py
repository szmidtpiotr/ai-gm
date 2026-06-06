"""TDD: Issue #241 — Compound action must not be collapsed to single skill roll.

Bug: pre-LLM keyword scanner in turns.py fires on first skill keyword found,
returns skill_test_keyword route immediately, LLM never sees NPC dialogue / travel.

Fix: add _is_compound_action() detector. If text combines dialogue/movement AND
a skill keyword, the scanner must be bypassed — let LLM handle the full compound turn.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Test główny — compound detector must exist and classify correctly ────────

def test_compound_action_detector_exists():
    """_is_compound_action must be importable from turns module."""
    from app.api.turns import _is_compound_action  # noqa: F401


def test_compound_action_with_dialogue_and_skill_detected():
    """Text with NPC speech + skill keyword = compound → should bypass scanner."""
    from app.api.turns import _is_compound_action

    compound_texts = [
        "Mówię Marcie że wychodzę i rozglądam się po okolicy",
        "pytam karczmarza o drogę i rozglądam się uważnie",
        "powiedziałem że idę szukać Ravana, wychodzę z karczmy i rozglądam się",
        "Podchodzę do Marty, pytam ją o tabakę, potem wychodzę i oglądam okolicę",
    ]
    for text in compound_texts:
        assert _is_compound_action(text), (
            f"Expected compound detection for: {text!r}"
        )


def test_simple_skill_action_not_compound():
    """Single-intent skill action is NOT compound — scanner should still fire."""
    from app.api.turns import _is_compound_action

    simple_texts = [
        "Rozglądam się uważnie",
        "oglądam okolicę",
        "nasłuchuję czy ktoś idzie",
        "sprawdzam drzwi",
    ]
    for text in simple_texts:
        assert not _is_compound_action(text), (
            f"Expected non-compound for simple action: {text!r}"
        )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_question_still_not_action_attempt():
    """Questions must still bypass scanner (existing behavior unchanged)."""
    from app.api.turns import _text_is_action_attempt

    assert not _text_is_action_attempt("Czy mogę tutaj odpocząć?")
    assert not _text_is_action_attempt("Co tu jest?")


def test_single_skill_text_is_action_attempt():
    """Simple non-question action still passes as action attempt."""
    from app.api.turns import _text_is_action_attempt

    assert _text_is_action_attempt("Rozglądam się uważnie")
    assert _text_is_action_attempt("Nasłuchuję dźwięków z piwnicy")
