"""TDD: Issue #988 — readable item description (pergamin/list/notatka) must not become placeholder."""
import sys
import os
sys.path.insert(0, "/app")

from app.api.turns import _parse_grant_item_entry


# ─── Helpers used in RED phase ────────────────────────────────────────────────

def _get_readable_detector():
    """Import _is_readable_item_label — fails RED if function does not exist."""
    from app.api.turns import _is_readable_item_label
    return _is_readable_item_label


# ─── FAZA 1: _is_readable_item_label must exist and work ─────────────────────

def test_is_readable_item_label_exists():
    """Function _is_readable_item_label must be importable from turns."""
    fn = _get_readable_detector()
    assert callable(fn)


def test_readable_item_pergamin():
    fn = _get_readable_detector()
    assert fn("Złożony pergamin") is True
    assert fn("Stary pergamin z pieczęcią") is True


def test_readable_item_list():
    fn = _get_readable_detector()
    assert fn("List od kupca") is True
    assert fn("Tajemniczy list") is True


def test_readable_item_notatka():
    fn = _get_readable_detector()
    assert fn("Notatka badacza") is True
    assert fn("Skrwawiona notatka") is True


def test_readable_item_zwoj():
    fn = _get_readable_detector()
    assert fn("Zwój z mapą") is True
    assert fn("Magiczny zwój") is True


def test_readable_item_ksiega():
    fn = _get_readable_detector()
    assert fn("Stara księga") is True
    assert fn("Księga zaklęć") is True


def test_readable_item_mapa():
    fn = _get_readable_detector()
    assert fn("Mapa skarbu") is True


def test_non_readable_items_are_false():
    fn = _get_readable_detector()
    assert fn("Żelazny klucz") is False
    assert fn("Pochodnia") is False
    assert fn("Mieszek z monetami") is False
    assert fn("Zardzewiały miecz") is False


# ─── FAZA 2: _parse_grant_item_entry with object form preserves description ──

def test_parse_object_form_preserves_description():
    """Object form grant_item must carry full description to engine."""
    result = _parse_grant_item_entry({
        "label": "Złożony pergamin",
        "description": "Drogi bracie, piszę z obozu nad Prypecią. Straż widziała ognie na wschodzie."
    })
    assert result is not None
    label, desc = result
    assert label == "Złożony pergamin"
    assert desc is not None
    assert "Prypecią" in desc


def test_parse_string_form_gives_none_description():
    """String form grant_item still returns None description (backward compat)."""
    result = _parse_grant_item_entry("Złożony pergamin")
    assert result is not None
    label, desc = result
    assert label == "Złożony pergamin"
    assert desc is None


# ─── FAZA 3: readable item without description → NOT "Narracyjny przedmiot:" ─

def test_readable_item_no_description_avoids_generic_placeholder():
    """When readable item arrives without description, stored desc must NOT equal
    the generic 'Narracyjny przedmiot: <label>' placeholder.

    This test verifies the engine fallback: if LLM forgot the description,
    the item should at least not mislead the player with technical noise.
    """
    import sqlite3
    from app.api.turns import _grant_pending_item

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE game_config_items (
        key TEXT PRIMARY KEY,
        label TEXT,
        item_type TEXT,
        description TEXT,
        value_gp INTEGER,
        ai_generated INTEGER,
        approved INTEGER,
        campaign_id INTEGER,
        review_status TEXT,
        is_active INTEGER,
        pending_category TEXT
    )""")
    conn.execute("""CREATE TABLE character_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER,
        weapon_key TEXT,
        item_key TEXT,
        consumable_key TEXT,
        label TEXT,
        quantity INTEGER,
        equipped INTEGER,
        source TEXT,
        meta_json TEXT
    )""")
    conn.commit()

    _grant_pending_item(
        conn,
        campaign_id=99791,
        character_id=42,
        label="Złożony pergamin",
        description=None,  # LLM forgot to include description
    )
    conn.commit()

    row = conn.execute(
        "SELECT description FROM game_config_items WHERE label = 'Złożony pergamin'"
    ).fetchone()
    assert row is not None, "Item not inserted"
    stored_desc = row[0]
    assert stored_desc != "Narracyjny przedmiot: Złożony pergamin", (
        f"Stored description is generic placeholder — readable item should get better fallback. Got: {stored_desc!r}"
    )


# ─── Backward compat: non-readable item still gets normal placeholder ─────────

def test_non_readable_item_keeps_generic_placeholder():
    """Non-readable items (torba, klucz) keep current 'Narracyjny przedmiot:' placeholder."""
    import sqlite3
    from app.api.turns import _grant_pending_item

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE game_config_items (
        key TEXT PRIMARY KEY,
        label TEXT,
        item_type TEXT,
        description TEXT,
        value_gp INTEGER,
        ai_generated INTEGER,
        approved INTEGER,
        campaign_id INTEGER,
        review_status TEXT,
        is_active INTEGER,
        pending_category TEXT
    )""")
    conn.execute("""CREATE TABLE character_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER,
        weapon_key TEXT,
        item_key TEXT,
        consumable_key TEXT,
        label TEXT,
        quantity INTEGER,
        equipped INTEGER,
        source TEXT,
        meta_json TEXT
    )""")
    conn.commit()

    _grant_pending_item(
        conn,
        campaign_id=1,
        character_id=1,
        label="Żelazny klucz",
        description=None,
    )
    conn.commit()

    row = conn.execute(
        "SELECT description FROM game_config_items WHERE label = 'Żelazny klucz'"
    ).fetchone()
    assert row is not None
    stored_desc = row[0]
    # non-readable items keep their placeholder as before
    assert "Żelazny klucz" in stored_desc
