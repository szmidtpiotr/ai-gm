import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.migrations_admin import _ensure_location_integrity_schema
from app.api import turns as turns_api
from app.services import location_integrity_config as lic
from app.services import location_integrity_service as lis
from app.services import location_intent_parser as lip
from app.services import location_validator as lv


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


def _setup_phase8d_db(uri: str) -> sqlite3.Connection:
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT
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
    conn.execute(
        """
        CREATE TABLE game_locations (
            id            INTEGER PRIMARY KEY,
            key           TEXT UNIQUE NOT NULL,
            label         TEXT NOT NULL,
            description   TEXT,
            parent_id     INTEGER REFERENCES game_locations(id),
            location_type TEXT DEFAULT 'macro' CHECK(location_type IN ('macro', 'sub')),
            rules         TEXT,
            enemy_keys    TEXT DEFAULT '[]',
            npc_keys      TEXT DEFAULT '[]',
            is_active     INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE location_integrity_log (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            attempted_move TEXT NOT NULL,
            current_location_key TEXT,
            reason_blocked TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value) VALUES
        ('location_integrity_enabled', '1'),
        ('location_parser_json_enabled', '1'),
        ('location_parser_fallback_enabled', '1')
        """
    )
    conn.execute(
        """
        INSERT INTO campaigns (id, title, current_location_id, session_flags)
        VALUES (1, 'Phase8D test', 2, '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO game_locations (id, key, label, parent_id, location_type, rules, enemy_keys, npc_keys, is_active)
        VALUES
          (1, 'city_varen', 'Miasto Varen', NULL, 'macro', '{}', '[]', '[]', 1),
          (2, 'tavern_hanged_man', 'Karczma Pod Wisielcem', 1, 'sub', '{}', '[]', '[]', 1),
          (3, 'market_square', 'Rynek', 1, 'sub', '{}', '[]', '[]', 1),
          (4, 'forest_black', 'Las Czarny', NULL, 'macro', '{}', '[]', '[]', 1)
        """
    )
    conn.commit()
    return conn


