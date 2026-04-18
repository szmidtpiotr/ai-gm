"""GM narrative prompt: death-save mechanica injection and stabilization hints."""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Avoid pulling optional HTTP deps when running tests without full venv.
if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from app.services.game_engine import build_narrative_messages


class _Row(dict):
    """Minimal row-like object for campaign/character."""

    def __getitem__(self, k):
        return self.get(k)


def _campaign():
    return _Row({"id": 1, "system_id": "fantasy", "language": "pl"})


def _char(failures: int):
    sheet = {"death_save_failures": failures}
    return _Row({"name": "Hero", "sheet_json": json.dumps(sheet)})


class TestDeathMechanica(unittest.TestCase):
    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_appended_when_failures_one_or_two(self, _, __):
        conn = MagicMock()
        msgs = build_narrative_messages(
            conn,
            _campaign(),
            _char(1),
            "Co widzę?",
            None,
            None,
        )
        self.assertEqual(msgs[0]["role"], "system")
        c = msgs[0]["content"]
        self.assertIn("[MECHANIKA — STAN ŚMIERCI]", c)
        self.assertIn("Roll Death Save d20", c)

    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_not_appended_on_death_save_roll_turn(self, _, __):
        conn = MagicMock()
        roll = {
            "test": "death_save",
            "total": 5,
            "raw": 5,
            "is_nat20": False,
            "is_nat1": False,
            "stat_mod": 0,
            "skill_rank": 0,
            "proficiency": 0,
        }
        msgs = build_narrative_messages(
            conn,
            _campaign(),
            _char(1),
            "roll",
            None,
            roll,
        )
        self.assertNotIn("[MECHANIKA — STAN ŚMIERCI]", msgs[0]["content"])

    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_not_appended_when_healthy(self, _, __):
        conn = MagicMock()
        msgs = build_narrative_messages(
            conn,
            _campaign(),
            _char(0),
            "hello",
            None,
            None,
        )
        self.assertNotIn("[MECHANIKA — STAN ŚMIERCI]", msgs[0]["content"])

    @patch("app.services.game_engine.build_runtime_config_block", return_value="")
    @patch("app.services.game_engine.loadrecentturns", return_value=[])
    def test_death_save_success_adds_stabilization_note(self, _, __):
        conn = MagicMock()
        roll = {
            "test": "death_save",
            "total": 12,
            "raw": 12,
            "is_nat20": False,
            "is_nat1": False,
            "stat_mod": 0,
            "skill_rank": 0,
            "proficiency": 0,
        }
        msgs = build_narrative_messages(
            conn,
            _campaign(),
            _char(2),
            "roll result",
            None,
            roll,
        )
        c = msgs[0]["content"]
        self.assertIn("[USTABILIZOWANIE]", c)
        self.assertIn("death_save_failures = 0", c)


class TestHelpmePromptFile(unittest.TestCase):
    def test_is_ooc_not_old_atmospheric_rules(self):
        root = os.path.join(os.path.dirname(__file__), "..", "prompts", "helpme-gm.txt")
        with open(root, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("narratorem", text.lower())
        self.assertNotIn("Opisz SYTUACJĄ", text)


if __name__ == "__main__":
    unittest.main()
