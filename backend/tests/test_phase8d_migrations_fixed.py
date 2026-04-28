"""Phase 8D — Location Integrity: Fixed migration tests using tmp_path for isolated SQLite DB.

Tests 8D-1 to 8D-4: Database migrations for location integrity feature.
Uses pytest tmp_path fixture for proper test isolation.
"""

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def fresh_db_path(tmp_path):
    """Fixture providing isolated database file path using pytest tmp_path."""
    db_file = tmp_path / "test_migrations.db"
    return str(db_file)


@pytest.fixture
def migrations_module(fresh_db_path):
    """Fixture providing migrations module with mocked DB_PATH."""
    # Import fresh to avoid cached DB_PATH
    from app import migrations_admin

    # Store original and mock the path
    original_path = migrations_admin.DB_PATH
    migrations_admin.DB_PATH = fresh_db_path

    yield migrations_admin

    # Restore original path
    migrations_admin.DB_PATH = original_path


@pytest.fixture
def db_connection(fresh_db_path, migrations_module):
    """Fixture providing DB connection after migrations are run."""
    # Run migrations on isolated database
    migrations_module.run_admin_migrations()

    conn = sqlite3.connect(fresh_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestGameLocationsTable:
    """8D-1: Tabela game_locations musi być utworzona przez migracje."""

    def test_table_exists(self, db_connection):
        """Tabela game_locations musi istnieć w schemacie."""
        row = db_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_locations'"
        ).fetchone()
        assert row is not None, "Tabela game_locations nie istnieje"

    def test_required_columns_exist(self, db_connection):
        """Wszystkie wymagane kolumny muszą istnieć w tabeli."""
        cur = db_connection.execute("PRAGMA table_info(game_locations)")
        columns = {row[1] for row in cur.fetchall()}

        required = {
            "id", "key", "label", "description", "parent_id",
            "location_type", "rules", "enemy_keys", "npc_keys",
            "is_active", "created_at", "updated_at"
        }

        missing = required - columns
        assert not missing, f"Brakujące kolumny: {missing}"

    def test_key_unique_constraint(self, db_connection):
        """Kolumna key musi być UNIQUE (tworzy autoindex)."""
        cur = db_connection.execute("PRAGMA index_list(game_locations)").fetchall()
        index_names = {row[1] for row in cur}

        # sqlite_autoindex_game_locations_1 tworzy się automatycznie dla UNIQUE
        has_unique_index = any("game_locations" in name for name in index_names)
        assert has_unique_index, "Brak unikalnego indeksu na kolumnie key"

    def test_parent_id_foreign_key(self, db_connection):
        """parent_id musi mieć FK do game_locations(id)."""
        cur = db_connection.execute("PRAGMA foreign_key_list(game_locations)").fetchall()
        fks = {row[3] for row in cur}  # column name

        assert "parent_id" in fks, "Brak FK na kolumnie parent_id"

    def test_location_type_check_constraint(self, db_connection):
        """location_type ma CHECK constraint (macro, sub)."""
        # Próba wstawienia niedozwolonej wartości
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute(
                "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
                ("test_loc", "Test", "invalid_type")
            )

    def test_is_active_default(self, db_connection):
        """is_active domyślnie = 1."""
        db_connection.execute(
            "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
            ("active_test", "Active Test", "macro")
        )
        db_connection.commit()

        row = db_connection.execute(
            "SELECT is_active FROM game_locations WHERE key = ?",
            ("active_test",)
        ).fetchone()

        assert row["is_active"] == 1, "Domyślna wartość is_active powinna być 1"


class TestGameSessionsColumns:
    """8D-2 i 8D-3: Nowe kolumny w tabeli game_sessions."""

    def test_current_location_id_column_exists(self, db_connection):
        """Kolumna current_location_id musi istnieć."""
        cur = db_connection.execute("PRAGMA table_info(game_sessions)")
        columns = {row[1] for row in cur.fetchall()}

        assert "current_location_id" in columns, "Brak kolumny current_location_id"

    def test_session_flags_column_exists(self, db_connection):
        """Kolumna session_flags musi istnieć."""
        cur = db_connection.execute("PRAGMA table_info(game_sessions)")
        columns = {row[1] for row in cur.fetchall()}

        assert "session_flags" in columns, "Brak kolumny session_flags"

    def test_current_location_id_foreign_key(self, db_connection):
        """current_location_id ma FK do game_locations(id)."""
        cur = db_connection.execute("PRAGMA foreign_key_list(game_sessions)").fetchall()
        fk_targets = {(row[2], row[3], row[4]) for row in cur}  # table, from, to

        expected = ("game_locations", "current_location_id", "id")
        assert expected in fk_targets, f"Brak FK: {expected}"


class TestGameConfigMetaFlags:
    """8D-3: Flagi Location Integrity w game_config_meta."""

    def test_meta_flags_exist(self, db_connection):
        """Trzy domyślne flagi muszą istnieć po migracjach."""
        cur = db_connection.execute(
            "SELECT key, value FROM game_config_meta WHERE key LIKE 'location_%'"
        )
        flags = {row[0]: row[1] for row in cur.fetchall()}

        assert "location_integrity_enabled" in flags, "Brak flagi location_integrity_enabled"
        assert "location_parser_json_enabled" in flags, "Brak flagi location_parser_json_enabled"
        assert "location_parser_fallback_enabled" in flags, "Brak flagi location_parser_fallback_enabled"

    def test_meta_flags_default_values(self, db_connection):
        """Domyślne wartości flag to '1' (włączone)."""
        cur = db_connection.execute(
            "SELECT key, value FROM game_config_meta WHERE key LIKE 'location_%'"
        )
        flags = {row[0]: row[1] for row in cur.fetchall()}

        for key, value in flags.items():
            assert value == "1", f"Flaga {key} powinna mieć wartość '1', ma '{value}'"

    def test_game_config_meta_updated_at_exists(self, db_connection):
        """Kolumna updated_at musi istnieć w game_config_meta."""
        cur = db_connection.execute("PRAGMA table_info(game_config_meta)")
        columns = {row[1] for row in cur.fetchall()}

        assert "updated_at" in columns, "Brak kolumny updated_at w game_config_meta"


