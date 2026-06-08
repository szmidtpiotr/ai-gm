"""TDD: Issue #381 (D6 follow-up) — Narrative State widoczny w snapshot/Stan Świata.

build_snapshot musi dołączyć narrative_state (z session_flags) do snapshotu, żeby
zakładka admin3 "🌍 Stan Świata" oraz Inspector mogły go pokazać.
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import world_state_service as wss


def _make_db(tmp: Path) -> None:
    conn = sqlite3.connect(str(tmp))
    conn.executescript(
        """
        CREATE TABLE game_sessions (
          id TEXT, campaign_id INTEGER,
          scene_enemies TEXT, scene_npcs TEXT, scene_cleared INTEGER DEFAULT 0,
          active_quests TEXT, player_conditions TEXT,
          session_flags TEXT
        );
        CREATE TABLE campaign_turns (
          id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, turn_number INTEGER
        );
        INSERT INTO campaign_turns (campaign_id, turn_number) VALUES (1, 7);
        """
    )
    nstate = {
        "events": [{"key": "met_aldric", "note": "Gracz spotkał Aldrica", "turn": 5}],
        "seeds": [{"key": "daughter", "hint": "Marta wspomniała o córce", "status": "active", "planted_turn": 3}],
        "chapter_summaries": [], "current_situation": "",
    }
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES ('1', 1, ?)",
        (json.dumps({"narrative_state": nstate}, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()


class TestSnapshotNarrativeState(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_d6b_snapshot.db"
        if self._tmp.exists():
            self._tmp.unlink()
        _make_db(self._tmp)
        self._p = patch.object(wss, "DB_PATH", str(self._tmp))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def test_snapshot_includes_narrative_state(self):
        snap = wss.build_snapshot(1)
        self.assertIn("narrative_state", snap)
        self.assertEqual(snap["narrative_state"]["events"][0]["key"], "met_aldric")
        self.assertEqual(snap["narrative_state"]["seeds"][0]["key"], "daughter")

    def test_snapshot_narrative_state_empty_when_absent(self):
        # campaign 999 has no session → narrative_state defaults to empty dict, no crash
        snap = wss.build_snapshot(999)
        self.assertIn("narrative_state", snap)
        self.assertEqual(snap["narrative_state"], {})


if __name__ == "__main__":
    unittest.main()
