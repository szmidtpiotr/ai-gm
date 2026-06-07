"""TDD: Issue #379 (D4) — Auto-screening admin queue.

Dwa poziomy:
- L1: mechaniczna walidacja (wymagane pola, typy, zakresy) — deterministyczna.
- L2: LLM scoring 0-100 (czy rekord pasuje do świata) — w testach wstrzyknięty.
Decyzja: L1 pass AND score >= threshold(80) → auto-approve; inaczej → kolejka admina.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE game_config_enemies (
          key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          hp_base INTEGER NOT NULL,
          ac_base INTEGER NOT NULL,
          attack_bonus INTEGER NOT NULL,
          damage_die TEXT NOT NULL,
          tier TEXT NOT NULL DEFAULT 'standard',
          xp_award INTEGER NOT NULL DEFAULT 0,
          loot_table_key TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          review_status TEXT NOT NULL DEFAULT 'permanent'
        );
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,tier,review_status)
        VALUES ('goblin_szaman','Goblin Szaman',12,11,2,'d6','standard','pending_review');
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,tier,review_status)
        VALUES ('zepsuty','',0,0,0,'','wrong_tier','pending_review');
        """
    )
    conn.commit()


# ─── L1 — walidacja mechaniczna ──────────────────────────────────────────────

class TestLevel1Validation(unittest.TestCase):
    def test_valid_enemy_passes_l1(self):
        from app.services.screening_service import validate_level1

        rec = {"label": "Goblin Szaman", "hp_base": 12, "ac_base": 11,
               "damage_die": "d6", "tier": "standard"}
        res = validate_level1("enemy", rec)
        self.assertTrue(res["passed"], res.get("errors"))
        self.assertEqual(res["errors"], [])

    def test_invalid_enemy_fails_l1(self):
        from app.services.screening_service import validate_level1

        rec = {"label": "", "hp_base": 0, "ac_base": 0, "damage_die": "", "tier": "wrong_tier"}
        res = validate_level1("enemy", rec)
        self.assertFalse(res["passed"])
        self.assertTrue(len(res["errors"]) >= 1)


# ─── Decyzja ─────────────────────────────────────────────────────────────────

class TestDecision(unittest.TestCase):
    def test_high_score_and_l1_pass_auto_approves(self):
        from app.services.screening_service import decide_screening
        self.assertEqual(decide_screening(l1_passed=True, score=90), "auto_approve")

    def test_low_score_goes_to_queue(self):
        from app.services.screening_service import decide_screening
        self.assertEqual(decide_screening(l1_passed=True, score=50), "queue")

    def test_l1_fail_always_queue_even_high_score(self):
        from app.services.screening_service import decide_screening
        self.assertEqual(decide_screening(l1_passed=False, score=99), "queue")


# ─── Orchestrator (L1 + L2 wstrzyknięty + apply) ─────────────────────────────

class TestAutoScreenRecord(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_valid_high_score_auto_approves(self):
        from app.services.screening_service import auto_screen_record

        out = auto_screen_record(self.conn, "enemy", "goblin_szaman", score_fn=lambda *_: 92)
        self.assertEqual(out["decision"], "auto_approve")
        self.assertEqual(out["score"], 92)
        # rekord przestaje być pending
        rs = self.conn.execute(
            "SELECT review_status FROM game_config_enemies WHERE key='goblin_szaman'"
        ).fetchone()["review_status"]
        self.assertNotEqual(rs, "pending_review")

    def test_low_score_stays_in_queue(self):
        from app.services.screening_service import auto_screen_record

        out = auto_screen_record(self.conn, "enemy", "goblin_szaman", score_fn=lambda *_: 40)
        self.assertEqual(out["decision"], "queue")
        rs = self.conn.execute(
            "SELECT review_status FROM game_config_enemies WHERE key='goblin_szaman'"
        ).fetchone()["review_status"]
        self.assertEqual(rs, "pending_review")

    def test_l1_fail_never_auto_approves(self):
        from app.services.screening_service import auto_screen_record

        # 'zepsuty' nie przejdzie L1 — mimo wysokiego score zostaje w kolejce
        out = auto_screen_record(self.conn, "enemy", "zepsuty", score_fn=lambda *_: 100)
        self.assertEqual(out["decision"], "queue")
        self.assertFalse(out["l1"]["passed"])
        rs = self.conn.execute(
            "SELECT review_status FROM game_config_enemies WHERE key='zepsuty'"
        ).fetchone()["review_status"]
        self.assertEqual(rs, "pending_review")


if __name__ == "__main__":
    unittest.main()
