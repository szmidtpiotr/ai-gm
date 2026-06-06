"""TDD: Issue #374 — C18 resolve_starting_hex must reuse discovered hexes, not create new peripheral ones.

Tests verify:
- When character has discovered hexes in previous campaign → new campaign lands on one of them
- When no prior hexes exist → new campaign lands on (0,0), not a random peripheral hex
- Label-match path unchanged (backward compat)
- is_new=False when reusing existing hex
- New helper _find_character_existing_hex returns correct coords
"""
import sys
import sqlite3
import json
sys.path.insert(0, "/app")


SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT,
    atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.15,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    created_by_campaign_id INTEGER,
    discovered_in_campaign_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    forge_encounter_pool TEXT DEFAULT '[]',
    map_level INTEGER NOT NULL DEFAULT 0,
    parent_hex_id INTEGER,
    UNIQUE(q, r)
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Test',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    language TEXT NOT NULL DEFAULT 'pl',
    mode TEXT NOT NULL DEFAULT 'solo'
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Hero',
    campaign_id INTEGER,
    gold_gp INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL,
    hex_r INTEGER NOT NULL,
    campaign_label TEXT,
    campaign_notes TEXT,
    narrative_encounter TEXT,
    discovered INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}',
    current_location_id INTEGER,
    scene_enemies TEXT NOT NULL DEFAULT '[]',
    scene_npcs TEXT NOT NULL DEFAULT '[]',
    scene_cleared INTEGER NOT NULL DEFAULT 0,
    active_quests TEXT NOT NULL DEFAULT '[]',
    player_conditions TEXT NOT NULL DEFAULT '[]',
    ingame_hours INTEGER NOT NULL DEFAULT 9
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    canonical INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT 'test',
    is_active INTEGER NOT NULL DEFAULT 1,
    approved INTEGER NOT NULL DEFAULT 1,
    review_status TEXT NOT NULL DEFAULT 'approved',
    ai_generated INTEGER NOT NULL DEFAULT 0,
    source_campaign_id INTEGER,
    location_subtype TEXT DEFAULT NULL,
    biome TEXT DEFAULT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0,
    temporary INTEGER NOT NULL DEFAULT 0
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_hex(conn, q, r, hex_type="plains", label=None, is_active=1):
    conn.execute(
        "INSERT OR IGNORE INTO world_hexes(q,r,hex_type,label,is_active) VALUES(?,?,?,?,?)",
        (q, r, hex_type, label, is_active)
    )
    conn.commit()


def _add_discovered_hex(conn, campaign_id, q, r):
    conn.execute(
        "INSERT OR IGNORE INTO campaign_hex_data(campaign_id, hex_q, hex_r, discovered) VALUES(?,?,?,1)",
        (campaign_id, q, r)
    )
    conn.commit()


def _setup_previous_campaign(conn, user_id=1, prev_camp_id=100, new_camp_id=101, char_id=1):
    """Create user with old campaign having discovered hexes, new empty campaign."""
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(?,?,'Old Campaign')", (prev_camp_id, user_id))
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(?,?,'New Campaign')", (new_camp_id, user_id))
    conn.execute("INSERT INTO characters(id, name, campaign_id) VALUES(?,?,?)", (char_id, "Hero", prev_camp_id))
    conn.commit()


# ─── Core fix: reuse existing discovered hex ─────────────────────────────────

def test_resolve_starting_hex_reuses_existing_hex():
    """When character has discovered hexes in previous campaign, new campaign must land on one."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _setup_previous_campaign(conn)

    # Previous campaign (100) has a discovered hex at (3, 2)
    _add_hex(conn, 3, 2, hex_type="town", label="Miasto Kotwica")
    _add_discovered_hex(conn, 100, 3, 2)

    # Also add some world hexes for background
    _add_hex(conn, 0, 0)
    _add_hex(conn, 1, 0)

    result = resolve_starting_hex(101, 1, None, conn)

    # Must land on existing hex (3,2), not a new peripheral one
    assert result["q"] == 3 and result["r"] == 2, (
        f"resolve_starting_hex powinno wybrać istniejący odkryty hex (3,2), "
        f"ale wybrało ({result['q']},{result['r']}). "
        f"Nowe kampanie lądują na nowych obrzeżach zamiast reużywać odkrytych hexów."
    )


def test_resolve_starting_hex_no_prior_hexes_lands_on_origin():
    """Character with no prior discovered hexes must start at (0,0), not a random peripheral hex."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    # New campaign, no previous campaign, no discovered hexes
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(101, 1,'New')")
    conn.execute("INSERT INTO characters(id, name) VALUES(1,'Hero')")
    conn.commit()

    # World has some hexes (so _find_nearby_empty_hex would normally pick something adjacent)
    _add_hex(conn, 5, 5)
    _add_hex(conn, 6, 5)

    result = resolve_starting_hex(101, 1, None, conn)

    assert result["q"] == 0 and result["r"] == 0, (
        f"Gracz bez żadnych odkrytych hexów powinien startować na (0,0), "
        f"ale wylądował na ({result['q']},{result['r']}). "
        f"Fallback powinien być (0,0) nie losowy hex."
    )


