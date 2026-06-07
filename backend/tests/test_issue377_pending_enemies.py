"""TDD: Issue #377 (D2) — Pending flow wrogów.

Analogicznie do D1 (przedmioty): gdy walka startuje z nieznanym kluczem wroga
(`[COMBAT_START:goblin_szaman]` a `goblin_szaman` nie ma w game_config_enemies),
silnik nie może go po cichu pominąć — musi utworzyć rekord pending_review
w game_config_enemies, żeby walka się odbyła, a wróg trafił do kolejki recenzji.
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
          description TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          tier TEXT NOT NULL DEFAULT 'standard',
          attacks_per_turn INTEGER NOT NULL DEFAULT 1,
          damage_bonus INTEGER NOT NULL DEFAULT 0,
          xp_award INTEGER NOT NULL DEFAULT 0,
          loot_table_key TEXT,
          drop_chance REAL NOT NULL DEFAULT 1.0,
          dex_modifier INTEGER NOT NULL DEFAULT 0,
          skills_json TEXT,
          review_status TEXT NOT NULL DEFAULT 'permanent'
        );
        INSERT INTO game_config_enemies
          (key, label, hp_base, ac_base, attack_bonus, damage_die, tier, xp_award, review_status)
        VALUES ('goblin', 'Goblin', 8, 10, 2, 'd6', 'weak', 10, 'permanent');
        """
    )
    conn.commit()


# ─── Test główny — nowe zachowanie ───────────────────────────────────────────

class TestPendingEnemyCreation(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_unknown_enemy_creates_pending_template(self):
        """Nieznany klucz wroga → rekord pending_review w game_config_enemies, gotowy do walki."""
        from app.services.combat_service import _create_pending_combat_enemy

        row = _create_pending_combat_enemy(self.conn, "goblin_szaman")
        self.assertIsNotNone(row, "helper musi zwrócić wiersz wroga gotowy do walki")
        self.assertEqual(row["key"], "goblin_szaman")
        # statystyki muszą być sensowne (>0), żeby walka działała od razu
        self.assertGreater(int(row["hp_base"]), 0)
        self.assertGreater(int(row["ac_base"]), 0)
        self.assertTrue((row["damage_die"] or "").strip(), "wróg musi mieć kość obrażeń")

        # status pending weryfikujemy w DB (wiersz bojowy nie niesie review_status)
        db = self.conn.execute(
            "SELECT review_status, is_active FROM game_config_enemies WHERE key = ?",
            ("goblin_szaman",),
        ).fetchone()
        self.assertIsNotNone(db, "pending wróg nie zapisany w DB")
        self.assertEqual(db["review_status"], "pending_review")
        self.assertEqual(int(db["is_active"]), 1)

    def test_pending_enemy_visible_in_admin_review_queue(self):
        """Admin widzi pending wroga w kolejce recenzji (get_pending_enemies + licznik)."""
        from app.services.combat_service import _create_pending_combat_enemy
        from app.services.world_service import get_pending_enemies, get_pending_review_counts

        _create_pending_combat_enemy(self.conn, "goblin_szaman")

        pending = get_pending_enemies(self.conn)
        keys = {p["key"] for p in pending}
        self.assertIn("goblin_szaman", keys)

        counts = get_pending_review_counts(self.conn)
        self.assertGreaterEqual(counts.get("enemies", 0), 1)


# ─── Backward compatibility — stary kod nadal działa ─────────────────────────

class TestKnownEnemyUnchanged(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_known_enemy_fetch_unchanged(self):
        """Znany wróg nadal rozwiązuje się normalnie i pozostaje permanent."""
        from app.services.combat_service import _fetch_enemy_row

        row = _fetch_enemy_row(self.conn, "goblin")
        self.assertIsNotNone(row)
        self.assertEqual(row["key"], "goblin")

        # żaden nowy pending wróg nie powstał
        n = self.conn.execute(
            "SELECT COUNT(*) FROM game_config_enemies WHERE review_status = 'pending_review'",
        ).fetchone()[0]
        self.assertEqual(int(n), 0)

    def test_helper_does_not_downgrade_existing_enemy(self):
        """INSERT OR IGNORE: helper na istniejącym kluczu NIE psuje permanent wroga."""
        from app.services.combat_service import _create_pending_combat_enemy

        row = _create_pending_combat_enemy(self.conn, "goblin")
        self.assertIsNotNone(row)
        # istniejący goblin pozostaje permanent (INSERT OR IGNORE nie nadpisuje)
        db = self.conn.execute(
            "SELECT review_status FROM game_config_enemies WHERE key = ?", ("goblin",),
        ).fetchone()
        self.assertEqual(db["review_status"], "permanent")


if __name__ == "__main__":
    unittest.main()
