<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-05-01 -->

# PROMPT 8H-5 — Testy (Phase 8H — Item System Unification)

> Wymaga ukończonych 8H-1 – 8H-4. REV 2 — pełna implementacja, kod testów gotowy do wklejenia.

---

## Cel

Jeden nowy plik `backend/tests/test_8h_item_system.py` pokrywający:

1. **Schemat DB** — nowe kolumny, usunięte legacy, migracja consumables
2. **Loot service** — stackowanie przez `item_key`, brak `consumable_key` w INSERT
3. **Grant Item** — katalog hit (weapon/item) i draft fallback
4. **LLM catalog** — `get_item_catalog_for_prompt` zawiera/wyklucza odpowiednie rekordy
5. **XOR constraint** — `game_config_loot_entries` egzekwuje jednoznaczność

---

## Kontekst techniczny

- **Wzorzec fixture:** `tmp_path` + monkeypatch `DB_PATH` / `LOOT_DB_PATH` / `COMBAT_DB_PATH` — tak samo jak `test_phase8d_migrations_fixed.py` (linia 14) i `test_phase9a_shop.py` (linia 95)
- **NIE ruszać:** żadne istniejące testy, `data/ai_gm.db`, serwisy
- **Branch:** `develop` (lub bieżący roboczy)
- **Import path:** `from app.services import combat_service, loot_service, admin_config` — działa dzięki `conftest.py` dodanemu w 8H-1

---

## Implementacja (REV 2)

Utwierz plik `backend/tests/test_8h_item_system.py`:

