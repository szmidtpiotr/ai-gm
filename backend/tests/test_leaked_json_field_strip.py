"""Regression: LLM leaks a bare `location_intent: null` line inside the narrative
string (observed on gpt-5.4). The JSON envelope is valid and the field is parsed
from its real top-level position, but the duplicated bare line inside `narrative`
was shown verbatim to the player. strip_leaked_json_fields removes such lines
without touching ordinary prose (which legitimately contains colons)."""

from app.services.llm_tag_parser import strip_leaked_json_fields


def test_strips_bare_location_intent_line():
    narr = (
        "Godziny w kuźni wloką się w rytmie młota.\n\n"
        "Wiesz już, dokąd chcesz iść: pod młyn, gdzie zbierają się ludzie Harla. \n\n"
        "location_intent: null"
    )
    out = strip_leaked_json_fields(narr)
    assert "location_intent" not in out
    # Prose with a legitimate colon survives.
    assert "dokąd chcesz iść: pod młyn" in out
    assert out.endswith("ludzie Harla.")


def test_strips_various_leaked_fields():
    narr = "Idziesz dalej.\nroll_cue: Roll Stealth d20\nadvance_to_time_of_day: dusk"
    out = strip_leaked_json_fields(narr)
    assert "roll_cue" not in out
    assert "advance_to_time_of_day" not in out
    assert out == "Idziesz dalej."


def test_prose_colon_never_stripped():
    narr = "— Mówię ci wprost: nie idź tam.\nToma szepcze: uważaj."
    out = strip_leaked_json_fields(narr)
    assert out == narr  # no envelope keys → untouched


def test_empty_and_none():
    assert strip_leaked_json_fields("") == ""
    assert strip_leaked_json_fields(None) == ""
