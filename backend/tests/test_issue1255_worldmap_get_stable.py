"""TDD: Issue #1255 (P1, Podróże 2.0) — world-map GET must not move the pin.

Regression introduced in PM1 #1220: the origin_region block in the world-map GET
called resolve_starting_hex(..., None, ...) unconditionally. With no start name the
call hit the sentinel → _pick_random_start_location → label-match to a RANDOM hex,
BEFORE the existing-position / C18 reuse, and set_position() overwrote
session_flags.current_hex. Net effect: a read endpoint teleported the pin and grew
`discovered` on every call (observed 38,6 → 13,22 → 28,-49; discovered 2→3→3).

Fix is two-layered and this suite guards the SOURCE layer (resolve_starting_hex):
- An established session current_hex wins over everything → resolve is idempotent.
- C18 reuse pre-empts the random sentinel pick.
- A truly-new character with zero history still gets a start.
- Kuźnia template start_hex is untouched (covered by test_issue1110).
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
    region TEXT,
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
    known INTEGER NOT NULL DEFAULT 0,
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
    location_type TEXT DEFAULT NULL,
    map_icon TEXT DEFAULT NULL,
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


def _add_hex(conn, q, r, hex_type="plains", label=None, region=None):
    conn.execute(
        "INSERT OR IGNORE INTO world_hexes(q,r,hex_type,label,region,is_active,map_level) "
        "VALUES(?,?,?,?,?,1,0)",
        (q, r, hex_type, label, region),
    )
    conn.commit()


def _add_campaign(conn, camp_id=8888, user_id=1):
    conn.execute(
        "INSERT INTO campaigns(id, owner_user_id, title) VALUES(?,?,'Freeform')",
        (camp_id, user_id),
    )
    conn.commit()


def _add_session(conn, camp_id=8888, current_hex=None):
    flags = {}
    if current_hex is not None:
        flags["current_hex"] = current_hex
    conn.execute(
        "INSERT INTO game_sessions(id, campaign_id, session_flags) VALUES(?,?,?)",
        (f"sess-{camp_id}", camp_id, json.dumps(flags)),
    )
    conn.commit()


def _discovered_count(conn, camp_id):
    return conn.execute(
        "SELECT COUNT(*) AS c FROM campaign_hex_data WHERE campaign_id = ? AND discovered = 1",
        (camp_id,),
    ).fetchone()["c"]


def _current_hex(conn, camp_id):
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (camp_id,),
    ).fetchone()
    return json.loads(row["session_flags"] or "{}").get("current_hex")


# ─── Core fix: resolve_starting_hex is idempotent when a position exists ──────

def test_resolve_is_idempotent_with_existing_current_hex():
    """Template-less campaign whose session already has current_hex must resolve to
    the SAME hex on every call — no random teleport, matching the world-map GET path."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _add_campaign(conn, 8888, user_id=1)
    # Błotstein anchor at (38,6) — the pin the campaign actually sits on.
    _add_hex(conn, 38, 6, hex_type="town", label="Błotstein", region="kresy")
    # Decoys spread across the map that the old random sentinel path could jump to.
    _add_hex(conn, 13, 22, hex_type="town", label="Wolfsmark", region="kresy")
    _add_hex(conn, 28, -49, hex_type="town", label="Czarnogród", region="kresy")
    _add_hex(conn, 0, 0, hex_type="plains")
    _add_session(conn, 8888, current_hex={"q": 38, "r": 6})

    coords = []
    for _ in range(3):
        res = resolve_starting_hex(8888, 999, None, conn)
        coords.append((res["q"], res["r"]))

    assert coords == [(38, 6), (38, 6), (38, 6)], (
        f"Pinezka musi być STABILNA na (38,6), a skakała: {coords}. "
        "GET world-map nie może przenosić gracza."
    )
    assert _current_hex(conn, 8888) == {"q": 38, "r": 6}, (
        "session_flags.current_hex nadpisany losowym hexem — desync hex↔lokacja (#1255)."
    )


def test_repeated_resolve_does_not_grow_discovered():
    """Every call used to inject a fresh random `discovered` hex. Now the discovered
    set must stay at exactly one row (the anchor) across repeated resolves."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _add_campaign(conn, 8889, user_id=1)
    _add_hex(conn, 38, 6, hex_type="town", label="Błotstein", region="kresy")
    _add_hex(conn, 13, 22, hex_type="town", label="Wolfsmark", region="kresy")
    _add_hex(conn, 28, -49, hex_type="town", label="Czarnogród", region="kresy")
    _add_session(conn, 8889, current_hex={"q": 38, "r": 6})

    for _ in range(3):
        resolve_starting_hex(8889, 999, None, conn)

    assert _discovered_count(conn, 8889) == 1, (
        f"discovered rosło co GET (regresja PM1) — jest "
        f"{_discovered_count(conn, 8889)}, oczekiwano 1."
    )


# ─── Regression guards: the resolution paths below must still work ───────────

def test_c18_reuse_preempts_random_when_no_position():
    """No current_hex, no template, but the owner has a prior discovered hex → reuse it
    (C18) instead of randomizing. Guards that reuse now pre-empts the sentinel pick."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    # Prior campaign 200 with a discovered hex; new campaign 201 empty, same owner.
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(200,7,'Old')")
    conn.execute("INSERT INTO campaigns(id, owner_user_id, title) VALUES(201,7,'New')")
    conn.execute("INSERT INTO characters(id, name, campaign_id) VALUES(1,'Hero',200)")
    conn.commit()
    _add_hex(conn, 5, 5, hex_type="town", label="Kotwica", region="kresy")
    conn.execute(
        "INSERT INTO campaign_hex_data(campaign_id, hex_q, hex_r, discovered) VALUES(200,5,5,1)"
    )
    conn.commit()
    # Decoys the random sentinel could pick instead.
    _add_hex(conn, 40, 40, hex_type="town", label="Losowa Osada")
    _add_session(conn, 201, current_hex=None)

    res = resolve_starting_hex(201, 1, None, conn)
    assert (res["q"], res["r"]) == (5, 5), (
        f"C18 reuse musi wygrać z losowaniem: dostałem ({res['q']},{res['r']})."
    )


def test_brand_new_character_still_gets_a_start():
    """No position, no prior hex, no template, no world at all → deterministic (0,0)
    fallback. A genuinely new character must still be placed somewhere valid."""
    from app.services.hex_travel_service import resolve_starting_hex

    conn = _make_db()
    _add_campaign(conn, 300, user_id=9)
    _add_session(conn, 300, current_hex=None)

    res = resolve_starting_hex(300, 1, None, conn)
    assert res["q"] == 0 and res["r"] == 0, (
        f"Nowa postać bez historii i bez świata → (0,0), a dostała "
        f"({res['q']},{res['r']})."
    )
