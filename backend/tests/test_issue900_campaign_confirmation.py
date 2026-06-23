"""TDD: Issue #900 — confirm before silently overwriting hero's active campaign."""
import sqlite3
import sys
sys.path.insert(0, '/app')

import pytest


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_has_active_campaign_helper_exists():
    """character_campaign_service exposes has_active_campaign(conn, hero_id)."""
    from app.services import character_campaign_service
    assert hasattr(character_campaign_service, 'has_active_campaign'), (
        "character_campaign_service missing has_active_campaign — "
        "needed for #900 confirmation guard before hero reassignment"
    )


def test_has_active_campaign_returns_false_for_unlinked_hero():
    """Hero with campaign_id=NULL → has_active_campaign returns False."""
    from app.services.character_campaign_service import has_active_campaign
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE characters "
        "(id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, NULL, 1)")
    conn.commit()

    result = has_active_campaign(conn, 1)

    assert result is False, "hero with no campaign should return False"
    conn.close()


def test_has_active_campaign_returns_true_for_linked_hero():
    """Hero with campaign_id set → has_active_campaign returns True."""
    from app.services.character_campaign_service import has_active_campaign
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE characters "
        "(id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 42, 1)")
    conn.commit()

    result = has_active_campaign(conn, 1)

    assert result is True, "hero with campaign_id=42 should return True"
    conn.close()


def test_has_active_campaign_ignores_inactive_hero():
    """Inactive hero (is_active=0) — not counted as having active campaign."""
    from app.services.character_campaign_service import has_active_campaign
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE characters "
        "(id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO characters (id, campaign_id, is_active) VALUES (1, 42, 0)")
    conn.commit()

    result = has_active_campaign(conn, 1)

    assert result is False, "inactive hero should not block new campaign creation"
    conn.close()


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_maybe_reset_hp_unaffected():
    """Existing maybe_reset_hp_for_new_campaign still importable and callable."""
    from app.services.character_campaign_service import maybe_reset_hp_for_new_campaign
    assert callable(maybe_reset_hp_for_new_campaign)
