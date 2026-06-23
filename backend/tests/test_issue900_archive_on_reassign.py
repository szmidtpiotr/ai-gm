"""TDD: Issue #900 phase 2 — archive old campaign when hero moves to a new one."""
import sqlite3
import sys
sys.path.insert(0, '/app')

import pytest

# ─── Schema helper ────────────────────────────────────────────────────────────

def _make_db():
    """Minimal in-memory DB with characters + campaigns tables."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            campaign_id INTEGER,
            is_active INTEGER DEFAULT 1,
            status TEXT DEFAULT 'idle'
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'active',
            title TEXT,
            mode TEXT DEFAULT 'solo'
        );
    """)
    conn.commit()
    return conn


# ─── Test główny: helper exists ───────────────────────────────────────────────

def test_archive_previous_campaign_helper_exists():
    """character_campaign_service exposes archive_previous_campaign(conn, hero_id, new_campaign_id)."""
    from app.services import character_campaign_service
    assert hasattr(character_campaign_service, 'archive_previous_campaign'), (
        "character_campaign_service missing archive_previous_campaign — "
        "needed for #900: seal old campaign when hero starts a new one"
    )


def test_archive_previous_campaign_archives_old():
    """Hero with old campaign → old campaign gets status='archived'."""
    from app.services.character_campaign_service import archive_previous_campaign
    conn = _make_db()
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (10, 'active', 'Stara')")
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (20, 'active', 'Nowa')")
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 10, 1)")
    conn.commit()

    archive_previous_campaign(conn, hero_id=1, new_campaign_id=20)
    conn.commit()

    old_status = conn.execute("SELECT status FROM campaigns WHERE id=10").fetchone()["status"]
    assert old_status == 'archived', f"Old campaign should be 'archived', got '{old_status}'"
    conn.close()


def test_archive_previous_campaign_new_stays_active():
    """New campaign must NOT be archived — only the old one."""
    from app.services.character_campaign_service import archive_previous_campaign
    conn = _make_db()
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (10, 'active', 'Stara')")
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (20, 'active', 'Nowa')")
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 10, 1)")
    conn.commit()

    archive_previous_campaign(conn, hero_id=1, new_campaign_id=20)
    conn.commit()

    new_status = conn.execute("SELECT status FROM campaigns WHERE id=20").fetchone()["status"]
    assert new_status == 'active', f"New campaign should stay 'active', got '{new_status}'"
    conn.close()


def test_archive_previous_campaign_noop_when_same():
    """Hero resuming the same campaign (old_id == new_id) → nothing archived."""
    from app.services.character_campaign_service import archive_previous_campaign
    conn = _make_db()
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (10, 'active', 'Kampania')")
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 10, 1)")
    conn.commit()

    archive_previous_campaign(conn, hero_id=1, new_campaign_id=10)
    conn.commit()

    status = conn.execute("SELECT status FROM campaigns WHERE id=10").fetchone()["status"]
    assert status == 'active', "Resuming same campaign must NOT archive it"
    conn.close()


def test_archive_previous_campaign_noop_when_no_previous():
    """Hero with campaign_id=NULL → nothing happens, no crash."""
    from app.services.character_campaign_service import archive_previous_campaign
    conn = _make_db()
    conn.execute("INSERT INTO campaigns (id, status, title) VALUES (20, 'active', 'Nowa')")
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, NULL, 1)")
    conn.commit()

    archive_previous_campaign(conn, hero_id=1, new_campaign_id=20)  # must not raise
    conn.commit()

    status = conn.execute("SELECT status FROM campaigns WHERE id=20").fetchone()["status"]
    assert status == 'active'
    conn.close()


def test_archive_previous_campaign_noop_for_dungeon_campaign():
    """Dungeon campaigns (mode='dungeon') must NOT be archived — they're disposable."""
    from app.services.character_campaign_service import archive_previous_campaign
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active', title TEXT, mode TEXT DEFAULT 'solo');
    """)
    conn.execute("INSERT INTO campaigns (id, status, mode) VALUES (10, 'active', 'dungeon')")
    conn.execute("INSERT INTO campaigns (id, status, mode) VALUES (20, 'active', 'solo')")
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 10, 1)")
    conn.commit()

    archive_previous_campaign(conn, hero_id=1, new_campaign_id=20)
    conn.commit()

    # Dungeon campaigns should NOT be archived — they end by their own lifecycle
    status = conn.execute("SELECT status FROM campaigns WHERE id=10").fetchone()["status"]
    assert status == 'active', "Dungeon campaign must NOT be archived on hero reassign"
    conn.close()


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_has_active_campaign_still_works():
    """Existing has_active_campaign helper unaffected."""
    from app.services.character_campaign_service import has_active_campaign
    conn = _make_db()
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 42, 1)")
    conn.commit()
    assert has_active_campaign(conn, 1) is True
    conn.close()
