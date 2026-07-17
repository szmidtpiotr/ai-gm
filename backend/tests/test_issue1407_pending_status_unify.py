"""#1407 — badge "31 oczekujących" vs pusta lista "Do zatwierdzenia".

Root cause: two status strings for the same concept. Forge (adventure_forge) and
template_start_anchor wrote review_status='pending'; the review LIST
(get_pending_locations) + approve flow + map badge SHOULD all agree on
'pending_review' + is_active=1. The badge counted 'pending' (31), the list
queried 'pending_review' (0) → badge lied about an empty queue.

Fix: unify writers on 'pending_review', migrate legacy 'pending' rows, and make
the badge query identical to the list query.
"""
import sqlite3

import pytest

from app.services.world_service import get_pending_locations

_DDL = """
CREATE TABLE game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE, label TEXT, location_type TEXT, description TEXT,
    review_status TEXT, created_by TEXT, location_subtype TEXT, biome TEXT,
    tier INTEGER, canonical INTEGER, safe_for_rest INTEGER, parent_key TEXT,
    source_campaign_id INTEGER, ai_generated INTEGER, is_active INTEGER DEFAULT 1,
    temporary INTEGER, created_at TEXT
);
"""

# The exact badge query after the fix (hex_world.get_locations_map).
_BADGE_SQL = "SELECT COUNT(*) FROM game_locations WHERE review_status = 'pending_review' AND is_active = 1"
# The legacy status-unify migration (migrations_admin v2-locations-provenance-fixup).
_MIGRATE_SQL = "UPDATE game_locations SET review_status = 'pending_review' WHERE review_status = 'pending'"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_DDL)
    return c


def _add(conn, key, status, active=1):
    conn.execute(
        "INSERT INTO game_locations (key, label, review_status, is_active, ai_generated) VALUES (?, ?, ?, ?, 1)",
        (key, key.title(), status, active),
    )
    conn.commit()


def test_legacy_pending_rows_are_invisible_before_migration(conn):
    _add(conn, "forge_loc", "pending")            # legacy forge string
    _add(conn, "review_loc", "pending_review")    # canonical
    # list only sees the canonical one → the forge row is the "31 but 0 shown" bug
    keys = {r["key"] for r in get_pending_locations(conn)}
    assert keys == {"review_loc"}


def test_migration_unifies_and_badge_matches_list(conn):
    _add(conn, "forge_loc", "pending")
    _add(conn, "review_loc", "pending_review")
    _add(conn, "dead_forge", "pending", active=0)   # soft-deleted — stays hidden

    conn.execute(_MIGRATE_SQL)
    conn.commit()

    listed = {r["key"] for r in get_pending_locations(conn)}
    assert listed == {"forge_loc", "review_loc"}     # forge row now visible
    badge = conn.execute(_BADGE_SQL).fetchone()[0]
    # badge count == number of rows the list renders — no more lying badge
    assert badge == len(listed) == 2


def test_inactive_pending_not_counted(conn):
    _add(conn, "ghost", "pending_review", active=0)
    assert conn.execute(_BADGE_SQL).fetchone()[0] == 0
    assert get_pending_locations(conn) == []
