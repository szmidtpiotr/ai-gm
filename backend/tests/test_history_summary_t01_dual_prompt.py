"""T01 — dual rollup prompt (single JSON) parsing and leak heuristic."""

import json
import unittest

from app.services.history_summary_dual_prompt import (
    build_dual_single_messages,
    leaked_plan_tokens_in_player_summary,
    parse_dual_json_response,
    plan_tokens_not_in_transcript,
)


class TestParseDualJson(unittest.TestCase):
    def test_plain_json(self):
        raw = json.dumps(
            {"player_summary": "Był w karczmie.", "gm_notes": "Hak: Zalthor czeka."},
            ensure_ascii=False,
        )
        ps, gn = parse_dual_json_response(raw)
        self.assertIn("karczmie", ps)
        self.assertIn("Zalthor", gn)

    def test_json_with_fence(self):
        inner = json.dumps(
            {"player_summary": "Recap.", "gm_notes": "Notatka."},
            ensure_ascii=False,
        )
        raw = "```json\n" + inner + "\n```"
        ps, gn = parse_dual_json_response(raw)
        self.assertEqual(ps, "Recap.")
        self.assertEqual(gn, "Notatka.")


class TestLeakHeuristic(unittest.TestCase):
    def test_detects_plan_only_name_in_player_summary(self):
        transcript = "Gracz rozmawiał z Jankiem w lesie."
        gm_plan = "Główny antagonista to Zalthor; spotka ich w rozdziale 3."
        player_bad = "Gracz spotkał Zalthora w lesie."
        leaks = leaked_plan_tokens_in_player_summary(player_bad, gm_plan, transcript)
        self.assertIn("zalthor", leaks)

    def test_no_false_positive_when_name_in_transcript(self):
        transcript = "Zalthor ukazał się w drzwiach."
        gm_plan = "Zalthor ma brata Velkora."
        player_ok = "Zalthor był w drzwiach."
        leaks = leaked_plan_tokens_in_player_summary(player_ok, gm_plan, transcript)
        self.assertNotIn("zalthor", leaks)
        # velkora only in plan — if model puts it in player text, flag
        self.assertIn("velkora", plan_tokens_not_in_transcript(gm_plan, transcript))


class TestBuildMessages(unittest.TestCase):
    def test_includes_plan_block(self):
        msgs = build_dual_single_messages(
            transcript="MG: Witajcie.",
            gm_plan_excerpt='{"roadmap": "test"}',
        )
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("[PLAN_MG]", msgs[1]["content"])
        self.assertIn("Witajcie", msgs[1]["content"])

    def test_empty_plan(self):
        msgs = build_dual_single_messages(transcript="A.", gm_plan_excerpt=None)
        self.assertIn("(brak)", msgs[1]["content"])
