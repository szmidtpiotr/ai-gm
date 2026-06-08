"""TDD: Issue #384 (D9) — Hub kampanii: 5 trybów + dostępność.

Hub oferuje 5 trybów: Nowa / Gotowa (template) / Loch / Loch-kafelki / Multiplayer.
Backend zwraca listę trybów z flagą `available` (zależną od danych: published
templates, aktywne lochy, kafelki) — żeby UI nie prowadził w broken state.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EXPECTED_KEYS = {"nowa", "gotowa", "loch", "loch_kafelki", "multiplayer"}


def _schema(conn: sqlite3.Connection, *, published=1, dungeons=1, tiles=1) -> None:
    conn.executescript(
        """
        CREATE TABLE campaign_templates (id INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE game_dungeons (key TEXT PRIMARY KEY, is_active INTEGER DEFAULT 1);
        CREATE TABLE dungeon_tiles (id INTEGER PRIMARY KEY);
        INSERT INTO campaign_templates (status) VALUES ('draft'), ('draft');
        """
    )
    if published:
        conn.execute("INSERT INTO campaign_templates (status) VALUES ('published')")
    if dungeons:
        conn.execute("INSERT INTO game_dungeons (key, is_active) VALUES ('cave', 1)")
    if tiles:
        conn.execute("INSERT INTO dungeon_tiles (id) VALUES (1)")
    conn.commit()


class TestCampaignModes(unittest.TestCase):
    def _modes(self, **kw):
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row
        _schema(conn, **kw)
        from app.services.campaign_modes_service import get_available_modes
        modes = get_available_modes(conn)
        conn.close()
        return {m["key"]: m for m in modes}

    def test_returns_all_five_modes(self):
        modes = self._modes()
        self.assertEqual(set(modes.keys()), EXPECTED_KEYS)
        for m in modes.values():
            self.assertIn("label", m)
            self.assertIn("available", m)

    def test_nowa_and_mp_always_available(self):
        modes = self._modes(published=0, dungeons=0, tiles=0)
        self.assertTrue(modes["nowa"]["available"])
        self.assertTrue(modes["multiplayer"]["available"])

    def test_gotowa_needs_published_template(self):
        self.assertTrue(self._modes(published=1)["gotowa"]["available"])
        self.assertFalse(self._modes(published=0)["gotowa"]["available"])

    def test_loch_needs_active_dungeon(self):
        self.assertTrue(self._modes(dungeons=1)["loch"]["available"])
        self.assertFalse(self._modes(dungeons=0)["loch"]["available"])

    def test_loch_kafelki_needs_tiles(self):
        self.assertTrue(self._modes(tiles=1)["loch_kafelki"]["available"])
        self.assertFalse(self._modes(tiles=0)["loch_kafelki"]["available"])


if __name__ == "__main__":
    unittest.main()
