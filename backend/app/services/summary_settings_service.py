"""Shared runtime settings for history summary / dual preview."""

from __future__ import annotations

import sqlite3

from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

META_KEY_SUMMARY_ROLLUP_COOLDOWN = "summary_rollup_cooldown_turns"
DEFAULT_SUMMARY_ROLLUP_COOLDOWN_TURNS = 20

META_KEY_DUAL_SUMMARY_PREVIEW_MODE = "dual_summary_preview_mode"
DEFAULT_DUAL_SUMMARY_PREVIEW_MODE = "owner_admin"
ALLOWED_DUAL_SUMMARY_PREVIEW_MODES = frozenset({"owner", "owner_admin", "off"})


def normalize_dual_summary_preview_mode(raw: object) -> str:
    mode = str(raw or "").strip().lower()
    if mode in ALLOWED_DUAL_SUMMARY_PREVIEW_MODES:
        return mode
    return DEFAULT_DUAL_SUMMARY_PREVIEW_MODE


def get_summary_rollup_cooldown_turns(conn: sqlite3.Connection) -> int:
    """Minimal spacing between rollup LLM runs per campaign, in narrative turns."""
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (META_KEY_SUMMARY_ROLLUP_COOLDOWN,),
        ).fetchone()
        if row:
            raw_val = row["value"] if hasattr(row, "keys") else row[0]
            if raw_val is not None:
                n = int(str(raw_val).strip())
                return max(1, min(500, n))
    except (sqlite3.OperationalError, ValueError, TypeError):
        pass
    return DEFAULT_SUMMARY_ROLLUP_COOLDOWN_TURNS


def get_dual_summary_preview_mode(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (META_KEY_DUAL_SUMMARY_PREVIEW_MODE,),
        ).fetchone()
        if row:
            raw_val = row["value"] if hasattr(row, "keys") else row[0]
            return normalize_dual_summary_preview_mode(raw_val)
    except sqlite3.OperationalError:
        pass
    return DEFAULT_DUAL_SUMMARY_PREVIEW_MODE


def read_summary_settings(conn: sqlite3.Connection) -> dict[str, object]:
    return {
        "summary_rollup_cooldown_turns": get_summary_rollup_cooldown_turns(conn),
        "dual_summary_preview_mode": get_dual_summary_preview_mode(conn),
    }


def upsert_summary_settings(
    conn: sqlite3.Connection,
    *,
    summary_rollup_cooldown_turns: int | None = None,
    dual_summary_preview_mode: str | None = None,
) -> dict[str, object]:
    if summary_rollup_cooldown_turns is not None:
        n = max(1, min(500, int(summary_rollup_cooldown_turns)))
        conn.execute(
            """
            INSERT INTO game_config_meta (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (META_KEY_SUMMARY_ROLLUP_COOLDOWN, str(n)),
        )
    if dual_summary_preview_mode is not None:
        mode = normalize_dual_summary_preview_mode(dual_summary_preview_mode)
        conn.execute(
            """
            INSERT INTO game_config_meta (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (META_KEY_DUAL_SUMMARY_PREVIEW_MODE, mode),
        )
    conn.commit()
    return read_summary_settings(conn)
