"""T02 — campaign_ai_summaries.audience (player vs gm) + narrative fetch order."""

import sqlite3
import unittest

from app.migrations_admin import _ensure_campaign_ai_summaries_audience
from app.services.history_summary_service import (
    SUMMARY_AUDIENCE_GM,
    SUMMARY_AUDIENCE_PLAYER,
    fetch_latest_saved_summary,
    fetch_latest_saved_summary_for_narrative,
    persist_summary,
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaign_ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            summary_text TEXT NOT NULL,
            model_used TEXT,
            included_turn_count INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    return conn


class TestAudienceMigrationHelpers(unittest.TestCase):
    def test_ensure_adds_audience_idempotent(self):
        conn = _make_conn()
        _ensure_campaign_ai_summaries_audience(conn)
        info = conn.execute("PRAGMA table_info(campaign_ai_summaries)").fetchall()
        names = {r[1] for r in info}
        self.assertIn("audience", names)
        _ensure_campaign_ai_summaries_audience(conn)  # no error

    def test_ensure_noop_when_column_exists(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE campaign_ai_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                model_used TEXT,
                included_turn_count INTEGER,
                audience TEXT NOT NULL DEFAULT 'player',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        _ensure_campaign_ai_summaries_audience(conn)
        n = conn.execute("SELECT COUNT(*) AS c FROM campaign_ai_summaries").fetchone()["c"]
        self.assertEqual(n, 0)


class TestPersistAndFetchByAudience(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE campaign_ai_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                model_used TEXT,
                included_turn_count INTEGER,
                audience TEXT NOT NULL DEFAULT 'player',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

    def test_latest_per_audience_stacks_independently(self):
        cid = 10
        persist_summary(
            self.conn,
            campaign_id=cid,
            summary_text="Player v1",
            model_used="m1",
            included_turn_count=3,
            audience=SUMMARY_AUDIENCE_PLAYER,
        )
        persist_summary(
            self.conn,
            campaign_id=cid,
            summary_text="GM v1",
            model_used="m1",
            included_turn_count=3,
            audience=SUMMARY_AUDIENCE_GM,
        )
        persist_summary(
            self.conn,
            campaign_id=cid,
            summary_text="Player v2",
            model_used="m1",
            included_turn_count=5,
            audience=SUMMARY_AUDIENCE_PLAYER,
        )

        p = fetch_latest_saved_summary(self.conn, cid, audience=SUMMARY_AUDIENCE_PLAYER)
        g = fetch_latest_saved_summary(self.conn, cid, audience=SUMMARY_AUDIENCE_GM)
        self.assertEqual(p["summary_text"], "Player v2")
        self.assertEqual(g["summary_text"], "GM v1")
        self.assertEqual(p["audience"], "player")
        self.assertEqual(g["audience"], "gm")

    def test_narrative_prefers_gm_else_player(self):
        cid = 7
        persist_summary(
            self.conn,
            campaign_id=cid,
            summary_text="legacy player only",
            model_used="x",
            included_turn_count=1,
            audience=SUMMARY_AUDIENCE_PLAYER,
        )
        n = fetch_latest_saved_summary_for_narrative(self.conn, cid)
        self.assertEqual(n["summary_text"], "legacy player only")

        persist_summary(
            self.conn,
            campaign_id=cid,
            summary_text="gm row",
            model_used="x",
            included_turn_count=2,
            audience=SUMMARY_AUDIENCE_GM,
        )
        n2 = fetch_latest_saved_summary_for_narrative(self.conn, cid)
        self.assertEqual(n2["summary_text"], "gm row")
        self.assertEqual(n2["audience"], "gm")

    def test_invalid_audience_raises(self):
        with self.assertRaises(ValueError):
            persist_summary(
                self.conn,
                campaign_id=1,
                summary_text="x",
                model_used="m",
                included_turn_count=0,
                audience="narrator",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
