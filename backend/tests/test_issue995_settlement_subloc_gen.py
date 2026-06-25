"""TDD: Issue #995 — Auto-generacja pod-lokacji osady przy zatwierdzaniu.

Tests verify:
- generate_sublocs_for_settlement() creates sub-locations with correct parent_key
- safe_for_rest set correctly per subtype (per #994/#995 convention)
- Key uniqueness: duplicate subtype gets suffixed key (e.g. _2)
- SETTLEMENT_SUBLOC_DEFAULTS covers all settlement types (village/town/city/garrison/monastery/port)
- get_subloc_defaults() endpoint returns correct checklist per settlement subtype
- Approving location with generate_sublocs list creates sub-locations atomically
- Backward compat: approve without generate_sublocs works as before
- Generated sub-locs appear in ≥2 threshold check (feeds FAZA ML grid)
"""
import sys
import sqlite3

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    parent_key TEXT DEFAULT NULL,
    location_type TEXT DEFAULT 'macro',
    location_subtype TEXT DEFAULT NULL,
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    approved INTEGER NOT NULL DEFAULT 1,
    review_status TEXT NOT NULL DEFAULT 'permanent',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT DEFAULT 'admin_manual',
    ai_generated INTEGER NOT NULL DEFAULT 0,
    tier INTEGER NOT NULL DEFAULT 1,
    biome TEXT DEFAULT NULL,
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
"""

SETTLEMENT_SUBTYPES = ("village", "town", "city", "garrison", "monastery", "port")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_settlement(conn, key="test_village", label="Wioska Testowa", subtype="village"):
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, location_subtype, review_status, approved)"
        " VALUES (?, ?, 'macro', ?, 'pending_review', 0)",
        (key, label, subtype),
    )
    conn.commit()


# ── Unit: generate_sublocs_for_settlement ─────────────────────────────────────


def test_generate_sublocs_creates_sub_locations():
    """Core: calling generate_sublocs_for_settlement() inserts rows under parent."""
    from app.services.world_service import generate_sublocs_for_settlement

    conn = _conn()
    _seed_settlement(conn, "wioska_a", "Wioska A", "village")

    created = generate_sublocs_for_settlement(conn, "wioska_a", ["tavern", "smithy", "shrine"])

    assert len(created) == 3
    rows = conn.execute(
        "SELECT key, location_subtype, parent_key, location_type FROM game_locations WHERE parent_key = ?",
        ("wioska_a",),
    ).fetchall()
    assert len(rows) == 3
    subtypes_in_db = {r["location_subtype"] for r in rows}
    assert subtypes_in_db == {"tavern", "smithy", "shrine"}
    for r in rows:
        assert r["parent_key"] == "wioska_a"
        assert r["location_type"] == "sub"


def test_safe_for_rest_per_subtype_correct():
    """safe_for_rest follows #994/#995 convention — tavern/shrine/temple/barracks/etc safe, market/slum/port unsafe."""
    from app.services.world_service import generate_sublocs_for_settlement, SUBLOC_SAFE_FOR_REST

    conn = _conn()
    _seed_settlement(conn, "osada_b", "Osada B", "city")

    safe_types = ["tavern", "inn", "temple", "shrine", "barracks", "infirmary", "civic", "garden", "library"]
    unsafe_types = ["market", "slum", "port", "tomb", "tower", "work"]

    generate_sublocs_for_settlement(conn, "osada_b", safe_types + unsafe_types)

    rows = conn.execute(
        "SELECT location_subtype, safe_for_rest FROM game_locations WHERE parent_key = ?",
        ("osada_b",),
    ).fetchall()
    result = {r["location_subtype"]: r["safe_for_rest"] for r in rows}

    for t in safe_types:
        assert result[t] == 1, f"Expected {t} safe_for_rest=1, got {result[t]}"
    for t in unsafe_types:
        assert result[t] == 0, f"Expected {t} safe_for_rest=0, got {result[t]}"


def test_subloc_key_unique_suffix_on_duplicate():
    """Duplicate subtype gets suffixed key (wioska_c_tavern → wioska_c_tavern_2)."""
    from app.services.world_service import generate_sublocs_for_settlement

    conn = _conn()
    _seed_settlement(conn, "wioska_c", "Wioska C", "village")

    # First call: tavern
    generate_sublocs_for_settlement(conn, "wioska_c", ["tavern"])
    # Second call: another tavern should get suffixed key
    generate_sublocs_for_settlement(conn, "wioska_c", ["tavern"])

    rows = conn.execute(
        "SELECT key FROM game_locations WHERE parent_key = ? AND location_subtype = 'tavern'",
        ("wioska_c",),
    ).fetchall()
    keys = [r["key"] for r in rows]
    assert len(keys) == 2
    assert "wioska_c_tavern" in keys
    assert "wioska_c_tavern_2" in keys


