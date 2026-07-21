"""TDD: Issue #1527 (fala 4, runda 4) — KONWENCJA NAZW we WSZYSTKICH generatorach.

Runda 3 nauczyła konwencji jeden generator (podpowiadacz gospodarza). Ale nazwy
własne wymyśla w tym projekcie kilkanaście miejsc — Kreator AI, generator
sub-lokacji osady, Kuźnia, plan GM, plotki, spotkania, kafle lochów. Każde miało
własną instrukcję i każde mogło popełnić dokładnie ten sam błąd („Agnieszka Kruk"
w karczmie na Kresach).

Ta runda:
1. podpina `naming_prompt_block()` do wszystkich generatorów nazw,
2. zostawia **test-guard**, który pilnuje, żeby konwencja nie wypadła z żadnego
   z nich po cichu przy następnej przebudowie promptu.

Guard patrzy na ŹRÓDŁO: moduł z listy generatorów musi używać
`naming_prompt_block` (albo `world_naming_service`). Wyjątki są jawne i mają
powód wpisany w `_EXEMPT` — cicha degradacja („ktoś usunął import") = czerwony test.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1527d_naming_guard.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

import app.services.world_naming_service as wns

APP_DIR = Path(wns.__file__).resolve().parents[1]      # backend/app/

#: Moduły, które proszą model o WYMYŚLENIE nazwy własnej trafiającej do świata.
#: Dopisujesz nowy generator treści → dopisujesz go tutaj (albo do `_EXEMPT`).
NAME_GENERATORS = [
    "routers/world_lint.py",          # podpowiadacz gospodarza (runda 3)
    "services/world_service.py",      # sub-lokacje osady + uzupełnianie pól pending
    "routers/smart_entry.py",         # Kreator AI (przedmioty, wrogowie, NPC)
    "routers/adventure_forge.py",     # Kuźnia — szablony kampanii
    "services/gm_plan_generation_service.py",   # plan GM: NPC, lokacje, haki
    "services/world_rumor_service.py",          # plotki (nazwy własne w treści)
    "services/encounter_catalog_service.py",    # katalog spotkań
    "services/campaign_plan_service.py",        # plan kampanii V2
    "services/new_act_service.py",              # nowy akt: NPC, lokacje, haki
    "routers/dungeon_tiles.py",                 # nazwy komnat lochu
]

#: Świadome wyjątki — moduł woła LLM, ale NIE tworzy nowych nazw własnych.
_EXEMPT = {
    "services/narrator_service.py":
        "narrator ma konwencję wprost w system_prompt.txt (sekcja NAZEWNICTWO, #997)",
    "services/game_engine.py":
        "j.w. — prowadzi turę na systemowym prompcie narratora",
}


def _source(rel: str) -> str:
    path = APP_DIR / rel
    assert path.is_file(), f"nie ma pliku {rel} — zaktualizuj listę generatorów"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", NAME_GENERATORS)
def test_every_name_generator_uses_the_naming_convention(rel):
    """Generator nazw bez konwencji = powrót do „Agnieszki Kruk"."""
    src = _source(rel)
    assert "naming_prompt_block" in src or "world_naming_service" in src, (
        f"{rel} wymyśla nazwy własne, ale nie wkleja konwencji nazw. "
        f"Albo podepnij `naming_prompt_block()`, albo dopisz jawny wyjątek "
        f"z powodem do `_EXEMPT` w tym teście."
    )


def test_exempt_modules_are_documented():
    """Wyjątek bez powodu to nie wyjątek, tylko dziura."""
    for rel, reason in _EXEMPT.items():
        assert reason.strip(), f"{rel}: wyjątek bez uzasadnienia"
        assert (APP_DIR / rel).is_file(), f"{rel}: wyjątek dla nieistniejącego pliku"


def test_generator_list_has_no_duplicates():
    assert len(NAME_GENERATORS) == len(set(NAME_GENERATORS))


def test_naming_block_is_importable_from_one_place():
    """Jedno źródło konwencji — nie kopiujemy reguł po plikach."""
    assert hasattr(wns, "naming_prompt_block")
    assert hasattr(wns, "REGION_NAMING")
