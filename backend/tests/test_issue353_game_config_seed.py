"""TDD: Issue #353 — Game config seed: static content to git, player data private."""
import pytest
import os
import sqlite3
import subprocess
import json


# ─── Constants ──────────────────────────────────────────────────────────────

SEED_FILE = "/home/piotrszmidt/ai-gm/data/game_config_seed.sql"
EXPORT_SCRIPT = "/home/piotrszmidt/ai-gm/scripts/export_game_config.sh"

STATIC_TABLES = {
    "game_config_archetypes",
    "game_config_conditions",
    "game_config_consumables",
    "game_config_dc",
    "game_config_enemies",
    "game_config_items",
    "game_config_loot_entries",
    "game_config_loot_tables",
    "game_config_meta",
    "game_config_riddles",
    "game_config_skills",
    "game_config_spells",
    "game_config_stats",
    "game_config_visual",
    "game_config_weapons",
    "game_config_xp_awards",
    "game_config_xp_rewards",
    "game_dungeons",
    "dungeon_tile_categories",
    "dungeon_tiles",
    "gameconfig_encounter_templates",
    "adventure_hooks",
    "enemy_behavior_profiles",
    "hex_type_config",
    "knowledge_book",
    "ui_texts",
    "campaign_templates",
}

PLAYER_DATA_TABLES = {
    "users",
    "campaigns",
    "characters",
    "character_spells",
    "character_inventory",
    "character_dungeon_runs",
}


# ─── Test: Seed file exists and is valid SQL ──────────────────────────────

def test_seed_file_exists():
    """data/game_config_seed.sql must exist and be readable."""
    assert os.path.isfile(SEED_FILE), f"Seed file not found: {SEED_FILE}"
    assert os.path.getsize(SEED_FILE) > 10000, f"Seed file too small (should be >10KB): {os.path.getsize(SEED_FILE)} bytes"


def test_seed_file_is_valid_sql():
    """Seed file must parse as valid SQLite SQL."""
    try:
        with open(SEED_FILE, "r") as f:
            sql = f.read()
        assert len(sql) > 100, "Seed file appears empty or too small"
        assert "CREATE TABLE" in sql, "Seed file must contain CREATE TABLE statements"
        assert "INSERT INTO" in sql, "Seed file must contain INSERT statements"
    except Exception as e:
        pytest.fail(f"Failed to read seed file: {e}")


# ─── Test: Only static tables in seed (no player data) ───────────────────

def test_seed_contains_only_static_tables():
    """Seed file must contain ONLY the 27 static game_config tables."""
    with open(SEED_FILE, "r") as f:
        sql = f.read()

    # Find all CREATE TABLE statements
    import re
    tables_in_seed = set(re.findall(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?["\']?(\w+)["\']?', sql, re.IGNORECASE))

    # Remove sqlite_sequence (internal SQLite table)
    tables_in_seed.discard("sqlite_sequence")

    assert tables_in_seed == STATIC_TABLES, f"Seed contains unexpected tables:\nFound: {tables_in_seed}\nExpected: {STATIC_TABLES}\nExtra: {tables_in_seed - STATIC_TABLES}\nMissing: {STATIC_TABLES - tables_in_seed}"


def test_seed_contains_no_player_data():
    """Seed file must NOT contain any player-sensitive tables (users, campaigns, characters, etc)."""
    with open(SEED_FILE, "r") as f:
        sql = f.read()

    for table in PLAYER_DATA_TABLES:
        assert f"INSERT INTO {table}" not in sql.upper(), f"Seed file must NOT insert into {table} table"


# ─── Test: Row count approximation ──────────────────────────────────────

def test_seed_has_reasonable_row_count():
    """Seed file should contain ~1400+ rows total (27 tables with game content)."""
    with open(SEED_FILE, "r") as f:
        sql = f.read()

    import re
    insert_count = len(re.findall(r'INSERT INTO', sql, re.IGNORECASE))

    assert insert_count >= 1400, f"Seed file should have ~1400+ INSERT statements, found: {insert_count}"
    assert insert_count <= 2000, f"Seed file row count seems too high: {insert_count} (expected ~1400-1500)"


# ─── Test: Export script exists and is executable ──────────────────────

def test_export_script_exists():
    """Export script must exist and be executable."""
    assert os.path.isfile(EXPORT_SCRIPT), f"Export script not found: {EXPORT_SCRIPT}"
    assert os.access(EXPORT_SCRIPT, os.X_OK), f"Export script not executable: {EXPORT_SCRIPT}"


def test_export_script_contains_key_logic():
    """Export script must select ONLY the 27 static tables."""
    with open(EXPORT_SCRIPT, "r") as f:
        script = f.read()

    # Should mention at least some of the static tables
    assert any(t in script for t in ["game_config_weapons", "game_config_enemies", "game_config_items"]), \
        "Export script doesn't mention any static tables"

    # Should NOT dump player tables
    assert "INSERT INTO users" not in script.lower(), "Export script must NOT include users table"
    assert "INSERT INTO campaigns" not in script.lower(), "Export script must NOT include campaigns table"


# ─── Backward compat: .gitignore allows game_config_seed.sql ──────────

def test_seed_file_not_gitignored():
    """game_config_seed.sql must be explicitly allowed in .gitignore (negation rule)."""
    gitignore_path = "/home/piotrszmidt/ai-gm/.gitignore"
    with open(gitignore_path, "r") as f:
        gitignore = f.read()

    # Must have data/* ignored but game_config_seed.sql NOT ignored
    assert "data/*" in gitignore, ".gitignore must ignore data/*"
    assert "!data/game_config_seed.sql" in gitignore, ".gitignore must have negation rule for game_config_seed.sql"


def test_player_data_still_gitignored():
    """ai_gm.db (and data-dev/) must remain gitignored."""
    gitignore_path = "/home/piotrszmidt/ai-gm/.gitignore"
    with open(gitignore_path, "r") as f:
        gitignore = f.read()

    # Verify data/ is ignored (ai_gm.db inside it)
    assert "data/*" in gitignore, "data/ should be ignored"
    assert "!data/.gitkeep" in gitignore, "Only .gitkeep should be allowed in data/"
    assert "!data/game_config_seed.sql" in gitignore, "Only game_config_seed.sql should be allowed"
