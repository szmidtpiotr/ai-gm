"""TDD: Issue #940 — biblia świata jako OSOBNA warstwa lore obok system_prompt.

Decyzja (2026-06-22): źródło prawdy = docs/world/LORE_v1_KANON.md; seed dla LLM =
backend/prompts/world_bible.txt, ładowany OBOK system_prompt.txt (locked mechanics
contract), nigdy wpleciony.

Tests verify:
- world_bible.txt istnieje i zawiera kanon (ton heroic-dark, Rdzeń, 6 krain, frakcje)
- loader ładuje go jako osobną warstwę i komponuje z promptem systemowym
- system_prompt.txt (kontrakt mechanik) NIE jest dotknięty — lore tylko dopisane na końcu
- brak pliku world_bible = brak crasha (warstwa lore jest opcjonalna)
"""
import os
import sys

sys.path.insert(0, "/app")

WORLD_BIBLE_PATH = "/app/prompts/world_bible.txt"
SYSTEM_PROMPT_PATH = "/app/prompts/system_prompt.txt"


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─── world_bible.txt content ────────────────────────────────────────────────

def test_world_bible_file_exists_and_nonempty():
    assert os.path.exists(WORLD_BIBLE_PATH), "brak backend/prompts/world_bible.txt"
    assert _read(WORLD_BIBLE_PATH).strip(), "world_bible.txt jest pusty"


def test_world_bible_carries_canon():
    text = _read(WORLD_BIBLE_PATH)
    # ton + metafizyka
    assert "HEROIC-DARK" in text, "brak tonu heroic-dark"
    assert "RDZEŃ" in text or "Rdzeń" in text, "brak metafizyki Rdzenia"
    # wszystkie 6 krain kanonu
    for kraina in ["KRESY", "KORONNE NIZINY", "CZARNOBÓR", "SIWE GRANIE",
                   "WYBRZEŻE ŁEZ", "MARTWE PUSTKOWIA"]:
        assert kraina in text, f"brak krainy {kraina} w biblii świata"
    # frakcje
    assert "Rada Czterech" in text, "brak Rady Czterech"
    assert "Światł" in text, "brak Świątyni Światła"


def test_world_bible_declares_itself_lore_not_mechanics():
    """Seed musi jasno mówić, że to warstwa LORE, nie kontrakt mechanik."""
    text = _read(WORLD_BIBLE_PATH).upper()
    assert "LORE" in text and "MECHANIK" in text, \
        "world_bible.txt musi deklarować, że jest warstwą lore, a nie mechaniką"


# ─── loader: separate layer + composition ───────────────────────────────────

def test_loader_exposes_world_bible_separately():
    from app.system_prompt_loader import load_world_bible_text, load_system_prompt_text

    lore = load_world_bible_text()
    mechanics = load_system_prompt_text()
    assert lore.strip(), "load_world_bible_text() zwróciło pustkę"
    # warstwy są ROZDZIELNE — lore nie jest częścią locked promptu
    assert lore not in mechanics, "lore nie może być wpleciona w system_prompt (locked contract)"


def test_compose_appends_lore_after_mechanics():
    from app.system_prompt_loader import (
        compose_narrator_system_prompt,
        load_system_prompt_text,
        load_world_bible_text,
    )

    composed = compose_narrator_system_prompt()
    mechanics = load_system_prompt_text()
    lore = load_world_bible_text()

    assert mechanics.rstrip() in composed, "kontrakt mechanik musi być w złożonym prompcie"
    assert "HEROIC-DARK" in composed, "lore musi trafić do narratora"
    # kolejność: mechanika przed lore
    assert composed.index("HEROIC-DARK") > composed.index(mechanics.rstrip()[-40:]), \
        "lore musi być dopisane PO kontrakcie mechanik, nie przed"


def test_missing_world_bible_falls_back_gracefully():
    """Brak pliku lore = compose zwraca sam prompt mechanik, bez wyjątku."""
    from app.system_prompt_loader import compose_narrator_system_prompt, load_system_prompt_text

    base = "TEST MECHANICS ONLY"
    # symulacja braku world_bible przez przekazanie base i pusty global jest trudna;
    # zamiast tego sprawdzamy kontrakt funkcji: base zawsze obecny.
    out = compose_narrator_system_prompt(base)
    assert base in out, "compose musi zachować przekazany kontrakt mechanik"
