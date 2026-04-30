import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.db_runtime import resolve_db_path

# .../backend/scripts/this_file.py -> backend root (works in Docker: /app/scripts -> /app).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PASSWORD_HASH = "demo"


def _config_path() -> Path:
    return Path(os.getenv("AI_TEST_CONFIG_PATH", str(_BACKEND_ROOT / "ai_test_config.json")))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    db_path = resolve_db_path()
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_users_table_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(users)").fetchall()
    return {str(r[1]) for r in rows}


def _ensure_core_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_admin INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            system_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            owner_user_id INTEGER NOT NULL,
            language TEXT NOT NULL DEFAULT 'pl',
            mode TEXT NOT NULL DEFAULT 'solo',
            status TEXT NOT NULL DEFAULT 'active',
            death_reason TEXT,
            ended_at TEXT,
            epitaph TEXT
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL,
            sheet_json TEXT NOT NULL,
            location TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            gold_gp INTEGER NOT NULL DEFAULT 0
        );
        """
    )


def _ensure_user(conn: sqlite3.Connection, username: str, display_name: str, is_admin: int) -> int:
    row = conn.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,)).fetchone()
    if row:
        return int(row["id"])
    cols = _ensure_users_table_columns(conn)
    if {"is_admin", "is_active"}.issubset(cols):
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, is_admin, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (username, DEFAULT_PASSWORD_HASH, display_name, int(is_admin)),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name)
            VALUES (?, ?, ?)
            """,
            (username, DEFAULT_PASSWORD_HASH, display_name),
        )
    return int(cur.lastrowid)


def _ensure_campaign(conn: sqlite3.Connection, owner_user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM campaigns WHERE title = ? ORDER BY id DESC LIMIT 1",
        ("AI Test Campaign",),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO campaigns (title, system_id, model_id, owner_user_id, language, mode, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("AI Test Campaign", "fantasy", "gemma4:e4b", owner_user_id, "pl", "solo", "active"),
    )
    return int(cur.lastrowid)


def _ensure_campaign_member(conn: sqlite3.Connection, campaign_id: int, user_id: int, role: str) -> None:
    exists = conn.execute(
        """
        SELECT id FROM campaign_members WHERE campaign_id = ? AND user_id = ? LIMIT 1
        """,
        (campaign_id, user_id),
    ).fetchone()
    if exists:
        conn.execute("UPDATE campaign_members SET role = ? WHERE id = ?", (role, int(exists["id"])))
        return
    conn.execute(
        """
        INSERT INTO campaign_members (campaign_id, user_id, role)
        VALUES (?, ?, ?)
        """,
        (campaign_id, user_id, role),
    )


def _ensure_character(conn: sqlite3.Connection, campaign_id: int, player_id: int) -> int:
    row = conn.execute(
        """
        SELECT id FROM characters
        WHERE campaign_id = ? AND user_id = ? AND name = ?
        ORDER BY id ASC LIMIT 1
        """,
        (campaign_id, player_id, "TestPlayer"),
    ).fetchone()
    if row:
        return int(row["id"])
    sheet = {
        "archetype": "warrior",
        "current_hp": 10,
        "max_hp": 10,
        "quests_completed": [],
        "quests_active": [],
    }
    cur = conn.execute(
        """
        INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json, location, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (campaign_id, player_id, "TestPlayer", "fantasy", json.dumps(sheet), "Start"),
    )
    return int(cur.lastrowid)


def _write_config(*, player_id: int, character_id: int, campaign_id: int, gm_id: int) -> None:
    payload = {
        "player_id": player_id,
        "character_id": character_id,
        "campaign_id": campaign_id,
        "gm_id": gm_id,
        "player_username": "ai_test_player",
        "gm_username": "ai_test_gm",
        "created_at": _now_iso(),
    }
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def seed() -> dict:
    conn = _connect()
    try:
        conn.execute("BEGIN")
        _ensure_core_tables(conn)
        player_id = _ensure_user(conn, "ai_test_player", "AI Test Player", 0)
        gm_id = _ensure_user(conn, "ai_test_gm", "AI Test GM", 1)
        # Owner must be the test player — UI lists only campaigns owned by logged-in user.
        campaign_id = _ensure_campaign(conn, player_id)
        conn.execute(
            "UPDATE campaigns SET owner_user_id = ? WHERE id = ?",
            (player_id, campaign_id),
        )
        _ensure_campaign_member(conn, campaign_id, player_id, "player")
        _ensure_campaign_member(conn, campaign_id, gm_id, "gm")
        character_id = _ensure_character(conn, campaign_id, player_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _write_config(player_id=player_id, character_id=character_id, campaign_id=campaign_id, gm_id=gm_id)
    return {
        "player_id": player_id,
        "character_id": character_id,
        "campaign_id": campaign_id,
        "gm_id": gm_id,
    }


def main() -> None:
    out = seed()
    print(
        f"SEED OK — player_id={out['player_id']}, character_id={out['character_id']}, "
        f"campaign_id={out['campaign_id']}, gm_id={out['gm_id']}"
    )


if __name__ == "__main__":
    main()
