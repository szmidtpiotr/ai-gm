"""TDD: Issue #965 — usunąć 4 stare dev/test funkcje z zakładki Ustawienia (player UI).

Deletion task — weryfikujemy że serwowane pliki frontu (nginx, bind-mount, live)
nie zawierają już usuwanych elementów, a niezależny FAB raportu bugów (#955) i
współdzielona funkcja showDeathScreen pozostają nietknięte.

Test sięga po pliki przez HTTP do kontenera frontendu (`http://frontend`), bo
backend nie montuje katalogu `frontend/`. Frontend to nginx z bind-mountem —
edycja pliku jest live, bez rebuildu.
"""
import urllib.request

FRONT = "http://frontend/front"


def _fetch(path: str) -> str:
    with urllib.request.urlopen(f"{FRONT}/{path}", timeout=10) as r:
        assert r.status == 200, f"{path} → HTTP {r.status}"
        return r.read().decode("utf-8", errors="replace")


# ─── Test główny — 4 usuwane elementy znikają z UI ───────────────────────────

def test_dev_settings_elements_removed_from_html():
    """index.html nie zawiera już 4 starych dev/test elementów Ustawień."""
    html = _fetch("index.html")
    for needle in (
        'id="debug-log-section"',      # 📋 Skopiuj log do zgłoszenia błędu
        'id="debug-copy-btn"',
        'id="debug-log-preview"',
        'id="reset-campaign-btn"',     # Reset kampanii
        'id="reset-character-btn"',    # Reset postaci
        'id="test-death-btn"',         # Test: Śmierć
        'settings-admin-actions',      # wrapper
        'debug-turns-btn',             # pigułki 3/5/10
    ):
        assert needle not in html, f"USUNIĘTY element wciąż w index.html: {needle}"


def test_dev_settings_handlers_removed_from_js():
    """app.js nie ma już bindów/referencji do usuniętych guzików."""
    app_js = _fetch("js/app.js")
    for needle in (
        "btnResetCampaign",
        "btnResetCharacter",
        "handleResetCampaign",
        "handleResetCharacter",
        "test-death-btn",
        "debug-copy-btn",
        "debug-log-preview",
        "_debugTurnsN",
        "debug-turns-btn",
        "turns/debug-log",
    ):
        assert needle not in app_js, f"USUNIĘTA referencja wciąż w app.js: {needle}"


def test_orphaned_reset_handlers_removed_from_game_js():
    """Osierocone handleResetCampaign/Character zniknęły z game.js."""
    game_js = _fetch("js/screens/game.js")
    assert "function handleResetCampaign" not in game_js
    assert "function handleResetCharacter" not in game_js


# ─── Backward compat — co MUSI zostać nietknięte ─────────────────────────────

def test_bug_report_fab_955_untouched():
    """FAB raportu bugów dla testerów (#955) to osobna ścieżka — zostaje."""
    html = _fetch("index.html")
    # FAB bug-report ma własny element; nie może paść ofiarą tego cleanupu.
    assert "bug-report" in html, "FAB raportu bugów (#955) zniknął — regresja!"


def test_show_death_screen_still_referenced():
    """showDeathScreen jest współdzielony (combat_ui.js) — definicja zostaje."""
    game_js = _fetch("js/screens/game.js")
    assert "function showDeathScreen" in game_js
    combat_js = _fetch("js/screens/combat_ui.js")
    assert "showDeathScreen(" in combat_js, "combat_ui nadal woła showDeathScreen"
