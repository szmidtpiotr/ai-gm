"""TDD: Issue #1073 — narrative crit-hit terms in system_prompt.txt must match
player-facing UI wording ('Krytyczny sukces' / 'Krytyczna porażka', adjective
first) established in #641. Mechanic-controlling terms ('Nat 20', 'Nat 1' as
logic conditions) stay untouched — this is a narration-wording fix only.
"""
from pathlib import Path

SYSTEM_PROMPT_PATH = "/app/prompts/system_prompt.txt"


def _read_prompt():
    return Path(SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_narrative_crit_terms_match_ui_word_order():
    """Narrative result-degree headers must use UI order 'Krytyczny sukces' /
    'Krytyczna porażka', not the old reversed 'Sukces krytyczny' / 'Porażka
    krytyczna' — those two exact reversed strings must be fully gone.
    """
    text = _read_prompt()
    assert "Sukces krytyczny" not in text, (
        "system_prompt.txt wciąż używa 'Sukces krytyczny' (stara kolejność) — "
        "gracz widzi 'Krytyczny sukces' na karcie kości (#641), narracja MG rozjeżdża się (#1073)"
    )
    assert "Porażka krytyczna" not in text, (
        "system_prompt.txt wciąż używa 'Porażka krytyczna' (stara kolejność) — "
        "gracz widzi 'Krytyczna porażka' na karcie kości (#641), narracja MG rozjeżdża się (#1073)"
    )
    assert "Krytyczny sukces" in text, "Brak ujednoliconego terminu 'Krytyczny sukces' w system_prompt.txt"
    assert "Krytyczna porażka" in text, "Brak ujednoliconego terminu 'Krytyczna porażka' w system_prompt.txt"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_mechanic_controlling_nat20_nat1_logic_untouched():
    """'Nat 20' / 'Nat 1' as mechanic-condition terms (logic, not narration
    wording) must remain exactly as-is — this issue is narration-only.
    """
    text = _read_prompt()
    assert "Nat 20 = automatyczny sukces z dramatycznym efektem narracyjnym." in text
    assert "Nat 1 = automatyczna porażka z narracyjną komplikacją." in text
    assert "nat 20 = podwójne obrażenia, nat 1 = komplikacja" in text
