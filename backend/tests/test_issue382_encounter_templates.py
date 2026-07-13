"""TDD: Issue #382 (D7) — Encountery generyczne: dobór template per teren/poziom.

Unifikacja: pipeline spotkań ma dobierać z gameconfig_encounter_templates
(nowy, nieużywany system) po poziomie bohatera i tagu lokacji/terenu.
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE gameconfig_encounter_templates (
          key TEXT PRIMARY KEY, label TEXT NOT NULL, difficulty TEXT NOT NULL,
          min_level INTEGER DEFAULT 1, max_level INTEGER DEFAULT 5,
          location_tags TEXT, enemies_json TEXT NOT NULL, threat_total INTEGER,
          is_active INTEGER DEFAULT 1, note TEXT
        );
        INSERT INTO gameconfig_encounter_templates
          (key,label,difficulty,min_level,max_level,location_tags,enemies_json,threat_total,is_active) VALUES
          ('forest_wolves','Wilki w lesie','medium',1,5,'["forest"]','[{"key":"wolf","count":2}]',4,1),
          ('cave_bats','Nietoperze','easy',1,3,'["cave"]','[{"key":"bat","count":3}]',3,1),
          ('road_bandits','Bandyci','medium',1,8,NULL,'[{"key":"bandit","count":2}]',5,1),
          ('dragon','Smok','deadly',8,12,'["mountain"]','[{"key":"dragon","count":1}]',20,1),
          ('old_event','Wyłączony','easy',1,5,'["forest"]','[]',2,0);
        """
    )
    conn.commit()


class TestSelectEncounterTemplate(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_matches_by_level_and_tag(self):
        from app.services.encounter_service import select_encounter_template
        t = select_encounter_template(self.conn, level=3, location_tag="forest")
        self.assertIsNotNone(t)
        # tylko forest_wolves (forest, lvl 1-5) albo road_bandits (tagless, generic)
        self.assertIn(t["key"], {"forest_wolves", "road_bandits"})

    def test_tag_specific_template_for_cave(self):
        from app.services.encounter_service import select_encounter_template
        # w jaskini smok (mountain) ani wolves (forest) nie pasują; tylko cave_bats lub generic bandits
        for _ in range(8):
            t = select_encounter_template(self.conn, level=2, location_tag="cave")
            self.assertIn(t["key"], {"cave_bats", "road_bandits"})

    def test_excludes_out_of_level_range(self):
        from app.services.encounter_service import select_encounter_template
        # poziom 2 → smok (8-12) nigdy
        for _ in range(10):
            t = select_encounter_template(self.conn, level=2, location_tag="mountain")
            self.assertNotEqual(t["key"] if t else None, "dragon")

    def test_excludes_inactive(self):
        from app.services.encounter_service import select_encounter_template
        for _ in range(10):
            t = select_encounter_template(self.conn, level=3, location_tag="forest")
            self.assertNotEqual(t["key"] if t else None, "old_event")

    def test_enemies_parsed(self):
        from app.services.encounter_service import select_encounter_template
        t = select_encounter_template(self.conn, level=3, location_tag="forest")
        self.assertIsInstance(t.get("enemies"), list)

    def test_no_match_returns_none(self):
        """Brak pasującego template (wysoki poziom, brak generic) → None."""
        from app.services.encounter_service import select_encounter_template
        # usuń generic bandits + dragon zostaje (ale lvl 50 nie pasuje nigdzie)
        self.conn.execute("DELETE FROM gameconfig_encounter_templates WHERE location_tags IS NULL")
        t = select_encounter_template(self.conn, level=50, location_tag="forest")
        self.assertIsNone(t)


# ─── Bezpieczeństwo + częstotliwość (uwagi gracza) ───────────────────────────

class TestEncounterSafetyAndConfig(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            """ + table_sql("game_config_meta") + """
            CREATE TABLE game_locations (
              id INTEGER PRIMARY KEY, key TEXT, label TEXT, safe_for_rest INTEGER DEFAULT 0,
              location_subtype TEXT, is_active INTEGER DEFAULT 1
            );
            INSERT INTO game_locations (key,label,safe_for_rest,location_subtype,is_active) VALUES
              ('tavern','Karczma',1,'tavern',1),
              ('forest_clearing','Polana',0,'wilderness',1);
            CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                        current_location_id INTEGER, session_flags TEXT DEFAULT '{}');
            INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES (1, 1, NULL);
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_default_interval_is_20(self):
        from app.services.encounter_config_service import get_encounter_config
        cfg = get_encounter_config(conn=self.conn)
        self.assertEqual(cfg["n_turns_interval"], 20)

    def test_set_and_get_interval(self):
        from app.services.encounter_config_service import get_encounter_config, set_encounter_config
        set_encounter_config(conn=self.conn, n_turns_interval=15)
        self.assertEqual(get_encounter_config(conn=self.conn)["n_turns_interval"], 15)

    def test_safe_location_blocks_encounter(self):
        from app.services.encounter_service import is_encounter_blocked_by_location
        self.conn.execute("UPDATE game_sessions SET current_location_id=(SELECT id FROM game_locations WHERE key='tavern') WHERE campaign_id=1")
        self.conn.commit()
        self.assertTrue(is_encounter_blocked_by_location(self.conn, 1))

    def test_unsafe_location_not_blocked(self):
        from app.services.encounter_service import is_encounter_blocked_by_location
        self.conn.execute("UPDATE game_sessions SET current_location_id=(SELECT id FROM game_locations WHERE key='forest_clearing') WHERE campaign_id=1")
        self.conn.commit()
        self.assertFalse(is_encounter_blocked_by_location(self.conn, 1))

    def test_dwell_reduces_chance_when_settled(self):
        from app.services.encounter_service import dwell_chance_multiplier
        self.assertEqual(dwell_chance_multiplier(0), 1.0)
        self.assertEqual(dwell_chance_multiplier(2), 1.0)            # poniżej progu osiedlenia
        self.assertLess(dwell_chance_multiplier(6), 1.0)            # osiadł → niższa szansa
        self.assertLessEqual(dwell_chance_multiplier(20), dwell_chance_multiplier(6))  # dłużej → niżej


if __name__ == "__main__":
    unittest.main()
