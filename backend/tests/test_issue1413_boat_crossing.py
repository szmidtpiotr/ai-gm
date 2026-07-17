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
    # #1418 — naturalne frazy przeprawy (wcześniej gubione → flavor bez ruchu pina)
    "przekraczam rzeke",
    "szukam miejsca w który moge przekroczyc rzeke na druga strone",
    "buduję prowizoryczną przeprawę",
    "brodzę przez rzekę",
    "idę na drugą stronę",
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
