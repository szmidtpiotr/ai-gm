"""#1215 — generyczne preferencje gracza (key/value per user_id).

Pierwszy klient: 'quick_chips' ('1'/'0') — czy pokazywać temu graczowi chipy
szybkich akcji GENEROWANE PRZEZ LLM. Chipy regułowe (podróż/odpoczynek/usługi)
nie są tym sterowane — zawsze dostępne.

Wzorzec 1:1 z user_llm_settings: dedykowana tabela + get/upsert po user_id.
"""

from __future__ import annotations

import sqlite3

from app.core.db_runtime import resolve_db_path

# Domyślne wartości preferencji (gdy gracz nic nie ustawił).
_DEFAULTS: dict[str, str] = {
    "quick_chips": "1",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def get_preference(user_id: int, key: str, default: str | None = None) -> str:
    """Zwraca wartość preferencji gracza; fallback: podany default → _DEFAULTS → '' ."""
    fallback = default if default is not None else _DEFAULTS.get(key, "")
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE user_id = ? AND key = ? LIMIT 1",
            (user_id, key),
        ).fetchone()
        return row["value"] if row else fallback
    except sqlite3.Error:
        return fallback
    finally:
        conn.close()


def get_all_preferences(user_id: int) -> dict[str, str]:
    """Wszystkie preferencje gracza z domyślnymi wypełnionymi dla brakujących kluczy."""
    merged = dict(_DEFAULTS)
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT key, value FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        for r in rows:
            merged[r["key"]] = r["value"]
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return merged


def set_preference(user_id: int, key: str, value: str) -> None:
    """Upsert pojedynczej preferencji gracza."""
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, key, value, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (user_id, key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()