class TestLocationIntegrityLog:
    """8D-4: Tabela location_integrity_log."""

    def test_table_exists(self, db_connection):
        """Tabela location_integrity_log musi istnieć."""
        row = db_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='location_integrity_log'"
        ).fetchone()

        assert row is not None, "Tabela location_integrity_log nie istnieje"

    def test_required_columns_exist(self, db_connection):
        """Wszystkie wymagane kolumny muszą istnieć."""
        cur = db_connection.execute("PRAGMA table_info(location_integrity_log)")
        columns = {row[1] for row in cur.fetchall()}

        required = {
            "id", "session_id", "character_id", "attempted_move",
            "current_location_key", "reason_blocked", "created_at"
        }

        missing = required - columns
        assert not missing, f"Brakujące kolumny w logu: {missing}"

    def test_session_id_foreign_key(self, db_connection):
        """session_id ma FK do game_sessions(id)."""
        cur = db_connection.execute("PRAGMA foreign_key_list(location_integrity_log)").fetchall()
        fk_targets = {(row[2], row[3], row[4]) for row in cur}

        expected = ("game_sessions", "session_id", "id")
        assert expected in fk_targets, f"Brak FK w logu: {expected}"

    def test_index_exists(self, db_connection):
        """Indeks na session_id + created_at musi istnieć."""
        row = db_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_location_integrity_log_session'"
        ).fetchone()

        assert row is not None, "Brak indeksu idx_location_integrity_log_session"


class TestIntegration:
    """Testy integracyjne: pełny flow Location Integrity z izolacją."""

    def test_insert_location_and_verify_structure(self, db_connection):
        """Można wstawić lokalizację i zweryfikować strukturę."""
        # Wstaw makro-lokalizację
        cur = db_connection.execute(
            """INSERT INTO game_locations
                (key, label, description, location_type, rules, enemy_keys, npc_keys)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("test_tavern", "Karczma Testowa", "Opis testowy", "macro",
             '{"no_combat": true}', '["rat"]', '["innkeeper"]')
        )
        loc_id = cur.lastrowid
        db_connection.commit()

        # Weryfikacja
        row = db_connection.execute(
            "SELECT * FROM game_locations WHERE id = ?",
            (loc_id,)
        ).fetchone()

        assert row is not None
        assert row["key"] == "test_tavern"
        assert row["label"] == "Karczma Testowa"
        assert row["location_type"] == "macro"

    def test_parent_child_relationship(self, db_connection):
        """Można tworzyć relacje parent-child między lokalizacjami."""
        # Wstaw parent (macro)
        parent_cur = db_connection.execute(
            "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
            ("parent_city", "Test City", "macro")
        )
        parent_id = parent_cur.lastrowid

        # Wstaw child (sub)
        child_cur = db_connection.execute(
            "INSERT INTO game_locations (key, label, location_type, parent_id) VALUES (?, ?, ?, ?)",
            ("child_tavern", "Test Tavern", "sub", parent_id)
        )
        child_id = child_cur.lastrowid
        db_connection.commit()

        # Weryfikacja relacji
        child_row = db_connection.execute(
            "SELECT * FROM game_locations WHERE id = ?",
            (child_id,)
        ).fetchone()

        assert child_row["parent_id"] == parent_id

    def test_log_blocked_move_entry(self, db_connection):
        """Można zapisać log blokady zmiany lokalizacji."""
        # Wstaw log blokady (bez pełnego FK - test struktury)
        db_connection.execute(
            """INSERT INTO location_integrity_log
                (session_id, character_id, attempted_move, current_location_key, reason_blocked)
            VALUES (?, ?, ?, ?, ?)""",
            (999, 123, "Las Mroczny", "forest_test", "Brak fabularnego uzasadnienia")
        )
        db_connection.commit()

        # Weryfikacja
        row = db_connection.execute(
            "SELECT * FROM location_integrity_log WHERE session_id = ?",
            (999,)
        ).fetchone()

        assert row is not None
        assert row["attempted_move"] == "Las Mroczny"
        assert row["current_location_key"] == "forest_test"
        assert row["reason_blocked"] == "Brak fabularnego uzasadnienia"
        assert row["character_id"] == 123


class TestTmpPathIsolation:
    """Weryfikacja izolacji bazy danych między testami."""

    def test_isolated_database_per_test(self, fresh_db_path, migrations_module):
        """Każdy test dostaje izolowaną bazę danych."""
        # Uruchom migracje
        migrations_module.run_admin_migrations()

        # Połącz się z bazą
        conn = sqlite3.connect(fresh_db_path)
        conn.row_factory = sqlite3.Row

        # Dodaj testowe dane
        conn.execute(
            "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
            ("isolation_test", "Isolation Test", "macro")
        )
        conn.commit()

        # Weryfikacja - dane istnieją
        row = conn.execute(
            "SELECT 1 FROM game_locations WHERE key = ?",
            ("isolation_test",)
        ).fetchone()

        assert row is not None
        conn.close()

        # Sprawdź że plik istnieje w tmp_path
        assert os.path.exists(fresh_db_path)
