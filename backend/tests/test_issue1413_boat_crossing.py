"""TDD: Issue #1413 — Model C: narracyjna przeprawa łodzią.

Gracz na hexie sąsiadującym z rzeką: „szukam łodzi"/„buduję tratwę"/„przeprawiam się
łodzią" → test survival → flaga river_crossing (jednorazowa przeprawa przez wodę).
Tu: bramka intencji (regex) — musi wymagać CZASOWNIKA, nie łapać zwykłych opisów.
Pełny przepływ (adjacency + skill + LLM + bypass) = live smoke na DEV.
"""
import sys

import pytest

sys.path.insert(0, "/app")

from app.api.turns import _BOAT_INTENT_RE


@pytest.mark.parametrize("text", [
    "Szukam łodzi nad brzegiem",
    "buduję tratwę z gałęzi",
    "sklecam tratwę",
    "chcę się przeprawić łodzią",
    "przeprawiam się przez rzekę",
    "przeprawiam się na drugi brzeg",
    "potrzebuję łodzi żeby przejść",
    "wsiadam do łódki",
])
def test_boat_intent_matches(text):
    assert _BOAT_INTENT_RE.search(text) is not None, f"powinno złapać: {text}"


@pytest.mark.parametrize("text", [
    "Widzę starą łódź przy brzegu",       # opis, nie akcja
    "Na rzece kołysze się tratwa",         # opis
    "Rozglądam się po okolicy",            # brak łodzi
    "Atakuję bandytę przy moście",         # co innego
    "Idę wzdłuż rzeki na północ",          # ruch, nie przeprawa
])
def test_boat_intent_rejects(text):
    assert _BOAT_INTENT_RE.search(text) is None, f"NIE powinno łapać: {text}"
