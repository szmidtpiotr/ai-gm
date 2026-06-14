"""TDD: Issue #592 — knowledge_book gains 4 FAZA U mechanic entries.

durability (U16/#564), robbery/raids (U24/#574), affix pity (U25/#575),
economy/gold telemetry (U26/#576).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.migrations_admin import FAZA_U_KNOWLEDGE_TIPS  # noqa: E402

EXPECTED_KEYS = {"durability", "robbery_raids", "affix_pity_timer", "economy_telemetry"}


def test_four_faza_u_tips_defined():
    keys = {t["tip_key"] for t in FAZA_U_KNOWLEDGE_TIPS}
    assert keys == EXPECTED_KEYS, f"expected {EXPECTED_KEYS}, got {keys}"


def test_tips_have_required_fields():
    for t in FAZA_U_KNOWLEDGE_TIPS:
        for col in ("tip_key", "category", "title", "body", "sort_order"):
            assert t.get(col) not in (None, ""), f"{t.get('tip_key')} missing {col}"
        assert len(t["body"]) > 40, f"{t['tip_key']} body too short"


def test_tips_insert_into_knowledge_book():
    """Seeding the rows yields 4 retrievable knowledge_book entries."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE knowledge_book (
            tip_key TEXT PRIMARY KEY, category TEXT, title TEXT, body TEXT,
            is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0)"""
    )
    for t in FAZA_U_KNOWLEDGE_TIPS:
        conn.execute(
            "INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) "
            "VALUES (?,?,?,?,?)",
            (t["tip_key"], t["category"], t["title"], t["body"], t["sort_order"]),
        )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM knowledge_book").fetchone()[0]
    assert n == 4
