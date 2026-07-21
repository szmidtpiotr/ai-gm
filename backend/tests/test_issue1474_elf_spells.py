"""Issue #1474 — szkoła Stroiciela: czary race-locked elfa + łagodny miscast.

Kanon magii (#1509): jedno źródło (Rdzeń), cztery techniki. Elf **stroi** —
kontrola/ochrona/iluzje, niższe obrażenia, miscast łagodniejszy i fabularnie inny
(„las odpowiada nie tak, jak prosiłeś"), nie krwawy jak u krasnoluda.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.migrations_admin import _seed_elf_spells
from app.services import spell_service as ss


# ─── Zestaw startowy ─────────────────────────────────────────────────────────

def test_elf_scholar_starting_spells():
    assert ss.ELF_SCHOLAR_STARTING_SPELLS == ("tune_thorn", "leaf_veil", "root_snare")


def test_starting_sets_are_disjoint():
    """Pule ras nie mogą się przenikać — inaczej race_lock traci sens."""
    human = set(ss.HUMAN_SCHOLAR_STARTING_SPELLS)
    dwarf = set(ss.DWARF_SCHOLAR_STARTING_SPELLS)
    elf = set(ss.ELF_SCHOLAR_STARTING_SPELLS)
    assert not (elf & human) and not (elf & dwarf) and not (dwarf & human)


def test_unknown_race_falls_back_to_human_set():
    assert ss._RACE_STARTING_SPELLS.get("wyspiarz", ss.HUMAN_SCHOLAR_STARTING_SPELLS) == \
        ss.HUMAN_SCHOLAR_STARTING_SPELLS


# ─── Katalog czarów ──────────────────────────────────────────────────────────

def _spells_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_spells (
          key TEXT PRIMARY KEY, label TEXT, tier INTEGER, mana_cost INTEGER,
          spell_type TEXT DEFAULT 'attack', damage_die TEXT, description TEXT,
          is_active INTEGER DEFAULT 1, race_lock TEXT, effect_json TEXT, aoe INTEGER
        )
    """)
    conn.commit()
    return conn


def test_seed_creates_six_elf_locked_spells():
    conn = _spells_conn()
    try:
        _seed_elf_spells(conn)
        rows = conn.execute(
            "SELECT key, race_lock, spell_type, tier FROM game_config_spells ORDER BY tier, key"
        ).fetchall()
        keys = [r["key"] for r in rows]
        assert len(rows) == 6
        assert set(keys) == {
            "tune_thorn", "leaf_veil", "root_snare",
            "false_grove", "hush_of_boughs", "mend_bark",
        }
        assert all(r["race_lock"] == "elf" for r in rows)
    finally:
        conn.close()


def test_school_is_control_and_protection_not_burst():
    """Tożsamość szkoły: więcej kontroli/ochrony niż czystych obrażeń."""
    conn = _spells_conn()
    try:
        _seed_elf_spells(conn)
        types = [r["spell_type"] for r in conn.execute(
            "SELECT spell_type FROM game_config_spells"
        ).fetchall()]
        attacking = [t for t in types if str(t).startswith("attack")]
        assert len(attacking) <= 2, "Stroiciel nie jest szkołą ognia"
        assert "defense" in types and "heal" in types
        assert "effect" in types and "effect_aoe" in types
    finally:
        conn.close()


def test_elf_damage_is_lower_than_dwarf_at_same_tier():
    """Elf tier 1 = 1d6; krasnolud tier 1 (vein_tremor) = 2d6. Damage ↓, kontrola ↑."""
    conn = _spells_conn()
    try:
        _seed_elf_spells(conn)
        die = conn.execute(
            "SELECT damage_die FROM game_config_spells WHERE key='tune_thorn'"
        ).fetchone()["damage_die"]
        assert die == "1d6"
    finally:
        conn.close()


def test_seed_is_idempotent():
    conn = _spells_conn()
    try:
        _seed_elf_spells(conn)
        _seed_elf_spells(conn)
        n = conn.execute("SELECT COUNT(*) FROM game_config_spells").fetchone()[0]
        assert n == 6
    finally:
        conn.close()


# ─── Miscast strojenia ───────────────────────────────────────────────────────

def _sheet(level: int, hp: int = 30) -> dict:
    return {"level": level, "current_hp": hp, "max_hp": hp}


def test_elf_miscast_is_flagged_and_harmless_at_low_levels():
    sheet = _sheet(2)
    out = ss.resolve_miscast(sheet, {}, conn=None, race="elf")
    assert out["tuning_miscast"] is True and out["rdzen_miscast"] is False
    assert out["self_damage"] == 0
    assert out["stun"] is False, "strojenie nie ogłusza na niskich poziomach"
    assert "las" in out["narrative"].lower() or "liście" in out["narrative"].lower()


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_elf_miscast_never_damages_below_level_5(level):
    out = ss.resolve_miscast(_sheet(level), {}, conn=None, race="elf")
    assert out["self_damage"] == 0


def test_elf_miscast_is_milder_than_dwarf_at_high_level():
    # Kość ustawiona na maksimum swojego zakresu — porównujemy najgorszy przypadek.
    with patch.object(ss.random, "randint", side_effect=lambda a, b: b):
        elf_out = ss.resolve_miscast(_sheet(10), {}, conn=None, race="elf")
        dwarf_out = ss.resolve_miscast(_sheet(10), {}, conn=None, race="dwarf")
    # Krasnolud: d8 + efekt kaskadowy. Elf: d6, bez kaskady.
    assert elf_out["self_damage"] == 6 and dwarf_out["self_damage"] == 8
    assert "secondary" in dwarf_out and "secondary" not in elf_out


def test_elf_miscast_threshold_is_human_like():
    """Tylko krasnolud pudłuje na Nat 2 — elf jak człowiek, na Nat 1."""
    assert ss.is_miscast(1, "elf") is True
    assert ss.is_miscast(2, "elf") is False
    assert ss.is_miscast(2, "dwarf") is True


def test_human_miscast_unchanged():
    out = ss.resolve_miscast(_sheet(2), {}, conn=None, race="human")
    assert out["rdzen_miscast"] is False and out["tuning_miscast"] is False
    assert out["stun"] is True, "ludzka drabina bez zmian (zero regresji)"
