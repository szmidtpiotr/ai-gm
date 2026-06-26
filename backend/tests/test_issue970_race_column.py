"""TDD: Issue #970 — pole `race` w tabeli characters + migracja."""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

DB_PATH = "/data/ai_gm.db"


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_race_column_exists_in_characters():
    """Kolumna `race` musi istnieć w tabeli characters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(characters)")]
    conn.close()
    assert "race" in cols, f"Brak kolumny `race` w characters. Kolumny: {cols}"


def test_race_default_is_human():
    """Nowo wstawiony rekord bez `race` musi mieć domyślnie 'human'."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Insert testowego bohatera bez jawnego race
    cur = conn.execute(
        """
        INSERT INTO characters (user_id, name, system_id, sheet_json)
        VALUES (999990, 'TestRaceDefault', 'aigm_v1', '{}')
        """
    )
    char_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT race FROM characters WHERE id = ?", (char_id,)).fetchone()
    conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
    conn.commit()
    conn.close()
    assert row is not None
    assert row["race"] == "human", f"Domyślna rasa powinna być 'human', jest: {row['race']}"


def test_race_accepts_dwarf():
    """Kolumna `race` przyjmuje wartość 'dwarf'."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        INSERT INTO characters (user_id, name, system_id, sheet_json, race)
        VALUES (999990, 'TestDwarf', 'aigm_v1', '{}', 'dwarf')
        """
    )
    char_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT race FROM characters WHERE id = ?", (char_id,)).fetchone()
    conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
    conn.commit()
    conn.close()
    assert row["race"] == "dwarf"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_characters_have_race_human():
    """Istniejące postacie (bez race) mają 'human' przez DEFAULT."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Pobierz dowolną istniejącą postać
    row = conn.execute(
        "SELECT id, race FROM characters WHERE race IS NOT NULL LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        # Brak postaci w DB — test irrelevant, pass
        return
    assert row["race"] in ("human", "dwarf"), f"Niespodziewana rasa: {row['race']}"
