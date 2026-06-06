"""TDD: Issues #251 + #252 — narrative items in inventory (backend + frontend).

Both issues were already implemented before this TDD session:
#251: _grant_narrative_item_to_inventory() in turns.py — uses '__narrative__' sentinel
#252: Frontend _invIsLore() checks item_type='narrative'; _renderLoreRow() renders them

These tests document and verify the existing implementation.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db_runtime import resolve_db_path


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ─── #251 — backend: _grant_narrative_item_to_inventory ──────────────────────

def test_grant_narrative_item_inserts_with_narrative_sentinel(conn):
    """_grant_narrative_item_to_inventory must insert item_key='__narrative__' sentinel."""
    from app.api.turns import _grant_narrative_item_to_inventory

    row = conn.execute(
        "SELECT id FROM characters WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No active character found")
    char_id = row["id"]

    test_label = "__test_narrative_item_TDD__"
    # Clean up before
    conn.execute(
        "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
        (char_id, test_label),
    )
    conn.commit()

    _grant_narrative_item_to_inventory(conn, character_id=char_id, label=test_label)

    inv_row = conn.execute(
        "SELECT item_key, weapon_key, consumable_key, label, meta_json "
        "FROM character_inventory WHERE character_id = ? AND label = ? LIMIT 1",
        (char_id, test_label),
    ).fetchone()

    # Clean up
    conn.execute(
        "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
        (char_id, test_label),
    )
    conn.commit()

    assert inv_row is not None, "Narrative item must be inserted"
    assert inv_row["item_key"] == "__narrative__", (
        "item_key must be '__narrative__' sentinel to satisfy XOR constraint"
    )
    assert inv_row["weapon_key"] is None
    assert inv_row["consumable_key"] is None
    assert inv_row["label"] == test_label

    meta = json.loads(inv_row["meta_json"] or "{}")
    assert meta.get("item_type") == "narrative", "meta_json must have item_type=narrative"


def test_get_character_inventory_returns_narrative_item_type(conn):
    """get_character_inventory must return item_type='narrative' for __narrative__ items."""
    from app.services.loot_service import get_character_inventory
    from app.api.turns import _grant_narrative_item_to_inventory

    row = conn.execute(
        "SELECT id FROM characters WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No active character found")
    char_id = row["id"]

    test_label = "__test_narrative_item_TDD_2__"
    conn.execute(
        "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
        (char_id, test_label),
    )
    conn.commit()

    _grant_narrative_item_to_inventory(conn, character_id=char_id, label=test_label)
    conn.commit()  # commit so _conn() in get_character_inventory sees the row

    try:
        inventory = get_character_inventory(char_id)
        narrative_items = [i for i in inventory if i.get("label") == test_label]
        assert narrative_items, f"Narrative item '{test_label}' must appear in inventory"
        item = narrative_items[0]
        assert item.get("item_type") == "narrative", (
            f"item_type must be 'narrative', got: {item.get('item_type')}"
        )
        assert item.get("is_narrative") is True or item.get("item_type") == "narrative", (
            "is_narrative or item_type='narrative' must be set"
        )
    finally:
        conn.execute(
            "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
            (char_id, test_label),
        )
        conn.commit()


# ─── #252 — frontend contract (backend side) ─────────────────────────────────

def test_inventory_response_includes_label_for_narrative_items(conn):
    """Inventory response must include 'label' field for narrative items."""
    from app.services.loot_service import get_character_inventory
    from app.api.turns import _grant_narrative_item_to_inventory

    row = conn.execute(
        "SELECT id FROM characters WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No active character found")
    char_id = row["id"]

    test_label = "__test_label_field_TDD__"
    conn.execute(
        "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
        (char_id, test_label),
    )
    conn.commit()

    _grant_narrative_item_to_inventory(conn, character_id=char_id, label=test_label)
    conn.commit()

    try:
        inventory = get_character_inventory(char_id)
        found = next((i for i in inventory if i.get("label") == test_label), None)
        assert found is not None, f"Label '{test_label}' must be returned in inventory"
        assert "label" in found, "Inventory item dict must have 'label' key"
        assert found["label"] == test_label
    finally:
        conn.execute(
            "DELETE FROM character_inventory WHERE character_id = ? AND label = ?",
            (char_id, test_label),
        )
        conn.commit()
