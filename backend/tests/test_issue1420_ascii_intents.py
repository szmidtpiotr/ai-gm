"""TDD: Issue #1420 — matchery intencji odporne na brak polskich znaków.

Polacy na mobilnych piszą bez ogonków. Deterministyczne matchery tekstu gracza muszą
łapać oba warianty (z diakrytykami i ASCII). Testujemy CZYSTE funkcje offenderów.
"""
import sys
sys.path.insert(0, "/app")

import pytest

from app.core.text_utils import strip_pl_diacritics, fold
from app.services.gate_service import classify_intent_stub
from app.services.intent_service import parse_intent
from app.services.hex_travel_service import detect_route_choice, _PT3_MOVE_VERB_RE
from app.services.game_engine import _SKILL_VERB_HINT
from app.services import spend_gold_service as SG


def test_strip_handles_l_stroke():
    # NFKD NIE rozkłada ł — maketrans musi
    assert strip_pl_diacritics("przepływam") == "przeplywam"
    assert strip_pl_diacritics("ŁÓDŹ") == "LODZ"
    assert fold("Ście") == "scie"


@pytest.mark.parametrize("text,expected", [
    ("ide na polnoc", "MOVEMENT"),
    ("idę na północ", "MOVEMENT"),
    ("uciekam z pola walki", "FLEE"),
    ("spie w namiocie", "REST"),          # śpię→spie
    ("przeszukuje pokoj", "SEARCH"),      # przeszukuję→przeszukuje
    ("ogladam sciane", "EXAMINE"),        # oglądam→ogladam
    ("probuje otworzyc zamek", "SKILL_ATTEMPT"),  # próbuję→probuje
])
def test_gate_classify_ascii(text, expected):
    assert classify_intent_stub(text)["action_type"] == expected


@pytest.mark.parametrize("text,expected", [
    ("ide do wsi", "move"),
    ("przeszukuje skrzynie", "explore"),
    ("uciekam", "flee"),
    ("probuje wspiac sie", "skill_test"),
])
def test_intent_service_ascii(text, expected):
    assert parse_intent(text).action_type == expected


@pytest.mark.parametrize("text,expected", [
    ("ide goscincem", "road"),            # gościńcem→goscincem
    ("wybieram dluzsza droge", "road"),   # dłuższą→dluzsza
    ("ide na skroty", "direct"),
    ("odwoluje podroz", "cancel"),        # odwołuję→odwoluje
    ("nie podrozuje", "cancel"),
])
def test_route_choice_ascii(text, expected):
    assert detect_route_choice(text) == expected


@pytest.mark.parametrize("text", [
    "podazam do wsi",     # podążam
    "prbuje... probuje przejsc",  # próbuję
    "wracam do obozu",
])
def test_move_verb_ascii(text):
    assert _PT3_MOVE_VERB_RE.search(strip_pl_diacritics(text)) is not None


@pytest.mark.parametrize("text", [
    "uzyj wytrychu",           # użyj
    "tworze miksture",         # tworzę
    "lecze rany",              # leczę
    "napraw zbroje",           # napraw
])
def test_skill_verb_hint_ascii(text):
    assert _SKILL_VERB_HINT.search(strip_pl_diacritics(text)) is not None


def test_skill_verb_hint_diacritic_equivalence():
    # #1420 — kluczowe: ASCII i wersja z ogonkami dają TEN SAM wynik.
    for pl, ascii_ in [("użyj wytrychu", "uzyj wytrychu"),
                       ("leczę rany", "lecze rany"),
                       ("tworzę miksturę", "tworze miksture")]:
        assert bool(_SKILL_VERB_HINT.search(strip_pl_diacritics(pl))) == \
               bool(_SKILL_VERB_HINT.search(strip_pl_diacritics(ascii_)))


@pytest.mark.parametrize("text,food,drink", [
    ("zamawiam posilek", True, False),     # posiłek
    ("place za sniadanie", True, False),   # płacę śniadanie
    ("prosze o gorzale", False, True),     # proszę gorzałę
])
def test_food_drink_ascii(text, food, drink):
    n = strip_pl_diacritics(text)
    assert SG._FOOD_ORDER_VERB_RE.search(n) is not None
    assert bool(SG._FOOD_NOUN_RE.search(n)) == food
    assert bool(SG._DRINK_NOUN_RE.search(n)) == drink
