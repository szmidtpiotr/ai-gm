"""T15 — nowy akt po ukończeniu głównego questa (ten sam campaign_id)."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.services.gm_plan_schema import normalize_gm_plan
from app.services.new_act_service import (
    main_quest_just_completed,
    maybe_trigger_new_act_after_main_quest,
    resolve_main_quest_key,
)


def _ready_plan_json() -> str:
    plan = normalize_gm_plan("{}")
    plan["arcs"]["default"] = {
        "id": "default",
        "title": "Start",
        "status": "active",
        "roadmap": "Łuk otwierający.",
        "scene_goals": ["Cel A"],
        "hooks": {"npcs": ["NPC1"], "locations": ["Miasto"]},
    }
    plan["active_arc_id"] = "default"
    plan["engine_private"] = {"next_act_seq": 2}
    return json.dumps(plan, ensure_ascii=False)


class TestMainQuestDetection(unittest.TestCase):
    def test_just_completed(self):
        old = {"quests_completed": []}
        new = {"quests_completed": ["main_quest"]}
        self.assertTrue(main_quest_just_completed(old, new, "main_quest"))

    def test_already_completed_no_repeat(self):
        old = {"quests_completed": ["main_quest"]}
        new = {"quests_completed": ["main_quest"]}
        self.assertFalse(main_quest_just_completed(old, new, "main_quest"))

    def test_resolve_main_quest_key_default(self):
        p = normalize_gm_plan("{}")
        self.assertEqual(resolve_main_quest_key(p), "main_quest")


class TestNewActPipeline(unittest.TestCase):
    def test_maybe_trigger_updates_plan_and_turn(self):
        plan_llm = json.dumps(
            {
                "roadmap": "Drugi łuk fabularny.",
                "scene_goals": ["Cel nowej sceny"],
                "hooks": {"npcs": ["Zoja"], "locations": ["Port"]},
                "title": "Następny rozdział",
            },
            ensure_ascii=False,
        )
        bridge = "Most narracyjny łączy przeszłość z nowym tropem."

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE campaigns (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    system_id TEXT,
                    model_id TEXT,
                    language TEXT,
                    owner_user_id INTEGER,
                    gm_plan_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT DEFAULT 'active'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE characters (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER,
                    sheet_json TEXT,
                    name TEXT,
                    location TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE campaign_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    character_id INTEGER,
                    user_text TEXT,
                    assistant_text TEXT,
                    route TEXT,
                    turn_number INTEGER
                )
                """
            )
            conn.execute(
                """
                INSERT INTO campaigns (id, title, system_id, model_id, language, owner_user_id, gm_plan_json, status)
                VALUES (1, 'Test', 'sys', 'mock', 'pl', 1, ?, 'active')
                """,
                (_ready_plan_json(),),
            )
            conn.execute(
                """
                INSERT INTO characters (id, campaign_id, sheet_json, name, location)
                VALUES (1, 1, '{"archetype":"warrior","max_hp":10}', 'Hero', 'Miasto')
                """
            )
            conn.execute(
                """
                INSERT INTO campaign_turns (campaign_id, character_id, user_text, assistant_text, route, turn_number)
                VALUES (1, 1, 'Idę naprzód.', 'MG opisuje drogę.', 'narrative', 1)
                """
            )
            conn.commit()
            conn.close()

            old_sheet: dict = {"quests_completed": [], "quests_active": ["main_quest"]}
            new_sheet: dict = {"quests_completed": ["main_quest"], "quests_active": []}

            with patch("app.services.new_act_service.DB_PATH", path):
                with patch(
                    "app.services.new_act_service.get_user_llm_settings_full",
                    return_value={"model": "mock"},
                ):
                    with patch(
                        "app.services.new_act_service.generate_chat",
                        side_effect=[plan_llm, bridge],
                    ):
                        out = maybe_trigger_new_act_after_main_quest(
                            campaign_id=1,
                            character_id=1,
                            old_sheet=old_sheet,
                            new_sheet=new_sheet,
                        )

            self.assertIsNotNone(out)
            assert out is not None
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("new_arc_id"), "act_2")

            conn2 = sqlite3.connect(path)
            row = conn2.execute("SELECT gm_plan_json FROM campaigns WHERE id = 1").fetchone()
            self.assertIsNotNone(row)
            plan = json.loads(row[0])
            self.assertEqual(plan.get("active_arc_id"), "act_2")
            self.assertEqual(plan["arcs"]["default"]["status"], "closed")
            self.assertEqual(plan["arcs"]["act_2"]["status"], "active")

            n = conn2.execute(
                "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = 1"
            ).fetchone()[0]
            self.assertEqual(n, 2)
            last = conn2.execute(
                "SELECT assistant_text, user_text FROM campaign_turns ORDER BY turn_number DESC LIMIT 1"
            ).fetchone()
            self.assertIn("Most narracyjny", last[0])
            self.assertIn("[Nowy akt]", last[1])
            conn2.close()
        finally:
            os.unlink(path)

    def test_no_trigger_when_not_main_quest(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, "
                "model_id TEXT, language TEXT, owner_user_id INTEGER, gm_plan_json TEXT, status TEXT)"
            )
            conn.execute(
                "INSERT INTO campaigns (id, title, system_id, model_id, language, owner_user_id, gm_plan_json, status) "
                "VALUES (1,'T','s','m','pl',1,?,'active')",
                (_ready_plan_json(),),
            )
            conn.commit()
            conn.close()

            old_sheet = {"quests_completed": []}
            new_sheet = {"quests_completed": ["side_quest"]}

            with patch("app.services.new_act_service.DB_PATH", path):
                out = maybe_trigger_new_act_after_main_quest(
                    campaign_id=1,
                    character_id=1,
                    old_sheet=old_sheet,
                    new_sheet=new_sheet,
                )
            self.assertIsNone(out)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
