"""TDD U12 (#560) — db_lint: audyt integralności bazy treści.

Tests verify run_lint() on a hand-crafted SQLite DB:
  - returns {errors, warnings, exit_code} structure
  - dangling FK (enemy.loot_table_key → missing loot table) → error (exit 2)
  - value out of range (enemy hp_base=0) → warning
  - enum violation (game_items.kind not in valid set) → warning
  - NEW: rarity out of 1..5 → warning
  - NEW: loot_entries.weight out of 1..100 → warning
  - NEW: negative weight_kg → warning
  - NEW: duplicate key in game_items → error (exit 2)
  - clean DB → exit 0, no errors/warnings
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql


def _make_test_db() -> tuple[str, sqlite3.Connection]:
    """Create a temp SQLite DB with a minimal subset of game tables.

    NOTE: game_items.key intentionally has NO PRIMARY KEY constraint here so the
    duplicate-key lint can be exercised (production enforces PK; the lint is defensive).
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        """ + table_sql("game_config_loot_tables") + """
        """ + table_sql("game_config_loot_entries") + """
        """ + table_sql("game_config_enemies") + """
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        CREATE TABLE game_items (
            key       TEXT,
            kind      TEXT NOT NULL,
            label     TEXT NOT NULL,
            rarity    INTEGER NOT NULL DEFAULT 1,
            weight_kg REAL NOT NULL DEFAULT 0.0,
            price_gp  INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
    return path, conn


# ─── structure ───────────────────────────────────────────────────────────────

def test_run_lint_returns_dict_structure():
    """run_lint() must return dict with errors / warnings / exit_code."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    conn.close()
    try:
        result = run_lint(path)
        assert isinstance(result, dict)
        assert "errors" in result and "warnings" in result and "exit_code" in result
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)
        assert result["exit_code"] in (0, 1, 2)
    finally:
        os.unlink(path)


# ─── dangling FK (error) ───────────────────────────────────────────────────────

def test_dangling_fk_detected():
    """Enemy referencing non-existent loot_table_key → error → exit 2."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, loot_table_key) "
            "VALUES ('wolf_bad', 'Wilk', 'loot_does_not_exist')"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] == 2, result
        text = " ".join(result["errors"])
        assert "wolf_bad" in text or "loot_does_not_exist" in text
    finally:
        os.unlink(path)


# ─── value out of range ─────────────────────────────────────────────────────────

def test_value_out_of_range_detected():
    """Enemy with hp_base=0 → at least a warning."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_config_enemies (key, label, hp_base) VALUES ('goblin_zero_hp', 'Goblin', 0)")
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, result
        text = " ".join(result["errors"] + result["warnings"])
        assert "goblin_zero_hp" in text or "hp" in text.lower()
    finally:
        os.unlink(path)


# ─── enum violation: kind ─────────────────────────────────────────────────────

def test_enum_violation_kind_detected():
    """game_items row with kind='bad_kind' → at least a warning."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_items (key, kind, label) VALUES ('sword_bad', 'bad_kind', 'Sword')")
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, result
        text = " ".join(result["errors"] + result["warnings"])
        assert "sword_bad" in text or "bad_kind" in text or "kind" in text.lower()
    finally:
        os.unlink(path)


# ─── NEW: enum violation: rarity ──────────────────────────────────────────────

def test_rarity_out_of_range_detected():
    """game_items with rarity=9 (outside 1..5) → warning mentioning the key/rarity."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_items (key, kind, label, rarity) VALUES ('gem_weird', 'item', 'Gem', 9)")
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, result
        text = " ".join(result["errors"] + result["warnings"])
        assert "gem_weird" in text or "rarity" in text.lower()
    finally:
        os.unlink(path)


# ─── NEW: loot weight out of range ────────────────────────────────────────────

def test_loot_weight_out_of_range_detected():
    """loot_entries.weight=150 (outside 1..100) → warning."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_x', 'X')")
        conn.execute(
            "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight) "
            "VALUES ('loot_x', 'something', 150)"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, result
        text = " ".join(result["errors"] + result["warnings"])
        assert "weight" in text.lower() or "150" in text
    finally:
        os.unlink(path)


# ─── NEW: negative weight_kg ──────────────────────────────────────────────────

def test_negative_weight_kg_detected():
    """game_items.weight_kg=-2 → warning."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute(
            "INSERT INTO game_items (key, kind, label, weight_kg) VALUES ('float_item', 'item', 'Float', -2.0)"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, result
        text = " ".join(result["errors"] + result["warnings"])
        assert "float_item" in text or "weight" in text.lower()
    finally:
        os.unlink(path)


# ─── NEW: duplicate key in game_items (error) ─────────────────────────────────

def test_duplicate_key_in_game_items_detected():
    """Two game_items rows with the same key → error → exit 2."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_items (key, kind, label) VALUES ('dup_key', 'item', 'A')")
        conn.execute("INSERT INTO game_items (key, kind, label) VALUES ('dup_key', 'weapon', 'B')")
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] == 2, result
        text = " ".join(result["errors"])
        assert "dup_key" in text
    finally:
        os.unlink(path)


# ─── clean DB ─────────────────────────────────────────────────────────────────

def test_clean_db_exit_0():
    """Clean DB with valid data → exit_code 0, no errors/warnings."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_wolf', 'Łupy Wilka')")
        conn.execute(
            "INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight) VALUES ('loot_wolf', 'pelt', 40)"
        )
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, loot_table_key, hp_base) "
            "VALUES ('wolf_ok', 'Wilk', 'loot_wolf', 10)"
        )
        conn.execute(
            "INSERT INTO game_items (key, kind, label, rarity, weight_kg, price_gp) "
            "VALUES ('pelt', 'item', 'Skóra', 1, 0.5, 5)"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] == 0, result
        assert len(result["errors"]) == 0, result["errors"]
        assert len(result["warnings"]) == 0, result["warnings"]
    finally:
        os.unlink(path)
