"""TDD: Issue #400 — Admin spectator + resume.

Backend core (część 1):
- is_admin_user: tylko admin ma dostęp.
- list_all_campaigns: wszystkie kampanie w systemie z meta (owner, hero, status, ostatnia tura).
- resume_campaign: podpina z powrotem bohatera (z historii tur) + aktywuje kampanię,
  żeby odpięta/nieaktywna kampania stała się grywalna z frontendu.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, is_admin INTEGER DEFAULT 0);
        INSERT INTO users (id, username, display_name, is_admin) VALUES
          (1, 'demo', 'Demo', 1), (2, 'gracz', 'Gracz', 0);

        CREATE TABLE campaigns (
          id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', owner_user_id INTEGER,
          created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO campaigns (id, title, status, owner_user_id) VALUES
          (100, 'Aktywna kampania', 'active', 1),
          (101, 'Stara odpięta', 'active', 1),
          (102, 'Cudza kampania', 'active', 2);

        CREATE TABLE characters (
          id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER,
          status TEXT DEFAULT 'idle', is_active INTEGER DEFAULT 1
        );
        -- hero 100 nadal w kampanii 100; hero 101 odpięty (grał 101 wg historii)
        INSERT INTO characters (id, name, user_id, campaign_id, status, is_active) VALUES
          (200, 'Kiran', 1, 100, 'active', 1),
          (201, 'Lotrzyk', 1, NULL, 'idle', 1),
          (202, 'Obcy', 2, 102, 'active', 1);

        CREATE TABLE campaign_turns (
          id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
          turn_number INTEGER, assistant_text TEXT
        );
        INSERT INTO campaign_turns (campaign_id, character_id, turn_number) VALUES
          (100, 200, 1), (101, 201, 1), (101, 201, 2), (102, 202, 1);
        """
    )
    conn.commit()


class TestAdminGate(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_user_passes(self):
        from app.services.admin_spectate_service import is_admin_user
        self.assertTrue(is_admin_user(self.conn, 1))

    def test_non_admin_rejected(self):
        from app.services.admin_spectate_service import is_admin_user
        self.assertFalse(is_admin_user(self.conn, 2))


class TestListAllCampaigns(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_lists_every_campaign_with_meta(self):
        from app.services.admin_spectate_service import list_all_campaigns
        rows = list_all_campaigns(self.conn)
        ids = {r["id"] for r in rows}
        self.assertEqual(ids, {100, 101, 102})  # wszystkie, także cudza i odpięta
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[100]["owner_user_id"], 1)
        self.assertEqual(by_id[101]["last_turn"], 2)   # z historii tur
        # hero rozpoznany nawet dla odpiętej kampanii (z campaign_turns)
        self.assertEqual(by_id[101]["character_id"], 201)

    def test_filter_by_user_for_dropdown(self):
        """Dropdown wyboru usera → filtr po owner_user_id."""
        from app.services.admin_spectate_service import list_all_campaigns
        rows = list_all_campaigns(self.conn, user_id=1)
        self.assertEqual({r["id"] for r in rows}, {100, 101})  # tylko user 1

    def test_list_users_for_dropdown(self):
        """Lista userów do dropdowna (id + nazwa)."""
        from app.services.admin_spectate_service import list_users
        users = list_users(self.conn)
        by_id = {u["id"]: u for u in users}
        self.assertIn(1, by_id)
        self.assertEqual(by_id[1]["display_name"], "Demo")


class TestResumeCampaign(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_resume_reattaches_detached_hero(self):
        from app.services.admin_spectate_service import resume_campaign
        out = resume_campaign(self.conn, 101)
        self.assertTrue(out["ok"])
        self.assertEqual(out["character_id"], 201)
        row = self.conn.execute(
            "SELECT campaign_id, status FROM characters WHERE id = 201"
        ).fetchone()
        self.assertEqual(row["campaign_id"], 101)
        self.assertEqual(row["status"], "active")
        camp = self.conn.execute("SELECT status FROM campaigns WHERE id = 101").fetchone()
        self.assertEqual(camp["status"], "active")

    def test_resume_unknown_campaign_returns_not_ok(self):
        from app.services.admin_spectate_service import resume_campaign
        out = resume_campaign(self.conn, 9999)
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
