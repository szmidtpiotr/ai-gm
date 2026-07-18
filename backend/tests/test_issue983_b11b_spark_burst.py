"""TDD: Issue #983 (B11b) — czar AoE tier 1 maga (spark_burst) w starterze.

Najniższy czar obszarowy maga. Rozszerza B11 (#659): silnik AoE już działa,
ten task dodaje tani AoE od L1 i wstawia go do startowego zestawu scholara.

spark_burst: tier 1, mana 3, spell_type='attack_aoe', damage_die='1d4', aoe=1.
Słabszy od burning_arc (T2, 1d6) — zachowuje progresję, ale daje magowi
opcję obszarową od pierwszego poziomu.
"""
from _fixtures_schema import table_sql
import sqlite3
import pytest

import app.services.spell_service as spell_service

# Startowy zestaw B11b = B8 + spark_burst (5 czarów: atak ST/AoE/heal/obrona/utility)
B11B_STARTER = {"fire_bolt", "minor_heal", "ward_of_iron", "detect_magic", "spark_burst"}

# Seed spell-row — MUSI odpowiadać migrations_admin.py (v2-spells-b11b-spark-burst)
SPARK_BURST_SEED = """
    INSERT OR IGNORE INTO game_config_spells
        (key, label, tier, mana_cost, spell_type, damage_die, heal_die,
         effect_stat, effect_type, effect_duration, target_zone, aoe, description)
    VALUES
        ('spark_burst', 'Iskrowy Wybuch', 1, 3, 'attack_aoe', '1d4', NULL,
         NULL, NULL, 1, 'any', 1, 'Wybuch iskier rani wszystkich pobliskich wrogów.')
"""

BACKFILL_SQL = """
    INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank)
    SELECT c.id, 'spark_burst', 1
    FROM characters c
    WHERE JSON_EXTRACT(c.sheet_json, '$.archetype') = 'scholar'
"""


def _mem_db_with_spells():
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


def _mem_db_with_spell_catalog():
    """In-memory game_config_spells (kolumny istotne dla testu)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        """ + table_sql("game_config_spells") + """
        """
    )
    return conn


# ─── Test główny — definicja czaru ───────────────────────────────────────────

def test_spark_burst_is_tier1_aoe():
    """spark_burst: tier 1, attack_aoe, aoe=1, mana 3, 1d4."""
    conn = _mem_db_with_spell_catalog()
    conn.executescript(SPARK_BURST_SEED)
    row = conn.execute(
        "SELECT tier, mana_cost, spell_type, damage_die, aoe FROM game_config_spells WHERE key='spark_burst'"
    ).fetchone()
    assert row is not None, "spark_burst nie zaseedowany"
    assert row["tier"] == 1, f"tier != 1: {row['tier']}"
    assert row["spell_type"] == "attack_aoe"
    assert row["aoe"] == 1, "aoe musi być 1 (wszyscy wrogowie)"
    assert row["mana_cost"] == 3
    assert row["damage_die"] == "1d4"


# ─── Starter kit ──────────────────────────────────────────────────────────────

def test_grant_starting_spells_includes_spark_burst():
    """Nowy scholar dostaje spark_burst w starcie."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    granted = {
        r["spell_key"]
        for r in conn.execute(
            "SELECT spell_key FROM character_spells WHERE character_id = 7"
        ).fetchall()
    }
    assert "spark_burst" in granted, f"spark_burst brak w starcie: {granted}"


def test_grant_starting_spells_is_b11b_set():
    """Startowy zestaw = DOKŁADNIE 5 czarów B11b."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    granted = {
        r["spell_key"]
        for r in conn.execute(
            "SELECT spell_key FROM character_spells WHERE character_id = 7"
        ).fetchall()
    }
    assert granted == B11B_STARTER, f"startowy zestaw != B11b: {granted}"


def test_grant_all_rank_1():
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    ranks = {
        r["rank"]
        for r in conn.execute(
            "SELECT rank FROM character_spells WHERE character_id = 7"
        ).fetchall()
    }
    assert ranks == {1}


# ─── Backfill istniejących magów ──────────────────────────────────────────────

def test_backfill_grants_to_scholar_only():
    """spark_burst dosiany scholarowi, omija non-scholara."""
    conn = _mem_db_with_spells()
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT)")
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (1, '{\"archetype\":\"scholar\"}')")
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (2, '{\"archetype\":\"warrior\"}')")
    conn.executescript(BACKFILL_SQL)
    scholar = {
        r["spell_key"]
        for r in conn.execute("SELECT spell_key FROM character_spells WHERE character_id = 1").fetchall()
    }
    warrior = conn.execute("SELECT COUNT(*) c FROM character_spells WHERE character_id = 2").fetchone()["c"]
    assert scholar == {"spark_burst"}
    assert warrior == 0


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_grant_is_idempotent():
    """Dwukrotne wywołanie = brak duplikatów, nadal 5 czarów."""
    conn = _mem_db_with_spells()
    spell_service.grant_starting_spells(7, conn)
    spell_service.grant_starting_spells(7, conn)
    count = conn.execute(
        "SELECT COUNT(*) c FROM character_spells WHERE character_id = 7"
    ).fetchone()["c"]
    assert count == len(B11B_STARTER)
