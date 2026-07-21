"""Issue #1518 — czary użytkowe elfa i krasnoluda (wyrównanie pul bez ruszania bojówki).

Decyzja designerska: ogień/mróz/nekromancja zostają ludzkie, Rdzeń krasnoludzki,
strojenie elfie. Wyrównujemy UŻYTKOWYMI czarami pisanymi pod lore każdej rasy —
nie otwieraniem ludzkiej puli.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.migrations_admin import _backfill_spell_race_lock, _seed_race_utility_spells
from app.services import spell_service as ss


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_spells (
          key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1,
          mana_cost INTEGER DEFAULT 1, spell_type TEXT DEFAULT 'attack',
          damage_die TEXT, heal_die TEXT, target_zone TEXT DEFAULT 'any',
          aoe INTEGER DEFAULT 0, description TEXT,
          is_active INTEGER DEFAULT 1, race_lock TEXT
        )
    """)
    conn.commit()
    return conn


def _rows(conn, race: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM game_config_spells WHERE race_lock = ? ORDER BY tier, key", (race,)
    ).fetchall()


def test_seeds_seven_spells_per_race():
    conn = _conn()
    try:
        _seed_race_utility_spells(conn)
        assert len(_rows(conn, "elf")) == 7
        assert len(_rows(conn, "dwarf")) == 7
    finally:
        conn.close()


def test_all_utility_spells_are_narrative_and_harmless():
    """Użytkowe = narrative: brak kości obrażeń/leczenia, brak AoE, cel = self."""
    conn = _conn()
    try:
        _seed_race_utility_spells(conn)
        for row in conn.execute("SELECT * FROM game_config_spells"):
            assert row["spell_type"] == "narrative", row["key"]
            assert row["damage_die"] is None and row["heal_die"] is None, row["key"]
            assert row["aoe"] == 0 and row["target_zone"] == "self", row["key"]
            assert (row["description"] or "").strip(), row["key"]
    finally:
        conn.close()


def test_tier_spread_covers_one_to_five():
    """Elf miał dziurę na T4/T5 — po tej fali każda rasa ma czym grać do końca."""
    conn = _conn()
    try:
        _seed_race_utility_spells(conn)
        for race in ("elf", "dwarf"):
            tiers = sorted(r["tier"] for r in _rows(conn, race))
            assert tiers == [1, 1, 2, 2, 3, 4, 5], (race, tiers)
    finally:
        conn.close()


def test_pools_stay_disjoint_no_human_spell_touched():
    conn = _conn()
    try:
        _seed_race_utility_spells(conn)
        assert not _rows(conn, "human")
        for row in conn.execute("SELECT race_lock FROM game_config_spells"):
            assert row["race_lock"] in ("elf", "dwarf")
    finally:
        conn.close()


def test_seed_is_idempotent():
    conn = _conn()
    try:
        _seed_race_utility_spells(conn)
        _seed_race_utility_spells(conn)
        assert conn.execute("SELECT COUNT(*) FROM game_config_spells").fetchone()[0] == 14
    finally:
        conn.close()


def test_catalog_shows_new_spells_to_their_race_only():
    def factory():
        conn = _conn()
        _seed_race_utility_spells(conn)
        _backfill_spell_race_lock(conn)
        return conn

    from unittest.mock import patch
    with patch.object(ss, "_get_db", side_effect=factory):
        elf = {sp["key"] for sp in ss.get_spell_catalog("elf")}
        dwarf = {sp["key"] for sp in ss.get_spell_catalog("dwarf")}
        human = {sp["key"] for sp in ss.get_spell_catalog("human")}
    assert "warden_tree" in elf and "anvil_ward" not in elf
    assert "anvil_ward" in dwarf and "warden_tree" not in dwarf
    assert human == set()
