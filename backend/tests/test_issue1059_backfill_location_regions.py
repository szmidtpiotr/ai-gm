"""TDD: Issue #1059 — backfill region on game_locations with NULL region."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.world_service import backfill_location_regions


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            map_level INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'kresy',
            location_key TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            region TEXT,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    return conn


# ─── Test główny — hex lookup ─────────────────────────────────────────────────

def test_backfill_location_regions_from_hex():
    """Location with hex coords should get region from world_hexes."""
    conn = _make_db()
    conn.execute("INSERT INTO world_hexes(q,r,region,map_level) VALUES(5,10,'czarnobor',0)")
    conn.execute(
        "INSERT INTO game_locations(key,label,region,world_hex_q,world_hex_r) VALUES('loc_a','Loc A',NULL,5,10)"
    )
    conn.commit()

    n = backfill_location_regions(conn)

    row = conn.execute("SELECT region FROM game_locations WHERE key='loc_a'").fetchone()
    assert row["region"] == "czarnobor", f"Expected 'czarnobor', got {row['region']!r}"
    assert n == 1


def test_backfill_location_regions_fallback_kresy():
    """Location without hex coords should get fallback region 'kresy'."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_locations(key,label,region,world_hex_q,world_hex_r) VALUES('loc_b','Loc B',NULL,NULL,NULL)"
    )
    conn.commit()

    n = backfill_location_regions(conn)

    row = conn.execute("SELECT region FROM game_locations WHERE key='loc_b'").fetchone()
    assert row["region"] == "kresy", f"Expected 'kresy', got {row['region']!r}"
    assert n == 1


# ─── Backward compat — idempotency ───────────────────────────────────────────

def test_backfill_location_regions_idempotent():
    """Already-assigned region must not be overwritten on second run."""
    conn = _make_db()
    conn.execute("INSERT INTO world_hexes(q,r,region,map_level) VALUES(5,10,'siwe_granie',0)")
    conn.execute(
        "INSERT INTO game_locations(key,label,region,world_hex_q,world_hex_r) VALUES('loc_c','Loc C','czarnobor',5,10)"
    )
    conn.commit()

    n = backfill_location_regions(conn)

    row = conn.execute("SELECT region FROM game_locations WHERE key='loc_c'").fetchone()
    assert row["region"] == "czarnobor", "Existing region must not be overwritten"
    assert n == 0, f"Expected 0 updates on second run, got {n}"


def test_backfill_location_regions_mixed():
    """Batch: some with hex, some without, some already set — correct outcome."""
    conn = _make_db()
    conn.execute("INSERT INTO world_hexes(q,r,region,map_level) VALUES(1,2,'wybrzeze_lez',0)")
    conn.executemany(
        "INSERT INTO game_locations(key,label,region,world_hex_q,world_hex_r) VALUES(?,?,?,?,?)",
        [
            ("loc_hex", "Hex Location", None, 1, 2),        # has hex → wybrzeze_lez
            ("loc_nohex", "No Hex", None, None, None),       # no hex → kresy
            ("loc_set", "Already Set", "martwe_pustkowia", None, None),  # already set → unchanged
        ],
    )
    conn.commit()

    n = backfill_location_regions(conn)

    results = {
        r["key"]: r["region"]
        for r in conn.execute("SELECT key, region FROM game_locations").fetchall()
    }
    assert results["loc_hex"] == "wybrzeze_lez"
    assert results["loc_nohex"] == "kresy"
    assert results["loc_set"] == "martwe_pustkowia"
    assert n == 2, f"Expected 2 updates, got {n}"
