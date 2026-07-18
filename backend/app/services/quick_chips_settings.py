"""#1215 — globalne ustawienia „Szybkich akcji" (chipy LLM pod composerem).

Przechowywane w game_config_meta:
  quick_chips_enabled  '1'/'0'  — czy w ogóle domieszywać chipy generowane przez LLM
  quick_chips_max      int      — ile takich chipów maks. (wartość startowa 3)

Steruje TYLKO chipami LLM. Chipy regułowe (podróż/odpoczynek/usługi) są zawsze
dostępne, niezależnie od tej flagi.
"""

from __future__ import annotations

import sqlite3

from app.core.db_runtime import resolve_db_path

MAX_DEFAULT = 3


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def get_quick_chips_settings() -> dict:
    enabled, max_n = True, MAX_DEFAULT
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT key, value FROM game_config_meta "
            "WHERE key IN ('quick_chips_enabled', 'quick_chips_max')"
        ).fetchall()
        meta = {r["key"]: r["value"] for r in rows}
        if "quick_chips_enabled" in meta:
            enabled = str(meta["quick_chips_enabled"]).strip().lower() not in (
                "0", "false", "no", "off", "",
            )
        if "quick_chips_max" in meta:
            try:
                max_n = max(0, int(str(meta["quick_chips_max"]).strip() or MAX_DEFAULT))
            except ValueError:
                max_n = MAX_DEFAULT
    finally:
        conn.close()
    return {"enabled": enabled, "max": max_n}


def set_quick_chips_settings(enabled: bool | None = None, max_n: int | None = None) -> dict:
    conn = _conn()
    try:
        if enabled is not None:
            conn.execute(
                """
                INSERT INTO game_config_meta (key, value, updated_at)
                VALUES ('quick_chips_enabled', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                ("1" if enabled else "0",),
            )
        if max_n is not None:
            conn.execute(
                """
                INSERT INTO game_config_meta (key, value, updated_at)
                VALUES ('quick_chips_max', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (str(max(0, int(max_n))),),
            )
        conn.commit()
    finally:
        conn.close()
    return get_quick_chips_settings()
