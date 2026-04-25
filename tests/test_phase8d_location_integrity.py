import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.migrations_admin import _ensure_location_integrity_schema


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_phase8d_location_integrity_schema_migration_in_memory():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE game_config_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()

        _ensure_location_integrity_schema(conn)
        # idempotence
        _ensure_location_integrity_schema(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "game_locations" in tables
        assert "location_integrity_log" in tables

        game_locations_cols = _cols(conn, "game_locations")
        assert {
            "id",
            "key",
            "label",
            "description",
            "parent_id",
            "location_type",
            "rules",
            "enemy_keys",
            "npc_keys",
            "is_active",
            "created_at",
            "updated_at",
        }.issubset(game_locations_cols)

        campaign_cols = _cols(conn, "campaigns")
        assert "current_location_id" in campaign_cols
        assert "session_flags" in campaign_cols

        flags = dict(conn.execute("SELECT key, value FROM game_config_meta").fetchall())
        assert flags.get("location_integrity_enabled") == "1"
        assert flags.get("location_parser_json_enabled") == "1"
        assert flags.get("location_parser_fallback_enabled") == "1"
    finally:
        conn.close()
