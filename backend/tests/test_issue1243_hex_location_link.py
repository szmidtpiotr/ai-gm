"""TDD: Issue #1243 (R3) — one canonical direction for the hex↔location link.

Decision: the OVERWORLD hex (`world_hexes.location_key`, map_level=0) is canon;
`game_locations.world_hex_q/r` is a derived cache. `reconcile_location_hex_links`
rebuilds the cache from hex canon and clears stale/junk pins.

The headline test seeds a deliberately DRIFTED fixture (mirroring the real DEV DB
pollution: brzezino stamped (1,0) while it lives on hex (39,9); a (0,0) junk pile;
a stray sub-pin on wolanka's hex; a borowiec smear on two hexes) and asserts the
DB is consistent afterwards.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL, r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT, location_key TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    parent_hex_id INTEGER,
    map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
    parent_key TEXT DEFAULT NULL, location_type TEXT DEFAULT 'macro',
    is_active INTEGER NOT NULL DEFAULT 1,
    world_hex_q INTEGER, world_hex_r INTEGER,
    placement TEXT NOT NULL DEFAULT 'floating'
);
"""


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _hex(c, q, r, location_key=None, map_level=0):
    c.execute(
        "INSERT INTO world_hexes (q,r,location_key,map_level) VALUES (?,?,?,?)",
        (q, r, location_key, map_level),
    )


def _loc(c, key, wq=None, wr=None, **kw):
    c.execute(
        "INSERT INTO game_locations (key,label,parent_key,location_type,is_active,world_hex_q,world_hex_r,placement) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            key, kw.get("label", key), kw.get("parent_key"),
            kw.get("location_type", "macro"), kw.get("is_active", 1),
            wq, wr, kw.get("placement", "placed" if wq is not None else "floating"),
        ),
    )


# ── link_location_to_hex — the single writer ────────────────────────────────────

def test_link_writes_both_canon_and_cache():
    c = _conn()
    _hex(c, 39, 9, location_key=None)
    _loc(c, "brzezino", wq=None, wr=None)
    from app.services.hex_location_link import link_location_to_hex
    assert link_location_to_hex(c, "brzezino", 39, 9) is True
    assert c.execute("SELECT location_key FROM world_hexes WHERE q=39 AND r=9").fetchone()["location_key"] == "brzezino"
    row = c.execute("SELECT world_hex_q, world_hex_r, placement FROM game_locations WHERE key='brzezino'").fetchone()
    assert (row["world_hex_q"], row["world_hex_r"], row["placement"]) == (39, 9, "placed")


def test_link_only_if_empty_does_not_steal_claimed_hex():
    c = _conn()
    _hex(c, 5, 5, location_key="settlement")
    _loc(c, "settlement", wq=5, wr=5)
    _loc(c, "intruder", wq=None, wr=None)
    from app.services.hex_location_link import link_location_to_hex
    assert link_location_to_hex(c, "intruder", 5, 5, only_if_empty=True) is False
    assert c.execute("SELECT location_key FROM world_hexes WHERE q=5 AND r=5").fetchone()["location_key"] == "settlement"
    # cache untouched because the claim failed
    assert c.execute("SELECT world_hex_q FROM game_locations WHERE key='intruder'").fetchone()["world_hex_q"] is None


def test_link_level1_sets_only_hex_no_cache():
    c = _conn()
    _hex(c, 0, 0, location_key=None, map_level=1)
    _loc(c, "sub_room", wq=None, wr=None, location_type="sub")
    from app.services.hex_location_link import link_location_to_hex
    link_location_to_hex(c, "sub_room", 0, 0, level=1)
    assert c.execute("SELECT location_key FROM world_hexes WHERE map_level=1").fetchone()["location_key"] == "sub_room"
    # level-1 must NOT stamp the overworld cache
    assert c.execute("SELECT world_hex_q FROM game_locations WHERE key='sub_room'").fetchone()["world_hex_q"] is None


# ── location_on_hex / resolve_location_to_hex readers ───────────────────────────

def test_location_on_hex_canon_first():
    c = _conn()
    _hex(c, 21, 1, location_key="wolanka")
    _loc(c, "wolanka", wq=21, wr=1)
    from app.services.hex_location_link import location_on_hex, resolve_location_to_hex
    assert location_on_hex(c, 21, 1) == "wolanka"
    assert resolve_location_to_hex(c, "wolanka") == (21, 1)


def test_location_on_hex_cache_fallback_when_canon_missing():
    c = _conn()
    # no hex canon, only the derived cache still knows the pairing
    _hex(c, 21, 1, location_key="temp_camp_x")
    _loc(c, "temp_camp_x", wq=None, wr=None)
    _loc(c, "wolanka", wq=21, wr=1)
    from app.services.hex_location_link import resolve_location_to_hex
    assert resolve_location_to_hex(c, "wolanka") == (21, 1)


# ── reconcile — the headline consistency migration ──────────────────────────────