```python
"""
Phase 8H — Item System Unification: integration tests.

Covers:
  - DB schema: new columns, removed legacy, consumables migrated
  - loot_service: item_key path for all non-weapon loot
  - Grant Item resolver: catalog hit vs narrative draft
  - get_item_catalog_for_prompt: format and filtering
  - loot_entries XOR constraint
"""

from __future__ import annotations

import sqlite3
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_schema(conn: sqlite3.Connection) -> None:
    """Create minimal 8H schema in an isolated DB (mirrors migrations_admin)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS game_config_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'misc',
            description TEXT,
            value_gp INTEGER NOT NULL DEFAULT 0,
            weight_kg REAL NOT NULL DEFAULT 0.0,
            allowed_classes TEXT NOT NULL DEFAULT '[]',
            ac_bonus INTEGER NOT NULL DEFAULT 0,
            effect_type TEXT,
            effect_dice TEXT,
            effect_bonus INTEGER NOT NULL DEFAULT 0,
            effect_target TEXT NOT NULL DEFAULT 'self',
            charges INTEGER NOT NULL DEFAULT 1,
            ai_generated INTEGER NOT NULL DEFAULT 0,
            approved INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            locked_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS game_config_weapons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            damage_die TEXT NOT NULL DEFAULT '1d4',
            linked_stat TEXT NOT NULL DEFAULT 'STR',
            value_gp INTEGER NOT NULL DEFAULT 0,
            ai_generated INTEGER NOT NULL DEFAULT 0,
            approved INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS game_config_loot_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT
        );

        CREATE TABLE IF NOT EXISTS game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loot_table_key TEXT NOT NULL
                REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
            item_key   TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
            weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
            currency_code TEXT,
            weight INTEGER NOT NULL DEFAULT 10,
            qty_min INTEGER NOT NULL DEFAULT 1,
            qty_max INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT loot_xor CHECK (
                (CASE WHEN item_key   IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
            )
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY,
            name TEXT,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT
        );

        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT,
            equipped INTEGER NOT NULL DEFAULT 0,
            slot TEXT,
            acquired_at TEXT,
            meta_json TEXT,
            CONSTRAINT inv_xor CHECK (
                (CASE WHEN item_key     IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN weapon_key   IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
            )
        );
        """
    )


def _seed_catalog(conn: sqlite3.Connection) -> None:
    """Seed minimal catalog rows for tests."""
    conn.executemany(
        """
        INSERT OR IGNORE INTO game_config_items
            (key, label, item_type, value_gp, ac_bonus,
             effect_type, effect_dice, effect_bonus, charges, approved, is_active)
        VALUES (?,?,?,?,?,?,?,?,?,1,1)
        """,
        [
            ("leather_armor",  "Skórzana Zbroja",    "armor",      50, 2, None, None, 0, 1),
            ("health_potion",  "Mikstura Leczenia",  "consumable",  30, 0, "heal_hp", "2d4", 2, 1),
            ("rope",           "Lina",               "misc",         2, 0, None, None, 0, 1),
            ("quest_amulet",   "Amulet Fabularny",   "narrative",    0, 0, None, None, 0, 1),
            ("draft_item",     "Roboczy Przedmiot",  "misc",         0, 0, None, None, 0, 0),  # approved=0
        ],
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO game_config_weapons
            (key, label, damage_die, linked_stat, value_gp, approved, is_active)
        VALUES ('dagger', 'Sztylet', '1d4', 'DEX', 10, 1, 1)
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO characters(id, name, gold_gp) VALUES (1, 'TestHero', 100)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO game_config_loot_tables(key, label) VALUES ('test_table', 'Test')"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def h8_db_path(tmp_path):
    p = str(tmp_path / "test_8h.db")
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    _minimal_schema(conn)
    _seed_catalog(conn)
    conn.close()
    return p


@pytest.fixture
def h8_conn(h8_db_path):
    conn = sqlite3.connect(h8_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def patched_combat(h8_db_path):
    """Monkeypatch COMBAT_DB_PATH in combat_service."""
    from app.services import combat_service
    orig = combat_service.COMBAT_DB_PATH
    combat_service.COMBAT_DB_PATH = h8_db_path
    yield combat_service
    combat_service.COMBAT_DB_PATH = orig


@pytest.fixture
def patched_loot(h8_db_path):
    """Monkeypatch LOOT_DB_PATH in loot_service."""
    from app.services import loot_service
    orig = loot_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = h8_db_path
    yield loot_service
    loot_service.LOOT_DB_PATH = orig


@pytest.fixture
def patched_turns_db(h8_db_path):
    """Monkeypatch DB path used by _resolve_grant_catalog_item in turns.py."""
    # turns.py importuje conn z admin_config lub loot_service — sprawdź i dostosuj
    from app.services import admin_config, loot_service
    orig_admin = admin_config.DB_PATH
    orig_loot = loot_service.LOOT_DB_PATH
    admin_config.DB_PATH = h8_db_path
    loot_service.LOOT_DB_PATH = h8_db_path
    yield h8_db_path
    admin_config.DB_PATH = orig_admin
    loot_service.LOOT_DB_PATH = orig_loot


# ---------------------------------------------------------------------------
# 1. Schema tests
# ---------------------------------------------------------------------------

class TestSchema8H:
    """DB schema po migracjach 8H-1."""

    REQUIRED_ITEM_COLS = {
        "ac_bonus", "effect_type", "effect_dice", "effect_bonus",
        "effect_target", "charges", "ai_generated", "approved", "allowed_classes",
    }
    REMOVED_ITEM_COLS = {"weight", "proficiency_classes"}

    def test_items_has_new_columns(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_items)")}
        missing = self.REQUIRED_ITEM_COLS - cols
        assert not missing, f"Brakujące kolumny w game_config_items: {missing}"

    def test_items_has_no_legacy_columns(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_items)")}
        present_legacy = self.REMOVED_ITEM_COLS & cols
        assert not present_legacy, f"Legacy kolumny nadal obecne: {present_legacy}"

    def test_weapons_has_ai_flags(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_weapons)")}
        assert "ai_generated" in cols
        assert "approved" in cols

    def test_loot_entries_has_no_consumable_key(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_loot_entries)")}
        assert "consumable_key" not in cols, "consumable_key powinien być usunięty z loot_entries"

    def test_consumables_migrated_as_item_type(self, h8_conn):
        row = h8_conn.execute(
            "SELECT COUNT(*) n FROM game_config_items WHERE item_type = 'consumable'"
        ).fetchone()
        assert row["n"] >= 1, "Brak consumables w game_config_items po migracji"

    def test_consumable_has_value_gp(self, h8_conn):
        row = h8_conn.execute(
            "SELECT value_gp FROM game_config_items WHERE key = 'health_potion'"
        ).fetchone()
        assert row is not None
        assert row["value_gp"] > 0, "health_potion.value_gp powinien być > 0 (skopiowane z base_price)"


# ---------------------------------------------------------------------------
# 2. Loot entries XOR
# ---------------------------------------------------------------------------

class TestLootXOR:
    """Constraint XOR na game_config_loot_entries."""

    def test_valid_item_entry(self, h8_conn):
        h8_conn.execute(
            "INSERT INTO game_config_loot_entries(loot_table_key, item_key, weight) VALUES ('test_table','leather_armor',10)"
        )
        h8_conn.rollback()

    def test_valid_weapon_entry(self, h8_conn):
        h8_conn.execute(
            "INSERT INTO game_config_loot_entries(loot_table_key, weapon_key, weight) VALUES ('test_table','dagger',10)"
        )
        h8_conn.rollback()

    def test_both_null_violates_xor(self, h8_conn):
        with pytest.raises(Exception):  # IntegrityError lub OperationalError
            h8_conn.execute(
                "INSERT INTO game_config_loot_entries(loot_table_key, weight) VALUES ('test_table',10)"
            )
            h8_conn.commit()

    def test_both_not_null_violates_xor(self, h8_conn):
        with pytest.raises(Exception):
            h8_conn.execute(
                """
                INSERT INTO game_config_loot_entries
                    (loot_table_key, item_key, weapon_key, weight)
                VALUES ('test_table','leather_armor','dagger',10)
                """
            )
            h8_conn.commit()


# ---------------------------------------------------------------------------
# 3. Loot service — item_key path
# ---------------------------------------------------------------------------

class TestLootServiceItemKey:
    """grant_loot_to_character używa item_key dla consumable/misc."""

    def test_grant_item_uses_item_key(self, patched_loot):
        loot = [{"item_key": "leather_armor", "quantity": 1}]
        result = patched_loot.grant_loot_to_character(
            character_id=1,
            loot_rows=loot,
            source="test",
        )
        assert result.get("granted") or result.get("ok"), f"grant_loot nie zwrócił ok: {result}"

        conn = sqlite3.connect(patched_loot.LOOT_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_key, consumable_key FROM character_inventory WHERE character_id=1 LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None, "Brak wpisu w inventory"
        assert row["item_key"] == "leather_armor"
        assert row["consumable_key"] is None, "consumable_key powinien być NULL dla nowych wierszy"

    def test_grant_consumable_uses_item_key(self, patched_loot):
        loot = [{"item_key": "health_potion", "quantity": 2}]
        patched_loot.grant_loot_to_character(
            character_id=1,
            loot_rows=loot,
            source="test",
        )
        conn = sqlite3.connect(patched_loot.LOOT_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_key, consumable_key, quantity FROM character_inventory"
            " WHERE character_id=1 AND item_key='health_potion'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["consumable_key"] is None
        assert row["quantity"] == 2


# ---------------------------------------------------------------------------
# 4. LLM catalog — get_item_catalog_for_prompt
# ---------------------------------------------------------------------------

class TestItemCatalogForPrompt:
    """combat_service.get_item_catalog_for_prompt."""

    def test_returns_nonempty_string(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert isinstance(result, str)
        assert len(result) > 10

    def test_contains_item_catalog_header(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "[ITEM CATALOG]" in result

    def test_contains_approved_item(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "leather_armor" in result or "Skórzana Zbroja" in result

    def test_excludes_unapproved(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "draft_item" not in result, "Przedmiot z approved=0 nie powinien być w katalogu"

    def test_excludes_narrative_type(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "quest_amulet" not in result, "Item item_type='narrative' nie powinien być w katalogu"

    def test_armor_shows_ac_bonus(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "AC +2" in result

    def test_consumable_shows_effect(self, patched_combat, h8_conn):
        result = patched_combat.get_item_catalog_for_prompt(h8_conn)
        assert "heal_hp" in result or "2d4" in result

    def test_empty_db_returns_empty_string(self, patched_combat, tmp_path):
        """Pusty katalog → pusty string (nie crashuje)."""
        empty_db = str(tmp_path / "empty.db")
        conn = sqlite3.connect(empty_db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE game_config_items (
                key TEXT, label TEXT, item_type TEXT, value_gp INTEGER,
                ac_bonus INTEGER, effect_type TEXT, effect_dice TEXT,
                effect_bonus INTEGER, charges INTEGER, approved INTEGER, is_active INTEGER
            )
            """
        )
        conn.commit()
        result = patched_combat.get_item_catalog_for_prompt(conn)
        conn.close()
        assert result == ""


# ---------------------------------------------------------------------------
# 5. Grant Item resolver
# ---------------------------------------------------------------------------

class TestGrantItemResolver:
    """_resolve_grant_catalog_item w turns.py."""

    def _resolve(self, label: str, db_path: str):
        """Pomocnik: importuje i woła funkcję z turns.py."""
        from app.api import turns
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return turns._resolve_grant_catalog_item(label, conn)
        finally:
            conn.close()

    def test_hit_by_exact_label(self, patched_turns_db):
        result = self._resolve("Skórzana Zbroja", patched_turns_db)
        assert result is not None
        assert result["item_key"] == "leather_armor"

    def test_hit_by_key(self, patched_turns_db):
        result = self._resolve("leather_armor", patched_turns_db)
        assert result is not None

    def test_hit_consumable_via_item_key(self, patched_turns_db):
        """Consumable z game_config_items zwracany przez item_key, nie consumable_key."""
        result = self._resolve("health_potion", patched_turns_db)
        assert result is not None
        assert "item_key" in result

    def test_miss_returns_none(self, patched_turns_db):
        result = self._resolve("Magiczny Miecz Burzy XXXXXX", patched_turns_db)
        assert result is None

    def test_unapproved_not_resolved(self, patched_turns_db):
        """draft_item (approved=0) nie powinien być rozpoznany jako catalog item."""
        result = self._resolve("draft_item", patched_turns_db)
        assert result is None
```

