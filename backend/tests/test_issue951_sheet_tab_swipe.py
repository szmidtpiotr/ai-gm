"""TDD: Issue #951 — initSheetTabSwipe uses dynamic visible tabs, not hardcoded TAB_ORDER."""
import pytest
import requests


FRONTEND_BASE = "http://frontend:80"
GAME_JS_PATH = "/front/js/screens/game.js"


def _fetch_game_js():
    resp = requests.get(FRONTEND_BASE + GAME_JS_PATH, timeout=5)
    assert resp.status_code == 200, f"Could not fetch game.js: {resp.status_code}"
    return resp.text


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_sheet_tab_swipe_no_phantom_skills_tab():
    """TAB_ORDER must not contain phantom 'skills' tab — it doesn't exist in DOM."""
    content = _fetch_game_js()
    # Find the initSheetTabSwipe function block
    start = content.find("function initSheetTabSwipe")
    assert start != -1, "initSheetTabSwipe function not found in game.js"
    snippet = content[start:start + 800]
    # The broken hardcoded array had 'skills' which doesn't exist in DOM
    assert "'skills'" not in snippet, (
        "initSheetTabSwipe still contains phantom 'skills' tab in TAB_ORDER. "
        "Use dynamic tab resolution instead."
    )


def test_sheet_tab_swipe_uses_dynamic_tab_order():
    """initSheetTabSwipe must resolve visible tabs dynamically from DOM, not a hardcoded list."""
    content = _fetch_game_js()
    start = content.find("function initSheetTabSwipe")
    assert start != -1, "initSheetTabSwipe function not found in game.js"
    snippet = content[start:start + 1400]
    # Must query DOM for actual visible tabs instead of static TAB_ORDER
    assert "querySelectorAll('.sheet-tab')" in snippet or 'querySelectorAll(".sheet-tab")' in snippet, (
        "initSheetTabSwipe must build tab list from DOM via querySelectorAll('.sheet-tab'). "
        "Static TAB_ORDER array is broken."
    )


def test_sheet_tab_swipe_includes_spells_tab():
    """initSheetTabSwipe must NOT exclude 'spells' tab from the order."""
    content = _fetch_game_js()
    start = content.find("function initSheetTabSwipe")
    assert start != -1, "initSheetTabSwipe function not found in game.js"
    snippet = content[start:start + 800]
    # Old broken code: hardcoded list without 'spells'
    # After fix: dynamic list includes spells automatically when visible
    # Verify the old broken static list is gone
    assert "TAB_ORDER = [" not in snippet, (
        "Static TAB_ORDER array still present. Replace with dynamic visible-tab resolution."
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_init_sheet_tab_swipe_function_still_exists():
    """initSheetTabSwipe function must still exist and be callable."""
    content = _fetch_game_js()
    assert "function initSheetTabSwipe(" in content, (
        "initSheetTabSwipe function was removed — it must still exist."
    )
    assert "initSheetTabSwipe" in content, "Function reference gone"
