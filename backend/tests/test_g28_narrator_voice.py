"""TDD: Issue #809 G28 — narrator voice consistency rules in MP system prompt."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from services.multiplayer_round_service import _MULTIPLAYER_SYSTEM_PROMPT


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_prompt_has_voice_consistency_section():
    """G28: prompt must contain the SPÓJNOŚĆ GŁOSU NARRATORA section header."""
    assert "SPÓJNOŚĆ GŁOSU NARRATORA" in _MULTIPLAYER_SYSTEM_PROMPT, (
        "G28 section header missing from _MULTIPLAYER_SYSTEM_PROMPT"
    )


def test_prompt_gm_voice_independent_of_player_style():
    """G28: prompt must state GM voice is independent of player input style."""
    # At least one of these phrasings must be present
    markers = [
        "rejestr",           # register/register-of-language
        "styl wejść",        # style of inputs
        "INTENCJĘ",          # INTENT marker
        "niezależnie od stylu",
    ]
    found = any(m in _MULTIPLAYER_SYSTEM_PROMPT for m in markers)
    assert found, (
        "G28: no rule found that GM voice is independent of player input style. "
        f"Checked markers: {markers}"
    )


def test_prompt_no_copy_player_slang():
    """G28: prompt must explicitly forbid copying player slang/typos into narration."""
    markers = [
        "slangu",
        "slang",
        "nie kopiuj",
        "nie przenoś",
        "surowiec",
    ]
    found = any(m in _MULTIPLAYER_SYSTEM_PROMPT for m in markers)
    assert found, (
        "G28: no rule found against copying player slang/typos into narration. "
        f"Checked markers: {markers}"
    )


def test_prompt_screen_time_equalization():
    """G28: prompt must equalize screen time regardless of input length."""
    markers = [
        "udział ekranowy",
        "ekranowy",
        "krótki wpis",
        "porównywalną wagę",
        "porównywalny",
    ]
    found = any(m in _MULTIPLAYER_SYSTEM_PROMPT for m in markers)
    assert found, (
        "G28: no screen-time equalization rule found. "
        f"Checked markers: {markers}"
    )


def test_prompt_consistent_world_terminology():
    """G28: prompt must require consistent world terminology across rounds."""
    markers = [
        "terminologi",        # "terminologia" / "terminologii"
        "spójna terminologi",
        "nazwy lokacji",
        "World State",
        "nazwy miejsc",
    ]
    found = any(m in _MULTIPLAYER_SYSTEM_PROMPT for m in markers)
    assert found, (
        "G28: no consistent world terminology rule found. "
        f"Checked markers: {markers}"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_existing_sections_still_present():
    """Existing MP prompt sections must not be removed by G28 edit."""
    required_sections = [
        "NARRACJA W TRZECIEJ OSOBIE",
        "JEDNOCZESNOŚĆ AKCJI",
        "INICJATYWA I KOLEJNOŚĆ ROZSTRZYGANIA",
        "FORMAT ODPOWIEDZI",
        "STYL",
    ]
    for section in required_sections:
        assert section in _MULTIPLAYER_SYSTEM_PROMPT, (
            f"Existing section '{section}' disappeared from prompt after G28 edit"
        )
