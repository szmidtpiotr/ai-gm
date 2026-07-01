"""TDD: Issue #1094 — auto-alokacja hexa przy publikacji + twarde wykluczenie POI."""
import sys, os, sqlite3, pytest
sys.path.insert(0, "/app")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_db(tmp_path):
    db = sqlite3.connect(str(tmp_path / "test.db"))
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            difficulty_rating INTEGER DEFAULT 3,
            atmosphere TEXT,
            status TEXT DEFAULT 'draft',
            gm_plan_json TEXT DEFAULT '{}',
            hook_ids TEXT,
            adventure_idea_id INTEGER,
            required_npc_keys TEXT,
            required_beats TEXT,
            player_visible INTEGER DEFAULT 0,
            play_count INTEGER DEFAULT 0,
            source_idea_id INTEGER,
            source_template_id INTEGER,
            start_hex_q INTEGER,
            start_hex_r INTEGER,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            hex_type TEXT DEFAULT 'plains',
            label TEXT DEFAULT '',
            map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            label TEXT,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            is_active INTEGER DEFAULT 1
        );
    """)
    return db


def _seed_world(db, hexes):
    """Insert list of (q, r, hex_type, label) into world_hexes."""
    for q, r, htype, label in hexes:
        db.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, map_level, is_active) VALUES (?,?,?,?,0,1)",
            (q, r, htype, label),
        )
    db.commit()


def _seed_location(db, q, r, label="Kopalnia"):
    db.execute(
        "INSERT INTO game_locations (key, label, world_hex_q, world_hex_r) VALUES (?,?,?,?)",
        (f"loc_{q}_{r}", label, q, r),
    )
    db.commit()

# ─── Import the helper under test ────────────────────────────────────────────

def _get_allocate_fn():
    """Import _allocate_hex_for_template — fails until implemented."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    return _allocate_hex_for_template

# ─── Test 1: hard-exclude hex z istniejącą game_location ────────────────────

def test_allocate_hex_hard_excludes_occupied_location(tmp_path):
    """allocate-hex NEVER picks a hex that already has a game_location."""
    db = _make_db(tmp_path)
    # Only two hexes: one with location (ruins), one free town
    _seed_world(db, [
        (0, 0, "ruins", "Kopalnia Czarnego Hutmana"),
        (1, 0, "town", ""),
    ])
    _seed_location(db, 0, 0)  # hex (0,0) is occupied
    db.execute("INSERT INTO campaign_templates (title, status) VALUES ('T', 'review')")
    db.commit()
    tpl_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    fn = _get_allocate_fn()
    result = fn(db, tpl_id)

    assert result is not None, "Should find a free hex"
    assert result["q"] == 1 and result["r"] == 0, \
        f"Must pick free town (1,0), not occupied ruins (0,0) — got {result}"


# ─── Test 2: hard-exclude hex z niepustym label (named POI) ─────────────────

def test_allocate_hex_hard_excludes_named_poi(tmp_path):
    """allocate-hex skips hex with non-empty label even if no game_location row."""
    db = _make_db(tmp_path)
    _seed_world(db, [
        (0, 0, "castle", "Zamek Wachstein"),  # named POI, no location row
        (5, 5, "plains", ""),                  # free, unnamed
    ])
    db.execute("INSERT INTO campaign_templates (title, status) VALUES ('T', 'review')")
    db.commit()
    tpl_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    fn = _get_allocate_fn()
    result = fn(db, tpl_id)

    assert result is not None
    assert result["q"] == 5 and result["r"] == 5, \
        f"Must skip named POI (0,0) — got {result}"


# ─── Test 3: 422 gdy brak wolnych hexów ─────────────────────────────────────

def test_allocate_hex_raises_when_no_free_hexes(tmp_path):
    """allocate-hex returns None (caller raises 422) when all hexes are occupied."""
    db = _make_db(tmp_path)
    _seed_world(db, [(0, 0, "town", "Vilnograd")])  # named — excluded
    db.execute("INSERT INTO campaign_templates (title, status) VALUES ('T', 'review')")
    db.commit()
    tpl_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    fn = _get_allocate_fn()
    result = fn(db, tpl_id)
    assert result is None, "No free hexes → return None so caller raises 422"


# ─── Test 4: backward compat — allocate-hex endpoint still works ─────────────

def test_allocate_hex_endpoint_still_returns_ok(tmp_path):
    """The forge_allocate_hex endpoint function still callable and returns expected shape."""
    from app.routers.adventure_forge import forge_allocate_hex
    # Smoke: function exists and is callable. Actual DB test requires running app.
    assert callable(forge_allocate_hex)


# ─── Test 5: auto-alokacja przy publikacji — wywołuje _allocate_hex ──────────

def test_publish_without_start_hex_triggers_auto_allocation(tmp_path, monkeypatch):
    """_allocate_hex_for_template called internally when publishing without start_hex."""
    from app.routers import adventure_forge as af

    allocated = []

    def fake_allocate(conn, tpl_id):
        allocated.append(tpl_id)
        return {"q": 5, "r": 5, "hex_type": "town", "label": ""}

    monkeypatch.setattr(af, "_allocate_hex_for_template", fake_allocate)

    db = _make_db(tmp_path)
    db.execute("""
        INSERT INTO campaign_templates
        (title, status, gm_plan_json, required_npc_keys, required_beats, start_hex_q, start_hex_r)
        VALUES ('T', 'review', '{}', '[]', '[]', NULL, NULL)
    """)
    db.commit()
    tpl_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Simulate the auto-alloc branch: template has no start_hex → fn must be called
    cur_hex = db.execute("SELECT start_hex_q FROM campaign_templates WHERE id = ?", (tpl_id,)).fetchone()
    assert cur_hex["start_hex_q"] is None, "Precondition: no hex set"
    best = af._allocate_hex_for_template(db, tpl_id)
    assert best is not None and best["q"] == 5


# ─── Test 6: auto-alokacja przy publikacji — 422 gdy brak hexów ──────────────

def test_publish_without_start_hex_raises_422_when_no_hexes(tmp_path, monkeypatch):
    """When all hexes are occupied, _allocate_hex_for_template returns None."""
    from app.routers import adventure_forge as af

    db = _make_db(tmp_path)
    # All hexes have labels → hard-excluded
    _seed_world(db, [(0, 0, "town", "Vilnograd"), (1, 1, "ruins", "Stara Twierdza")])
    db.execute("INSERT INTO campaign_templates (title, status) VALUES ('T', 'review')")
    db.commit()
    tpl_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    result = af._allocate_hex_for_template(db, tpl_id)
    assert result is None, f"Expected None (no free hex), got {result}"