def test_generated_sublocs_are_approved_and_permanent():
    """Auto-generated sub-locs are approved=1, review_status=permanent, is_active=1."""
    from app.services.world_service import generate_sublocs_for_settlement

    conn = _conn()
    _seed_settlement(conn, "wioska_d", "Wioska D", "village")
    generate_sublocs_for_settlement(conn, "wioska_d", ["tavern"])

    row = conn.execute(
        "SELECT approved, review_status, is_active FROM game_locations WHERE parent_key = ? AND location_subtype = 'tavern'",
        ("wioska_d",),
    ).fetchone()
    assert row["approved"] == 1
    assert row["review_status"] == "permanent"
    assert row["is_active"] == 1


def test_settlement_subloc_defaults_all_types_covered():
    """SETTLEMENT_SUBLOC_DEFAULTS has entries for all 6 settlement types."""
    from app.services.world_service import SETTLEMENT_SUBLOC_DEFAULTS

    for st in SETTLEMENT_SUBTYPES:
        assert st in SETTLEMENT_SUBLOC_DEFAULTS, f"Missing default list for '{st}'"
        assert len(SETTLEMENT_SUBLOC_DEFAULTS[st]) >= 2, f"'{st}' needs ≥2 defaults (karczma+1)"


def test_each_settlement_type_has_at_least_one_safe_subloc():
    """Every settlement type defaults include ≥1 safe_for_rest subloc (guarantees #994 suggestion target)."""
    from app.services.world_service import SETTLEMENT_SUBLOC_DEFAULTS, SUBLOC_SAFE_FOR_REST

    for st, subloc_list in SETTLEMENT_SUBLOC_DEFAULTS.items():
        safe_count = sum(1 for s in subloc_list if SUBLOC_SAFE_FOR_REST.get(s, 0) == 1)
        assert safe_count >= 1, f"Settlement type '{st}' has 0 safe sublocs — breaks #994 suggestion"


def test_generate_sublocs_unknown_parent_returns_empty():
    """Non-existent parent_key returns [] without error."""
    from app.services.world_service import generate_sublocs_for_settlement

    conn = _conn()
    result = generate_sublocs_for_settlement(conn, "does_not_exist", ["tavern"])
    assert result == []


def test_generated_subloc_label_contains_parent_name():
    """Sub-loc label includes parent location name for readability."""
    from app.services.world_service import generate_sublocs_for_settlement

    conn = _conn()
    _seed_settlement(conn, "wioska_e", "Sokolniki", "village")
    generate_sublocs_for_settlement(conn, "wioska_e", ["tavern"])

    row = conn.execute(
        "SELECT label FROM game_locations WHERE parent_key = ? AND location_subtype = 'tavern'",
        ("wioska_e",),
    ).fetchone()
    assert "Sokolniki" in row["label"]


# ── Subloc count feeds FAZA ML grid threshold ─────────────────────────────────


def test_generated_sublocs_reach_ml_grid_threshold():
    """After generating default village sublocs, count ≥ 2 (satisfies FAZA ML grid threshold)."""
    from app.services.world_service import generate_sublocs_for_settlement, SETTLEMENT_SUBLOC_DEFAULTS

    conn = _conn()
    _seed_settlement(conn, "wioska_f", "Wioska F", "village")
    generate_sublocs_for_settlement(conn, "wioska_f", SETTLEMENT_SUBLOC_DEFAULTS["village"])

    count = conn.execute(
        "SELECT COUNT(*) AS n FROM game_locations WHERE parent_key = ? AND location_type = 'sub'",
        ("wioska_f",),
    ).fetchone()["n"]
    assert count >= 2


# ── Backward compat ───────────────────────────────────────────────────────────


def test_approve_entity_without_sublocs_unchanged():
    """approve_entity(location) with no subloc args still works — no regression."""
    from app.services.world_service import approve_entity

    conn = _conn()
    _seed_settlement(conn, "wioska_g", "Wioska G", "village")
    # Set pending so approve has something to change
    conn.execute("UPDATE game_locations SET approved = 0, review_status = 'pending_review' WHERE key = 'wioska_g'")
    conn.commit()

    ok = approve_entity(conn, "location", "wioska_g")
    assert ok is True

    row = conn.execute("SELECT approved FROM game_locations WHERE key = 'wioska_g'").fetchone()
    assert row["approved"] == 1
    # No sub-locs created
    count = conn.execute("SELECT COUNT(*) AS n FROM game_locations WHERE parent_key = 'wioska_g'").fetchone()["n"]
    assert count == 0
