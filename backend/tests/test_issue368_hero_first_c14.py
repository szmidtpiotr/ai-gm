"""TDD: Issue #368 — C14 hero-first fix.

Tests verify that handleCreateCampaign() never calls startCharacterWizard()
and that selectCampaign() redirects to heroes screen when no hero exists
instead of calling startCharacterWizard().
"""
import re
import os

APP_JS = "/tmp/app_c14_test.js"


def _read_js() -> str:
    with open(APP_JS, encoding="utf-8") as f:
        return f.read()


def _extract_function_body(src: str, func_name: str) -> str:
    """Extract the body of a JS function by brace-counting from its definition."""
    pattern = re.compile(
        r"(?:async\s+)?function\s+" + re.escape(func_name) + r"\s*\([^)]*\)\s*\{"
    )
    m = pattern.search(src)
    if not m:
        return ""
    start = m.end() - 1  # position of opening brace
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    return src[start:]


# ─── C14: handleCreateCampaign ────────────────────────────────────────────────

def test_handleCreateCampaign_does_not_call_startCharacterWizard():
    """handleCreateCampaign must NOT call startCharacterWizard() — hero already exists at this point."""
    src = _read_js()
    body = _extract_function_body(src, "handleCreateCampaign")
    assert body, "handleCreateCampaign nie znaleziono w app.js"
    assert "startCharacterWizard" not in body, (
        "handleCreateCampaign() wciąż wywołuje startCharacterWizard() — narusza model hero-first. "
        "Zamiast tego: sprawdź currentHero → jeśli istnieje, przypisz do kampanii i wejdź do gry; "
        "jeśli nie, przekieruj na ekran Bohaterowie."
    )


def test_handleCreateCampaign_handles_existing_hero():
    """handleCreateCampaign must use currentHero when available."""
    src = _read_js()
    body = _extract_function_body(src, "handleCreateCampaign")
    assert body, "handleCreateCampaign nie znaleziono w app.js"
    # After C14: should check currentHero and use enterGame / assign-campaign
    assert "currentHero" in body or "assign-campaign" in body or "enterGame" in body, (
        "handleCreateCampaign nie sprawdza currentHero ani nie wywołuje enterGame/assign-campaign — "
        "brak obsługi przypadku 'bohater już istnieje'."
    )


# ─── C14: selectCampaign fallbacks ───────────────────────────────────────────

def test_selectCampaign_redirects_to_heroes_not_wizard():
    """selectCampaign must NOT fall back to startCharacterWizard() — redirect to heroes screen instead."""
    src = _read_js()
    body = _extract_function_body(src, "selectCampaign")
    if not body:
        # Function may be named differently — search broadly
        body = src
    # Count occurrences of startCharacterWizard inside selectCampaign
    wizard_calls = body.count("startCharacterWizard")
    assert wizard_calls == 0, (
        f"selectCampaign() ma {wizard_calls} wywołanie(a) startCharacterWizard() — "
        "zamiast tego powinno przekierowywać na ekran Bohaterowie."
    )


# ─── Backward compat: showNewCampaignScreen still works ──────────────────────

def test_showNewCampaignScreen_still_redirects_to_heroes_when_no_hero():
    """showNewCampaignScreen must still redirect to heroes screen when no hero is selected."""
    src = _read_js()
    body = _extract_function_body(src, "showNewCampaignScreen")
    assert body, "showNewCampaignScreen nie znaleziono w app.js"
    # Must still have the heroes-screen redirect logic
    assert "heroes" in body, (
        "showNewCampaignScreen nie zawiera przekierowania na ekran 'heroes' — backward compat broken."
    )


def test_handleNewCampaignWithHero_still_exists():
    """handleNewCampaignWithHero must still exist — it's the correct hero-first campaign creation path."""
    src = _read_js()
    assert "function handleNewCampaignWithHero" in src or "async function handleNewCampaignWithHero" in src, (
        "handleNewCampaignWithHero zniknęła — to jest poprawna ścieżka hero-first, musi zostać."
    )
