"""TDD: Issue #978 — Narrator system prompt awareness of character race."""
import sys
sys.path.insert(0, "/app")


def test_system_prompt_contains_race_section():
    """system_prompt.txt ma sekcję RASY BOHATERÓW."""
    from app.system_prompt_loader import load_system_prompt_text
    text = load_system_prompt_text()
    assert "RASY BOHATERÓW" in text, "Brak sekcji RASY BOHATERÓW w system_prompt.txt"
    assert "rdzen_miscast" in text.lower() or "RDZEŃ-MAGIA" in text, "Brak opisu rdzen_miscast"


def test_system_prompt_contains_dwarf_npc_reactions():
    """system_prompt.txt opisuje reakcje NPC na krasnoluda."""
    from app.system_prompt_loader import load_system_prompt_text
    text = load_system_prompt_text()
    assert "krasnolud" in text.lower() or "Krasnolud" in text, "Brak wzmianki o krasnoludach"


def test_buildmessages_injects_race_human():
    """buildmessages dodaje 'Rasa postaci: human' do systemu gdy race=human."""
    import sqlite3
    from unittest.mock import MagicMock
    from app.core.turn_engine import buildmessages

    character = MagicMock()
    character.__getitem__ = lambda self, key: {"name": "Aldric", "race": "human"}.get(key, None)
    campaign = MagicMock()
    campaign.__getitem__ = lambda self, key: {"system_id": "fantasy", "language": "pl"}.get(key, "")

    msgs = buildmessages(campaign=campaign, character=character, recentturns=[], usertext="test")
    system_msg = msgs[0]["content"]
    assert "Rasa postaci: human" in system_msg, f"Brak rasy w system msg. Got: {system_msg[-200:]}"


def test_buildmessages_injects_race_dwarf():
    """buildmessages dodaje 'Rasa postaci: dwarf' dla krasnoluda."""
    from unittest.mock import MagicMock
    from app.core.turn_engine import buildmessages

    character = MagicMock()
    character.__getitem__ = lambda self, key: {"name": "Durgrim", "race": "dwarf"}.get(key, None)
    campaign = MagicMock()
    campaign.__getitem__ = lambda self, key: {"system_id": "fantasy", "language": "pl"}.get(key, "")

    msgs = buildmessages(campaign=campaign, character=character, recentturns=[], usertext="test")
    system_msg = msgs[0]["content"]
    assert "Rasa postaci: dwarf" in system_msg, f"Brak rasy w system msg. Got: {system_msg[-200:]}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_buildmessages_race_fallback_when_no_race_key():
    """buildmessages nie crashuje gdy character nie ma pola race (legacy)."""
    from unittest.mock import MagicMock
    from app.core.turn_engine import buildmessages

    character = MagicMock()
    character.__getitem__ = MagicMock(side_effect=lambda key: {"name": "Legacy"}.get(key, None) if key != "race" else (_ for _ in ()).throw(KeyError("race")))
    campaign = MagicMock()
    campaign.__getitem__ = lambda self, key: {"system_id": "fantasy", "language": "pl"}.get(key, "")

    # Should not raise
    msgs = buildmessages(campaign=campaign, character=character, recentturns=[], usertext="test")
    system_msg = msgs[0]["content"]
    assert "Rasa postaci:" in system_msg
