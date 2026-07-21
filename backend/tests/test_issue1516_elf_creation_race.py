"""Issue #1516 — nowo utworzony elf zapisywał się jako człowiek.

Oba endpointy tworzenia postaci miały własną krotkę `("human", "dwarf")`, więc
`race="elf"` z kreatora był po cichu degradowany do człowieka: elf dostawał
ludzkie staty, ludzkie czary startowe i ludzką pulę do nauki. Do tego trzy
backfille FAZY B rozdawały ludzkie czary każdemu Uczonemu przy KAŻDYM starcie
backendu (`_exec` nie ma rejestru migracji), więc czyszczenie ręczne nie trzymało.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.characters import _normalize_race
from app.migrations_admin import _purge_race_illegal_spells
from app.services import spell_service as ss


# ─── Normalizacja rasy ───────────────────────────────────────────────────────

def test_elf_survives_normalization():
    assert _normalize_race("elf") == "elf"
    assert _normalize_race(" ELF ") == "elf"


def test_known_races_pass_through():
    assert _normalize_race("human") == "human"
    assert _normalize_race("dwarf") == "dwarf"


def test_unknown_race_falls_back_to_human():
    assert _normalize_race("ork") == "human"
    assert _normalize_race(None) == "human"
    assert _normalize_race("") == "human"


# ─── Czyszczenie czarów spoza szkoły rasy ────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
          id INTEGER PRIMARY KEY, race TEXT, sheet_json TEXT
        );
        CREATE TABLE character_spells (
          character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1
        );
        CREATE TABLE game_config_spells (
          key TEXT PRIMARY KEY, race_lock TEXT
        );
    """)
    conn.executemany(
        "INSERT INTO game_config_spells (key, race_lock) VALUES (?,?)",
        [
            ("fire_bolt", "human"), ("minor_heal", "human"),
            ("ward_of_iron", "human"), ("detect_magic", "human"),
            ("spark_burst", "human"), ("magic_light", "human"),
            ("mend_wounds", "dwarf,human"),
            ("vein_tremor", "dwarf"), ("rdzen_shield", "dwarf"),
            ("tune_thorn", "elf"), ("leaf_veil", "elf"), ("root_snare", "elf"),
        ],
    )
    sheet = '{"archetype": "scholar"}'
    conn.executemany(
        "INSERT INTO characters (id, race, sheet_json) VALUES (?,?,?)",
        [(1, "elf", sheet), (2, "dwarf", sheet), (3, "human", sheet)],
    )
    conn.executemany(
        "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (?,?,?)",
        [
            # elf zalany ludzkimi czarami przez backfille FAZY B
            (1, "fire_bolt", 1), (1, "magic_light", 1), (1, "spark_burst", 1),
            # krasnolud: swoje + doklejone ludzkie + wspólne
            (2, "vein_tremor", 2), (2, "fire_bolt", 1), (2, "mend_wounds", 1),
            # człowiek: wszystko legalne
            (3, "fire_bolt", 3), (3, "minor_heal", 1),
        ],
    )
    conn.commit()
    return conn


def _spells(conn, char_id: int) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT spell_key FROM character_spells WHERE character_id = ?", (char_id,))}


def test_purge_strips_human_spells_from_elf_and_regrants_school():
    conn = _conn()
    try:
        _purge_race_illegal_spells(conn)
        # elf traci wszystko ludzkie → zostaje bez czarów → dostaje szkołę Stroiciela
        assert _spells(conn, 1) == set(ss.ELF_SCHOLAR_STARTING_SPELLS)
    finally:
        conn.close()


def test_purge_keeps_dwarf_and_shared_spells():
    conn = _conn()
    try:
        _purge_race_illegal_spells(conn)
        assert _spells(conn, 2) == {"vein_tremor", "mend_wounds"}
    finally:
        conn.close()


def test_purge_leaves_human_untouched_with_ranks():
    conn = _conn()
    try:
        _purge_race_illegal_spells(conn)
        assert _spells(conn, 3) == {"fire_bolt", "minor_heal"}
        rank = conn.execute(
            "SELECT rank FROM character_spells WHERE character_id = 3 AND spell_key = 'fire_bolt'"
        ).fetchone()[0]
        assert rank == 3  # ranga nietknięta
    finally:
        conn.close()


def test_purge_is_idempotent():
    conn = _conn()
    try:
        _purge_race_illegal_spells(conn)
        first = {cid: _spells(conn, cid) for cid in (1, 2, 3)}
        _purge_race_illegal_spells(conn)
        assert {cid: _spells(conn, cid) for cid in (1, 2, 3)} == first
    finally:
        conn.close()
