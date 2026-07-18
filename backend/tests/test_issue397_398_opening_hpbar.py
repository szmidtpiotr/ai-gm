"""TDD: Issue #397 (opening scene zawsze w lochu).

#397 — backend/prompts/system_prompt.txt OTWARCIE SESJI:
  - NIE może już zabraniać tawern/miast (stara reguła "NIE otwieraj w tawernie")
  - MUSI zawierać jawny zakaz domyślnego tropu "budzisz się w zimnym miejscu"
  - MUSI dopuszczać miasta/tawerny/lokacje wśród ludzi

(#398 dotyczył app.js starego UI — testy usunięte razem z legacy frontend/front/,
skasowanym 2026-07-18; ŻAR (front-v2) jest jedynym UI gracza.)
"""
import os

REPO = "/app"  # baked image root; prompts copied in
SYS_PROMPT = os.path.join(REPO, "prompts", "system_prompt.txt")


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


# Testy #398 (app.js starego UI) usunięte — legacy frontend/front/ skasowany 2026-07-18.
