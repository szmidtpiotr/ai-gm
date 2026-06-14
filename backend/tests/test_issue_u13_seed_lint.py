"""TDD U13 (#561) — seed_lint: jedna ścieżka walidacji treści seedów.

Tests verify lint_seeds():
  - builds a fresh DB from a source schema, applies seed *.sql files in order
  - returns {applied, rejected, errors, warnings, exit_code} structure
  - a clean seed → applied, exit 0
  - a seed with a broken effect_json → warning (exit 1), still applied
  - a seed with malformed SQL → rejected (file listed in 'rejected'), exit 2
  - a seed with a dangling FK (enemy.loot_table_key → missing) → error (exit 2)
  - ORPHAN warnings (game_items empty at seed stage) are filtered out as noise
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, "/app")


# Minimal schema mirroring the columns the lint touches. lint_seeds copies the
# *source* DB schema, so we hand-build a tiny source DB here.
_SCHEMA = """
CREATE TABLE game_config_loot_tables (
    key   TEXT PRIMARY KEY,
    label TEXT NOT NULL
);
CREATE TABLE game_config_enemies (
    key            TEXT PRIMARY KEY,
    label          TEXT,
    hp_base        INTEGER,
    loot_table_key TEXT
);
CREATE TABLE game_config_weapons (
    key         TEXT PRIMARY KEY,
    label       TEXT,
    value_gp    INTEGER,
    weight_kg   REAL,
    effect_json TEXT
);
CREATE TABLE game_items (
    key         TEXT PRIMARY KEY,
    label       TEXT,
    kind        TEXT,
    rarity      INTEGER,
    price_gp    INTEGER,
    weight_kg   REAL,
    effect_json TEXT
);
"""


def _make_source_schema_db() -> str:
    fd, path = tempfile.mkstemp(suffix="_src.db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return path


def _write_seed(seeds_dir: str, name: str, sql: str) -> None:
    with open(os.path.join(seeds_dir, name), "w", encoding="utf-8") as fh:
        fh.write(sql)


# ─── Test główny: czysty seed → exit 0 ───────────────────────────────────────

def test_clean_seed_passes():
    """Poprawny seed: aplikuje się, brak errorów/warningów → exit 0."""
    from app.services.seed_lint_service import lint_seeds

    src = _make_source_schema_db()
    seeds = tempfile.mkdtemp()
    _write_seed(seeds, "01_loot.sql",
                "INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_goblin', 'Lup goblina');")
    _write_seed(seeds, "02_enemies.sql",
                "INSERT INTO game_config_enemies (key, label, hp_base, loot_table_key) "
                "VALUES ('goblin', 'Goblin', 12, 'loot_goblin');")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)

    assert result["exit_code"] == 0, f"oczekiwano czysto, dostałem: {result}"
    assert "01_loot.sql" in result["applied"]
    assert "02_enemies.sql" in result["applied"]
    assert result["rejected"] == []
    assert result["errors"] == []


# ─── effect_json niezgodny ze schematem U10 → warning ────────────────────────

def test_bad_effect_json_is_warning():
    """Seed z niepoprawnym effect_json: aplikuje się, ale lint daje warning (exit 1)."""
    from app.services.seed_lint_service import lint_seeds

    src = _make_source_schema_db()
    seeds = tempfile.mkdtemp()
    # effect_json bez schema_version=1 → validate_effect_json_payload zwróci błędy → warning
    _write_seed(seeds, "04_weapons.sql",
                "INSERT INTO game_config_weapons (key, label, value_gp, weight_kg, effect_json) "
                "VALUES ('cursed_blade', 'Klatwa', 50, 1.0, '{\"effects\": []}');")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)

    assert "04_weapons.sql" in result["applied"]
    assert result["exit_code"] == 1, f"oczekiwano warning (1), dostałem: {result}"
    assert any("EFFECT_JSON" in w for w in result["warnings"]), result["warnings"]


# ─── Malformed SQL → rejected ────────────────────────────────────────────────

def test_malformed_sql_is_rejected():
    """Seed z błędnym SQL trafia do 'rejected', nie wywala całego lintu, exit 2."""
    from app.services.seed_lint_service import lint_seeds

    src = _make_source_schema_db()
    seeds = tempfile.mkdtemp()
    _write_seed(seeds, "01_ok.sql",
                "INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_x', 'X');")
    _write_seed(seeds, "02_broken.sql",
                "INSERT INTO nonexistent_table (a) VALUES (1);")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)

    assert "01_ok.sql" in result["applied"]
    assert any(r["file"] == "02_broken.sql" for r in result["rejected"]), result["rejected"]
    assert result["exit_code"] == 2


# ─── Dangling FK → error ─────────────────────────────────────────────────────

def test_dangling_fk_is_error():
    """Wróg wskazujący na nieistniejącą tabelę łupów → error (exit 2)."""
    from app.services.seed_lint_service import lint_seeds

    src = _make_source_schema_db()
    seeds = tempfile.mkdtemp()
    _write_seed(seeds, "09_enemies.sql",
                "INSERT INTO game_config_enemies (key, label, hp_base, loot_table_key) "
                "VALUES ('orc', 'Ork', 20, 'loot_ghost');")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)

    assert any("FK" in e and "orc" in e for e in result["errors"]), result["errors"]
    assert result["exit_code"] == 2


# ─── ORPHAN warnings filtrowane (game_items puste na etapie seedu) ───────────

def test_orphan_warnings_filtered():
    """ORPHAN (legacy bez game_items) to szum runtime — lint_seeds go nie raportuje."""
    from app.services.seed_lint_service import lint_seeds

    src = _make_source_schema_db()
    seeds = tempfile.mkdtemp()
    _write_seed(seeds, "04_weapons.sql",
                "INSERT INTO game_config_weapons (key, label, value_gp, weight_kg) "
                "VALUES ('sword', 'Miecz', 30, 2.0);")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)

    assert not any("ORPHAN" in w for w in result["warnings"]), \
        f"ORPHAN nie powinien wyciekać do raportu seedów: {result['warnings']}"


# ─── U10 validator: dice string z modyfikatorem (+N/-N) musi być valid ───────

def test_effect_json_dice_with_modifier_valid():
    """heal_hp/restore_mana z '2d4+2' / '1d6-1' = poprawne (engine już to obsługuje)."""
    from app.services.admin_config import validate_effect_json_payload

    for effect_type, val in [
        ("heal_hp", "2d4+2"),
        ("heal_hp", "8d4+8"),
        ("restore_mana", "1d6+2"),
        ("heal_hp", "1d4-1"),
    ]:
        payload = {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [{"type": effect_type, "value": val}],
        }
        errs = validate_effect_json_payload(payload)
        assert errs == [], f"{effect_type} '{val}' powinien być valid, errors: {errs}"


def test_effect_json_bad_dice_still_rejected():
    """Śmieciowy 'value' dalej odrzucany (regex nie zrobił się permisywny na wszystko)."""
    from app.services.admin_config import validate_effect_json_payload

    payload = {
        "schema_version": 1,
        "effect_category": "consumable_immediate",
        "effects": [{"type": "heal_hp", "value": "abc"}],
    }
    errs = validate_effect_json_payload(payload)
    assert any("dice" in e for e in errs), errs


# ─── created_by='seed' egzekwowane w seed-lincie ─────────────────────────────

def test_seed_created_by_must_be_seed():
    """Rekord seedowy w tabeli z kolumną created_by != 'seed' → warning [SEED_OWNER]."""
    from app.services.seed_lint_service import lint_seeds

    src_fd, src = tempfile.mkstemp(suffix="_src.db")
    os.close(src_fd)
    sc = sqlite3.connect(src)
    sc.executescript(
        "CREATE TABLE game_locations (key TEXT PRIMARY KEY, label TEXT, created_by TEXT);"
    )
    sc.commit()
    sc.close()

    seeds = tempfile.mkdtemp()
    _write_seed(seeds, "10_locations.sql",
                "INSERT INTO game_locations (key, label, created_by) "
                "VALUES ('town_a', 'Miasto A', 'admin_manual');")

    result = lint_seeds(seeds_dir=seeds, source_schema_db=src)
    assert any("SEED_OWNER" in w and "town_a" in w for w in result["warnings"]), result["warnings"]


# ─── Backward compat: db_lint_service.run_lint nietknięty ────────────────────

def test_run_lint_still_works():
    """U12 run_lint dalej działa niezmieniony (lint_seeds go reużywa, nie podmienia)."""
    from app.services.db_lint_service import run_lint

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()

    result = run_lint(path)
    assert set(result.keys()) >= {"errors", "warnings", "exit_code"}
    assert result["exit_code"] == 0
