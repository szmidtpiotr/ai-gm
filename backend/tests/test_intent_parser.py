"""
Tests for Intent Parser — V2 Phase 01 Task 02

Tests the tag parsing, structured action detection, and clarification
suggestion generation WITHOUT making real LLM calls (uses mock).

For full LLM acceptance tests (the 15 cases from the spec), run with
AI_TEST_MODE=1 and a live LLM endpoint.
"""

import pytest
from unittest.mock import patch

from app.services.intent_parser import (
    ParsedIntent,
    _parse_tag,
    is_structured_action,
    parse_structured_action,
    generate_clarification_suggestions,
    VALID_ACTION_TYPES,
)

# ── _parse_tag unit tests ────────────────────────────────────────────────────

class TestParseTag:
    def test_simple_action_no_params(self):
        result = _parse_tag("[ACTION:FLEE]")
        assert result is not None
        assert result.action_type == "FLEE"
        assert result.params == {}

    def test_action_with_single_param(self):
        result = _parse_tag("[ACTION:ATTACK:target=goblin_1]")
        assert result is not None
        assert result.action_type == "ATTACK"
        assert result.params["target"] == "goblin_1"

    def test_action_with_multiple_params(self):
        result = _parse_tag("[ACTION:ATTACK:target=goblin_2:weapon=sword_iron]")
        assert result is not None
        assert result.action_type == "ATTACK"
        assert result.params["target"] == "goblin_2"
        assert result.params["weapon"] == "sword_iron"

    def test_clarify_tag(self):
        result = _parse_tag("[CLARIFY:reason=multiple_targets_ambiguous]")
        assert result is not None
        assert result.action_type == "CLARIFY"
        assert result.params["reason"] == "multiple_targets_ambiguous"

    def test_blocked_tag(self):
        result = _parse_tag("[BLOCKED:reason=action_unclear]")
        assert result is not None
        assert result.action_type == "BLOCKED"
        assert result.params["reason"] == "action_unclear"

    def test_invalid_format_returns_none(self):
        assert _parse_tag("The player attacks the goblin.") is None
        assert _parse_tag("") is None
        assert _parse_tag("ATTACK goblin_1") is None
        assert _parse_tag("[INVALID_TYPE:foo=bar]") is None

    def test_case_insensitive_type(self):
        result = _parse_tag("[ACTION:attack:target=goblin_1]")
        assert result is not None
        assert result.action_type == "ATTACK"

    def test_strips_surrounding_whitespace(self):
        result = _parse_tag("  [ACTION:FLEE]  ")
        assert result is not None
        assert result.action_type == "FLEE"

    def test_all_action_types_parse(self):
        for action_type in VALID_ACTION_TYPES:
            tag = f"[ACTION:{action_type}]"
            result = _parse_tag(tag)
            assert result is not None, f"Failed to parse: {tag}"
            assert result.action_type == action_type

    def test_movement_with_destination(self):
        result = _parse_tag("[ACTION:MOVEMENT:destination_key=loc_cave_entrance]")
        assert result is not None
        assert result.params["destination_key"] == "loc_cave_entrance"

    def test_dialogue_with_npc_and_topic(self):
        result = _parse_tag("[ACTION:DIALOGUE:npc_key=innkeeper_boris:topic=guild]")
        assert result is not None
        assert result.params["npc_key"] == "innkeeper_boris"
        assert result.params["topic"] == "guild"

    def test_rest_short(self):
        result = _parse_tag("[ACTION:REST:rest_type=short]")
        assert result is not None
        assert result.params["rest_type"] == "short"

    def test_search_with_focus(self):
        result = _parse_tag("[ACTION:SEARCH:focus=clues]")
        assert result is not None
        assert result.params["focus"] == "clues"


# ── is_structured_action ─────────────────────────────────────────────────────

class TestIsStructuredAction:
    def test_structured_payloads_detected(self):
        assert is_structured_action("ACTION:FLEE") is True
        assert is_structured_action("ACTION:ATTACK:target=goblin_1") is True
        assert is_structured_action("[ACTION:FLEE]") is True

    def test_free_text_not_structured(self):
        assert is_structured_action("Atakuję goblin mieczem!") is False
        assert is_structured_action("I attack") is False
        assert is_structured_action("") is False


# ── parse_structured_action ──────────────────────────────────────────────────

class TestParseStructuredAction:
    def test_button_flee(self):
        result = parse_structured_action("ACTION:FLEE")
        assert result.action_type == "FLEE"
        assert result.params == {}

    def test_button_attack_with_params(self):
        result = parse_structured_action("ACTION:ATTACK:target=goblin_1:weapon=sword_iron")
        assert result.action_type == "ATTACK"
        assert result.params["target"] == "goblin_1"

    def test_already_bracketed(self):
        result = parse_structured_action("[ACTION:REST:rest_type=long]")
        assert result.action_type == "REST"
        assert result.params["rest_type"] == "long"


# ── generate_clarification_suggestions ──────────────────────────────────────

