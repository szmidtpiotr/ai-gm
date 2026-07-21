"""Issue #1510 — pule czarów per rasa: elf w adminie + jawny race_lock + filtr katalogu.

Kanon (Księga Zasad, rozdz. Rasy): jedno źródło mocy, trzy techniki. Człowiek
czerpie arkana, krasnolud wydziera Rdzeń, elf stroi. Żadna szkoła nie uczy się
czarów pozostałych — a admin musi umieć to ustawić dla wszystkich trzech ras.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.migrations_admin import _backfill_spell_race_lock
from app.routers import admin as admin_router
from app.services import spell_service as ss


# ─── Admin: whitelisty ───────────────────────────────────────────────────────

def test_admin_knows_elf_race():
    assert admin_router._SPELL_RACES == {"human", "dwarf", "elf"}


def test_normalize_race_lock_accepts_elf():
    assert admin_router._normalize_race_lock("elf") == "elf"
    assert admin_router._normalize_race_lock("elf,human") == "elf,human"  # sorted


def test_normalize_race_lock_rejects_unknown():
    with pytest.raises(Exception):
        admin_router._normalize_race_lock("ork")


def test_spell_types_cover_every_type_in_seed():
    """Typy z DB (narrative/reaction/summon/effect_aoe) muszą przechodzić zapis."""
    for t in ("narrative", "reaction", "summon", "effect_aoe", "attack_aoe"):
        assert t in admin_router._SPELL_TYPES


# ─── Migracja backfill ───────────────────────────────────────────────────────

def _spells_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_spells (
          key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1,
          mana_cost INTEGER DEFAULT 1, spell_type TEXT DEFAULT 'attack',
          damage_die TEXT, heal_die TEXT, description TEXT,
          is_active INTEGER DEFAULT 1, race_lock TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO game_config_spells (key, label, tier, race_lock) VALUES (?,?,?,?)",
        [
            ("fire_bolt", "Ognisty Pocisk", 1, None),
            ("magic_light", "Magiczne Światło", 1, ""),
            ("vein_tremor", "Żyłowy Wstrząs", 1, "dwarf"),
            ("tune_thorn", "Nastrojony Cierń", 1, "elf"),
            ("mend_wounds", "Rana Uleczona", 1, "dwarf,human"),
        ],
    )
    conn.commit()
    return conn


def test_backfill_fills_null_with_human_and_keeps_race_pools():
    conn = _spells_conn()
    try:
        _backfill_spell_race_lock(conn)
        got = {r["key"]: r["race_lock"]
               for r in conn.execute("SELECT key, race_lock FROM game_config_spells")}
        assert got["fire_bolt"] == "human"      # NULL → jawny human
        assert got["magic_light"] == "human"    # "" → jawny human
        assert got["vein_tremor"] == "dwarf"    # rasowe nietknięte
        assert got["tune_thorn"] == "elf"
        assert got["mend_wounds"] == "dwarf,human"  # wspólne nietknięte
    finally:
        conn.close()


def test_backfill_is_idempotent():
    conn = _spells_conn()
    try:
        _backfill_spell_race_lock(conn)
        first = conn.execute("SELECT key, race_lock FROM game_config_spells").fetchall()
        _backfill_spell_race_lock(conn)
        second = conn.execute("SELECT key, race_lock FROM game_config_spells").fetchall()
        assert [tuple(r) for r in first] == [tuple(r) for r in second]
    finally:
        conn.close()


# ─── Reguła rasy ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("race,lock,expected", [
    ("human", "human", True),
    ("human", "dwarf", False),
    ("human", "elf", False),
    ("dwarf", "dwarf", True),
    ("dwarf", "human", False),
    ("dwarf", "elf", False),
    ("elf", "elf", True),
    ("elf", "human", False),
    ("elf", "dwarf", False),
    ("elf", "dwarf,human", False),
    ("dwarf", "dwarf,human", True),
    ("human", None, True),      # legacy NULL = pula ludzka
    ("elf", None, False),
    ("dwarf", "", False),
    (None, "human", True),      # brak rasy → human
])
def test_race_can_learn_matrix(race, lock, expected):
    assert ss.race_can_learn(race, lock) is expected


# ─── Katalog filtrowany rasą ─────────────────────────────────────────────────

def _catalog_conn() -> sqlite3.Connection:
    conn = _spells_conn()
    _backfill_spell_race_lock(conn)
    return conn


def test_catalog_filters_by_race():
    # get_spell_catalog zamyka połączenie → każde wywołanie dostaje świeże.
    with patch.object(ss, "_get_db", side_effect=_catalog_conn):
        elf = {sp["key"] for sp in ss.get_spell_catalog("elf")}
        dwarf = {sp["key"] for sp in ss.get_spell_catalog("dwarf")}
        human = {sp["key"] for sp in ss.get_spell_catalog("human")}
    assert elf == {"tune_thorn"}
    assert dwarf == {"vein_tremor", "mend_wounds"}
    assert human == {"fire_bolt", "magic_light", "mend_wounds"}


def test_catalog_without_race_returns_everything():
    with patch.object(ss, "_get_db", side_effect=_catalog_conn):
        allsp = ss.get_spell_catalog()
    assert len(allsp) == 5
