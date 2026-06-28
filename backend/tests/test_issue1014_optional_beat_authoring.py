"""TDD: Issue #1014 — GM-plan authoring: flaga beatu `optional` w Forge/szablonie.

Runtime od #1010/#1012 honoruje już `optional` (akt zamyka się po beatach krytycznych,
walidator scen-sierot pomija opcjonalne). #1017 zrobił beaty strukturą `PlotBeat`.
Brakowało WEJŚCIA DANYCH: edytor szablonu w Forge zapisywał `gm_plan_json` surowo,
więc beat dodany w UI nie dostawał `beat_key` (silnik go potrzebuje) ani nie miał gdzie
osadzić flagi `optional`.

Ten ticket dokłada `normalize_plan_beats()` — odpalany przy zapisie szablonu — który:
  • nadaje każdemu beatowi stabilny, unikalny w planie `beat_key` (slug z summary),
  • zachowuje `optional` (default False), akceptuje gołe stringi (legacy),
  • + checkbox „Scena opcjonalna" w UI Forge (Playwright).
"""
import pytest

from app.services.campaign_plan_service import normalize_plan_beats
from app.services.campaign_plan_runtime import find_orphan_beats


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_normalize_derives_beat_keys_and_preserves_optional():
    """Beat dodany w UI (dict bez beat_key) dostaje klucz; `optional` przetrwa zapis."""
    plan = {"acts": [{
        "number": 1, "title": "Akt I", "summary": "s",
        "key_beats": [
            {"summary": "Zbadaj opuszczoną wieżę", "optional": True},
            {"summary": "Pokonaj nekromantę", "objective_type": "kill_enemy",
             "objective_value": "nekromanta"},
        ],
    }]}

    out = normalize_plan_beats(plan)
    beats = out["acts"][0]["key_beats"]

    # każdy beat to obiekt z niepustym beat_key
    assert all(isinstance(b, dict) and b["beat_key"] for b in beats)
    # flaga optional zachowana dokładnie tak jak ustawił projektant
    assert beats[0]["optional"] is True
    assert beats[1]["optional"] is False
    # objective przeszedł bez szwanku
    assert beats[1]["objective_type"] == "kill_enemy"
    assert beats[1]["objective_value"] == "nekromanta"


def test_normalize_keeps_beat_keys_unique_plan_wide():
    """Dwa beaty o tym samym summary → różne beat_key (silnik zakłada unikalność)."""
    plan = {"acts": [
        {"number": 1, "title": "I", "summary": "", "key_beats": [{"summary": "Spotkanie"}]},
        {"number": 2, "title": "II", "summary": "", "key_beats": [{"summary": "Spotkanie"}]},
    ]}
    out = normalize_plan_beats(plan)
    keys = [out["acts"][0]["key_beats"][0]["beat_key"],
            out["acts"][1]["key_beats"][0]["beat_key"]]
    assert keys[0] != keys[1]
    assert len(set(keys)) == 2


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_legacy_string_beats_default_optional_false():
    """Gołe stringi (stary format) → obiekt z optional=False, bez zmiany zachowania."""
    plan = {"acts": [{"number": 1, "title": "I", "summary": "",
                      "key_beats": ["Wyrusz w drogę", "Dotrzyj do miasta"]}]}
    out = normalize_plan_beats(plan)
    beats = out["acts"][0]["key_beats"]
    assert [b["optional"] for b in beats] == [False, False]
    assert all(b["beat_key"] for b in beats)


def test_normalize_tolerates_planless_input():
    """Brak acts / nie-dict → zwróć wejście bez wybuchu (default-safe)."""
    assert normalize_plan_beats(None) is None
    assert normalize_plan_beats({}) == {}
    assert normalize_plan_beats({"acts": "nope"}) == {"acts": "nope"}


def test_orphan_validator_ignores_optional_beats():
    """Regresja #1010: walidator scen-sierot NIE zgłasza beatów optional."""
    plan = {"acts": [{"key_beats": [
        {"beat_key": "poboczna", "summary": "x", "optional": True},   # pomijalna → nie sierota
        {"beat_key": "glowna", "summary": "y"},                       # krytyczna, bez celu → sierota
    ]}]}
    assert find_orphan_beats(plan) == ["glowna"]
