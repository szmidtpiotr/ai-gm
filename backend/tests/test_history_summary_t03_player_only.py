"""T03 — player rollup uses transcript only and never relies on gm_plan_json."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.history_summary_service import (
    PLAYER_SUMMARY_SYSTEM_APPEND,
    SUMMARY_AUDIENCE_PLAYER,
    generate_campaign_summary,
)


class _DummyConn:
    row_factory = None

    def close(self) -> None:
        return None


class TestGenerateCampaignSummaryAudience(unittest.TestCase):
    def test_player_audience_uses_transcript_only_prompt(self):
        captured: dict = {}
        secret = "Sekretny NPC: Zalthor"

        def _fake_generate_chat(messages, model=None, llm_config=None):
            captured["messages"] = messages
            captured["model"] = model
            captured["llm_config"] = llm_config
            return "Jawny recap."

        with (
            patch("app.services.history_summary_service.sqlite3.connect", return_value=_DummyConn()),
            patch(
                "app.services.history_summary_service._fetch_campaign",
                return_value={
                    "id": 1,
                    "title": "Kampania testowa",
                    "language": "pl",
                    "model_id": "",
                    "gm_plan_json": secret,
                },
            ),
            patch(
                "app.services.history_summary_service.fetch_narrative_turns",
                return_value=[
                    {
                        "turn_number": 1,
                        "user_text": "Rozmawiam z karczmarzem.",
                        "assistant_text": "Karczmarz wskazuje drogę do młyna.",
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
                max_turns=50,
                audience=SUMMARY_AUDIENCE_PLAYER,
            )

        messages = captured["messages"]
        self.assertEqual(result["summary"], "Jawny recap.")
        self.assertEqual(result["audience"], "player")
        self.assertIn("AUDIENCE: PLAYER", messages[0]["content"])
        self.assertIn(PLAYER_SUMMARY_SYSTEM_APPEND.splitlines()[0], messages[0]["content"])
        self.assertIn("Rozmawiam z karczmarzem.", messages[1]["content"])
        self.assertNotIn(secret, messages[1]["content"])

if __name__ == "__main__":
    unittest.main()
