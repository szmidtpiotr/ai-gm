"""T06 — gm_plan_json W1: normalize, merge, format."""

from __future__ import annotations

import json
import unittest

from app.services.gm_plan_schema import (
    GM_PLAN_SCHEMA_VERSION,
    format_gm_plan_block,
    gm_plan_is_ready,
    merge_gm_plan_patch,
    normalize_gm_plan,
)


class TestGmPlanIsReady(unittest.TestCase):
    def test_empty_not_ready(self):
        self.assertFalse(gm_plan_is_ready("{}"))
        self.assertFalse(gm_plan_is_ready(None))

    def test_ready_with_roadmap_in_arc(self):
        raw = json.dumps(
            {
                "arcs": {"default": {"roadmap": "Noc w porcie."}},
                "active_arc_id": "default",
            }
        )
        self.assertTrue(gm_plan_is_ready(raw))


class TestNormalizeGmPlan(unittest.TestCase):
    def test_empty_and_invalid(self):
        self.assertEqual(normalize_gm_plan(None)["schema_version"], GM_PLAN_SCHEMA_VERSION)
        self.assertEqual(normalize_gm_plan("")["schema_version"], GM_PLAN_SCHEMA_VERSION)
        self.assertEqual(normalize_gm_plan("not-json")["schema_version"], GM_PLAN_SCHEMA_VERSION)

    def test_legacy_flat_migrates_to_default_arc(self):
        raw = json.dumps(
            {
                "roadmap": "A",
                "scene_goals": ["g1"],
                "hooks": {"npcs": ["N"], "locations": ["L"]},
                "current_scene_ordinal": 5,
            }
        )
        out = normalize_gm_plan(raw)
        self.assertEqual(out["schema_version"], GM_PLAN_SCHEMA_VERSION)
        self.assertEqual(out["active_arc_id"], "default")
        arc = out["arcs"]["default"]
        self.assertEqual(arc["roadmap"], "A")
        self.assertEqual(arc["scene_goals"], ["g1"])
        self.assertEqual(arc["hooks"]["npcs"], ["N"])
        self.assertEqual(arc["current_scene_ordinal"], 5)


class TestMergeGmPlanPatch(unittest.TestCase):
    def test_legacy_flat_keys_merge_into_active_arc(self):
        base = normalize_gm_plan(
            json.dumps(
                {
                    "roadmap": "Old top",
                    "arcs": {
                        "a1": {
                            "roadmap": "Arc text",
                            "scene_goals": ["keep"],
                        }
                    },
                    "active_arc_id": "a1",
                }
            )
        )
        merged = merge_gm_plan_patch(
            base,
            {"roadmap": "Updated roadmap", "scene_goals": ["new goal"]},
        )
        self.assertEqual(merged["arcs"]["a1"]["roadmap"], "Updated roadmap")
        self.assertEqual(merged["arcs"]["a1"]["scene_goals"], ["new goal"])

    def test_deep_merge_arcs_and_engine_private(self):
        base = normalize_gm_plan(
            json.dumps(
                {
                    "arcs": {
                        "a1": {
                            "scene_goals": ["old"],
                            "hooks": {"npcs": ["X"]},
                        }
                    },
                    "active_arc_id": "a1",
                    "engine_private": {"k": {"nested": 1}},
                }
            )
        )
        patch = {
            "arcs": {
                "a1": {
                    "scene_goals": ["new"],
                    "hooks": {"locations": ["P"]},
                }
            },
            "engine_private": {"k": {"other": 2}},
        }
        merged = merge_gm_plan_patch(base, patch)
        self.assertEqual(merged["arcs"]["a1"]["scene_goals"], ["new"])
        self.assertEqual(merged["arcs"]["a1"]["hooks"]["npcs"], ["X"])
        self.assertEqual(merged["arcs"]["a1"]["hooks"]["locations"], ["P"])
        self.assertEqual(merged["engine_private"]["k"]["nested"], 1)
        self.assertEqual(merged["engine_private"]["k"]["other"], 2)


class TestFormatGmPlanBlock(unittest.TestCase):
    def test_active_arc_line_when_multiple_arcs(self):
        raw = json.dumps(
            {
                "schema_version": GM_PLAN_SCHEMA_VERSION,
                "active_arc_id": "b2",
                "arcs": {
                    "a1": {"roadmap": "ignore"},
                    "b2": {
                        "roadmap": "Visible",
                        "scene_goals": ["x"],
                        "hooks": {},
                        "current_scene_ordinal": 1,
                    },
                },
            }
        )
        text = format_gm_plan_block(raw)
        self.assertIn("## Aktywny łuk (MG): b2", text)
        self.assertIn("Visible", text)


if __name__ == "__main__":
    unittest.main()
