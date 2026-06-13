"""TDD U12 (#559) — db_lint: audyt integralności bazy.

Tests verify:
  - run_lint() returns dict with errors / warnings / exit_code
  - dangling FK detected (enemy.loot_table_key pointing to non-existent loot table)
  - value out of range detected (enemy hp_base=0)
  - enum violation detected (game_items.kind not in valid set)
  - clean DB → exit_code 0, no errors
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, "/app")


def _make_test_db() -> tuple[str, sqlite3.Connection]:
    """Create a temp SQLite DB with a minimal subset of game tables."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE game_config_loot_tables (
            key   TEXT PRIMARY KEY,
            label TEXT NOT NULL
        );
        CREATE TABLE game_config_enemies (
            key           TEXT PRIMARY KEY,
            label         TEXT,
            hp_base       INTEGER NOT NULL DEFAULT 10,
            ac_base       INTEGER NOT NULL DEFAULT 10,
            attack_bonus  INTEGER NOT NULL DEFAULT 0,
            dex_modifier  INTEGER NOT NULL DEFAULT 0,
            damage_die    TEXT NOT NULL DEFAULT '1d6',
            loot_table_key TEXT,
            is_active     INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_config_weapons (
            key        TEXT PRIMARY KEY,
            label      TEXT NOT NULL,
            damage_die TEXT NOT NULL DEFAULT '1d6',
            weight_kg  REAL NOT NULL DEFAULT 0.0,
            value_gp   INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE game_config_items (
            key      TEXT PRIMARY KEY,
            label    TEXT NOT NULL,
            rarity   INTEGER NOT NULL DEFAULT 1,
            value_gp INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE game_items (
            key   TEXT PRIMARY KEY,
            kind  TEXT NOT NULL,
            label TEXT NOT NULL
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
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "errors" in result, "Missing 'errors' key"
        assert "warnings" in result, "Missing 'warnings' key"
        assert "exit_code" in result, "Missing 'exit_code' key"
        assert isinstance(result["errors"], list), "'errors' must be list"
        assert isinstance(result["warnings"], list), "'warnings' must be list"
        assert result["exit_code"] in (0, 1, 2), f"exit_code must be 0/1/2, got {result['exit_code']}"
    finally:
        os.unlink(path)


# ─── dangling FK ─────────────────────────────────────────────────────────────

def test_dangling_fk_detected():
    """Enemy referencing non-existent loot_table_key → classified as error."""
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
        assert result["exit_code"] == 2, f"Expected exit_code=2, got {result['exit_code']}"
        text = " ".join(result["errors"])
        assert "wolf_bad" in text or "loot_does_not_exist" in text, (
            f"Error must mention 'wolf_bad' or 'loot_does_not_exist'. Got: {result['errors']}"
        )
    finally:
        os.unlink(path)


# ─── value out of range ───────────────────────────────────────────────────────

def test_value_out_of_range_detected():
    """Enemy with hp_base=0 → at least a warning reported."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, hp_base) "
            "VALUES ('goblin_zero_hp', 'Goblin', 0)"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, f"Expected exit_code >= 1, got {result['exit_code']}"
        all_issues = result["errors"] + result["warnings"]
        text = " ".join(all_issues)
        assert "goblin_zero_hp" in text or "hp" in text.lower(), (
            f"Should mention 'goblin_zero_hp' or 'hp'. Got: {all_issues}"
        )
    finally:
        os.unlink(path)


# ─── enum violation ───────────────────────────────────────────────────────────

def test_enum_violation_detected():
    """game_items row with kind='bad_kind' → at least a warning reported."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute(
            "INSERT INTO game_items (key, kind, label) VALUES ('sword_bad', 'bad_kind', 'Sword')"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] >= 1, f"Expected exit_code >= 1, got {result['exit_code']}"
        all_issues = result["errors"] + result["warnings"]
        text = " ".join(all_issues)
        assert "sword_bad" in text or "bad_kind" in text or "kind" in text.lower(), (
            f"Should mention enum violation. Got: {all_issues}"
        )
    finally:
        os.unlink(path)


# ─── clean DB ────────────────────────────────────────────────────────────────

def test_clean_db_exit_0():
    """Clean DB with valid data → exit_code 0, no errors."""
    from app.services.db_lint_service import run_lint
    path, conn = _make_test_db()
    try:
        conn.execute("INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_wolf', 'Łupy Wilka')")
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, loot_table_key, hp_base) "
            "VALUES ('wolf_ok', 'Wilk', 'loot_wolf', 10)"
        )
        conn.commit()
        conn.close()
        result = run_lint(path)
        assert result["exit_code"] == 0, (
            f"Expected exit_code=0 on clean DB, got {result['exit_code']}. "
            f"Errors: {result['errors']}. Warnings: {result['warnings']}"
        )
        assert len(result["errors"]) == 0, f"Expected no errors on clean DB: {result['errors']}"
    finally:
        os.unlink(path)