def test_resolve_starting_hex_is_new_false_when_reusing():
    """When reusing an existing hex, is_new must be False."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _setup_previous_campaign(conn)
    _add_hex(conn, 2, 3, hex_type="forest")
    _add_discovered_hex(conn, 100, 2, 3)

    result = resolve_starting_hex(101, 1, None, conn)

    assert result.get("is_new") is False or result.get("is_new") == False, (
        f"is_new powinno być False gdy reużywamy istniejący hex, "
        f"got is_new={result.get('is_new')}. "
        f"Nie tworzymy nowego hexu — używamy już istniejącego."
    )


def test_resolve_starting_hex_label_match_unchanged():
    """Label match path (priority 1) must still work — backward compat."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(101, 1,'New')")
    conn.execute("INSERT INTO characters(id, name) VALUES(1,'Hero')")
    conn.commit()
    _add_hex(conn, 4, 4, hex_type="town", label="Srebrna Zatoka")

    result = resolve_starting_hex(101, 1, "Srebrna Zatoka", conn)

    assert result["q"] == 4 and result["r"] == 4, (
        f"Label match 'Srebrna Zatoka' powinno trafić w hex (4,4), "
        f"ale wybrało ({result['q']},{result['r']}). "
        f"Backward compat label-match path jest zepsuty."
    )


# ─── Helper function test ─────────────────────────────────────────────────────

def test_find_character_existing_hex_helper():
    """_find_character_existing_hex must return coords of a previously discovered hex."""
    from app.services.hex_travel_service import _find_character_existing_hex

    conn = _make_db()
    _setup_previous_campaign(conn)
    _add_hex(conn, 7, 7)
    _add_discovered_hex(conn, 100, 7, 7)

    result = _find_character_existing_hex(conn, new_campaign_id=101, user_id=1)

    assert result is not None, (
        "_find_character_existing_hex zwróciło None mimo że użytkownik ma odkryty hex (7,7). "
        "Funkcja musi sprawdzać campaign_hex_data dla kampanii tego samego użytkownika."
    )
    q, r = result
    assert (q, r) == (7, 7), (
        f"Oczekiwano hex (7,7), otrzymano ({q},{r})"
    )


def test_find_character_existing_hex_returns_none_when_no_history():
    """_find_character_existing_hex returns None when no prior discovered hexes."""
    from app.services.hex_travel_service import _find_character_existing_hex

    conn = _make_db()
    conn.execute("INSERT INTO campaigns(id, owner_user_id) VALUES(101,1)")
    conn.commit()

    result = _find_character_existing_hex(conn, new_campaign_id=101, user_id=1)
    assert result is None, (
        f"_find_character_existing_hex powinno zwrócić None gdy brak historii, "
        f"ale zwróciło {result}"
    )


# ─── Backward compat: existing world still functions ─────────────────────────

def test_campaign_hex_data_row_added_on_reuse():
    """Reusing an existing hex must still add a campaign_hex_data row for the new campaign."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _setup_previous_campaign(conn)
    _add_hex(conn, 1, 1)
    _add_discovered_hex(conn, 100, 1, 1)

    resolve_starting_hex(101, 1, None, conn)

    row = conn.execute(
        "SELECT * FROM campaign_hex_data WHERE campaign_id = 101 AND hex_q = 1 AND hex_r = 1"
    ).fetchone()
    assert row is not None, (
        "Po resolve_starting_hex dla nowej kampanii (101) musi istnieć wpis w campaign_hex_data. "
        "Reużycie hexu nie zwalnia z dodania go do kampanii."
    )
    assert row["discovered"] == 1, "Nowy wpis w campaign_hex_data musi mieć discovered=1"
