import sqlite3
from typing import Any

from app.services import llm_service


DB_PATH = "/data/ai_gm.db"


def _row_to_masked(row: sqlite3.Row) -> dict[str, Any]:
    api_key_set = bool(row["api_key_set"]) if row.keys() else False
    # We never return api_key to the client.
    return {
        "provider": row["provider"],
        "base_url": str(row["base_url"] or "").strip().rstrip("/"),
        "model": row["model"],
        "api_key_set": api_key_set,
    }


def get_user_llm_settings_full(user_id: int) -> dict[str, str]:
    """
    Returns full LLM config including api_key for backend use.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT provider, base_url, model, api_key
            FROM user_llm_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            effective = llm_service.get_effective_config()
            return {
                "provider": effective["provider"],
                "base_url": effective["base_url"],
                "model": effective["model"],
                "api_key": effective["api_key"],
            }

        return {
            "provider": str(row["provider"] or "").strip().lower(),
            "base_url": str(row["base_url"] or "").strip().rstrip("/"),
            "model": str(row["model"] or "").strip(),
            "api_key": str(row["api_key"] or "").strip(),
        }
    finally:
        conn.close()


def get_user_llm_settings_masked(user_id: int) -> dict[str, Any]:
    """
    Returns safe LLM settings for UI (does not include api_key).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT provider, base_url, model, api_key_set
            FROM user_llm_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row:
            return _row_to_masked(row)

        # No row yet -> fall back to effective runtime config, but api_key_set is inferred.
        effective = llm_service.get_effective_config()
        api_key_set = bool(effective.get("api_key"))
        return {
            "provider": effective["provider"],
            "base_url": effective["base_url"],
            "model": effective["model"],
            "api_key_set": api_key_set,
        }
    finally:
        conn.close()


def upsert_user_llm_settings(
    user_id: int,
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        api_key_value = (api_key or "").strip() if api_key is not None else ""
        api_key_set = 1 if api_key_value else 0
        provider_value = (provider or "").strip().lower()
        base_value = (base_url or "").strip().rstrip("/")
        model_value = (model or "").strip()

        if api_key is None:
            # Keep existing api_key/api_key_set for existing rows (only update provider/url/model).
            conn.execute(
                """
                INSERT INTO user_llm_settings (user_id, provider, base_url, model, api_key, api_key_set)
                VALUES (?, ?, ?, ?, '', 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    updated_at = (datetime('now'))
                """,
                (user_id, provider_value, base_value, model_value),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_llm_settings (user_id, provider, base_url, model, api_key, api_key_set)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    api_key = excluded.api_key,
                    api_key_set = excluded.api_key_set,
                    updated_at = (datetime('now'))
                """,
                (user_id, provider_value, base_value, model_value, api_key_value, api_key_set),
            )
        conn.commit()
    finally:
        conn.close()

