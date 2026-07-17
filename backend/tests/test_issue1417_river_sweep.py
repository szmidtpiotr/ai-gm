"""TDD: Issue #1417 — porwanie przez nurt PRZENOSI PIN 1d4 hexów wzdłuż rzeki.

Tu: trasowanie rzeki `_sweep_along_river` (pure) — niesie N hexów wzdłuż łańcucha rzeki
i wyrzuca na LOSOWY przyległy przechodni brzeg. Pełny przepływ (przeniesienie pina,
obrażenia, przemoczony) = live smoke na DEV.
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services.hex_travel_service import _sweep_along_river


def _conn(hexes):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains',
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        )
    """)
    for (q, r, t) in hexes:
        conn.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (?,?,?)", (q, r, t))
    conn.commit()
    return conn


def test_sweep_carries_along_river_to_bank():
    """Bród na (0,0), rzeka w linii (1,0),(2,0),(3,0), ląd obok → wyrzut na ląd."""
    # oś flat-top: sąsiedzi (q±1,r), (q,r±1), (q+1,r-1), (q-1,r+1)
    conn = _conn([
        (0, 0, "brod"),
        (1, 0, "river"), (2, 0, "river"), (3, 0, "river"),
        (1, 1, "plains"), (2, 1, "plains"), (3, 1, "plains"),  # brzeg południowy
    ])
    res = _sweep_along_river(conn, (0, 0), 3)
    conn.close()
    assert res is not None, "musi wyrzucić na brzeg"
    bank = res["bank"]
    # brzeg to LĄD, nie rzeka
    assert bank not in [(1, 0), (2, 0), (3, 0)]
    # river_path to hexy RZEKI (spływ)
    assert all(h in [(1, 0), (2, 0), (3, 0)] for h in res["river_path"])
    assert len(res["river_path"]) >= 1


def test_sweep_no_river_returns_none():
    """Brak rzeki obok brodu → None (fallback do starego zachowania w hazardzie)."""
    conn = _conn([(0, 0, "brod"), (1, 0, "plains"), (0, 1, "plains")])
    assert _sweep_along_river(conn, (0, 0), 3) is None
    conn.close()


def test_sweep_river_no_land_returns_none():
    """Rzeka bez przyległego lądu (otoczona wodą) → None."""
    conn = _conn([
        (0, 0, "brod"),
        (1, 0, "river"), (2, 0, "river"),
        (1, 1, "water"), (2, 1, "lake"), (0, 1, "sea"),
    ])
    # wszystkie sąsiedztwa rzek to woda → brak brzegu
    assert _sweep_along_river(conn, (0, 0), 2) is None
    conn.close()


def test_sweep_distance_one_still_finds_bank():
    """Dystans 1 — pierwszy hex rzeki, brzeg tuż obok."""
    conn = _conn([(0, 0, "brod"), (1, 0, "river"), (1, 1, "forest")])
    res = _sweep_along_river(conn, (0, 0), 1)
    conn.close()
    assert res is not None and res["bank"] == (1, 1)
    assert res["river_path"] == [(1, 0)]
