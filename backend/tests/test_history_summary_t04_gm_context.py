"""T04 — GM rollup uses transcript plus gm_plan_json context."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.gm_plan_schema import format_gm_plan_block
from app.services.history_summary_service import (
    GM_SUMMARY_SYSTEM_APPEND,
    SUMMARY_AUDIENCE_GM,
    generate_campaign_summary,
)


class _DummyConn:
    row_factory = None

    def close(self) -> None:
        return None


class TestGenerateCampaignSummaryGmAudience(unittest.TestCase):
    def test_gm_audience_does_not_get_player_only_append(self):
        captured: dict = {}

        def _fake_generate_chat(messages, model=None, llm_config=None):
            captured["messages"] = messages
            return "Notatka."

        with (
            patch("app.services.history_summary_service.sqlite3.connect", return_value=_DummyConn()),
            patch(
                "app.services.history_summary_service._fetch_campaign",
                return_value={
                    "id": 1,
                    "title": "Kampania testowa",
                    "language": "pl",
                    "model_id": "",
                    "gm_plan_json": '{"secret":"Zalthor"}',
                },
            ),
            patch(
                "app.services.history_summary_service.fetch_narrative_turns",
                return_value=[
                    {
                        "turn_number": 1,
                        "user_text": "Idę do portu.",
                        "assistant_text": "Nad zatoką unosi się mgła.",
                        "created_at": "2026-05-04T10:00:00",
                    }
                ],
            ),
            patch(
                "app.services.history_summary_service.get_user_llm_settings_full",
                return_value={"model": "mock-model"},
            ),
            patch("app.services.history_summary_service.generate_chat", side_effect=_fake_generate_chat),
        ):
            result = generate_campaign_summary(
                campaign_id=1,
                user_id=7,
                audience=SUMMARY_AUDIENCE_GM,
            )

        messages = captured["messages"]
        self.assertEqual(result["audience"], "gm")
        self.assertNotIn("AUDIENCE: PLAYER", messages[0]["content"])
        self.assertIn("AUDIENCE: GM", messages[0]["content"])

    def test_gm_audience_includes_formatted_plan_block(self):
        captured: dict = {}
        gm_plan = (
            '{"roadmap":"Zamieszki w porcie",'
            '"scene_goals":["Podkręcić napięcie","Wprowadzić Zalthora"],'
            '"hooks":{"npcs":["Zalthor"],"locations":["Port"]},'
            '"current_scene_ordinal":3}'
        )

        def _fake_generate_chat(messages, model=None, llm_config=None):
            captured["messages"] = messages
            return "Prywatna notatka MG."

        with (
            patch("app.services.history_summary_service.sqlite3.connect", return_value=_DummyConn()),
            patch(
                "app.services.history_summary_service._fetch_campaign",
                return_value={
                    "id": 1,
                    "title": "Kampania testowa",
                    "language": "pl",
                    "model_id": "",
                    "gm_plan_json": gm_plan,
                },
            ),
            patch(
                "app.services.history_summary_service.fetch_narrative_turns",
                return_value=[
                    {
                        "turn_number": 1,
                        "user_text": "Idę do portu.",
                        "assistant_text": "W porcie jest tłok.",
                        "created_at": "2026-05-04T10:00:00",
                    }
                ],
            ),
            patch(
                "app.services.history_summary_service.get_user_llm_settings_full",
                return_value={"model": "mock-model"},
            ),
            patch("app.services.history_summary_service.generate_chat", side_effect=_fake_generate_chat),
        ):
            result = generate_campaign_summary(
                campaign_id=1,
                user_id=7,
                audience=SUMMARY_AUDIENCE_GM,
            )

        formatted = format_gm_plan_block(gm_plan)
        messages = captured["messages"]
        self.assertEqual(result["summary"], "Prywatna notatka MG.")
        self.assertEqual(result["audience"], "gm")
        self.assertIn(GM_SUMMARY_SYSTEM_APPEND.splitlines()[0], messages[0]["content"])
        self.assertIn("[PLAN_MG]", messages[1]["content"])
        self.assertIn(formatted, messages[1]["content"])
        self.assertIn("[TRANSKRYPT]", messages[1]["content"])


class TestFormatGmPlanBlockGmSummary(unittest.TestCase):
    def test_formats_expected_sections(self):
        raw = (
            '{"roadmap":"Ucieczka z twierdzy",'
            '"scene_goals":["Zdobyć klucz"],'
            '"hooks":{"npcs":["Strażnik"],"locations":["Loch"]},'
            '"current_scene_ordinal":2}'
        )
        formatted = format_gm_plan_block(raw)
        self.assertIn("## Plan / roadmap MG", formatted)
        self.assertIn("## Cele bieżącego odcinka / sceny", formatted)
        self.assertIn("## Haki fabularne", formatted)
        self.assertIn("## Licznik odcinka (MG): 2", formatted)
        self.assertIn("## Aktywny łuk (MG): default", formatted)


if __name__ == "__main__":
    unittest.main()
