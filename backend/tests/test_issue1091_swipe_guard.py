"""TDD: Issue #1091 — Mobile swipe guard: scroll nie zamyka modala, overscroll nie odświeża strony."""
import requests
import pytest

FRONTEND_BASE = "http://frontend:80"


def _get_asset(path: str) -> str:
    resp = requests.get(f"{FRONTEND_BASE}/{path}", timeout=10)
    assert resp.status_code == 200, f"Cannot fetch {path}: HTTP {resp.status_code}"
    return resp.text


class TestSwipeGuardFix:
    """CSS + JS source checks for #1091 swipe-down guard."""

    def test_overscroll_behavior_in_sheet_content_css(self):
        """.sheet-panel__content must have overscroll-behavior: contain to block pull-to-refresh."""
        css = _get_asset("css/styles.css")
        idx = css.find(".sheet-panel__content")
        assert idx != -1, ".sheet-panel__content not found in styles.css"
        rule_block = css[idx: idx + 300]
        assert "overscroll-behavior" in rule_block, (
            ".sheet-panel__content brak `overscroll-behavior: contain` — "
            "pull-to-refresh odpala się na mobile gdy użytkownik jest na górze listy ekwipunku"
        )

    def test_swipe_down_guard_checks_scrolltop(self):
        """initPanelSwipeDown must check scrollTop before starting drag-to-close."""
        js = _get_asset("js/screens/game.js")
        fn_idx = js.find("function initPanelSwipeDown")
        assert fn_idx != -1, "initPanelSwipeDown not found in game.js"
        fn_body = js[fn_idx: fn_idx + 900]
        assert "scrollTop" in fn_body, (
            "initPanelSwipeDown brak guard `scrollTop` — "
            "normalny scroll listy w dół >80px zamyka modal na mobile"
        )


class TestBackwardCompatSwipe:
    """Swipe-to-close musi nadal działać z góry listy."""

    def test_swipe_fn_still_exists(self):
        """initPanelSwipeDown function must still exist."""
        js = _get_asset("js/screens/game.js")
        assert "function initPanelSwipeDown" in js, "initPanelSwipeDown usunięta — swipe-to-close zepsuty"

    def test_closefn_still_called_in_touchend(self):
        """closeFn() must still be called — swipe z góry listy nadal zamyka panel."""
        js = _get_asset("js/screens/game.js")
        fn_idx = js.find("function initPanelSwipeDown")
        fn_body = js[fn_idx: fn_idx + 1500]
        assert "closeFn()" in fn_body, "closeFn() usunięta — gest zamknięcia z góry nie działa"
