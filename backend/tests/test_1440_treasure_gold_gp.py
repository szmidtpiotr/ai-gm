"""AUDIT #1440 (P2) — treasure payout credits the authoritative gold_gp column.

The old _payout wrote `UPDATE characters SET gold = COALESCE(gold,0)+?` — but the
authoritative column is `gold_gp`. The write hit a non-authoritative/absent column
and was swallowed by `except OperationalError`, so treasure gold was silently lost
and never journaled. It now routes through economy_service.change_gold.
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import treasure_service as ts


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE world_treasures (
            id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT,
            loot_snapshot_json TEXT, gold_snapshot INTEGER NOT NULL DEFAULT 0,
            gold_bonus INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'buried',
            found_at TEXT, found_by_character_id INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, gold_gp INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, campaign_id INTEGER, meta_json TEXT, game_clock_day INTEGER DEFAULT 1,
            wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')), reverted_at TEXT
        );
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT);
        """
    )
    conn.execute("INSERT INTO characters(id, campaign_id, gold_gp) VALUES (900, 7, 0)")
    conn.execute("INSERT INTO game_sessions(campaign_id, session_flags) VALUES (7, ?)",
                 (json.dumps({}),))
    conn.execute(
        "INSERT INTO world_treasures(id, label, loot_snapshot_json, gold_snapshot, gold_bonus, state) "
        "VALUES (1, 'Skrzynia', NULL, 200, 50, 'buried')"
    )
    conn.commit()
    return conn


def test_treasure_payout_credits_gold_gp():
    conn = _make_db()
    res = ts._payout(conn, campaign_id=7, character_id=900, treasure_id=1)

    assert res["resolved"] is True
    assert res["gold"] == 250            # gold_snapshot 200 + gold_bonus 50

    gold = conn.execute("SELECT gold_gp FROM characters WHERE id = 900").fetchone()[0]
    assert gold == 250                   # credited to gold_gp, not the dead `gold` column

    row = conn.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 900 AND source = 'treasure'"
    ).fetchone()
    assert row is not None and int(row["delta"]) == 250   # journaled through change_gold
    conn.close()
