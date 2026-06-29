"""TDD: Issue #992 — starting-hex must anchor to the location ON the hex.

Bug: resolve_starting_hex matched an existing world hex by label, then paired the
SESSION location via name-match → RANDOM canonical fallback. Result: current_hex
pointed at one place (e.g. Brzezino) while current_location_id pointed at an
unrelated random location (e.g. Pustkowie Solne) whose safe_for_rest=0 — breaking
rest and feeding wrong location context to the narrator.

Fix: _find_location_on_hex(conn, q, r) returns the game_location physically placed
on the hex (world_hex_q/r match), preferring a top-level macro over a sub-location.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db(with_world_hexes=False):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            key           TEXT NOT NULL,
            label         TEXT,
            location_type TEXT,
            parent_key    TEXT,
            is_active     INTEGER DEFAULT 1,
            world_hex_q   INTEGER,
            world_hex_r   INTEGER
        );
    """)
    if with_world_hexes:
        conn.executescript("""
            CREATE TABLE world_hexes (
                q            INTEGER,
                r            INTEGER,
                map_level    INTEGER DEFAULT 0,
                is_active    INTEGER DEFAULT 1,
                location_key TEXT,
                label        TEXT
            );
        """)
    return conn


def _ins(conn, **kw):
    conn.execute(
        "INSERT INTO game_locations (key,label,location_type,parent_key,is_active,world_hex_q,world_hex_r) "
        "VALUES (:key,:label,:location_type,:parent_key,:is_active,:world_hex_q,:world_hex_r)",
        {"label": None, "location_type": None, "parent_key": None,
         "is_active": 1, "world_hex_q": None, "world_hex_r": None, **kw},
    )
    conn.commit()


def test_returns_location_on_matching_hex():
    """The location whose world_hex_q/r match (q,r) is returned."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db()
    _ins(conn, key="brzezino", label="Brzezino", location_type="macro", world_hex_q=1, world_hex_r=0)
    _ins(conn, key="pustkowie_solne", label="Pustkowie Solne", location_type="macro", world_hex_q=None, world_hex_r=None)

    assert _find_location_on_hex(conn, 1, 0) == "brzezino"


def test_none_when_no_location_on_hex():
    """Hex with no mapped location → None (caller falls back to placement/canonical)."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db()
    _ins(conn, key="pustkowie_solne", world_hex_q=None, world_hex_r=None)

    assert _find_location_on_hex(conn, 9, 9) is None


def test_prefers_macro_over_sublocation():
    """When a settlement and its sub-location share a hex, the macro anchor wins."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db()
    _ins(conn, key="brzezino_tartak", label="Tartak", location_type="sub",
         parent_key="brzezino", world_hex_q=1, world_hex_r=0)
    _ins(conn, key="brzezino", label="Brzezino", location_type="macro",
         parent_key=None, world_hex_q=1, world_hex_r=0)

    assert _find_location_on_hex(conn, 1, 0) == "brzezino"


def test_skips_inactive_location():
    """An inactive location on the hex is ignored."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db()
    _ins(conn, key="dead", label="Dead", location_type="macro", is_active=0, world_hex_q=1, world_hex_r=0)

    assert _find_location_on_hex(conn, 1, 0) is None


# ── Canonical world_hexes pairing wins over stale game_locations coords ────────

def test_prefers_canonical_world_hex_pairing():
    """world_hexes.location_key is authoritative; used even when game_locations
    stamped the location at a DIFFERENT (stale) hex — the brzezino (1,0) vs (39,9) case."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db(with_world_hexes=True)
    # game_locations says brzezino is on a stale hex (1,0); real overworld pairing is (39,9).
    _ins(conn, key="brzezino", label="Brzezino", location_type="macro", world_hex_q=1, world_hex_r=0)
    conn.execute(
        "INSERT INTO world_hexes (q,r,map_level,is_active,location_key,label) VALUES (39,9,0,1,'brzezino','Birkenwald')"
    )
    conn.commit()

    assert _find_location_on_hex(conn, 39, 9) == "brzezino"


def test_ignores_world_hex_pairing_on_local_map_level():
    """A map_level=1 (local sub-map) world_hex pairing must NOT anchor an overworld hex."""
    from app.services.hex_travel_service import _find_location_on_hex
    conn = _make_db(with_world_hexes=True)
    conn.execute(
        "INSERT INTO world_hexes (q,r,map_level,is_active,location_key,label) VALUES (1,0,1,1,'wolanka_kosciol','Wolanka: Kościół')"
    )
    conn.commit()
    # No game_location on (1,0) either → nothing to anchor.
    assert _find_location_on_hex(conn, 1, 0) is None
