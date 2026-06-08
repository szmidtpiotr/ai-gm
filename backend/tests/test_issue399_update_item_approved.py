"""TDD: Issue #399 D14 — update_item preserves approved=0 when not explicitly passed."""
import sys
import sqlite3

sys.path.insert(0, "/app")

import pytest

DB_PATH = "/data/ai_gm.db"
_TEST_KEY = "test_d14_item_399"


def _insert_pending_item(approved: int = 0, ai_generated: int = 0):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO game_config_items
               (key, label, description, item_type, value_gp, weight_kg,
                charges, effect_json, ai_generated, approved)
               VALUES (?, 'Test D14 Item', 'desc', 'misc', 10, 0.5,
                       1, NULL, ?, ?)""",
            (_TEST_KEY, ai_generated, approved),
        )
        conn.commit()
    finally:
        conn.close()


def _get_item() -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM game_config_items WHERE key = ?", (_TEST_KEY,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _cleanup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM game_config_items WHERE key = ?", (_TEST_KEY,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    _cleanup()
    _insert_pending_item(approved=0, ai_generated=0)
    yield
    _cleanup()


def _do_update(**kwargs):
    from app.services.admin_config import update_item
    defaults = dict(
        key=_TEST_KEY,
        label="Test D14 Item",
        description="desc",
        item_type="misc",
        value_gp=10,
        effect_json=None,
        is_active=True,
        force=True,
        weight_kg=0.5,
    )
    defaults.update(kwargs)
    return update_item(**defaults)


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_update_item_preserves_approved_zero_when_not_passed():
    """update_item bez approved=... nie zmienia approved=0 na 1."""
    _do_update(description="updated desc", value_gp=15)
    # approved NOT passed — should stay 0
    item = _get_item()
    assert item.get("approved") == 0, (
        f"approved should stay 0 after edit without passing approved, got {item.get('approved')}"
    )


def test_update_item_preserves_ai_generated_zero_when_not_passed():
    """update_item bez ai_generated=... nie zmienia ai_generated=0."""
    _do_update(description="updated desc 2", value_gp=15)
    # ai_generated NOT passed — should stay 0
    item = _get_item()
    assert item.get("ai_generated") == 0, (
        f"ai_generated should stay 0, got {item.get('ai_generated')}"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_update_item_explicit_approved_1_still_sets_1():
    """Jawne approved=1 nadal ustawia 1."""
    _do_update(approved=1)
    item = _get_item()
    assert item.get("approved") == 1, f"explicit approved=1 should set 1, got {item.get('approved')}"


def test_update_item_approved_1_item_stays_1_when_not_passed():
    """Przedmiot z approved=1 pozostaje approved=1 po edycji bez przekazania approved."""
    _cleanup()
    _insert_pending_item(approved=1)
    _do_update(description="updated")
    item = _get_item()
    assert item.get("approved") == 1, f"approved=1 item should stay 1, got {item.get('approved')}"