class TestClarificationSuggestions:
    def test_combat_state_suggests_attacks(self):
        roster = [
            {"key": "goblin_1", "name": "Goblin Strażnik", "hp": 12},
            {"key": "goblin_2", "name": "Goblin Szaman", "hp": 18},
        ]
        suggestions = generate_clarification_suggestions("COMBAT", roster, [], [])
        assert len(suggestions) <= 3
        assert any("Goblin Strażnik" in s for s in suggestions)
        assert any("uciec" in s.lower() for s in suggestions)

    def test_narrative_state_suggests_npc_and_exits(self):
        npcs = [{"key": "innkeeper_boris", "name": "Boris"}]
        exits = ["loc_market", "loc_alley"]
        suggestions = generate_clarification_suggestions("NARRATIVE", [], npcs, exits)
        assert len(suggestions) <= 3
        assert any("Boris" in s for s in suggestions)

    def test_max_three_suggestions(self):
        roster = [{"key": f"g{i}", "name": f"Goblin {i}", "hp": 10} for i in range(10)]
        suggestions = generate_clarification_suggestions("COMBAT", roster, [], [])
        assert len(suggestions) <= 3

    def test_empty_context_returns_fallback(self):
        suggestions = generate_clarification_suggestions("UNKNOWN_STATE", [], [], [])
        assert len(suggestions) >= 1


# ── parse_intent with mocked LLM ─────────────────────────────────────────────

class TestParseIntentMocked:
    """Tests parse_intent() by mocking the LLM call."""

    _BASE_KWARGS = dict(
        game_state="COMBAT",
        current_location_key="loc_forest_clearing",
        current_location_name="Forest Clearing",
        combat_roster=[
            {"key": "goblin_1", "name": "Goblin Strażnik", "hp": 12},
            {"key": "goblin_2", "name": "Goblin Szaman", "hp": 18},
        ],
        npcs_present=[],
        inventory_keys=["sword_iron", "potion_minor_healing"],
        available_destination_keys=["loc_forest_path", "loc_cave_entrance"],
        loot_available_keys=[],
    )

    def _call(self, message: str, llm_response: str):
        from app.services.intent_parser import parse_intent
        with patch("app.services.intent_parser._call_llm", return_value=llm_response):
            return parse_intent(player_message=message, **self._BASE_KWARGS)

    def test_attack_with_target(self):
        result = self._call(
            "Atakuję szamana mieczem!",
            "[ACTION:ATTACK:target=goblin_2:weapon=sword_iron]"
        )
        assert result.action_type == "ATTACK"
        assert result.params["target"] == "goblin_2"
        assert result.params["weapon"] == "sword_iron"

    def test_flee(self):
        result = self._call("Próbuję uciec!", "[ACTION:FLEE]")
        assert result.action_type == "FLEE"
        assert result.params == {}

    def test_item_use(self):
        result = self._call("Piję miksturę", "[ACTION:ITEM_USE:item_key=potion_minor_healing]")
        assert result.action_type == "ITEM_USE"
        assert result.params["item_key"] == "potion_minor_healing"

    def test_ambiguous_attack_returns_clarify(self):
        result = self._call("Atakuję", "[CLARIFY:reason=multiple_targets_ambiguous]")
        assert result.action_type == "CLARIFY"
        assert result.params["reason"] == "multiple_targets_ambiguous"

    def test_ooc_returns_blocked(self):
        result = self._call("What are my options?", "[BLOCKED:reason=action_unclear]")
        assert result.action_type == "BLOCKED"

    def test_retry_on_bad_first_response(self):
        """First LLM call returns prose; second returns correct tag."""
        from app.services.intent_parser import parse_intent
        call_count = 0

        def mock_llm(messages, llm_config):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "The player attacks the goblin."  # bad output
            return "[ACTION:ATTACK:target=goblin_1]"     # correct on retry

        with patch("app.services.intent_parser._call_llm", side_effect=mock_llm):
            result = parse_intent(player_message="I attack", **self._BASE_KWARGS)

        assert result.action_type == "ATTACK"
        assert result.attempt_number == 2
        assert call_count == 2

    def test_both_attempts_fail_returns_clarify(self):
        """Both LLM calls return prose; parser returns CLARIFY with parsing_failed=True."""
        from app.services.intent_parser import parse_intent
        with patch("app.services.intent_parser._call_llm", return_value="I am not sure."):
            result = parse_intent(player_message="???", **self._BASE_KWARGS)

        assert result.action_type == "CLARIFY"
        assert result.params["reason"] == "action_unclear"
        assert result.parsing_failed is True

    def test_movement_with_destination(self):
        result = self._call(
            "Chcę iść do jaskini",
            "[ACTION:MOVEMENT:destination_key=loc_cave_entrance]"
        )
        assert result.action_type == "MOVEMENT"
        assert result.params["destination_key"] == "loc_cave_entrance"

    def test_search_focus(self):
        result = self._call("Szukam wyjścia", "[ACTION:SEARCH:focus=exits]")
        assert result.action_type == "SEARCH"
        assert result.params["focus"] == "exits"

    def test_stealth_attempt(self):
        result = self._call("Chcę się schować za drzewem", "[ACTION:STEALTH_ATTEMPT]")
        assert result.action_type == "STEALTH_ATTEMPT"
