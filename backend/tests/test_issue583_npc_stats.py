"""TDD: Issue #583 (S3) — Staty NPC + lazy generation archetypu.

RED→GREEN: NPC z kampanii dostaje 7 statów (STR..LCK) LENIWIE — generowane
z archetypu (ta sama heurystyka co wrogowie w S2) dopiero przy pierwszym
teście przeciwnym, i zapamiętane per-kampania (`campaign_known_npcs.stats_json`).
Ten sam NPC zawsze ma te same staty. Template globalny (`npcs.stats_json`) ma
pierwszeństwo nad archetypem. Cele bezimienne nie dostają wpisu.
"""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.actor_stats import STAT_KEYS, ARCHETYPE_STATS, DEFAULT_STAT
from app.services.npc_memory_service import ensure_npc_stats


def _mk_conn() -> sqlite3.Connection:
    """In-memory DB z minimalnym schematem (kolumny jak po migracji S3)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
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
            stats_json TEXT,
            UNIQUE(campaign_id, npc_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            stats_json TEXT
        )
        """
    )
    return conn


# ─── Test główny: lazy generation z archetypu ───────────────────────────────

def test_ensure_npc_stats_brute_archetype():
    """NPC 'strażnik-osiłek' dostaje archetyp brute (STR 16)."""
    conn = _mk_conn()
    stats = ensure_npc_stats(conn, campaign_id=1, npc_name="strażnik-osiłek")
    assert set(stats.keys()) == set(STAT_KEYS)
    assert stats["STR"] == ARCHETYPE_STATS["brute"]["STR"]  # 16
    assert stats == ARCHETYPE_STATS["brute"]


def test_ensure_npc_stats_humanoid_default():
    """Bezklasowy NPC ('marta karczmarka') → humanoid (wszystko 10)."""
    conn = _mk_conn()
    stats = ensure_npc_stats(conn, campaign_id=1, npc_name="marta karczmarka")
    assert all(v == DEFAULT_STAT for v in stats.values())


# ─── Persystencja: stabilność per-kampania ──────────────────────────────────

def test_ensure_npc_stats_persists_identical():
    """Dwukrotne wołanie dla tego samego NPC → identyczne staty + jeden wpis."""
    conn = _mk_conn()
    first = ensure_npc_stats(conn, campaign_id=7, npc_name="bandyta herszt")
    second = ensure_npc_stats(conn, campaign_id=7, npc_name="bandyta herszt")
    assert first == second
    rows = conn.execute(
        "SELECT stats_json FROM campaign_known_npcs WHERE campaign_id=7 AND npc_name=?",
        ("bandyta herszt",),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["stats_json"], "stats_json musi być zapisany w DB"
    assert json.loads(rows[0]["stats_json"])["STR"] == first["STR"]


def test_ensure_npc_stats_stable_after_archetype_change():
    """Zapisane staty wygrywają nad ponownym liczeniem archetypu (stabilność)."""
    conn = _mk_conn()
    ensure_npc_stats(conn, campaign_id=3, npc_name="cichy nieznajomy")
    # Ręczna podmiana zapisanych statów — kolejne wołanie musi je uszanować.
    conn.execute(
        "UPDATE campaign_known_npcs SET stats_json=? WHERE campaign_id=3 AND npc_name=?",
        (json.dumps({k: 13 for k in STAT_KEYS}), "cichy nieznajomy"),
    )
    again = ensure_npc_stats(conn, campaign_id=3, npc_name="cichy nieznajomy")
    assert all(v == 13 for v in again.values())


# ─── Template globalny ma pierwszeństwo nad archetypem ───────────────────────

def test_npcs_template_takes_precedence():
    """Gdy npcs.stats_json (template) istnieje → użyj go, nie archetypu."""
    conn = _mk_conn()
    template = {k: 11 for k in STAT_KEYS}
    template["STR"] = 18
    conn.execute(
        "INSERT INTO npcs (key, label, stats_json) VALUES (?, ?, ?)",
        ("bandyta_wodz", "Bandyta Wódz", json.dumps(template)),
    )
    # Nazwa pasuje do labelu npcs (template), choć keyword 'bandyta' = brute.
    stats = ensure_npc_stats(conn, campaign_id=1, npc_name="Bandyta Wódz")
    assert stats["STR"] == 18  # z template, nie brute (16)
    assert stats["WIS"] == 11


# ─── Cele bezimienne nie dostają wpisu ───────────────────────────────────────

def test_blank_name_no_row():
    """Pusta/whitespace nazwa → brak wpisu, brak wyjątku (fallback po stronie S4)."""
    conn = _mk_conn()
    stats = ensure_npc_stats(conn, campaign_id=1, npc_name="   ")
    assert stats is None
    rows = conn.execute("SELECT COUNT(*) c FROM campaign_known_npcs").fetchone()
    assert rows["c"] == 0
