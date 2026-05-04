"""T05 — initial gm_plan LLM generation + json extract."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.services.gm_plan_generation_service import (
    extract_first_json_object,
    generate_initial_gm_plan_with_retries,
)
from app.services.gm_plan_schema import gm_plan_is_ready


class TestExtractJson(unittest.TestCase):
    def test_fenced(self):
        text = '```json\n{"roadmap": "A", "scene_goals": ["b"], "hooks": {"npcs": ["x"]}, "title": "T"}\n```'
        d = extract_first_json_object(text)
        self.assertIsNotNone(d)
        assert d is not None
        self.assertEqual(d.get("roadmap"), "A")


class TestGenerateInitialPlan(unittest.TestCase):
    def test_persists_on_valid_llm_response(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE campaigns (
                id INTEGER PRIMARY KEY,
                gm_plan_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, '{}')")

        llm_json = json.dumps(
            {
                "roadmap": "Fabularny szkielet.",
                "scene_goals": ["Cel 1", "Cel 2"],
                "hooks": {"npcs": ["Jan"], "locations": ["Port"]},
                "title": "Start",
            },
            ensure_ascii=False,
        )

        def _fake_chat(messages, model=None, llm_config=None):
            return llm_json

        with patch(
            "app.services.gm_plan_generation_service.generate_chat",
            side_effect=_fake_chat,
        ):
            ok, err = generate_initial_gm_plan_with_retries(
                conn,
                campaign_id=1,
                campaign_title="T",
                campaign_language="pl",
                system_id="test",
                char_summary="Postać: X.",
                user_id=1,
                model="mock",
                llm_config={},
                max_attempts=2,
            )

        self.assertTrue(ok)
        self.assertIsNone(err)
        row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
        self.assertTrue(gm_plan_is_ready(row["gm_plan_json"]))
        conn.close()


if __name__ == "__main__":
    unittest.main()
