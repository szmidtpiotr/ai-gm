"""TDD: Issue #370 — C16 delete confirmation modals (kampania, postac).

Tests verify:
- handleDeleteCampaignFromList uses a modal, NOT browser confirm()
- showDeleteCampaignModal function exists
- Swipe delete (skipConfirm path) also shows confirmation — no instant delete
- Hero delete modal still works (backward compat)
"""
import re
import os

APP_JS = "/tmp/app_c16_test.js"


def _read_js() -> str:
    with open(APP_JS, encoding="utf-8") as f:
        return f.read()


def _extract_function_body(src: str, func_name: str) -> str:
    pattern = re.compile(
        r"(?:async\s+)?function\s+" + re.escape(func_name) + r"\s*\([^)]*\)\s*\{"
    )
    m = pattern.search(src)
    if not m:
        return ""
    start = m.end() - 1
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    return src[start:]


# ─── C16.1: campaign delete must use a modal, not browser confirm() ──────────

def test_handleDeleteCampaignFromList_no_browser_confirm():
    """handleDeleteCampaignFromList must NOT use browser confirm() — use a styled modal."""
    src = _read_js()
    body = _extract_function_body(src, "handleDeleteCampaignFromList")
    assert body, "handleDeleteCampaignFromList nie znaleziono w app.js"
    # Must not have native confirm() call
    assert "confirm(" not in body, (
        "handleDeleteCampaignFromList() wciąż używa natywnego confirm() przeglądarki — "
        "zastąp go wywołaniem showDeleteCampaignModal() lub podobnego."
    )


def test_showDeleteCampaignModal_exists():
    """showDeleteCampaignModal function must exist — modal for campaign deletion."""
    src = _read_js()
    assert (
        "function showDeleteCampaignModal" in src
        or "async function showDeleteCampaignModal" in src
    ), (
        "Brak funkcji showDeleteCampaignModal() — musi istnieć modal potwierdzenia usuwania kampanii."
    )


def test_handleDeleteCampaignFromList_uses_campaign_modal():
    """handleDeleteCampaignFromList must call showDeleteCampaignModal (or equivalent)."""
    src = _read_js()
    body = _extract_function_body(src, "handleDeleteCampaignFromList")
    assert body, "handleDeleteCampaignFromList nie znaleziono w app.js"
    assert "showDeleteCampaignModal" in body or "DeleteCampaignModal" in body, (
        "handleDeleteCampaignFromList nie wywołuje showDeleteCampaignModal() — "
        "usuwanie kampanii nie będzie miało ładnego modalu."
    )


# ─── C16.2: swipe delete must also confirm — no instant delete ───────────────

def test_swipe_delete_no_skipConfirm():
    """Swipe delete (skipConfirm=true) must NOT bypass confirmation — instant delete is dangerous."""
    src = _read_js()
    body = _extract_function_body(src, "handleDeleteCampaignFromList")
    assert body, "handleDeleteCampaignFromList nie znaleziono w app.js"
    # skipConfirm parameter should not exist OR if it does, it should not bypass the modal
    # After C16: the skipConfirm=true path must still show the modal
    # Check: skipConfirm with true bypassing confirmation → bad
    # Simplest: after fix, skipConfirm parameter should be removed from calls
    # OR the function body should always show modal regardless of skipConfirm

    # Find all calls with skipConfirm=true in the whole file
    skip_calls = re.findall(r"handleDeleteCampaignFromList\s*\([^,)]+,\s*true\s*\)", src)
    assert len(skip_calls) == 0, (
        f"Znaleziono {len(skip_calls)} wywołanie(a) handleDeleteCampaignFromList(..., true) — "
        "skipConfirm=true pomija potwierdzenie, powodując natychmiastowe usuwanie kampanii bez pytania. "
        "Usuń parametr skipConfirm lub upewnij się że zawsze pokazuje modal."
    )


# ─── Backward compat: hero delete modal still works ──────────────────────────

def test_showDeleteHeroModal_still_exists():
    """showDeleteHeroModal must still exist — hero deletion already has a good modal."""
    src = _read_js()
    assert "function showDeleteHeroModal" in src, (
        "showDeleteHeroModal zniknęła — backward compat broken."
    )


def test_delete_campaign_still_calls_api():
    """handleDeleteCampaignFromList must still call the DELETE API."""
    src = _read_js()
    body = _extract_function_body(src, "handleDeleteCampaignFromList")
    assert body, "handleDeleteCampaignFromList nie znaleziono w app.js"
    assert "DELETE" in body and "campaigns" in body, (
        "handleDeleteCampaignFromList nie wywołuje DELETE API — backward compat broken."
    )
