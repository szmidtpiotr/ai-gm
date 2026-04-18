"""Persisted Loki base URL (SQLite game_config_meta) with LOKI_URL env fallback."""

from __future__ import annotations

import os
import sqlite3

DB_PATH = "/data/ai_gm.db"
LOKI_META_KEY = "loki_url"
# Suggested default for Docker Compose service name (observability stack).
DEFAULT_LOKI_URL = "http://loki:3100"


def get_stored_loki_url() -> str:
    """Return URL stored in DB, or empty string if unset."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (LOKI_META_KEY,),
        ).fetchone()
        if not row:
            return ""
        return str(row["value"] or "").strip()
    finally:
        conn.close()


def set_stored_loki_url(url: str) -> None:
    """Persist URL; empty string removes the row (fall back to env only)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        trimmed = (url or "").strip()
        if not trimmed:
            conn.execute("DELETE FROM game_config_meta WHERE key = ?", (LOKI_META_KEY,))
        else:
            conn.execute(
                """
                INSERT INTO game_config_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (LOKI_META_KEY, trimmed),
            )
        conn.commit()
    finally:
        conn.close()


def get_effective_loki_base() -> str:
    """
    URL used for health checks: database value first, then LOKI_URL environment.
    """
    db_val = get_stored_loki_url()
    if db_val:
        return db_val
    return (os.getenv("LOKI_URL") or "").strip()


def get_display_loki_url() -> str:
    """
    Value to show in admin UI: stored → env → built-in default.
    """
    s = get_stored_loki_url()
    if s:
        return s
    env = (os.getenv("LOKI_URL") or "").strip()
    if env:
        return env
    return DEFAULT_LOKI_URL
