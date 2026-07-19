"""G6 — Odporność narracji (#1468, #1469).

Unit tests for the narrative-resilience hardening:
  #1468 — broken JSON envelope still yields clean narrative (no leaked braces).
  #1469 — [DEATH_TRIGGER] is parsed and stripped, and never leaks to the player.
"""
import pytest

from app.api.turns import _extract_narrative_for_cues
from app.services.llm_tag_parser import (
    TAG_REGISTRY,
    parse_death_trigger,
    strip_all_mechanic_tags,
)


# ── #1468 ─────────────────────────────────────────────────────────────────────

def test_broken_json_envelope_extracts_narrative():
    """A hard-broken JSON envelope (gemma) must still surface clean prose, never
    the raw `{"narrative": ...` scaffold."""
    # Truncated / unbalanced envelope with an escaped quote inside the value.
    broken = '{"narrative": "Wchodzisz do jaskini \\"Echo\\" i słyszysz kapanie.", "location_intent":'
    narrative, parsed = _extract_narrative_for_cues(broken)

    assert 'Wchodzisz do jaskini' in narrative
    assert 'Echo' in narrative
    # escaped quote decoded back to a real quote
    assert '"Echo"' in narrative
    # no JSON scaffold leaked to the player
    assert not narrative.lstrip().startswith('{')
    assert '"narrative"' not in narrative
    assert 'location_intent' not in narrative
    # broken → cannot repack, so parsed dict is None
    assert parsed is None


def test_valid_json_envelope_unchanged():
    """Valid envelopes keep the existing behaviour: narrative + parsed dict."""
    good = '{"narrative": "Ruszasz w drogę.", "location_intent": null}'
    narrative, parsed = _extract_narrative_for_cues(good)
    assert narrative == "Ruszasz w drogę."
    assert isinstance(parsed, dict)
    assert parsed.get("location_intent") is None


def test_plain_text_narrative_unchanged():
    """Plain (non-JSON) narration passes through untouched."""
    plain = "Stoisz na skraju lasu. Wiatr niesie zapach dymu."
    narrative, parsed = _extract_narrative_for_cues(plain)
    assert narrative == plain
    assert parsed is None


def test_broken_json_no_narrative_field_strips_brace():
    """Broken envelope with no recoverable narrative field: drop the leading brace
    so no JSON opening reaches the player."""
    broken = '{ Coś poszło nie tak z odpowiedzią modelu.'
    narrative, parsed = _extract_narrative_for_cues(broken)
    assert not narrative.lstrip().startswith('{')
    assert 'Coś poszło nie tak' in narrative
    assert parsed is None


# ── #1469 ─────────────────────────────────────────────────────────────────────

def test_death_trigger_parsed_and_stripped():
    """[DEATH_TRIGGER] is a registered tag, is detected by the parser, and is
    removed from player-visible text."""
    assert "DEATH_TRIGGER" in TAG_REGISTRY

    text = "Lawa pochłania cię w całości. [DEATH_TRIGGER]"
    present, reason = parse_death_trigger(text)
    assert present is True
    assert reason is None  # bare form → no reason

    cleaned = strip_all_mechanic_tags(text)
    assert "[DEATH_TRIGGER]" not in cleaned
    assert "DEATH_TRIGGER" not in cleaned
    assert "Lawa pochłania cię w całości." in cleaned


def test_death_trigger_with_reason_parsed():
    """`[DEATH_TRIGGER: reason]` exposes the narrative cause and is stripped."""
    text = "Spadasz w przepaść. [DEATH_TRIGGER: upadek z klifu]"
    present, reason = parse_death_trigger(text)
    assert present is True
    assert reason == "upadek z klifu"
    assert "DEATH_TRIGGER" not in strip_all_mechanic_tags(text)


def test_death_trigger_not_leaked():
    """Neither the bare nor the reason form ever leaks to the player, and prose
    is preserved."""
    for raw in (
        "Toniesz w lodowatej wodzie. [DEATH_TRIGGER]",
        "Trucizna dopełnia dzieła. [DEATH_TRIGGER: jad]",
        "Koniec drogi.[DEATH_TRIGGER]",
    ):
        cleaned = strip_all_mechanic_tags(raw)
        assert "DEATH_TRIGGER" not in cleaned
        assert "[" not in cleaned  # no dangling bracket residue
        # the sentence before the tag survives
        assert cleaned.split(".")[0] in cleaned


def test_no_false_positive_death_trigger():
    """Ordinary prose (no tag) is not detected as a death trigger."""
    present, reason = parse_death_trigger("Bohater ledwo uchodzi z życiem.")
    assert present is False
    assert reason is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
