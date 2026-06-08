"""TDD: Issue #383 (D8) — Ekran profilu: edycja konta (username + EMAIL).

PATCH /me/profile obsługuje username/display_name/avatar, ale NIE email.
D8 dodaje edycję email z walidacją formatu + unikalnością. Logika wyniesiona
do account_service.update_account (testowalna).
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE users (
          id INTEGER PRIMARY KEY, username TEXT UNIQUE, display_name TEXT,
          email TEXT, avatar_url TEXT
        );
        INSERT INTO users (id, username, display_name, email) VALUES
          (1, 'demo', 'Demo', 'demo@example.com'),
          (2, 'gracz', 'Gracz', 'gracz@example.com');
        """
    )
    conn.commit()


class TestUpdateEmail(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_update_valid_email(self):
        from app.services.account_service import update_account
        out = update_account(self.conn, 1, email="nowy@example.com")
        self.assertEqual(out["email"], "nowy@example.com")
        row = self.conn.execute("SELECT email FROM users WHERE id=1").fetchone()
        self.assertEqual(row["email"], "nowy@example.com")

    def test_invalid_email_rejected(self):
        from app.services.account_service import update_account
        with self.assertRaises(ValueError) as ctx:
            update_account(self.conn, 1, email="nie-email")
        self.assertEqual(str(ctx.exception), "invalid_email")

    def test_email_taken_rejected(self):
        from app.services.account_service import update_account
        with self.assertRaises(ValueError) as ctx:
            update_account(self.conn, 1, email="gracz@example.com")  # user 2 ma ten email
        self.assertEqual(str(ctx.exception), "email_taken")

    def test_same_email_for_self_ok(self):
        """Zapis własnego, niezmienionego maila nie jest 'zajęty'."""
        from app.services.account_service import update_account
        out = update_account(self.conn, 1, email="demo@example.com")
        self.assertEqual(out["email"], "demo@example.com")


class TestBackwardCompat(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row; _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_username_update_still_works(self):
        from app.services.account_service import update_account
        out = update_account(self.conn, 1, username="demo_new")
        self.assertEqual(out["username"], "demo_new")

    def test_invalid_username_rejected(self):
        from app.services.account_service import update_account
        with self.assertRaises(ValueError):
            update_account(self.conn, 1, username="ab")  # za krótki

    def test_partial_update_leaves_email(self):
        from app.services.account_service import update_account
        update_account(self.conn, 1, display_name="Nowa Nazwa")
        row = self.conn.execute("SELECT display_name, email FROM users WHERE id=1").fetchone()
        self.assertEqual(row["display_name"], "Nowa Nazwa")
        self.assertEqual(row["email"], "demo@example.com")


if __name__ == "__main__":
    unittest.main()