def test_reconcile_deliberate_drift_becomes_consistent():
    c = _conn()
    # Canon hexes (clean side).
    _hex(c, 39, 9, location_key="brzezino")
    _hex(c, 21, 1, location_key="wolanka")
    _hex(c, 42, 1, location_key="borowiec")
    _hex(c, 43, 1, location_key="borowiec")   # smear: same key on two hexes

    # Locations with DRIFTED / junk caches (mirrors real DEV pollution).
    _loc(c, "brzezino", wq=1, wr=0)                        # cache says (1,0), hex says (39,9)
    _loc(c, "wolanka", wq=21, wr=1)                        # consistent
    _loc(c, "borowiec", wq=42, wr=1)                       # smear owner, canon (42,1)
    _loc(c, "junk_a", wq=0, wr=0)                          # (0,0) pile — no hex backs it
    _loc(c, "junk_b", wq=0, wr=0)
    _loc(c, "stray_sub", wq=21, wr=1, parent_key="wolanka", location_type="sub")  # stray pin on wolanka's hex

    from app.services.hex_location_link import reconcile_location_hex_links
    report = reconcile_location_hex_links(c)

    # brzezino cache repaired to hex canon.
    b = c.execute("SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='brzezino'").fetchone()
    assert (b["world_hex_q"], b["world_hex_r"]) == (39, 9)

    # Smear resolved: borowiec keeps its canon-matching hex (42,1), (43,1) cleared.
    kept = {(row["q"], row["r"]): row["location_key"]
            for row in c.execute("SELECT q, r, location_key FROM world_hexes WHERE location_key='borowiec'")}
    assert kept == {(42, 1): "borowiec"}

    # Junk (0,0) pins cleared (no hex backs them).
    for k in ("junk_a", "junk_b", "stray_sub"):
        row = c.execute("SELECT world_hex_q, world_hex_r FROM game_locations WHERE key=?", (k,)).fetchone()
        assert row["world_hex_q"] is None, f"{k} should have lost its stale pin"

    # wolanka untouched.
    w = c.execute("SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='wolanka'").fetchone()
    assert (w["world_hex_q"], w["world_hex_r"]) == (21, 1)

    # Invariant: after reconcile, every location with a cached pin is backed by
    # a hex whose location_key points right back at it — zero drift.
    rows = c.execute(
        "SELECT gl.key, gl.world_hex_q q, gl.world_hex_r r FROM game_locations gl "
        "WHERE gl.is_active=1 AND gl.world_hex_q IS NOT NULL"
    ).fetchall()
    for row in rows:
        hx = c.execute(
            "SELECT location_key FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1",
            (row["q"], row["r"]),
        ).fetchone()
        assert hx and hx["location_key"] == row["key"], f"{row['key']} drift survived reconcile"

    assert report["canonical_pairs"] == 3
    assert len(report["smears"]) == 1
    assert any(x["key"] == "brzezino" for x in report["backfilled"])


def test_reconcile_promotes_pin_on_empty_hex():
    """A location cached on an EXISTING but empty hex (e.g. a template start
    location whose hex-claim was never written) is PROMOTED to canon, not cleared —
    it keeps its map pin."""
    c = _conn()
    _hex(c, 38, 6, location_key=None)   # empty template start hex
    _loc(c, "blotstein", wq=38, wr=6)   # cache points here, hex doesn't back it yet
    from app.services.hex_location_link import reconcile_location_hex_links
    rep = reconcile_location_hex_links(c)
    assert any(p["key"] == "blotstein" for p in rep["promoted"])
    # hex canon now written, cache preserved
    assert c.execute("SELECT location_key FROM world_hexes WHERE q=38 AND r=6").fetchone()["location_key"] == "blotstein"
    loc = c.execute("SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='blotstein'").fetchone()
    assert (loc["world_hex_q"], loc["world_hex_r"]) == (38, 6)


def test_reconcile_clears_pin_when_hex_missing_or_occupied():
    """No hex row (junk (0,0) default) or an occupied hex → the stray pin is cleared."""
    c = _conn()
    _hex(c, 5, 5, location_key="real_owner")   # occupied
    _loc(c, "real_owner", wq=5, wr=5)
    _loc(c, "no_hex_junk", wq=0, wr=0)          # no hex row at (0,0)
    _loc(c, "wants_occupied", wq=5, wr=5)       # hex holds real_owner
    from app.services.hex_location_link import reconcile_location_hex_links
    reconcile_location_hex_links(c)
    assert c.execute("SELECT world_hex_q FROM game_locations WHERE key='no_hex_junk'").fetchone()["world_hex_q"] is None
    assert c.execute("SELECT world_hex_q FROM game_locations WHERE key='wants_occupied'").fetchone()["world_hex_q"] is None
    # real owner untouched
    assert c.execute("SELECT world_hex_q FROM game_locations WHERE key='real_owner'").fetchone()["world_hex_q"] == 5


def test_reconcile_idempotent():
    c = _conn()
    _hex(c, 39, 9, location_key="brzezino")
    _loc(c, "brzezino", wq=1, wr=0)
    from app.services.hex_location_link import reconcile_location_hex_links
    reconcile_location_hex_links(c)
    second = reconcile_location_hex_links(c)
    assert second["backfilled"] == [] and second["cleared"] == [] and second["smears"] == []
