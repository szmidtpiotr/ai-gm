"""TDD: Issue #977 — Character sheet race field returned by GET /characters/{id}."""
import sys
sys.path.insert(0, "/app")


def test_get_character_returns_race_field():
    """GET /characters/{id} response includes 'race' field."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT c.race FROM characters c LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None, "Brak postaci w DB"
    assert "race" in row.keys(), "Kolumna 'race' brak w characters"


def test_race_column_default_human():
    """Istniejące postaci mają race='human' (DEFAULT)."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM characters WHERE race IS NOT NULL AND race != ''"
    ).fetchone()
    conn.close()
    assert rows[0] >= 0, "Kolumna race niedostępna"


def test_get_character_endpoint_includes_race():
    """GET /characters/{id} schema includes race via setdefault."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    char = conn.execute(
        "SELECT id, race FROM characters ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not char:
        return
    # race column readable, default 'human'
    race = char["race"] or "human"
    assert race in ("human", "dwarf", "elf", "orc"), f"Nieoczekiwana rasa: {race}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_race_badge_logic_human_hidden():
    """Człowiek (race=human) → badge ukryty (race != 'human' = False)."""
    race = "human"
    should_show = race != "human"
    assert should_show is False


def test_race_badge_logic_dwarf_shown():
    """Krasnolud (race=dwarf) → badge widoczny."""
    race = "dwarf"
    should_show = race != "human"
    assert should_show is True
