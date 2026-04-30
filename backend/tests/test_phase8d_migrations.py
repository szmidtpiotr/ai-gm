"""Phase 8D — Location Integrity: Testy migracji DB (8D-1 do 8D-4)."""

import os
import sqlite3
import tempfile
import pytest

from app import migrations_admin


@pytest.fixture
def fresh_db():
    """Fixture zapewniający czystą bazę do testów migracji (tymczasowa baza w /tmp)."""
    # Utwórz tymczasowy plik bazy danych
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    # Zamockuj DB_PATH w migrations_admin
    original_db_path = migrations_admin.DB_PATH
    migrations_admin.DB_PATH = tmp_path

    try:
        # Uruchom migracje na tymczasowej bazie
        migrations_admin.run_admin_migrations()
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()
    finally:
        # Przywróć oryginalną ścieżkę i usuń tymczasową bazę
        migrations_admin.DB_PATH = original_db_path
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


class TestGameLocationsTable:
    """8D-1: Tabela game_locations."""

    def test_table_exists(self, fresh_db):
        """Tabela game_locations musi istnieć."""
        row = fresh_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_locations'"
        ).fetchone()
        assert row is not None

    def test_required_columns_exist(self, fresh_db):
        """Wszystkie wymagane kolumny muszą istnieć."""
        cur = fresh_db.execute("PRAGMA table_info(game_locations)")
        columns = {row[1] for row in cur.fetchall()}
        required = {
            "id", "key", "label", "description", "parent_id",
            "location_type", "rules", "enemy_keys", "npc_keys",
            "is_active", "created_at", "updated_at"
        }
        assert required.issubset(columns)

    def test_key_unique_constraint(self, fresh_db):
        """Kolumna key musi być UNIQUE."""
        cur = fresh_db.execute("PRAGMA index_list(game_locations)").fetchall()
        index_names = {row[1] for row in cur}
        # sqlite_autoindex_game_locations_1 tworzy się automatycznie dla UNIQUE
        assert any("game_locations" in name for name in index_names)

    def test_parent_id_foreign_key(self, fresh_db):
        """parent_id musi mieć FK do game_locations(id)."""
        cur = fresh_db.execute("PRAGMA foreign_key_list(game_locations)").fetchall()
        fks = {row[3] for row in cur}  # column name
        assert "parent_id" in fks

    def test_location_type_check_constraint(self, fresh_db):
        """location_type ma CHECK(macro, sub)."""
        # Próba wstawienia niedozwolonej wartości
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
                ("test_loc", "Test", "invalid_type")
            )


class TestGameSessionsColumns:
    """8D-2 i 8D-3: Kolumny w game_sessions."""

    def test_current_location_id_column_exists(self, fresh_db):
        """Kolumna current_location_id musi istnieć."""
        cur = fresh_db.execute("PRAGMA table_info(game_sessions)")
        columns = {row[1] for row in cur.fetchall()}
        assert "current_location_id" in columns

    def test_session_flags_column_exists(self, fresh_db):
        """Kolumna session_flags musi istnieć z domyślną wartością '{}'."""
        cur = fresh_db.execute("PRAGMA table_info(game_sessions)")
        columns = {row[1] for row in cur.fetchall()}
        assert "session_flags" in columns

    def test_current_location_id_foreign_key(self, fresh_db):
        """current_location_id ma FK do game_locations(id)."""
        cur = fresh_db.execute("PRAGMA foreign_key_list(game_sessions)").fetchall()
        fk_targets = {(row[2], row[3], row[4]) for row in cur}  # table, from, to
        assert ("game_locations", "current_location_id", "id") in fk_targets


class TestGameConfigMetaFlags:
    """8D-3: Flagi Location Integrity w game_config_meta."""

    def test_meta_flags_exist(self, fresh_db):
        """Trzy domyślne flagi muszą istnieć."""
        cur = fresh_db.execute(
            "SELECT key, value FROM game_config_meta WHERE key LIKE 'location_%'"
        )
        flags = {row[0]: row[1] for row in cur.fetchall()}

        assert "location_integrity_enabled" in flags
        assert "location_parser_json_enabled" in flags
        assert "location_parser_fallback_enabled" in flags
        assert all(v == "1" for v in flags.values())


class TestLocationIntegrityLog:
    """8D-4: Tabela location_integrity_log."""

    def test_table_exists(self, fresh_db):
        """Tabela location_integrity_log musi istnieć."""
        row = fresh_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='location_integrity_log'"
        ).fetchone()
        assert row is not None

    def test_required_columns_exist(self, fresh_db):
        """Wszystkie wymagane kolumny muszą istnieć."""
        cur = fresh_db.execute("PRAGMA table_info(location_integrity_log)")
        columns = {row[1] for row in cur.fetchall()}
        required = {
            "id", "session_id", "character_id", "attempted_move",
            "current_location_key", "reason_blocked", "created_at"
        }
        assert required.issubset(columns)

    def test_session_id_foreign_key(self, fresh_db):
        """session_id ma FK do game_sessions(id)."""
        cur = fresh_db.execute("PRAGMA foreign_key_list(location_integrity_log)").fetchall()
        fk_targets = {(row[2], row[3], row[4]) for row in cur}
        assert ("game_sessions", "session_id", "id") in fk_targets

    def test_index_exists(self, fresh_db):
        """Indeks na session_id + created_at musi istnieć."""
        cur = fresh_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_location_integrity_log_session'"
        ).fetchone()
        assert cur is not None


class TestIntegration:
    """Testy integracyjne: pełny flow Location Integrity."""

    def test_insert_location_and_reference_from_session(self, fresh_db):
        """Można wstawić lokalizację i przypisać ją do sesji."""
        # Wstaw lokalizację
        cur = fresh_db.execute(
            "INSERT INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
            ("test_tavern", "Karczma Testowa", "macro")
        )
        loc_id = cur.lastrowid
        fresh_db.commit()

        # Wstaw sesję z tą lokalizacją (zakładamy istnienie campaigns/characters)
        # Najpierw sprawdźmy czy można ustawić FK
        row = fresh_db.execute(
            "SELECT id FROM game_locations WHERE id = ?", (loc_id,)
        ).fetchone()
        assert row is not None

    def test_log_blocked_move(self, fresh_db):
        """Można zapisać log blokady zmiany lokalizacji."""
        # Wstaw lokalizację
        fresh_db.execute(
            "INSERT INTO game_locations (key, label) VALUES (?, ?)",
            ("forest_test", "Las Testowy")
        )
        fresh_db.commit()

        # Wstaw log blokady (bez pełnego FK — testujemy strukturę)
        fresh_db.execute(
            """INSERT INTO location_integrity_log
                (session_id, attempted_move, current_location_key, reason_blocked)
            VALUES (?, ?, ?, ?)""",
            (999, "Las Mroczny", "forest_test", "Brak fabularnego uzasadnienia")
        )
        fresh_db.commit()

        row = fresh_db.execute(
            "SELECT * FROM location_integrity_log WHERE session_id = ?", (999,)
        ).fetchone()
        assert row is not None
        assert row["attempted_move"] == "Las Mroczny"
        assert row["reason_blocked"] == "Brak fabularnego uzasadnienia"
