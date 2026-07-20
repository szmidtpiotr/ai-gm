import sqlite3
from typing import Any

from app.services import llm_service
from app.core.db_runtime import resolve_db_path


DB_PATH = resolve_db_path()
LLM_MODE_DEFAULT = "default"
LLM_MODE_CUSTOM = "custom"


def _normalize_mode(mode: object, *, fallback: str = LLM_MODE_DEFAULT) -> str:
    value = str(mode or "").strip().lower()
    if value == LLM_MODE_CUSTOM:
        return LLM_MODE_CUSTOM
    if value == LLM_MODE_DEFAULT:
        return LLM_MODE_DEFAULT
    return fallback


def _row_to_effective(row: sqlite3.Row | None) -> dict[str, Any]:
    default_cfg = llm_service.get_default_config(mask_api_key=False)
    if not row:
        return {
            "mode": LLM_MODE_DEFAULT,
            "provider": default_cfg["provider"],
            "base_url": default_cfg["base_url"],
            "model": default_cfg["model"],
            "api_key": default_cfg["api_key"],
            "api_key_set": bool(default_cfg["api_key_set"]),
            "source": "server_default",
        }

    row_keys = set(row.keys())
    mode = _normalize_mode(
        row["mode"] if "mode" in row_keys else LLM_MODE_CUSTOM,
        fallback=LLM_MODE_CUSTOM,
    )
    if mode == LLM_MODE_DEFAULT:
        return {
            "mode": LLM_MODE_DEFAULT,
            "provider": default_cfg["provider"],
            "base_url": default_cfg["base_url"],
            "model": default_cfg["model"],
            "api_key": default_cfg["api_key"],
            "api_key_set": bool(default_cfg["api_key_set"]),
            "source": "server_default",
        }

    override = {
        "provider": str(row["provider"] or "").strip().lower(),
        "base_url": str(row["base_url"] or "").strip().rstrip("/"),
        "model": str(row["model"] or "").strip(),
        "api_key": str(row["api_key"] or "").strip(),
    }
    effective = llm_service.get_effective_config(override)
    return {
        "mode": LLM_MODE_CUSTOM,
        "provider": effective["provider"],
        "base_url": effective["base_url"],
        "model": effective["model"],
        "api_key": effective["api_key"],
        "api_key_set": bool((effective.get("api_key") or "").strip()),
        "source": "user_custom",
    }


def _row_to_masked(row: sqlite3.Row | None) -> dict[str, Any]:
    effective = _row_to_effective(row)
    return {
        "mode": effective["mode"],
        "provider": effective["provider"],
        "base_url": effective["base_url"],
        "model": effective["model"],
        "api_key_set": bool(effective["api_key_set"]),
        "source": effective["source"],
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
            SELECT mode, provider, base_url, model, api_key, api_key_set
            FROM user_llm_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        effective = _row_to_effective(row)
        return {
            "mode": str(effective["mode"]),
            "provider": str(effective["provider"]),
            "base_url": str(effective["base_url"]),
            "model": str(effective["model"]),
            "api_key": str(effective["api_key"]),
            "source": str(effective["source"]),
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
            SELECT mode, provider, base_url, model, api_key, api_key_set
            FROM user_llm_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        return _row_to_masked(row)
    finally:
        conn.close()


def upsert_user_llm_settings(
    user_id: int,
    *,
    mode: str = LLM_MODE_CUSTOM,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        mode_value = _normalize_mode(mode, fallback=LLM_MODE_CUSTOM)
        api_key_value = (api_key or "").strip() if api_key is not None else ""
        api_key_set = 1 if api_key_value else 0
        provider_value = (provider or "").strip().lower()
        base_value = (base_url or "").strip().rstrip("/")
        model_value = (model or "").strip()

        if mode_value == LLM_MODE_DEFAULT:
            existing = conn.execute(
                """
                SELECT provider, base_url, model, api_key, api_key_set
                FROM user_llm_settings
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE user_llm_settings
                    SET mode = ?, updated_at = (datetime('now'))
                    WHERE user_id = ?
                    """,
                    (mode_value, user_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_llm_settings (user_id, mode, provider, base_url, model, api_key, api_key_set)
                    VALUES (?, ?, '', '', '', '', 0)
                    """,
                    (user_id, mode_value),
                )
        elif api_key is None:
            # Keep existing api_key/api_key_set for existing rows (only update provider/url/model).
            conn.execute(
                """
                INSERT INTO user_llm_settings (user_id, mode, provider, base_url, model, api_key, api_key_set)
                VALUES (?, ?, ?, ?, ?, '', 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    updated_at = (datetime('now'))
                """,
                (user_id, mode_value, provider_value, base_value, model_value),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_llm_settings (user_id, mode, provider, base_url, model, api_key, api_key_set)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    api_key = excluded.api_key,
                    api_key_set = excluded.api_key_set,
                    updated_at = (datetime('now'))
                """,
                (user_id, mode_value, provider_value, base_value, model_value, api_key_value, api_key_set),
            )
        conn.commit()
    finally:
        conn.close()

