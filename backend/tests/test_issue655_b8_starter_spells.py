"""TDD: Issue #655 (B8) — Startowy zestaw maga L1.

Świeży scholar dostaje 4 czary tier 1 pokrywające pełną tożsamość maga:
atak / heal / obrona / utility — `fire_bolt`, `minor_heal`, `ward_of_iron`,
`detect_magic` (zamiast starego `magic_bolt`+`mend_wounds`+`magic_light`).

Decyzja czaru obronnego (Piotr 2026-06-15): ward_of_iron (tier 1), NIE
mage_armor (tier 2) — spójność z bramką nauki L1 z B7 (max_tier=ceil(lvl/2)=1).

Migracja istniejących magów = NIE-destrukcyjny backfill (INSERT OR IGNORE):
scholar dostaje 4 nowe czary, stare zostają nietknięte; non-scholar nic nie dostaje.
"""
import sqlite3
import pytest

import app.services.spell_service as spell_service

# Kanoniczny startowy zestaw B8 (źródło: CZĘŚĆ AK.4 + decyzja D-obronna 2026-06-15)
# B11b (#983): dodano spark_burst (tier-1 AoE) → starter ma teraz 5 czarów.
B8_STARTER = {"fire_bolt", "minor_heal", "ward_of_iron", "detect_magic", "spark_burst"}
# Stary zestaw (przed B8) — NIE może być nadawany nowym postaciom przez grant
LEGACY_STARTER = {"magic_bolt", "mend_wounds", "magic_light"}

# SQL backfillu — MUSI być identyczny z migrations_admin.py
# (v2-spells-faza-b-b8-starter-backfill). Test pilnuje semantyki migracji.
BACKFILL_SQL = """
    INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank)
    SELECT c.id, s.spell_key, 1
    FROM characters c
    CROSS JOIN (
        SELECT 'fire_bolt' AS spell_key UNION ALL
        SELECT 'minor_heal' UNION ALL
        SELECT 'ward_of_iron' UNION ALL
        SELECT 'detect_magic' UNION ALL
        SELECT 'spark_burst'
    ) s
    WHERE JSON_EXTRACT(c.sheet_json, '$.archetype') = 'scholar'
"""


def _mem_db_with_spells():
    """In-memory DB z tabelą character_spells (jak schemat produkcyjny)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            spell_key TEXT NOT NULL,
            rank INTEGER NOT NULL DEFAULT 1,
            UNIQUE(character_id, spell_key)
        )
        """
    )
    return conn


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_grant_starting_spells_is_b8_set():
    """Nowy scholar dostaje DOKŁADNIE 4 czary startowe B8."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    rows = conn.execute(
        "SELECT spell_key FROM character_spells WHERE character_id = 7"
    ).fetchall()
    granted = {r["spell_key"] for r in rows}
    assert granted == B8_STARTER, f"startowy zestaw != B8: {granted}"


def test_grant_starting_spells_no_legacy():
    """Stary zestaw (magic_bolt/mend_wounds/magic_light) NIE jest nadawany nowym magom."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    granted = {
        r["spell_key"]
        for r in conn.execute(
            "SELECT spell_key FROM character_spells WHERE character_id = 7"
        ).fetchall()
    }
    assert not (granted & LEGACY_STARTER), f"stare czary w starcie: {granted & LEGACY_STARTER}"


def test_grant_starting_spells_all_rank_1():
    """Wszystkie czary startowe na rank 1."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    ranks = {
        r["rank"]
        for r in conn.execute(
            "SELECT rank FROM character_spells WHERE character_id = 7"
        ).fetchall()
    }
    assert ranks == {1}


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_grant_is_idempotent():
    """Dwukrotne wywołanie = brak duplikatów (INSERT OR IGNORE), nadal 4 czary."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    spell_service.grant_starting_spells(7, conn)  # nie powinno rzucić ani zduplikować
    count = conn.execute(
        "SELECT COUNT(*) c FROM character_spells WHERE character_id = 7"
    ).fetchone()["c"]
    assert count == len(B8_STARTER)


# ─── Migracja istniejących magów (semantyka backfillu) ────────────────────────

def test_backfill_grants_to_scholar_only():
    """Backfill dosiewa 4 czary scholarowi, omija non-scholara."""
    conn = _mem_db_with_spells()
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT)"
    )
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (1, '{\"archetype\":\"scholar\"}')")
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (2, '{\"archetype\":\"warrior\"}')")
    conn.executescript(BACKFILL_SQL)

    scholar = {
        r["spell_key"]
        for r in conn.execute(
            "SELECT spell_key FROM character_spells WHERE character_id = 1"
        ).fetchall()
    }
    warrior = conn.execute(
        "SELECT COUNT(*) c FROM character_spells WHERE character_id = 2"
    ).fetchone()["c"]
    assert scholar == B8_STARTER, f"scholar backfill != B8: {scholar}"
    assert warrior == 0, "non-scholar nie powinien dostać czarów"


def test_backfill_is_non_destructive():
    """Backfill NIE usuwa istniejących (starych) czarów maga."""
    conn = _mem_db_with_spells()
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT)"
    )
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (1, '{\"archetype\":\"scholar\"}')")
    # istniejący mag ma stary zestaw
    for k in LEGACY_STARTER:
        conn.execute(
            "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (1, ?, 1)",
            (k,),
        )
    conn.executescript(BACKFILL_SQL)

    after = {
        r["spell_key"]
        for r in conn.execute(
            "SELECT spell_key FROM character_spells WHERE character_id = 1"
        ).fetchall()
    }
    assert LEGACY_STARTER <= after, "backfill skasował stare czary (destrukcyjny!)"
    assert B8_STARTER <= after, "backfill nie dodał nowego zestawu"


def test_backfill_idempotent():
    """Dwukrotny backfill = brak duplikatów."""
    conn = _mem_db_with_spells()
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT)"
    )
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (1, '{\"archetype\":\"scholar\"}')")
    conn.executescript(BACKFILL_SQL)
    conn.executescript(BACKFILL_SQL)
    count = conn.execute(
        "SELECT COUNT(*) c FROM character_spells WHERE character_id = 1"
    ).fetchone()["c"]
    assert count == len(B8_STARTER)
