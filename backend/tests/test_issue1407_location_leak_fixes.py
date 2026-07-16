"""#1407 — stop NEW location duplicates at the source (3 generators).

Root-cause fixes so the dedup detector isn't a treadmill:
- Fix 2: build_camp recycles a campaign's stale camps instead of piling up.
- Fix 3: plan materializer reuses a same-label location instead of `_<time>` dup.
(Fix 1 = conftest autouse cleanup fixture; exercised implicitly by the whole
suite no longer leaking rows — asserted here via a marker location.)
"""
import sqlite3

import pytest

_GAME_LOCATIONS_DDL = """
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT,
    description TEXT,
    parent_id INTEGER,
    parent_key TEXT,
    location_type TEXT,
    ai_generated INTEGER DEFAULT 0,
    approved INTEGER DEFAULT 0,
    created_by TEXT,
    review_status TEXT,
    canonical INTEGER DEFAULT 0,
    source_campaign_id INTEGER,
    biome TEXT,
    location_subtype TEXT,
    tier INTEGER,
    is_active INTEGER DEFAULT 1,
    safe_for_rest INTEGER DEFAULT 0,
    temporary INTEGER DEFAULT 0,
    world_hex_q INTEGER,
    world_hex_r INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

_WORLD_HEXES_DDL = """
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
    hex_type TEXT, label TEXT, location_key TEXT, is_active INTEGER DEFAULT 1
);
"""


# ─── Fix 2: camp recycle ─────────────────────────────────────────────────────

def test_build_camp_purges_campaign_stale_camps(monkeypatch):
    from app.services import world_service

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_GAME_LOCATIONS_DDL + _WORLD_HEXES_DDL)
    # a hex to camp on
    conn.execute("INSERT INTO world_hexes (q, r, map_level, hex_type, is_active) VALUES (5, 5, 0, 'forest', 1)")
    # three OLD deactivated camps for campaign 42 — pure garbage
    for i in range(3):
        conn.execute(
            "INSERT INTO game_locations (key, label, source_campaign_id, location_subtype, is_active, temporary) "
            "VALUES (?, 'Obozowisko', 42, 'camp', 0, 1)",
            (f"temp_camp_42_old{i}",),
        )
    # a stale camp from a DIFFERENT campaign — must survive
    conn.execute(
        "INSERT INTO game_locations (key, label, source_campaign_id, location_subtype, is_active, temporary) "
        "VALUES ('temp_camp_99_old', 'Obozowisko', 99, 'camp', 0, 1)"
    )
    conn.commit()

    # link_location_to_hex is exercised for real (schema has map_level)
    world_service.build_camp(conn, campaign_id=42, q=5, r=5)

    camps42 = conn.execute(
        "SELECT is_active FROM game_locations WHERE source_campaign_id = 42 AND location_subtype = 'camp'"
    ).fetchall()
    # only the one just-built (active) camp remains for campaign 42
    assert len(camps42) == 1
    assert camps42[0]["is_active"] == 1
    # other campaign's camp untouched
    assert conn.execute("SELECT COUNT(*) FROM game_locations WHERE source_campaign_id = 99").fetchone()[0] == 1


def test_build_camp_keeps_hex_linked_stale_camp(monkeypatch):
    """A stale camp a hex still points at is NOT purged (PIOTR-OWNED map safety)."""
    from app.services import world_service

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_GAME_LOCATIONS_DDL + _WORLD_HEXES_DDL)
    conn.execute("INSERT INTO world_hexes (q, r, map_level, hex_type, is_active) VALUES (5, 5, 0, 'forest', 1)")
    # hex 9,9 still references this inactive camp
    conn.execute("INSERT INTO world_hexes (q, r, map_level, hex_type, location_key, is_active) VALUES (9, 9, 0, 'forest', 'temp_camp_42_hexed', 1)")
    conn.execute(
        "INSERT INTO game_locations (key, label, source_campaign_id, location_subtype, is_active, temporary) "
        "VALUES ('temp_camp_42_hexed', 'Obozowisko', 42, 'camp', 0, 1)"
    )
    conn.commit()

    world_service.build_camp(conn, campaign_id=42, q=5, r=5)

    # hex-linked stale camp survived despite belonging to campaign 42
    assert conn.execute("SELECT 1 FROM game_locations WHERE key = 'temp_camp_42_hexed'").fetchone() is not None


# ─── Fix 3: plan materializer reuse-by-label ─────────────────────────────────

@pytest.fixture
def validator_db(tmp_path, monkeypatch):
    from app.services import location_validator as V

    dbfile = str(tmp_path / "loc.db")
    con = sqlite3.connect(dbfile)
    con.executescript(_GAME_LOCATIONS_DDL)
    # parent macro so ai_generated create isn't refused (needs a parent)
    con.execute(
        "INSERT INTO game_locations (key, label, location_type, is_active) VALUES ('macro_root', 'Kraina', 'macro', 1)"
    )
    con.commit()
    con.close()

    def _conn():
        c = sqlite3.connect(dbfile)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(V, "_get_db_connection", _conn)
    return V, dbfile


def _intent(V, label):
    return V.LocationIntent(
        action="create", target_label=label, target_key=None,
        parent_key="macro_root", description=None, biome="forest",
        location_subtype="wioska",
    )


def test_create_new_location_reuses_same_label_in_campaign(validator_db):
    V, dbfile = validator_db

    first = V._create_new_location(_intent(V, "Gospoda szlaku"), ai_generated=True, campaign_id=26)
    assert first is not None
    second = V._create_new_location(_intent(V, "Gospoda szlaku"), ai_generated=True, campaign_id=26)
    assert second is not None
    # same row reused — no timestamped duplicate
    assert first["id"] == second["id"]

    con = sqlite3.connect(dbfile)
    n = con.execute("SELECT COUNT(*) FROM game_locations WHERE LOWER(label)='gospoda szlaku'").fetchone()[0]
    con.close()
    assert n == 1


def test_create_new_location_separates_across_campaigns(validator_db):
    V, dbfile = validator_db

    a = V._create_new_location(_intent(V, "Gospoda szlaku"), ai_generated=True, campaign_id=26)
    b = V._create_new_location(_intent(V, "Gospoda szlaku"), ai_generated=True, campaign_id=27)
    assert a["id"] != b["id"]  # different campaigns stay separate
    # but campaign-scoped key is STABLE (idempotent), not time.time()
    assert b["key"].endswith("_27")
    # re-running campaign 27 reuses the scoped row, no third copy
    b2 = V._create_new_location(_intent(V, "Gospoda szlaku"), ai_generated=True, campaign_id=27)
    assert b2["id"] == b["id"]
