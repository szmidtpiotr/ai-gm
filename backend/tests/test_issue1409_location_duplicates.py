"""#1409 — location duplicate detector + merge + garbage scan.

Mirrors the item detector tests (#1399) but for game_locations, and pins the
key scope decision: merge NEVER deletes a location a world hex still points at.
"""
import sqlite3

import pytest

from app.services import location_duplicate_service as svc


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(
        """
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT,
            is_active INTEGER DEFAULT 1,
            parent_id INTEGER,
            parent_key TEXT,
            source_campaign_id INTEGER,
            created_by TEXT,
            location_type TEXT,
            world_hex_q INTEGER,
            world_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_location_id INTEGER
        );
        """
    )
    return c


def _add(conn, key, label, **kw):
    cols = "key, label, is_active, parent_id, parent_key, source_campaign_id, created_by, world_hex_q"
    conn.execute(
        f"INSERT INTO game_locations ({cols}) VALUES (?,?,?,?,?,?,?,?)",
        (
            key, label,
            kw.get("is_active", 1),
            kw.get("parent_id"),
            kw.get("parent_key"),
            kw.get("source_campaign_id"),
            kw.get("created_by"),
            kw.get("world_hex_q"),
        ),
    )
    conn.commit()
    return conn.execute("SELECT id FROM game_locations WHERE key=?", (key,)).fetchone()[0]


def test_scan_finds_exact_duplicate_group(conn):
    _add(conn, "tavern_1", "Karczma Pod Lipą")
    _add(conn, "tavern_2", "karczma pod lipą")  # same after normalize
    _add(conn, "unique_1", "Wieża Maga")

    report = svc.scan_location_duplicates(conn)
    exact = [g for g in report["groups"] if g["match"] == "exact"]
    assert len(exact) == 1
    assert {r["key"] for r in exact[0]["records"]} == {"tavern_1", "tavern_2"}
    assert report["excess"] == 1


def test_merge_repoints_children_and_sessions_then_deletes(conn):
    keep = _add(conn, "keep", "Miasto")
    drop = _add(conn, "drop", "miasto")
    child = _add(conn, "child", "Rynek", parent_id=drop, parent_key="drop")
    conn.execute("INSERT INTO game_sessions (current_location_id) VALUES (?)", (drop,))
    conn.commit()

    res = svc.merge_location_duplicates(conn, "keep", ["drop"])
    assert res["deleted"] == ["drop"]
    assert res["skipped_hex_locked"] == []

    # loser gone
    assert conn.execute("SELECT 1 FROM game_locations WHERE key='drop'").fetchone() is None
    # child re-homed onto survivor (both parent_id and parent_key)
    row = conn.execute("SELECT parent_id, parent_key FROM game_locations WHERE key='child'").fetchone()
    assert row[0] == keep and row[1] == "keep"
    # session re-pointed
    assert conn.execute("SELECT current_location_id FROM game_sessions").fetchone()[0] == keep


def test_merge_never_deletes_hex_locked_loser(conn):
    _add(conn, "keep", "Wioska")
    _add(conn, "hexed", "wioska")
    conn.execute("INSERT INTO world_hexes (location_key) VALUES ('hexed')")
    conn.commit()

    res = svc.merge_location_duplicates(conn, "keep", ["hexed"])
    assert res["deleted"] == []
    assert res["skipped_hex_locked"] == ["hexed"]
    # PIOTR-OWNED map untouched — hexed location still present
    assert conn.execute("SELECT 1 FROM game_locations WHERE key='hexed'").fetchone() is not None


def test_garbage_buckets(conn):
    _add(conn, "test_dummy_123456", "Śmieć testowy")            # test key
    _add(conn, "smoke_x", "X", created_by="smoke")              # created_by smoke
    ghost = 9999
    _add(conn, "orphan", "Sierota", parent_id=ghost)            # parent missing
    _add(conn, "floater", "Balon")                             # no hex/parent/campaign, active
    _add(conn, "dead", "Zmarły", is_active=0)                   # inactive

    g = svc.scan_location_duplicates(conn)["garbage"]
    assert any(r["key"] == "test_dummy_123456" for r in g["test"])
    assert any(r["key"] == "smoke_x" for r in g["test"])
    assert any(r["key"] == "orphan" for r in g["orphaned"])
    assert any(r["key"] == "floater" for r in g["floating"])
    assert any(r["key"] == "dead" for r in g["inactive"])


def test_ignore_hides_group_from_next_scan(conn):
    _add(conn, "a", "Ta Sama")
    _add(conn, "b", "ta sama")
    assert svc.count_location_duplicates(conn) == 1

    svc.ignore_location_duplicates(conn, ["a", "b"])
    assert svc.count_location_duplicates(conn) == 0
    report = svc.scan_location_duplicates(conn)
    assert not [g for g in report["groups"] if g["match"] == "exact"]


def test_inactive_rows_excluded_from_dup_groups_and_count(conn):
    """#1407: soft-deleted rows aren't live duplicates — only in inactive bucket."""
    _add(conn, "active_1", "Create Test Location")
    _add(conn, "dead_1", "Create Test Location", is_active=0)
    _add(conn, "dead_2", "Create Test Location", is_active=0)

    report = svc.scan_location_duplicates(conn)
    # 1 active + 2 inactive same label → NOT a duplicate group (only 1 active)
    assert not [g for g in report["groups"] if g["match"] == "exact"]
    assert report["excess"] == 0
    # but the two dead rows show up in the inactive garbage bucket
    dead_keys = {r["key"] for r in report["garbage"]["inactive"]}
    assert {"dead_1", "dead_2"} <= dead_keys


def test_merge_rejects_keep_in_remove(conn):
    _add(conn, "x", "X")
    with pytest.raises(ValueError):
        svc.merge_location_duplicates(conn, "x", ["x"])
