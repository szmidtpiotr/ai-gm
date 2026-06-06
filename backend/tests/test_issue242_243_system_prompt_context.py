"""TDD: Issues #242 + #243 — system_prompt.txt must forbid generic dungeon atmosphere
and NPC-as-enemy labeling outside combat.

#242: GM defaults to generic 'darkness/dungeon' atmosphere even in city morning.
Fix: system_prompt must instruct GM to respect injected [CZAS GRY] and [LOCATION CONTEXT]
and NOT default to dungeon/dark tone when no dungeon context is present.

#243: GM labels NPCs as 'opponents/enemies' (przeciwnik/wróg) in non-combat scenes.
Fix: system_prompt must forbid using combat framing for NPCs unless [COMBAT_START] is active.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"


def _read_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


# ─── #242 — atmosphere must respect injected context ─────────────────────────

def test_system_prompt_forbids_generic_dungeon_default():
    """system_prompt must instruct GM not to default to dungeon/darkness atmosphere
    when location context is city/village/tavern or when time is daytime.

    Before fix: no instruction → LLM defaults to 'mroku i lochów'.
    After fix: explicit rule to use location-appropriate atmosphere.
    """
    prompt = _read_prompt()

    # Must contain instruction to respect location/time context for atmosphere
    prompt_lower = prompt.lower()
    has_atmosphere_rule = any(phrase in prompt_lower for phrase in [
        "nie używaj generycznych opisów ciemności",
        "nie stosuj atmosfery lochu",
        "atmosferę dopasuj do",
        "nie defaultuj do ciemności",
        "atmosfera musi odpowiadać",
        "nie opisuj mroku gdy",
        "lochu gdy nie jesteś w lochu",
        "ciemności gdy jest dzień",
        "ciemność i lochy są właściwe tylko",
        "nie pasuje to do sceny",
    ])
    assert has_atmosphere_rule, (
        "system_prompt must forbid generic dungeon/darkness defaults when location is "
        "city/village/day. Add: 'Atmosferę dopasuj do bieżącej lokacji i pory dnia — "
        "nie stosuj domyślnie ciemności/lochów gdy nie pasuje to do sceny.'"
    )


def test_system_prompt_instructs_respect_injected_context():
    """system_prompt must instruct GM to respect [LOCATION CONTEXT] and [CZAS GRY] blocks."""
    prompt = _read_prompt()

    # Check that the 'no location context' section doesn't just say "no location_intent"
    # but also handles atmosphere
    no_loc_section_idx = prompt.find("Gdy NIE OTRZYMASZ bloku [LOCATION CONTEXT]")
    assert no_loc_section_idx >= 0, "[LOCATION CONTEXT] section must exist in system_prompt"

    # The section after 'no location context' must include atmospheric guidance
    section = prompt[no_loc_section_idx:no_loc_section_idx+400]
    has_atmosphere_guidance = any(phrase in section for phrase in [
        "atmosfer",
        "generyczn",
        "domyśln",
        "ciemno",
        "lochu",
        "pora dnia",
        "CZAS GRY",
    ])
    assert has_atmosphere_guidance, (
        f"'Gdy NIE OTRZYMASZ [LOCATION CONTEXT]' section must include atmospheric guidance. "
        f"Current section: {section!r}"
    )


# ─── #243 — NPC must not be labeled enemy outside combat ─────────────────────

def test_system_prompt_forbids_npc_enemy_label_outside_combat():
    """system_prompt must forbid calling NPCs 'opponents/enemies' outside combat context.

    Before fix: no rule → LLM uses 'przeciwnik' in any dramatic scene.
    After fix: explicit instruction that 'przeciwnik/wróg' labels only apply when
    [COMBAT_START] has been issued.
    """
    prompt = _read_prompt()

    prompt_lower = prompt.lower()
    has_npc_framing_rule = any(phrase in prompt_lower for phrase in [
        "nie nazywaj npc przeciwnikiem",
        "nie używaj słów 'przeciwnik'",
        "poza walką nie stosuj etykiety",
        "wróg ani przeciwnik poza walką",
        "npc nie jest przeciwnikiem",
        "przeciwnikiem tylko w walce",
        "nie etykietuj npc jako",
        "poza walką npc to",
        "[combat_start] nie był użyty",
    ])
    assert has_npc_framing_rule, (
        "system_prompt must forbid labeling NPCs as 'opponents/enemies' outside active combat. "
        "Add: 'Nie nazywaj NPC przeciwnikiem ani wrogiem jeśli nie trwa walka ([COMBAT_START] nie był użyty).'"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_system_prompt_still_has_combat_start_guidance():
    """[COMBAT_START] guidance must still be present (fix #243 must not remove it)."""
    prompt = _read_prompt()
    assert "[COMBAT_START" in prompt, "[COMBAT_START] guidance must remain in system_prompt"


def test_system_prompt_still_has_location_context_injection_info():
    """[LOCATION CONTEXT] section must still be present (#242 fix must not remove it)."""
    prompt = _read_prompt()
    assert "[LOCATION CONTEXT]" in prompt, "[LOCATION CONTEXT] section must remain in system_prompt"
