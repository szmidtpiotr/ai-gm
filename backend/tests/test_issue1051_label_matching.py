"""TDD: Issue #1051 — direct label fuzzy matching eliminates stem/keyword brittleness.

Primary: search game_locations.label directly against player message (token overlap)
BEFORE falling back to _INTENT_KEYWORDS subtype matching.
"""
import sqlite3

import pytest

from app.services import location_context_injector as lci


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT, label TEXT, description TEXT,
            location_subtype TEXT, location_type TEXT, biome TEXT,
            placement TEXT, parent_id INTEGER,
            world_hex_q INTEGER, world_hex_r INTEGER,
            approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT, label TEXT,
            atmosphere TEXT, location_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            location_key TEXT, npc_key TEXT, assignment_type TEXT,
            is_active INTEGER DEFAULT 1
        );
        """
    )
    return conn


def _add_loc(conn, key, label, subtype=None, q=0, r=0, approved=1, active=1):
    conn.execute(
        """INSERT INTO game_locations
           (key, label, location_subtype, world_hex_q, world_hex_r, approved, is_active)
           VALUES (?,?,?,?,?,?,?)""",
        (key, label, subtype, q, r, approved, active),
    )
    conn.commit()


def _add_hex(conn, q, r, hex_type="town", label="Miejsce"):
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, label) VALUES (?,?,?,?)",
        (q, r, hex_type, label),
    )
    conn.commit()


# ─── Test główny — dopasowanie po nazwie poza listą keywordów ────────────────

def test_label_match_finds_location_by_proper_name():
    """'idę do Kuźni Volmara' → kandydat Kuźnia Volmara po nazwie (token 'volmar')."""
    conn = _make_conn()
    _add_loc(conn, "kuznia_volmara", "Kuźnia Volmara", subtype="smithy", q=0, r=0)
    cands = lci._find_label_candidates(conn, 0, 0, "idę do Kuźni Volmara")
    assert any(c["key"] == "kuznia_volmara" for c in cands), \
        "Lokacja powinna być dopasowana po nazwie (Volmara)"


def test_swiat_block_label_match_suppresses_brak_dopasowania():
    """Karczma istnieje, gracz pisze 'karczma' → dopasowanie po nazwie, NIE brak_dopasowania."""
    conn = _make_conn()
    _add_hex(conn, 0, 0)
    _add_loc(conn, "karczma_lok", "Karczma Pod Wisielcem", subtype="tavern", q=0, r=0)
    block = lci.build_swiat_block(conn, {"current_hex": {"q": 0, "r": 0}}, "wchodzę do karczmy")
    assert block is not None
    assert "Karczma Pod Wisielcem" in block
    assert "brak_dopasowania: true" not in block


def test_no_label_no_subtype_yields_brak_dopasowania():
    """'kapliczka', brak istniejącej kapliczki → brak_dopasowania → LLM może stworzyć."""
    conn = _make_conn()
    _add_hex(conn, 0, 0, hex_type="plains")
    block = lci.build_swiat_block(
        conn, {"current_hex": {"q": 0, "r": 0}}, "szukam kapliczki przydrożnej"
    )
    assert block is not None
    assert "brak_dopasowania: true" in block


# ─── Backward compatibility — fallback po subtype nadal działa ───────────────

def test_subtype_fallback_when_label_has_no_overlap():
    """Tawerna o nazwie bez wspólnych tokenów ('Pod Złotym Lwem') vs 'gospoda'
    → brak trafienia po nazwie → fallback subtype 'tavern' dopasowuje."""
    conn = _make_conn()
    _add_hex(conn, 0, 0)
    _add_loc(conn, "tav1", "Pod Złotym Lwem", subtype="tavern", q=0, r=1)
    block = lci.build_swiat_block(conn, {"current_hex": {"q": 0, "r": 0}}, "szukam gospody")
    assert block is not None
    assert "Pod Złotym Lwem" in block
    assert "brak_dopasowania: true" not in block


def test_detect_intent_unchanged():
    """_INTENT_KEYWORDS subtype detection pozostaje bez zmian."""
    assert "tavern" in lci._detect_location_intent("idę do karczmy")
    assert "shrine" in lci._detect_location_intent("kapliczka przydrożna")


def test_label_candidate_distance_gate():
    """Lokacja po nazwie dalej niż 5 hexów nie jest kandydatem."""
    conn = _make_conn()
    _add_loc(conn, "far_smithy", "Kuźnia Volmara", subtype="smithy", q=20, r=0)
    cands = lci._find_label_candidates(conn, 0, 0, "idę do Volmara")
    assert all(c["key"] != "far_smithy" for c in cands), \
        "Lokacja >5 hexów nie powinna być kandydatem po nazwie"
