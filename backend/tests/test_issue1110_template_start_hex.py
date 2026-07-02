"""TDD: Issue #1110 — hex przypisany w Kuźni (template.start_hex) wyznacza start kampanii.

resolve_starting_hex musi najpierw użyć start_hex szablonu (przez campaigns.source_template_id),
a name-match zostawić jako fallback gdy szablon nie ma hexa.
"""
import sys, sqlite3
sys.path.insert(0, "/app")


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, owner_user_id INTEGER,
            source_template_id INTEGER, template_id INTEGER,
            party_hex_q INTEGER, party_hex_r INTEGER
        );
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY, start_hex_q INTEGER, start_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains', label TEXT,
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT, encounter_chance REAL DEFAULT 0,
            encounter_pool TEXT DEFAULT '[]', created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER, discovered_in_campaign_id INTEGER
        );
        CREATE TABLE campaign_hex_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER,
            campaign_label TEXT, discovered INTEGER DEFAULT 0,
            UNIQUE(campaign_id, hex_q, hex_r)
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, session_flags TEXT DEFAULT '{}',
            current_location_id INTEGER
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, world_hex_q INTEGER, world_hex_r INTEGER,
            canonical INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent', safe_for_rest INTEGER DEFAULT 0,
            created_by TEXT, approved INTEGER DEFAULT 1, ai_generated INTEGER DEFAULT 0,
            source_campaign_id INTEGER, location_subtype TEXT, biome TEXT
        );
    """)
    return db


def _seed_common(db):
    # a hex whose label WOULD win name-match for "Karczma"
    db.execute("INSERT INTO world_hexes (q,r,hex_type,label) VALUES (9,9,'town','Karczma Pod Kołem')")
    # the template's assigned hex (different place, plains)
    db.execute("INSERT INTO world_hexes (q,r,hex_type,label) VALUES (5,5,'plains','')")
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()


# ─── Test 1 (GŁÓWNY) — template start_hex wygrywa z name-match ────────────────

def test_template_start_hex_wins_over_name_match():
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    _seed_common(db)
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,5,5)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.commit()

    res = resolve_starting_hex(100, 999, "Karczma Pod Kołem", db)
    assert (res["q"], res["r"]) == (5, 5), \
        f"Start musi być na hexie szablonu (5,5), nie name-match (9,9) — {res}"


def test_template_start_hex_via_template_id_column():
    """Działa też gdy użyto kolumny template_id zamiast source_template_id."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    _seed_common(db)
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,5,5)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,template_id) VALUES (100,1,77)")
    db.commit()
    res = resolve_starting_hex(100, 999, "Karczma Pod Kołem", db)
    assert (res["q"], res["r"]) == (5, 5)


# ─── Test 2 (backward compat) — brak start_hex → name-match ──────────────────

def test_no_template_hex_falls_back_to_name_match():
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    _seed_common(db)
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,NULL,NULL)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.commit()
    res = resolve_starting_hex(100, 999, "Karczma Pod Kołem", db)
    assert (res["q"], res["r"]) == (9, 9), \
        f"Bez start_hex musi zadziałać name-match (9,9) — {res}"


def test_no_template_at_all_falls_back():
    """Kampania bez szablonu — name-match jak dotychczas."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    _seed_common(db)
    db.execute("INSERT INTO campaigns (id,owner_user_id) VALUES (100,1)")
    db.commit()
    res = resolve_starting_hex(100, 999, "Karczma Pod Kołem", db)
    assert (res["q"], res["r"]) == (9, 9)


# ─── Test 3 — helper _template_start_hex ─────────────────────────────────────

def test_helper_returns_template_hex():
    from app.services.hex_travel_service import _template_start_hex
    db = _make_db()
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,5,5)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.commit()
    assert _template_start_hex(db, 100) == (5, 5)


def test_helper_none_when_no_hex():
    from app.services.hex_travel_service import _template_start_hex
    db = _make_db()
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,NULL,NULL)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.commit()
    assert _template_start_hex(db, 100) is None


def test_helper_none_when_no_template():
    from app.services.hex_travel_service import _template_start_hex
    db = _make_db()
    db.execute("INSERT INTO campaigns (id,owner_user_id) VALUES (100,1)")
    db.commit()
    assert _template_start_hex(db, 100) is None


# ─── Test 4 — start_hex zapisany do party_hex + current_hex ──────────────────

def test_template_hex_persisted_to_session_current_hex():
    from app.services.hex_travel_service import resolve_starting_hex
    import json
    db = _make_db()
    _seed_common(db)
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,5,5)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.commit()
    resolve_starting_hex(100, 999, "Karczma Pod Kołem", db)
    flags = json.loads(db.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=100").fetchone()[0])
    assert flags.get("current_hex") == {"q": 5, "r": 5}