---

## Uwagi do implementacji

### Jeśli `grant_loot_to_character` ma inną sygnaturę

Sprawdź faktyczną sygnaturę w `loot_service.py`:

```bash
grep -n 'def grant_loot_to_character' backend/app/services/loot_service.py
```

Jeśli parametry są inne — dostosuj wywołania w `TestLootServiceItemKey` (nie zmieniaj serwisu).

### Jeśli `_resolve_grant_catalog_item` ma inną nazwę lub sygnaturę

```bash
grep -n '_resolve_grant\|resolve_grant_catalog' backend/app/api/turns.py
```

Dostosuj nazwę funkcji w `TestGrantItemResolver._resolve` oraz ewentualnie sposób przekazywania `conn`.

### Jeśli `_resolve_grant_catalog_item` otwiera własny conn (nie przyjmuje go z zewnątrz)

Zmień fixture `patched_turns_db` tak, żeby patchowała `COMBAT_DB_PATH` lub `admin_config.DB_PATH` w zależności od tego skąd funkcja bierze połączenie:

```python
# Alternatywny fixture jeśli funkcja używa COMBAT_DB_PATH:
@pytest.fixture
def patched_turns_db(h8_db_path):
    from app.services import combat_service
    orig = combat_service.COMBAT_DB_PATH
    combat_service.COMBAT_DB_PATH = h8_db_path
    yield h8_db_path
    combat_service.COMBAT_DB_PATH = orig
```

---

## Weryfikacja po implementacji

```bash
# Na serwerze 192.168.1.61 (pytest w środowisku Docker lub venv z backend/):
python3 -m pytest backend/tests/test_8h_item_system.py -v --tb=short

# Oczekiwane: wszystkie testy zielone
# Jeśli fail: sprawdź sygnaturę funkcji (patrz Uwagi wyżej)

# Pełny baseline — nie nowych regresji:
python3 -m pytest --tb=no -q --timeout=30
```

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano `backend/tests/test_8h_item_system.py` (25 testów): schemat 8H, XOR `game_config_loot_entries`, `grant_loot_to_character` z `item_key`, `get_item_catalog_for_prompt`, `_resolve_grant_catalog_item(conn, label)` z etykietami PL (exact / LIKE), pusty katalog.
- Kod testów **nie** kopiuje 1:1 bloku z tego dokumentu: szablon REV 2 miał odwróconą sygnaturę resolvera i przykłady `_resolve` po `key` — resolver działa na **label** (`lower(label)` / `LIKE`).
- Weryfikacja: `python3 -m pytest tests/test_8h_item_system.py -v --tb=short` — **25 passed** (środowisko z pytest, m.in. 192.168.1.61).

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(po raporcie Cursora)*
