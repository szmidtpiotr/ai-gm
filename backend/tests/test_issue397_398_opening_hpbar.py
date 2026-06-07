"""TDD: Issue #397 (opening scene zawsze w lochu) + #398 (header HP bar 50% mimo full).

#397 — backend/prompts/system_prompt.txt OTWARCIE SESJI:
  - NIE może już zabraniać tawern/miast (stara reguła "NIE otwieraj w tawernie")
  - MUSI zawierać jawny zakaz domyślnego tropu "budzisz się w zimnym miejscu"
  - MUSI dopuszczać miasta/tawerny/lokacje wśród ludzi

#398 — frontend/front/js/app.js:
  - enterGame() MUSI wołać updateHeaderStats() (ustawia tekst + pasek razem)
  - martwy lokalny `sheet` usunięty (nie ustawiamy samego textContent bez paska)
"""
import os
import re

REPO = "/app"  # baked image root; prompts + frontend copied in
SYS_PROMPT = os.path.join(REPO, "prompts", "system_prompt.txt")
# frontend is NOT in the backend image — resolve via repo path passed by mount or skip
APP_JS_CANDIDATES = [
    "/app/frontend/front/js/app.js",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "front", "js", "app.js"),
]


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _find_section(text, header):
    """Return text of a '## header' section up to the next '## '."""
    idx = text.find(header)
    assert idx != -1, f"Section {header!r} not found"
    rest = text[idx + len(header):]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


# ─── #397: system prompt OTWARCIE SESJI ──────────────────────────────────────

def test_opening_section_exists():
    """OTWARCIE SESJI section must still exist."""
    txt = _read(SYS_PROMPT)
    assert "## OTWARCIE SESJI" in txt, "Sekcja OTWARCIE SESJI zniknęła"


def test_opening_no_longer_forbids_taverns():
    """Old rule 'NIE otwieraj w tawernie' must be gone — taverns/cities now allowed."""
    section = _find_section(_read(SYS_PROMPT), "## OTWARCIE SESJI")
    assert "NIE otwieraj w tawernie" not in section, (
        "Stara reguła zabraniająca tawern nadal obecna — to ona pchała model w stronę "
        "dramatycznego 'budzisz się w lochu'."
    )


def test_opening_forbids_waking_up_trope():
    """Section must explicitly forbid the default 'waking up in a cold place' trope."""
    section = _find_section(_read(SYS_PROMPT), "## OTWARCIE SESJI").lower()
    assert "budzisz się" in section, (
        "Sekcja musi jawnie wspomnieć o tropie 'budzisz się' aby go zakazać jako domyślnego."
    )
    # the prohibition wording
    assert "zakaz" in section or "nie używaj" in section, (
        "Brak jawnego zakazu tropu przebudzenia (oczekiwano 'ZAKAZ' lub 'NIE używaj')."
    )


def test_opening_allows_cities_and_people():
    """Section must explicitly allow cities/taverns/among-people openings."""
    section = _find_section(_read(SYS_PROMPT), "## OTWARCIE SESJI").lower()
    assert "tawern" in section and ("miast" in section or "wśród ludzi" in section), (
        "Sekcja musi jawnie dopuszczać tawerny i miasta/lokacje wśród ludzi."
    )


def test_opening_prioritizes_campaign_plan():
    """Section must reference Kontekst kampanii / plan as priority (ties to #372)."""
    section = _find_section(_read(SYS_PROMPT), "## OTWARCIE SESJI").lower()
    assert "kontekst kampanii" in section or "plan kampanii" in section, (
        "Sekcja musi odwoływać się do planu kampanii (Kontekst kampanii z #372)."
    )


# ─── #398: enterGame calls updateHeaderStats ─────────────────────────────────

def _app_js():
    for p in APP_JS_CANDIDATES:
        if os.path.isfile(p):
            return _read(p)
    return None


def test_enter_game_updates_header_bar():
    """enterGame() must call updateHeaderStats() so the HP bar width matches the value."""
    js = _app_js()
    if js is None:
        import pytest
        pytest.skip("app.js not mounted in backend image — verified via frontend bind mount")
    # isolate enterGame function body
    idx = js.find("async function enterGame(")
    assert idx != -1, "enterGame() nie znaleziona w app.js"
    body = js[idx: idx + 1200]
    assert "updateHeaderStats()" in body, (
        "enterGame() musi wołać updateHeaderStats() — inaczej pasek HP w nagłówku "
        "zostaje ze starą szerokością (bug #398)."
    )


def test_enter_game_no_lone_textcontent_without_bar():
    """enterGame() must not set characterStatsDisplay.textContent inline without the bar update."""
    js = _app_js()
    if js is None:
        import pytest
        pytest.skip("app.js not mounted in backend image")
    idx = js.find("async function enterGame(")
    body = js[idx: idx + 1200]
    # the old buggy line set textContent directly; now it goes through updateHeaderStats
    assert "characterStatsDisplay.textContent = `${hp}/${maxHp} HP`" not in body, (
        "enterGame() nadal ustawia sam tekst HP bez aktualizacji paska — regresja #398."
    )