def _current_location_key(conn: sqlite3.Connection, campaign_id: int = 1) -> str | None:
    row = conn.execute(
        """
        SELECT gl.key
        FROM campaigns c
        JOIN game_locations gl ON gl.id = c.current_location_id
        WHERE c.id = ?
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    return None if not row else str(row["key"])


def _log_count(conn: sqlite3.Connection, campaign_id: int = 1) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM location_integrity_log WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    return int(row["n"] or 0)


def _patch_db_paths(monkeypatch, uri: str) -> None:
    monkeypatch.setattr(lv, "DB_PATH", uri)
    monkeypatch.setattr(lis, "DB_PATH", uri)
    monkeypatch.setattr(lic, "DB_PATH", uri)


def _disable_llm_calls(monkeypatch) -> None:
    monkeypatch.setattr(lip, "generate_chat", lambda **kwargs: (_ for _ in ()).throw(AssertionError("LLM call in test")))
    monkeypatch.setattr(lv, "generate_chat", lambda **kwargs: (_ for _ in ()).throw(AssertionError("LLM call in test")))


def test_8d20_block_teleportation_and_log_violation(monkeypatch):
    uri = "file:phase8d_20?mode=memory&cache=shared"
    keeper = _setup_phase8d_db(uri)
    try:
        _patch_db_paths(monkeypatch, uri)
        _disable_llm_calls(monkeypatch)
        before_key = _current_location_key(keeper)
        before_logs = _log_count(keeper)
        gm_response = (
            '{"location_intent":{"action":"move","target_label":"Las Czarny","target_key":"forest_black"}}'
        )
        turns_api._apply_location_integrity_from_response(
            conn=keeper,
            campaign_id=1,
            character_id=7,
            gm_response=gm_response,
            llm_config=None,
        )
        assert _current_location_key(keeper) == before_key == "tavern_hanged_man"
        assert _log_count(keeper) == before_logs + 1
        row = keeper.execute(
            """
            SELECT reason_blocked
            FROM location_integrity_log
            WHERE campaign_id = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row["reason_blocked"] == "travel_required"
    finally:
        keeper.close()


def test_8d21_allow_sub_to_sub_same_parent_without_new_log(monkeypatch):
    uri = "file:phase8d_21?mode=memory&cache=shared"
    keeper = _setup_phase8d_db(uri)
    try:
        _patch_db_paths(monkeypatch, uri)
        _disable_llm_calls(monkeypatch)
        before_logs = _log_count(keeper)
        gm_response = (
            '{"location_intent":{"action":"move","target_label":"Rynek","target_key":"market_square"}}'
        )
        turns_api._apply_location_integrity_from_response(
            conn=keeper,
            campaign_id=1,
            character_id=7,
            gm_response=gm_response,
            llm_config=None,
        )
        assert _current_location_key(keeper) == "market_square"
        assert _log_count(keeper) == before_logs
    finally:
        keeper.close()


def test_8d22_flag_disabled_skips_block_and_updates_location(monkeypatch):
    uri = "file:phase8d_22?mode=memory&cache=shared"
    keeper = _setup_phase8d_db(uri)
    try:
        keeper.execute(
            "UPDATE campaigns SET session_flags = ? WHERE id = 1",
            ('{"location_integrity_enabled": 0}',),
        )
        keeper.commit()
        _patch_db_paths(monkeypatch, uri)
        _disable_llm_calls(monkeypatch)
        before_logs = _log_count(keeper)
        gm_response = (
            '{"location_intent":{"action":"move","target_label":"Las Czarny","target_key":"forest_black"}}'
        )
        turns_api._apply_location_integrity_from_response(
            conn=keeper,
            campaign_id=1,
            character_id=7,
            gm_response=gm_response,
            llm_config=None,
        )
        assert _current_location_key(keeper) == "forest_black"
        assert _log_count(keeper) == before_logs
    finally:
        keeper.close()


def test_8d23a_create_new_location_and_move_session(monkeypatch):
    uri = "file:phase8d_23a?mode=memory&cache=shared"
    keeper = _setup_phase8d_db(uri)
    try:
        _patch_db_paths(monkeypatch, uri)
        _disable_llm_calls(monkeypatch)
        gm_response = (
            '{"location_intent":{"action":"create","target_label":"Grota za Wodospadem"}}'
        )
        turns_api._apply_location_integrity_from_response(
            conn=keeper,
            campaign_id=1,
            character_id=7,
            gm_response=gm_response,
            llm_config=None,
        )
        row = keeper.execute(
            "SELECT id, key FROM game_locations WHERE label = ? LIMIT 1",
            ("Grota za Wodospadem",),
        ).fetchone()
        assert row is not None
        assert row["key"] == "grota_za_wodospadem"
        assert _current_location_key(keeper) == "grota_za_wodospadem"
    finally:
        keeper.close()


def test_8d23b_fuzzy_match_reuses_existing_location(monkeypatch):
    uri = "file:phase8d_23b?mode=memory&cache=shared"
    keeper = _setup_phase8d_db(uri)
    try:
        _patch_db_paths(monkeypatch, uri)
        _disable_llm_calls(monkeypatch)
        before_count = int(
            keeper.execute("SELECT COUNT(*) AS n FROM game_locations").fetchone()["n"] or 0
        )
        gm_response = (
            '{"location_intent":{"action":"create","target_label":"karczma pod wisielcem"}}'
        )
        turns_api._apply_location_integrity_from_response(
            conn=keeper,
            campaign_id=1,
            character_id=7,
            gm_response=gm_response,
            llm_config=None,
        )
        after_count = int(
            keeper.execute("SELECT COUNT(*) AS n FROM game_locations").fetchone()["n"] or 0
        )
        assert after_count == before_count
        assert _current_location_key(keeper) == "tavern_hanged_man"
    finally:
        keeper.close()
