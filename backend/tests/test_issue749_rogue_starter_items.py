"""TDD: Issue #749 — Rogue w kampanii musi otrzymywać startowe wyposażenie.

Bug: create_character dla kampanii miał whitelist ("warrior", "scholar") —
Rogue był wykluczony i nie dostawał shortbow + 10 GP ani sztylet + leather_armor.

Fix: dodanie "rogue" do whitelist w characters.py.
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


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_rogue_archetype_has_starter_items_in_db(conn):
    """game_config_archetypes musi mieć rogue z niepustym starter_items_json."""
    row = conn.execute(
        "SELECT starter_items_json, starter_gold_gp FROM game_config_archetypes WHERE key = 'rogue' AND (is_active = 1 OR is_active IS NULL)"
    ).fetchone()
    assert row is not None, "Brak wiersza 'rogue' w game_config_archetypes"

    items = json.loads(row["starter_items_json"] or "[]")
    assert isinstance(items, list) and len(items) > 0, (
        f"rogue.starter_items_json pusta lub niepoprawna: {row['starter_items_json']!r}"
    )
    assert int(row["starter_gold_gp"] or 0) > 0, (
        f"rogue.starter_gold_gp musi być > 0, jest: {row['starter_gold_gp']}"
    )


def test_rogue_starter_items_include_shortbow_and_dagger(conn):
    """Rogue musi mieć shortbow + dagger w starter_items_json (#749 acceptance)."""
    row = conn.execute(
        "SELECT starter_items_json FROM game_config_archetypes WHERE key = 'rogue'"
    ).fetchone()
    assert row, "Brak rekordu rogue w game_config_archetypes"

    items = json.loads(row["starter_items_json"] or "[]")
    weapon_keys = [i.get("weapon_key") for i in items if i.get("weapon_key")]
    assert "shortbow" in weapon_keys, (
        f"shortbow nie ma w starter_items_json rogue. Są: {weapon_keys}"
    )
    assert "dagger" in weapon_keys, (
        f"dagger (sztylet) nie ma w starter_items_json rogue. Są: {weapon_keys}"
    )


def test_rogue_starter_items_include_leather_armor(conn):
    """Rogue musi mieć leather_armor w starter_items_json (#749 acceptance)."""
    row = conn.execute(
        "SELECT starter_items_json FROM game_config_archetypes WHERE key = 'rogue'"
    ).fetchone()
    assert row, "Brak rekordu rogue w game_config_archetypes"

    items = json.loads(row["starter_items_json"] or "[]")
    item_keys = [i.get("item_key") for i in items if i.get("item_key")]
    assert "leather_armor" in item_keys, (
        f"leather_armor nie ma w starter_items_json rogue. Są: {item_keys}"
    )


def test_rogue_in_campaign_creation_whitelist():
    """Whitelist w create_character musi zawierać 'rogue' (#749 root cause)."""
    import inspect
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "characters.py"
    code = src.read_text()

    # Szukamy linii z whitelist — musi zawierać "rogue"
    for line in code.splitlines():
        if "starter_archetype_key" in line and "in (" in line:
            assert '"rogue"' in line or "'rogue'" in line, (
                f"Whitelist starter_archetype_key NIE zawiera 'rogue'!\nLinia: {line.strip()}"
            )
            return

    pytest.fail("Nie znaleziono linii 'starter_archetype_key ... in (...)' w characters.py")


def test_grant_loot_creates_inventory_for_rogue(conn):
    """grant_loot_to_character z rogue starter_items_json tworzy wpisy w character_inventory."""
    from app.services.loot_service import grant_loot_to_character

    # Utwórz tymczasowego bohatera
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json, location, is_active)
           VALUES (NULL, 1, '__test_rogue_749__', 'aigm_v1',
                   '{"archetype":"rogue","stats":{},"skills":{}}', 'test', 0)"""
    )
    conn.commit()
    char_id = cur.lastrowid

    try:
        # Pobierz starter items rogue z DB
        row = conn.execute(
            "SELECT starter_items_json FROM game_config_archetypes WHERE key = 'rogue'"
        ).fetchone()
        assert row, "Brak rekordu rogue"

        starter_items = json.loads(row["starter_items_json"])
        granted = grant_loot_to_character(char_id, starter_items, source="start")

        # Sprawdź inventory
        inv = conn.execute(
            "SELECT weapon_key, item_key, consumable_key FROM character_inventory WHERE character_id = ?",
            (char_id,),
        ).fetchall()
        inv_weapons = [r["weapon_key"] for r in inv if r["weapon_key"]]
        inv_items = [r["item_key"] for r in inv if r["item_key"]]

        assert "shortbow" in inv_weapons, (
            f"shortbow nie w inventory po grant_loot. Mamy: {inv_weapons}"
        )
        assert "dagger" in inv_weapons, (
            f"dagger nie w inventory po grant_loot. Mamy: {inv_weapons}"
        )
        assert "leather_armor" in inv_items, (
            f"leather_armor nie w inventory po grant_loot. Mamy: {inv_items}"
        )

    finally:
        conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (char_id,))
        conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
        conn.commit()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_warrior_and_scholar_still_get_starter_items(conn):
    """Warrior i Scholar nadal muszą otrzymywać starter items po fixie (#749 nie może ich zepsuć)."""
    for archetype in ("warrior", "scholar"):
        row = conn.execute(
            "SELECT starter_items_json, starter_gold_gp FROM game_config_archetypes WHERE key = ?",
            (archetype,),
        ).fetchone()
        assert row is not None, f"Brak rekordu '{archetype}' w game_config_archetypes"
        items = json.loads(row["starter_items_json"] or "[]")
        assert isinstance(items, list) and len(items) > 0, (
            f"{archetype}.starter_items_json pusta"
        )
        assert int(row["starter_gold_gp"] or 0) > 0, (
            f"{archetype}.starter_gold_gp musi być > 0"
        )
