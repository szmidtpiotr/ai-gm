"""TDD: Issue #1037 — LocationResponse exposes region field via admin/locations endpoint."""
import sys
import os
import json
import sqlite3
import pytest

sys.path.insert(0, "/app")


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_admin_locations_returns_region_field():
    """API /api/locations/admin/locations must include 'region' in every row."""
    from app.routers.locations import row_to_location_dict

    # Simulate a DB row with region set
    class FakeRow(dict):
        def keys(self):
            return super().keys()

    row_data = {
        "id": 1,
        "key": "test_loc",
        "label": "Test Location",
        "description": None,
        "parent_id": None,
        "parent_key": None,
        "location_type": "macro",
        "rules": None,
        "enemy_keys": "[]",
        "npc_keys": "[]",
        "safe_for_rest": 0,
        "created_by": "seed",
        "location_subtype": None,
        "biome": None,
        "tier": 1,
        "canonical": 1,
        "source_campaign_id": None,
        "is_active": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "usage_count": 0,
        "image_url": None,
        "region": "siwe_granie",
    }

    # Wrap as sqlite3.Row-like dict
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_locations (
            id INTEGER, key TEXT, label TEXT, description TEXT,
            parent_id INTEGER, parent_key TEXT, location_type TEXT,
            rules TEXT, enemy_keys TEXT, npc_keys TEXT, safe_for_rest INTEGER,
            created_by TEXT, location_subtype TEXT, biome TEXT, tier INTEGER,
            canonical INTEGER, source_campaign_id INTEGER, is_active INTEGER,
            created_at TEXT, updated_at TEXT, usage_count INTEGER,
            image_url TEXT, region TEXT
        )
    """)
    conn.execute("""
        INSERT INTO game_locations VALUES (
            1,'test_loc','Test Location',NULL,NULL,NULL,'macro',
            NULL,'[]','[]',0,'seed',NULL,NULL,1,1,NULL,1,
            '2026-01-01T00:00:00','2026-01-01T00:00:00',0,NULL,'siwe_granie'
        )
    """)
    row = conn.execute("SELECT * FROM game_locations WHERE key='test_loc'").fetchone()
    result = row_to_location_dict(row)

    assert "region" in result, "row_to_location_dict must pass through 'region' field"
    assert result["region"] == "siwe_granie"
    conn.close()


def test_location_response_schema_includes_region():
    """LocationResponse (Pydantic model) must have a 'region' field."""
    from app.routers.locations import LocationResponse

    # Pydantic v2 may nest fields in $defs; check all possible locations
    schema = LocationResponse.model_json_schema()
    all_props = set(schema.get("properties", {}).keys())
    for defn in schema.get("$defs", {}).values():
        all_props.update(defn.get("properties", {}).keys())
    assert "region" in all_props, (
        f"LocationResponse missing 'region' field. All found fields: {sorted(all_props)}"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_location_response_null_region_valid():
    """LocationResponse must accept region=None (most existing rows have NULL region)."""
    from app.routers.locations import LocationResponse

    loc = LocationResponse(
        id=1,
        label="Test",
        location_type="macro",
        created_by="seed",
        tier=1,
        canonical=True,
        is_active=1,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        region=None,
    )
    assert loc.region is None


def test_existing_fields_unaffected():
    """Existing LocationResponse fields (tier, biome, safe_for_rest) still work."""
    from app.routers.locations import LocationResponse

    loc = LocationResponse(
        id=99,
        label="Wioska",
        location_type="macro",
        created_by="admin_manual",
        tier=3,
        biome="forest",
        safe_for_rest=True,
        canonical=True,
        is_active=1,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        region="czarnobor",
    )
    assert loc.tier == 3
    assert loc.biome == "forest"
    assert loc.safe_for_rest is True
    assert loc.region == "czarnobor"
