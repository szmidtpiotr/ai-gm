"""
Issue #1279 — NPC deduplication in [CREATE_NPC] processing.

Root cause: narrator emits `[CREATE_NPC: key=X]` with an LLM-chosen key that
varies every turn (brunn, brunn_zelaznoreki, brunn_936708 …). `_get_or_create_npc`
only deduped on exact `key`, so the same character produced a new row each turn.

Fix (variants 1+3+4):
  4. strip a trailing numeric suffix from the LLM key (>=4 digits)
  3. plan-roster precedence: match the incoming name against `gm_plan_json.key_npcs`
     and reuse that entry's canonical key
  1. name-based dedup fallback for ad-hoc NPCs not present in the plan roster
"""

import json
import sqlite3

import pytest

from app.services.world_service import _get_or_create_npc, process_create_tags


NPC_DDL = """
CREATE TABLE npcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    label TEXT,
    npc_type TEXT,
    personality_prompt TEXT,
    keyword_triggers TEXT,
    personality_json TEXT,
    review_status TEXT,
    is_active INTEGER,
    is_shop INTEGER
);
"""

CAMP_DDL = """
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    gm_plan_json TEXT
);
"""

LOC_ASSIGN_DDL = """
CREATE TABLE location_npc_assignments (
    location_key TEXT,
    npc_key TEXT,
    UNIQUE(location_key, npc_key)
);
"""


def _conn(plan_key_npcs=None, campaign_id=1):
    conn = sqlite3.connect(":memory:")
    conn.executescript(NPC_DDL + CAMP_DDL + LOC_ASSIGN_DDL)
    plan = {"key_npcs": plan_key_npcs or []}
    conn.execute(
        "INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)",
        (campaign_id, json.dumps(plan)),
    )
    conn.commit()
    return conn


def _seed_npc(conn, key, label):
    conn.execute(
        "INSERT INTO npcs (key, label, npc_type, review_status, is_active, is_shop) "
        "VALUES (?, ?, 'neutral', 'pending', 1, 0)",
        (key, label),
    )
    conn.commit()


def _npc_count(conn):
    return conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0]


# ── variant 4: numeric suffix ────────────────────────────────────────────────

def test_numeric_suffix_key_maps_to_base():
    conn = _conn()
    _seed_npc(conn, "brunn", "Brunn")
    res = _get_or_create_npc(conn, "brunn_936708", {"name": "Brunn"}, 1)
    assert res["key"] == "brunn"
    assert _npc_count(conn) == 1


def test_numeric_suffix_stripped_on_create():
    conn = _conn()
    res = _get_or_create_npc(conn, "kowal_082511", {"name": "Nowy Kowal"}, 1)
    assert res["key"] == "kowal"          # suffix stripped
    assert _npc_count(conn) == 1


def test_short_suffix_not_stripped():
    # forge collision keys like _2/_3 are legit — only >=4 digit suffixes stripped
    conn = _conn()
    _seed_npc(conn, "kowal", "Kowal")
    res = _get_or_create_npc(conn, "kowal_2", {"name": "Drugi Kowal"}, 1)
    assert res["key"] == "kowal_2"
    assert _npc_count(conn) == 2


# ── variant 3: plan roster precedence ────────────────────────────────────────

ROSTER = [{"key": "brunn_zelaznoreki", "name": "Brunn Żelaznoręki", "role": "kowal"}]


def test_plan_roster_canonicalizes_partial_name():
    conn = _conn(plan_key_npcs=ROSTER)
    _seed_npc(conn, "brunn_zelaznoreki", "Brunn Żelaznoręki")
    # narrator emits bare "Brunn" with its own key
    res = _get_or_create_npc(conn, "brunn", {"name": "Brunn"}, 1)
    assert res["key"] == "brunn_zelaznoreki"
    assert _npc_count(conn) == 1


def test_roster_creates_under_canonical_key_when_missing():
    conn = _conn(plan_key_npcs=ROSTER)
    # canonical NPC not yet materialized
    res = _get_or_create_npc(conn, "brunn_936708", {"name": "Brunn"}, 1)
    assert res["key"] == "brunn_zelaznoreki"
    assert _npc_count(conn) == 1
    row = conn.execute("SELECT key FROM npcs").fetchone()
    assert row[0] == "brunn_zelaznoreki"


def test_roster_matches_spelling_variant():
    conn = _conn(plan_key_npcs=ROSTER)
    _seed_npc(conn, "brunn_zelaznoreki", "Brunn Żelaznoręki")
    # ż -> z spelling drift
    res = _get_or_create_npc(conn, "brunn_zelaznorek", {"name": "Brunn Zelaznoreki"}, 1)
    assert res["key"] == "brunn_zelaznoreki"
    assert _npc_count(conn) == 1


# ── variant 1: name-based dedup fallback (no roster) ──────────────────────────

def test_name_dedup_for_adhoc_npc():
    conn = _conn()  # empty roster
    _seed_npc(conn, "zielarka_mira", "Zielarka Mira")
    res = _get_or_create_npc(conn, "zielarka_123456", {"name": "Zielarka Mira"}, 1)
    assert res["key"] == "zielarka_mira"
    assert _npc_count(conn) == 1


def test_distinct_npcs_not_merged():
    conn = _conn()
    _seed_npc(conn, "kapitan_krolewski", "Kapitan Królewski")
    res = _get_or_create_npc(conn, "kapitan_smolny", {"name": "Kapitan Smolny"}, 1)
    assert res["key"] == "kapitan_smolny"
    assert _npc_count(conn) == 2


# ── end-to-end through process_create_tags ───────────────────────────────────

def test_no_dup_across_turns_via_tags():
    conn = _conn(plan_key_npcs=ROSTER)
    _seed_npc(conn, "brunn_zelaznoreki", "Brunn Żelaznoręki")
    for tag_key in ("brunn", "brunn_zelaznorek", "brunn_936708", "brunn_082511"):
        cleaned, created = process_create_tags(
            f"Tekst [CREATE_NPC: key={tag_key}, name=Brunn] dalej.", conn, 1
        )
        assert "[CREATE_NPC" not in cleaned
    assert _npc_count(conn) == 1
    assert conn.execute("SELECT key FROM npcs").fetchone()[0] == "brunn_zelaznoreki"
