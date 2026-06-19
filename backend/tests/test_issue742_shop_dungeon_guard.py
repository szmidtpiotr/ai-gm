"""TDD: Issue #742 — open_shop blokowany w trybie dungeon + refresh inventory po zakupie."""
import sys
sys.path.insert(0, "/app")
import pytest


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_extract_grant_cues_finds_open_shop_cue():
    """extract_grant_cues poprawnie wykrywa 'Open Shop <key>' na ostatniej linii narracji."""
    from app.api.turns import extract_grant_cues
    # Format: "Open Shop <npc_key>" na OSTATNIEJ linii (bez nawiasów)
    text = "Handlarz Gren stoi przy stoisku.\nOpen Shop gren_trader"
    _, _, _, npc_key, _ = extract_grant_cues(text)
    assert npc_key is not None, "extract_grant_cues must detect 'Open Shop <key>' on last line"
    assert npc_key == "gren_trader"


# ─── Testy główne (RED przed fixem — ImportError; GREEN po fixie) ─────────────

def test_dungeon_mode_emission_blocked():
    """open_shop NIE może być emitowany gdy campaign.mode == 'dungeon'."""
    # Funkcja _should_emit_open_shop_in_mode NIE ISTNIEJE przed fixem → ImportError = RED
    from app.api.turns import _should_emit_open_shop_in_mode

    assert not _should_emit_open_shop_in_mode("merchant_001", "dungeon"), \
        "Bug: open_shop emitowany w trybie dungeon — brak guardu w turns.py"


def test_narrative_mode_emission_allowed():
    """open_shop MUSI być emitowany w trybie narracyjnym (solo/normal)."""
    from app.api.turns import _should_emit_open_shop_in_mode

    assert _should_emit_open_shop_in_mode("merchant_001", "solo"), \
        "open_shop powinien emitować się w trybie solo"

    assert _should_emit_open_shop_in_mode("merchant_001", ""), \
        "Pusty mode traktowany jak solo — open_shop powinien emitować"


def test_emission_blocked_when_no_npc_key():
    """Brak npc_key zawsze blokuje emisję niezależnie od trybu."""
    from app.api.turns import _should_emit_open_shop_in_mode

    assert not _should_emit_open_shop_in_mode(None, "solo")
    assert not _should_emit_open_shop_in_mode("", "solo")
    assert not _should_emit_open_shop_in_mode(None, "dungeon")
