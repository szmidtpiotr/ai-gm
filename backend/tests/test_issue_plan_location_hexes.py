"""TDD: auto-przydział globalnych hexów dla makro-lokacji planu + relokacja.

Generator AI nie przydzielał terenu startu ani hexów lokacjom z planu. Nowa
`ensure_plan_location_hexes`:
- daje każdej makro-lokacji planu (nie hub, nie sub, nie start) wolny world hex,
- pomija lokacje już mające przydzielony hex (reużyte) — trzymają swój,
- `force=True` (admin „rozrzuć ponownie") rozmieszcza je ponownie z szerszym
  odstępem — fix dla lokacji upchniętych za blisko siebie.
Kresy world map (POI/nazwane) i cudze lokacje/starty są nietykalne.
"""
import sys, sqlite3
sys.path.insert(0, "/app")


def _make_db(tmp_path):
    db = sqlite3.connect(str(tmp_path / "test.db"))
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            gm_plan_json TEXT DEFAULT '{}',
            start_hex_q INTEGER,
            start_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            hex_type TEXT DEFAULT 'plains',
            label TEXT DEFAULT '',
            location_key TEXT,
            map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            label TEXT,
            location_type TEXT DEFAULT 'macro',
            parent_key TEXT,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            source_campaign_id INTEGER
        );
    """)
    return db


def _seed_world(db, hexes):
    for q, r, htype, label in hexes:
        db.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, map_level, is_active) VALUES (?,?,?,?,0,1)",
            (q, r, htype, label),
        )
    db.commit()


def _seed_grid(db, radius=7):
    """A hex grid centred on (0,0), all free plains, so allocation always succeeds."""
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            db.execute(
                "INSERT INTO world_hexes (q, r, hex_type, label, map_level, is_active) VALUES (?,?,'plains','',0,1)",
                (q, r),
            )
    db.commit()


def _tpl(db, plan_json, start=(0, 0)):
    import json
    db.execute(
        "INSERT INTO campaign_templates (title, status, gm_plan_json, start_hex_q, start_hex_r) "
        "VALUES ('T','review',?,?,?)",
        (json.dumps(plan_json), start[0], start[1]),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _mk_loc(db, key, tpl_id, q=None, r=None):
    db.execute(
        "INSERT INTO game_locations (key, label, is_active, created_by, source_campaign_id, world_hex_q, world_hex_r) "
        "VALUES (?,?,1,'forge',?,?,?)",
        (key, key, tpl_id, q, r),
    )
    db.commit()


PLAN = {
    "key_locations": [
        {"key": "wioska", "name": "Wioska", "scale": "hub"},
        {"key": "karczma", "name": "Karczma", "scale": "sub", "parent": "wioska"},
        {"key": "kuznia", "name": "Kuźnia", "scale": "sub", "parent": "wioska"},
        {"key": "loch", "name": "Stary Loch"},          # macro → needs hex
        {"key": "ruiny", "name": "Ruiny Wieży"},        # macro → needs hex
        {"key": "oboz", "name": "Obóz Bandytów"},       # macro → needs hex
    ],
    "acts": [{"key_beats": [
        {"objective_type": "visit_location", "objective_value": "karczma"}
    ]}],
}


# ── _overworld_macro_locations ────────────────────────────────────────────────

def test_macro_filter_excludes_hub_sub_and_start():
    from app.services.template_start_anchor import _overworld_macro_locations
    keys = {l["key"] for l in _overworld_macro_locations(PLAN)}
    assert keys == {"loch", "ruiny", "oboz"}, f"got {keys}"


def test_macro_filter_flat_plan_excludes_start():
    """Flat plan (no hub): the start location is anchored on the start hex, so it
    is not double-placed; the other macro locations still qualify."""
    from app.services.template_start_anchor import _overworld_macro_locations
    plan = {
        "key_locations": [
            {"key": "start_town", "name": "Miasto"},
            {"key": "cave", "name": "Jaskinia"},
        ],
        "acts": [{"key_beats": [
            {"objective_type": "visit_location", "objective_value": "start_town"}
        ]}],
    }
    keys = {l["key"] for l in _overworld_macro_locations(plan)}
    assert keys == {"cave"}, f"start must be excluded — got {keys}"


# ── ensure_plan_location_hexes ────────────────────────────────────────────────

def test_assigns_free_hexes_to_each_macro_location(tmp_path):
    from app.services.template_start_anchor import ensure_plan_location_hexes
    from app.services.hex_location_link import resolve_location_to_hex
    db = _make_db(tmp_path)
    _seed_grid(db, radius=7)
    tpl_id = _tpl(db, PLAN, start=(0, 0))
    for k in ("loch", "ruiny", "oboz"):
        _mk_loc(db, k, tpl_id)

    res = ensure_plan_location_hexes(db, tpl_id)
    assert res is not None
    assert len(res["assigned"]) == 3, res
    # every macro location now resolves to a distinct hex, none on the start hex
    coords = set()
    for k in ("loch", "ruiny", "oboz"):
        hx = resolve_location_to_hex(db, k)
        assert hx is not None, f"{k} unplaced"
        assert hx != (0, 0), f"{k} landed on start hex"
        coords.add(hx)
    assert len(coords) == 3, f"locations share a hex: {coords}"


def test_skips_named_poi_and_occupied(tmp_path):
    from app.services.template_start_anchor import ensure_plan_location_hexes
    from app.services.hex_location_link import resolve_location_to_hex
    db = _make_db(tmp_path)
    # tiny world: start + one POI + one occupied + exactly one free hex
    _seed_world(db, [
        (0, 0, "town", ""),                 # start
        (1, 0, "castle", "Zamek Piotra"),   # named POI — off limits
        (0, 1, "plains", ""),               # occupied by foreign loc
        (1, -1, "plains", ""),              # the only free hex
    ])
    db.execute(
        "INSERT INTO game_locations (key, label, is_active, world_hex_q, world_hex_r) "
        "VALUES ('foreign','F',1,0,1)"
    )
    db.commit()
    plan = {"key_locations": [
        {"key": "hub", "scale": "hub"},
        {"key": "loch", "name": "Loch"},
    ], "acts": [{"key_beats": [
        {"objective_type": "visit_location", "objective_value": "hub"}]}]}
    tpl_id = _tpl(db, plan, start=(0, 0))
    _mk_loc(db, "loch", tpl_id)

    ensure_plan_location_hexes(db, tpl_id)
    hx = resolve_location_to_hex(db, "loch")
    assert hx == (1, -1), f"must pick the only free hex, not POI/occupied — got {hx}"


def test_reused_location_keeps_its_hex(tmp_path):
    from app.services.template_start_anchor import ensure_plan_location_hexes
    from app.services.hex_location_link import resolve_location_to_hex, link_location_to_hex
    db = _make_db(tmp_path)
    _seed_grid(db, radius=7)
    tpl_id = _tpl(db, PLAN, start=(0, 0))
    for k in ("loch", "ruiny", "oboz"):
        _mk_loc(db, k, tpl_id)
    # loch is a pre-existing/reused location already anchored on (4, 1)
    link_location_to_hex(db, "loch", 4, 1)
    db.commit()

    res = ensure_plan_location_hexes(db, tpl_id)
    assert resolve_location_to_hex(db, "loch") == (4, 1), "reused hex must be kept"
    reused_keys = {r["key"] for r in res["reused"]}
    assert "loch" in reused_keys, res


def test_force_rescatter_moves_and_spreads(tmp_path):
    from app.services.template_start_anchor import ensure_plan_location_hexes
    from app.services.hex_location_link import resolve_location_to_hex
    db = _make_db(tmp_path)
    _seed_grid(db, radius=8)
    tpl_id = _tpl(db, PLAN, start=(0, 0))
    for k in ("loch", "ruiny", "oboz"):
        _mk_loc(db, k, tpl_id)

    ensure_plan_location_hexes(db, tpl_id)  # first pass
    res = ensure_plan_location_hexes(db, tpl_id, force=True, min_spacing=3)
    assert len(res["assigned"]) == 3, res
    coords = [resolve_location_to_hex(db, k) for k in ("loch", "ruiny", "oboz")]
    assert all(c is not None for c in coords)
    assert len(set(coords)) == 3, f"forced re-scatter still overlaps: {coords}"


def test_no_start_hex_returns_none(tmp_path):
    from app.services.template_start_anchor import ensure_plan_location_hexes
    db = _make_db(tmp_path)
    _seed_grid(db)
    tpl_id = _tpl(db, PLAN, start=(None, None))
    db.execute("UPDATE campaign_templates SET start_hex_q = NULL, start_hex_r = NULL WHERE id = ?", (tpl_id,))
    db.commit()
    assert ensure_plan_location_hexes(db, tpl_id) is None
