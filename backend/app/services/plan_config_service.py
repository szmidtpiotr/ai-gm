"""BUG-04: GM plan auto-update configuration stored in game_config_meta."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from app.core.db_runtime import resolve_db_path

DB_PATH = Path(resolve_db_path())

_KEY_FORCE_UPDATE_TURNS = "gm_plan_force_update_turns"

_DEFAULTS: dict[str, int] = {
    "force_update_turns": 25,
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get_plan_config() -> dict[str, int]:
    """Returns plan update config from game_config_meta."""
    cfg = dict(_DEFAULTS)
    try:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT value FROM game_config_meta WHERE key = ?",
                (_KEY_FORCE_UPDATE_TURNS,),
            ).fetchone()
            if row:
                cfg["force_update_turns"] = int(row["value"])
        finally:
            conn.close()
    except Exception:
        pass
    return cfg


def set_plan_config(*, force_update_turns: int) -> dict[str, int]:
    """Update plan config. force_update_turns must be 5–200."""
    if not (5 <= int(force_update_turns) <= 200):
        raise ValueError("force_update_turns must be 5–200")
    val = int(force_update_turns)
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
            (_KEY_FORCE_UPDATE_TURNS, str(val)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"force_update_turns": val}
