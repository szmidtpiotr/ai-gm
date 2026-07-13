"""TDD: Issue #1353 (WALKA-T3) — data-fix metadanych czarów.

Rdzeń-Tarcza ma w bazie spell_type='attack' zamiast 'defense', a opisy czarów
krasnoludzkich są przycięte (stale INSERT OR IGNORE nigdy ich nie odświeżył).
Migracja `_fix_1353_spell_metadata` musi to naprawić na istniejących bazach.
"""
from _fixtures_schema import table_sql
import sqlite3

import pytest

from app.migrations_admin import _fix_1353_spell_metadata


def _stale_db() -> sqlite3.Connection:
    """Baza w stanie sprzed fixa: rdzen_shield='attack', krótkie opisy."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        """ + table_sql("game_config_spells") + """
        """
    )
    rows = [
        ("rdzen_shield", "Rdzeń-Tarcza", 2, 2, "attack", None, None, "Absorb hit", 1, "dwarf"),
        ("rdzen_pulse", "Rdzeń-Puls", 2, 2, "attack", None, None, "2d4 obszarowe + stun", 1, "dwarf"),
        ("magic_bolt", "Błysk Magiczny", 1, 2, "attack", "2d6", None,
         "Strumień magicznej energii uderzający wroga.", 1, None),
    ]
    conn.executemany(
        "INSERT INTO game_config_spells "
        "(key,label,tier,mana_cost,spell_type,damage_die,heal_die,description,is_active,race_lock) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_rdzen_shield_becomes_defense():
    """Rdzeń-Tarcza po migracji ma spell_type='defense' (trafia do sekcji Ochronne)."""
    conn = _stale_db()
    _fix_1353_spell_metadata(conn)
    row = conn.execute(
        "SELECT spell_type FROM game_config_spells WHERE key='rdzen_shield'"
    ).fetchone()
    assert row[0] == "defense"


def test_short_descriptions_get_enriched():
    """Przycięty opis Rdzeń-Tarczy (<30 zn.) zostaje rozpisany na pełne zdanie PL."""
    conn = _stale_db()
    _fix_1353_spell_metadata(conn)
    desc = conn.execute(
        "SELECT description FROM game_config_spells WHERE key='rdzen_shield'"
    ).fetchone()[0]
    assert desc and len(desc) >= 30
    assert "attack" not in desc.lower()  # opis efektu, nie surowy enum


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_rdzen_pulse_stays_attack():
    """rdzen_pulse pozostaje 'attack' (spec: OK) — fix nie rusza innych typów."""
    conn = _stale_db()
    _fix_1353_spell_metadata(conn)
    row = conn.execute(
        "SELECT spell_type FROM game_config_spells WHERE key='rdzen_pulse'"
    ).fetchone()
    assert row[0] == "attack"


def test_unrelated_spell_untouched_type():
    """Zwykły czar (magic_bolt) niezmieniony co do typu."""
    conn = _stale_db()
    _fix_1353_spell_metadata(conn)
    row = conn.execute(
        "SELECT spell_type FROM game_config_spells WHERE key='magic_bolt'"
    ).fetchone()
    assert row[0] == "attack"


def test_idempotent():
    """Dwukrotne uruchomienie nie psuje danych."""
    conn = _stale_db()
    _fix_1353_spell_metadata(conn)
    _fix_1353_spell_metadata(conn)
    row = conn.execute(
        "SELECT spell_type FROM game_config_spells WHERE key='rdzen_shield'"
    ).fetchone()
    assert row[0] == "defense"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
