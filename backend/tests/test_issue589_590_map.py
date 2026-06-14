"""TDD: Issue #589 + #590 — global world gen square shape + floating detail fields.

#589: generate_world produced HEX/diamond (cube-constraint). Must be square/rectangle.
#590: floating locations list missing full fields (description, parent_key, ai_generated)
      needed for a preview/edit modal before placing.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.hex_world import _world_hex_coords  # noqa: E402
from app.services.placement_engine import get_floating_locations  # noqa: E402


# ─── #589 — square world shape ───────────────────────────────────────────────

def test_world_coords_count_is_full_grid():
    """Global world grid must have (2R+1)x(2R+1) hexes."""
    radius = 5
    coords = _world_hex_coords(radius)
    expected = (2 * radius + 1) ** 2
    assert len(coords) == expected, f"expected {expected} hexes, got {len(coords)}"


def test_world_renders_as_rectangle_not_rhombus():
    """#589: pixel layout (flat-top: y depends on q/2 + r) must be a RECTANGLE.

    The map renders each hex at y ∝ (q/2 + r). A plain axial square [-R,R]² makes
    (q/2 + r) span widen with q → a rhombus on screen. A rectangle requires the
    vertical band (q/2 + r) to be identical width for every column q.
    """
    radius = 5
    coords = _world_hex_coords(radius)
    cols = {}
    for q, r in coords:
        cols.setdefault(q, []).append(q / 2 + r)  # vertical position term
    bands = [(min(v), max(v)) for v in cols.values()]
    # every column spans the same vertical band → rectangle, not rhombus
    widths = {round(hi - lo, 6) for lo, hi in bands}
    assert len(widths) == 1, f"columns have differing vertical spans → rhombus: {widths}"
    # horizontal extent is full 2R+1 columns
    assert max(cols) - min(cols) == 2 * radius


# ─── #590 — floating locations carry full preview fields ─────────────────────

def _mk_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_locations (
            key TEXT, label TEXT, location_type TEXT, location_subtype TEXT,
            terrain_tags TEXT, biome TEXT, tier INTEGER, description TEXT,
            parent_key TEXT, ai_generated INTEGER, placement TEXT,
            approved INTEGER, is_active INTEGER, world_hex_q INTEGER, world_hex_r INTEGER
        )"""
    )
    conn.execute(
        """INSERT INTO game_locations
           (key, label, location_type, location_subtype, terrain_tags, biome, tier,
            description, parent_key, ai_generated, placement, approved, is_active)
           VALUES ('cave1','Jaskinia','dungeon','cave','[\"forest\"]','forest',2,
                   'Mroczna jaskinia w lesie','forest_region',1,'floating',1,1)"""
    )
    conn.commit()
    return conn


def test_floating_includes_preview_fields():
    """#590: floating rows must expose description, parent_key, ai_generated for the modal."""
    conn = _mk_conn()
    rows = get_floating_locations(conn)
    assert len(rows) == 1
    r = rows[0]
    assert r["description"] == "Mroczna jaskinia w lesie"
    assert r["parent_key"] == "forest_region"
    assert r["ai_generated"] == 1


def test_floating_still_returns_basic_fields():
    """Backward compat: existing fields (label, terrain_tags parsed) still present."""
    conn = _mk_conn()
    rows = get_floating_locations(conn)
    r = rows[0]
    assert r["label"] == "Jaskinia"
    assert r["terrain_tags"] == ["forest"]
    assert r["tier"] == 2


# ─── #590 — edit a pending/floating location before approval ──────────────────

def test_update_location_fields_edits_whitelisted():
    """#590: admin can edit label/description/tier before approving/placing."""
    from app.services.world_service import update_location_fields

    conn = _mk_conn()
    ok = update_location_fields(
        conn, "cave1",
        {"label": "Głęboka Jaskinia", "description": "Nowy opis", "tier": 4},
    )
    assert ok is True
    row = conn.execute(
        "SELECT label, description, tier FROM game_locations WHERE key='cave1'"
    ).fetchone()
    assert row["label"] == "Głęboka Jaskinia"
    assert row["description"] == "Nowy opis"
    assert row["tier"] == 4


def test_update_location_fields_ignores_unknown_columns():
    """Only whitelisted columns are writable — unknown keys are ignored (no SQL injection)."""
    from app.services.world_service import update_location_fields

    conn = _mk_conn()
    ok = update_location_fields(
        conn, "cave1", {"approved": 0, "key": "hacked", "bogus": "x", "label": "Z"},
    )
    assert ok is True
    row = conn.execute(
        "SELECT key, label, approved FROM game_locations WHERE key='cave1'"
    ).fetchone()
    assert row is not None  # key not overwritten
    assert row["label"] == "Z"
    assert row["approved"] == 1  # not editable here
