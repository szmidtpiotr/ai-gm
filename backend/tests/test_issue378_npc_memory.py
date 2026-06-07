"""TDD: Issue #378 (D3) — NPC pamięć w World State.

LLM emituje tag `[NPC_MEMORY: Imię | zapamiętany fakt]`. Backend zapisuje fakt
w pamięci NPC (kumuluje fakty, nie nadpisuje), a przy kolejnej wizycie wstrzykuje
je do kontekstu LLM (przez istniejący format_known_npcs_block — pole `notes`).
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE campaign_known_npcs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          campaign_id INTEGER NOT NULL,
          npc_id INTEGER,
          npc_name TEXT NOT NULL,
          role TEXT,
          first_met_location TEXT,
          first_met_turn INTEGER,
          notes TEXT,
          relation_status TEXT NOT NULL DEFAULT 'neutral',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          purchase_count INTEGER NOT NULL DEFAULT 0,
          UNIQUE(campaign_id, npc_name)
        );
        CREATE TABLE npcs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          key TEXT,
          label TEXT,
          description TEXT,
          personality_json TEXT,
          is_shop INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()


# ─── Parser tagu ─────────────────────────────────────────────────────────────

class TestNpcMemoryTagParsing(unittest.TestCase):
    def test_parse_extracts_name_and_fact(self):
        from app.services.npc_memory_service import parse_npc_memory_tags

        text = "Marta uśmiecha się. [NPC_MEMORY: Marta | gracz uratował jej kota]"
        pairs = parse_npc_memory_tags(text)
        self.assertEqual(pairs, [("Marta", "gracz uratował jej kota")])

    def test_parse_multiple_tags(self):
        from app.services.npc_memory_service import parse_npc_memory_tags

        text = ("[NPC_MEMORY: Aldric | sprzedał graczowi miecz]\n"
                "[NPC_MEMORY: Marta | obiecała pomoc]")
        pairs = parse_npc_memory_tags(text)
        self.assertIn(("Aldric", "sprzedał graczowi miecz"), pairs)
        self.assertIn(("Marta", "obiecała pomoc"), pairs)

    def test_strip_removes_tag_keeps_narrative(self):
        from app.services.npc_memory_service import strip_npc_memory_tags

        text = "Marta kiwa głową. [NPC_MEMORY: Marta | zapamiętała twarz gracza]"
        out = strip_npc_memory_tags(text)
        self.assertNotIn("NPC_MEMORY", out)
        self.assertIn("Marta kiwa głową.", out)


# ─── Akumulacja pamięci ──────────────────────────────────────────────────────

class TestNpcMemoryAccumulation(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_append_accumulates_facts(self):
        """Kolejne fakty kumulują się (nie nadpisują)."""
        from app.services.npc_memory_service import append_npc_memory

        append_npc_memory(campaign_id=1, name="Marta", memory="uratował jej kota", conn=self.conn)
        append_npc_memory(campaign_id=1, name="Marta", memory="obiecał wrócić", conn=self.conn)

        notes = self.conn.execute(
            "SELECT notes FROM campaign_known_npcs WHERE campaign_id=1 AND npc_name='Marta'",
        ).fetchone()["notes"]
        self.assertIn("uratował jej kota", notes)
        self.assertIn("obiecał wrócić", notes)

    def test_append_dedups(self):
        """Ten sam fakt dwa razy → nie duplikuje się."""
        from app.services.npc_memory_service import append_npc_memory

        append_npc_memory(campaign_id=1, name="Marta", memory="uratował jej kota", conn=self.conn)
        append_npc_memory(campaign_id=1, name="Marta", memory="uratował jej kota", conn=self.conn)

        notes = self.conn.execute(
            "SELECT notes FROM campaign_known_npcs WHERE campaign_id=1 AND npc_name='Marta'",
        ).fetchone()["notes"]
        self.assertEqual(notes.count("uratował jej kota"), 1)

    def test_memory_injected_on_next_visit(self):
        """Zapamiętany fakt wraca do kontekstu (format_known_npcs_block)."""
        from app.services.npc_memory_service import (
            append_npc_memory, get_recent_known_npcs, format_known_npcs_block,
        )

        append_npc_memory(campaign_id=1, name="Marta", memory="uratował jej kota", conn=self.conn)
        rows = get_recent_known_npcs(1, conn=self.conn)
        block = format_known_npcs_block(rows)
        self.assertIn("Marta", block)
        self.assertIn("uratował jej kota", block)


# ─── Backward compatibility ──────────────────────────────────────────────────

class TestNoTagUnchanged(unittest.TestCase):
    def test_text_without_tag_unchanged(self):
        from app.services.npc_memory_service import parse_npc_memory_tags, strip_npc_memory_tags

        text = "Zwykła narracja bez żadnych tagów pamięci."
        self.assertEqual(parse_npc_memory_tags(text), [])
        self.assertEqual(strip_npc_memory_tags(text), text)


if __name__ == "__main__":
    unittest.main()
