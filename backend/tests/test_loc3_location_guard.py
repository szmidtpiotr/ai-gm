"""LOC-3: Backend guard dla location_intent (graf sesji vs target_key, fallback parent przy create)."""

import sqlite3
from pathlib import Path

import pytest

from app.services.location_intent_parser import LocationIntent
from app.services import location_validator as lv
from app.services import location_context_injector as lci
import app.services.location_config_service as lc


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE game_locations (
          id INTEGER PRIMARY KEY,
          key TEXT NOT NULL UNIQUE,
          label TEXT NOT NULL,
          parent_id INTEGER REFERENCES game_locations(id),
          location_type TEXT DEFAULT 'macro',
          is_active INTEGER DEFAULT 1,
          approved INTEGER DEFAULT 1,
          ai_generated INTEGER DEFAULT 0,
          description TEXT,
          npc_keys TEXT DEFAULT '[]'
        );
        CREATE TABLE game_sessions (
          id TEXT PRIMARY KEY,
          campaign_id INTEGER,
          current_location_id INTEGER REFERENCES game_locations(id),
          session_flags TEXT DEFAULT '{}',
          created_at TEXT DEFAULT 'now'
        );
        CREATE TABLE location_integrity_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL,
          character_id INTEGER,
          attempted_move TEXT NOT NULL,
          current_location_key TEXT,
          reason_blocked TEXT,
          created_at TEXT DEFAULT 'now'
        );
        CREATE TABLE game_config_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT DEFAULT '1970-01-01T00:00:00Z'
        );
        """
    )


@pytest.fixture
def loc3_db(monkeypatch, tmp_path: Path):
    db_path = str(tmp_path / "loc3.sqlite")
    monkeypatch.setattr(lv, "DB_PATH", db_path)
    monkeypatch.setattr(lci, "DB_PATH", db_path)
    monkeypatch.setattr(lc, "DB_PATH", db_path)
    monkeypatch.setattr("app.migrations_admin.DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _schema(conn)
    conn.executemany(
        "INSERT INTO game_config_meta (key, value) VALUES (?, ?)",
        [("location_integrity_enabled", "1"), ("location_auto_create_enabled", "0")],
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_id, approved)"
        " VALUES (1, 'square', 'Rynek', 'macro', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_id, approved)"
        " VALUES (2, 'tavern', 'Karczma', 'sub', 1, 1)"
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_id, approved)"
        " VALUES (99, 'elsewhere', 'Dalekie', 'macro', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id)"
        " VALUES ('s1', 1, 2)"
    )
    conn.commit()
    conn.close()
    yield db_path


@pytest.mark.usefixtures("loc3_db")
class TestLoc3Guard:
    def test_move_target_key_not_in_graph_is_blocked(self, loc3_db):
        intent = LocationIntent(
            action="move",
            target_label="Las",
            target_key="dark_forest",
        )
        r = lv.validate_move("s1", intent, campaign_id=1)
        assert r.allowed is False
        assert r.block_reason == "target_key_not_in_session_graph"

        cx = sqlite3.connect(loc3_db)
        log = cx.execute(
            "SELECT reason_blocked FROM location_integrity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        cx.close()
        assert log is not None
        assert log[0] == "target_key_not_in_session_graph"

    def test_move_target_key_square_in_graph_proceeds(self, loc3_db):
        intent = LocationIntent(
            action="move",
            target_label="Rynek",
            target_key="square",
        )
        r = lv.validate_move("s1", intent, campaign_id=1)
        assert r.allowed is True
        assert r.resolved_location_id == 1

    def test_move_without_current_location_fail_open_unknown_key(self, loc3_db):
        cx = sqlite3.connect(loc3_db)
        cx.execute("UPDATE game_sessions SET current_location_id = NULL WHERE id = 's1'")
        cx.commit()
        cx.close()

        intent = LocationIntent(
            action="move",
            target_label="Dalekie",
            target_key="elsewhere",
        )
        r = lv.validate_move("s1", intent, campaign_id=1)
        assert r.allowed is True
        assert r.resolved_location_id == 99

    def test_create_unknown_parent_fallback_to_current(self, loc3_db):
        intent = LocationIntent(
            action="create",
            target_label="Nowa kryjówka",
            parent_key="no_such_parent",
            description="x",
        )
        r = lv.validate_move("s1", intent, campaign_id=1, auto_create_enabled=True)
        assert intent.parent_key == "tavern"
        assert r.allowed is True
