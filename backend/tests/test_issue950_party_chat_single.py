"""TDD: Issue #950 — Party Chat panel must not appear in single-player session."""
import urllib.request
import pytest

FRONTEND = "http://frontend:80"


def _fetch(path, timeout=5):
    url = FRONTEND + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        pytest.fail(f"Cannot fetch {url} from frontend container: {e}")


# ── Test główny ────────────────────────────────────────────────────────────────

def test_enter_game_deactivates_multiplayer_panel():
    """#950 RED: enterGame() must call multiplayerUI.deactivate() to clear sticky party chat."""
    content = _fetch("/front/js/screens/game.js")

    idx = content.find("async function enterGame(")
    assert idx != -1, "enterGame function not found in game.js"

    # Check the first 500 chars of the function body for a deactivate call.
    fn_body_start = content[idx : idx + 500]
    assert "deactivate" in fn_body_start, (
        "BUG #950: enterGame() does not call multiplayerUI.deactivate(). "
        "Party chat panel stays visible (sticky) when entering single after MP session."
    )


def test_party_chat_panel_has_minimize_support():
    """#950 RED: multiplayer_ui.js must expose minimizePartyChat() for minimize-to-icon UX."""
    content = _fetch("/front/js/multiplayer_ui.js")
    assert "minimizePartyChat" in content, (
        "BUG #950: multiplayer_ui.js does not expose minimizePartyChat(). "
        "Players cannot minimize the Party Chat panel to an icon."
    )


# ── Backward compat ────────────────────────────────────────────────────────────

def test_party_chat_panel_hidden_by_default():
    """Backward compat: #party-chat-panel must start hidden in index.html."""
    content = _fetch("/")
    panel_idx = content.find('id="party-chat-panel"')
    assert panel_idx != -1, "#party-chat-panel not found in index.html"
    # The hidden attribute must appear within 60 chars of the opening tag
    snippet = content[panel_idx : panel_idx + 100]
    assert "hidden" in snippet, (
        "Regression: #party-chat-panel is not hidden by default — "
        "it would appear for all players regardless of game mode."
    )


def test_deactivate_still_exposed_on_window():
    """Backward compat: window.multiplayerUI.deactivate must remain in the public API."""
    content = _fetch("/front/js/multiplayer_ui.js")
    # The public API object at the bottom must still include 'deactivate'
    api_idx = content.find("window.multiplayerUI")
    assert api_idx != -1, "window.multiplayerUI assignment not found"
    api_snippet = content[api_idx : api_idx + 300]
    assert "deactivate" in api_snippet, (
        "Regression: deactivate() was removed from window.multiplayerUI public API."
    )
