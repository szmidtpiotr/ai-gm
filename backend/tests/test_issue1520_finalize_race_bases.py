"""Issue #1520 — finalize-sheet nie znał rasy: „expected 88; got 89" u elfa.

Stored stats zawierają modyfikatory rasowe (nakładane przy tworzeniu), ale
`_core_bases_from_stored_stats` odejmowało tylko bonus archetypu. Dla elfa
(+2 DEX +1 WIS −1 CON) „rolled bases" miały więc rasowy bilans (+2), a ujemny
mod CON potrafił zepchnąć bazę pod STAT_ROLL_MIN=8 — kreator clampował ją do 8
po swojej stronie i finalize odrzucał redystrybucję z sumą o 1 za dużą.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.characters import (
    SIX_CORE_STATS,
    _core_bases_from_stored_stats,
    _finalize_resolve_new_stats,
)
from app.services.actor_stats import apply_racial_modifiers


def _stored_stats(rolled: dict, archetype: str, race: str) -> dict:
    """Zbuduj staty tak, jak robi to tworzenie postaci: rzuty + klasa + rasa."""
    sheet = {"stats": dict(rolled)}
    stats = sheet["stats"]
    if archetype == "warrior":
        stats["STR"] += 2; stats["CON"] += 1
    elif archetype == "rogue":
        stats["DEX"] += 2; stats["LCK"] += 1
    else:
        stats["INT"] += 2; stats["WIS"] += 1
    apply_racial_modifiers(sheet, race)
    return sheet["stats"]


ROLLED = {"STR": 12, "DEX": 14, "CON": 8, "INT": 15, "WIS": 11, "CHA": 10, "LCK": 8}


@pytest.mark.parametrize("race,archetype", [
    ("human", "scholar"), ("human", "warrior"), ("human", "rogue"),
    ("dwarf", "scholar"), ("dwarf", "warrior"),
    ("elf", "scholar"), ("elf", "rogue"),
])
def test_bases_recover_exact_rolls_for_every_race(race, archetype):
    stored = _stored_stats(ROLLED, archetype, race)
    bases = _core_bases_from_stored_stats(stored, archetype, race)
    assert bases == ROLLED, (race, archetype)


def test_elf_low_con_no_longer_underflows_stat_min():
    """Rzucone CON=8, elf −1 → stored 7. Baza musi wrócić do 8, nie do 7."""
    stored = _stored_stats(ROLLED, "scholar", "elf")
    assert stored["CON"] == 7  # warunek scenariusza z buga
    bases = _core_bases_from_stored_stats(stored, "scholar", "elf")
    assert bases["CON"] == 8


def test_finalize_sum_matches_client_for_elf():
    """Scenariusz z buga: klient wysyła bazy = rzuty; suma musi się zgadzać."""
    sheet = {"archetype": "scholar", "stats": _stored_stats(ROLLED, "scholar", "elf")}
    req = SimpleNamespace(stat_overrides=dict(ROLLED))
    merged = _finalize_resolve_new_stats(sheet, req, "elf")
    assert {k: merged[k] for k in SIX_CORE_STATS} == ROLLED


def test_finalize_redistribution_within_rolls_passes():
    """Przerzucenie punktu (CON−… nie — INT→STR) w obrębie tej samej sumy."""
    sheet = {"archetype": "scholar", "stats": _stored_stats(ROLLED, "scholar", "elf")}
    redistributed = dict(ROLLED, INT=14, STR=13)
    req = SimpleNamespace(stat_overrides=redistributed)
    merged = _finalize_resolve_new_stats(sheet, req, "elf")
    assert merged["INT"] == 14 and merged["STR"] == 13


def test_finalize_still_rejects_sum_cheat():
    sheet = {"archetype": "scholar", "stats": _stored_stats(ROLLED, "scholar", "elf")}
    req = SimpleNamespace(stat_overrides=dict(ROLLED, STR=13))  # +1 z powietrza
    with pytest.raises(HTTPException) as e:
        _finalize_resolve_new_stats(sheet, req, "elf")
    assert e.value.status_code == 400


def test_race_default_keeps_old_behaviour_for_human():
    """Wywołania bez rasy (stare ścieżki) działają jak dotąd."""
    stored = _stored_stats(ROLLED, "warrior", "human")
    assert _core_bases_from_stored_stats(stored, "warrior") == ROLLED
