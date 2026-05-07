from __future__ import annotations

import sqlite3
from typing import Any

from app.core.db_runtime import resolve_db_path
from app.services.llm_service import (
    get_default_config,
    get_runtime_config,
    set_runtime_config,
)

DB_PATH = resolve_db_path()
ACTIVE_PRESET_META_KEY = "llm_global_active_preset_id"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _mask_api_key(api_key: str) -> str:
    val = (api_key or "").strip()
    if not val:
        return ""
    return f"{val[:6]}..." if len(val) > 6 else f"{val}..."


def _normalize_provider(provider: str) -> str:
    return str(provider or "").strip().lower()


def _normalize_base_url(base_url: str) -> str:
    return str(base_url or "").strip().rstrip("/")


def _normalize_model(model: str) -> str:
    return str(model or "").strip()


def _row_to_preset(row: sqlite3.Row, *, mask_api_key: bool = True) -> dict[str, Any]:
    api_key = str(row["api_key"] or "").strip()
    return {
        "id": int(row["id"]),
        "label": str(row["label"] or "").strip(),
        "provider": _normalize_provider(str(row["provider"] or "")),
        "base_url": _normalize_base_url(str(row["base_url"] or "")),
        "model": _normalize_model(str(row["model"] or "")),
        "api_key": _mask_api_key(api_key) if mask_api_key else api_key,
        "api_key_set": bool(int(row["api_key_set"] or 0)),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_active_global_preset_id() -> int | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (ACTIVE_PRESET_META_KEY,),
        ).fetchone()
        if not row:
            return None
        raw = str(row["value"] or "").strip()
        return int(raw) if raw.isdigit() else None
    finally:
        conn.close()


def _set_active_global_preset_id(conn: sqlite3.Connection, preset_id: int | None) -> None:
    if preset_id is None:
        conn.execute("DELETE FROM game_config_meta WHERE key = ?", (ACTIVE_PRESET_META_KEY,))
        return
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (ACTIVE_PRESET_META_KEY, str(int(preset_id))),
    )


def list_llm_presets(*, mask_api_key: bool = True) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        active_id = get_active_global_preset_id()
        rows = conn.execute(
            """
            SELECT id, label, provider, base_url, model, api_key, api_key_set, created_at, updated_at
            FROM llm_connection_presets
            ORDER BY label COLLATE NOCASE ASC, id ASC
            """
        ).fetchall()
        items = [_row_to_preset(row, mask_api_key=mask_api_key) for row in rows]
        for item in items:
            item["is_active"] = active_id is not None and int(item["id"]) == int(active_id)
        return items
    finally:
        conn.close()


def get_llm_preset(preset_id: int, *, mask_api_key: bool = True) -> dict[str, Any]:
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT id, label, provider, base_url, model, api_key, api_key_set, created_at, updated_at
            FROM llm_connection_presets
            WHERE id = ?
            """,
            (int(preset_id),),
        ).fetchone()
        if not row:
            raise KeyError("not_found")
        item = _row_to_preset(row, mask_api_key=mask_api_key)
        item["is_active"] = get_active_global_preset_id() == int(preset_id)
        return item
    finally:
        conn.close()


def save_llm_preset(
    *,
    label: str,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
    preset_id: int | None = None,
) -> dict[str, Any]:
    conn = _connect()
    try:
        safe_label = str(label or "").strip()
        if not safe_label:
            raise ValueError("invalid_label")
        safe_provider = _normalize_provider(provider)
        safe_base_url = _normalize_base_url(base_url)
        safe_model = _normalize_model(model)
        if not safe_provider or not safe_base_url or not safe_model:
            raise ValueError("invalid_preset_payload")

        if preset_id is not None:
            existing = conn.execute(
                "SELECT api_key, api_key_set FROM llm_connection_presets WHERE id = ?",
                (int(preset_id),),
            ).fetchone()
            if not existing:
                raise KeyError("not_found")
            api_key_value = (
                str(existing["api_key"] or "").strip()
                if api_key is None
                else str(api_key or "").strip()
            )
            api_key_set = 1 if api_key_value else 0
            conn.execute(
                """
                UPDATE llm_connection_presets
                SET label = ?, provider = ?, base_url = ?, model = ?,
                    api_key = ?, api_key_set = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    safe_label,
                    safe_provider,
                    safe_base_url,
                    safe_model,
                    api_key_value,
                    api_key_set,
                    int(preset_id),
                ),
            )
            conn.commit()
            return get_llm_preset(int(preset_id), mask_api_key=True)

        api_key_value = str(api_key or "").strip()
        api_key_set = 1 if api_key_value else 0
        cur = conn.execute(
            """
            INSERT INTO llm_connection_presets (label, provider, base_url, model, api_key, api_key_set)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (safe_label, safe_provider, safe_base_url, safe_model, api_key_value, api_key_set),
        )
        conn.commit()
        return get_llm_preset(int(cur.lastrowid), mask_api_key=True)
    except sqlite3.IntegrityError as exc:
        raise ValueError("preset_label_exists") from exc
    finally:
        conn.close()


def activate_llm_preset(preset_id: int) -> dict[str, Any]:
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT id, label, provider, base_url, model, api_key, api_key_set, created_at, updated_at
            FROM llm_connection_presets
            WHERE id = ?
            """,
            (int(preset_id),),
        ).fetchone()
        if not row:
            raise KeyError("not_found")
        _set_active_global_preset_id(conn, int(preset_id))
        conn.commit()
        set_runtime_config(
            provider=str(row["provider"] or ""),
            base_url=str(row["base_url"] or ""),
            model=str(row["model"] or ""),
            api_key=str(row["api_key"] or ""),
        )
        item = _row_to_preset(row, mask_api_key=True)
        item["is_active"] = True
        return item
    finally:
        conn.close()


def clear_global_llm_override() -> dict[str, Any]:
    conn = _connect()
    try:
        _set_active_global_preset_id(conn, None)
        conn.commit()
    finally:
        conn.close()
    set_runtime_config(provider="", base_url="", model="", api_key="")
    return get_default_config(mask_api_key=True)


def delete_llm_preset(preset_id: int) -> None:
    conn = _connect()
    try:
        active_id = get_active_global_preset_id()
        if active_id is not None and int(active_id) == int(preset_id):
            raise ValueError("preset_active")
        cur = conn.execute("DELETE FROM llm_connection_presets WHERE id = ?", (int(preset_id),))
        conn.commit()
        if cur.rowcount < 1:
            raise KeyError("not_found")
    finally:
        conn.close()


def apply_global_llm_settings(
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
) -> dict[str, Any]:
    current = get_runtime_config(mask_api_key=False)
    resolved_key = api_key if api_key is not None else str(current.get("api_key") or "")
    set_runtime_config(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=resolved_key,
    )
    conn = _connect()
    try:
        _set_active_global_preset_id(conn, None)
        conn.commit()
    finally:
        conn.close()
    return get_default_config(mask_api_key=True)


def hydrate_runtime_from_stored_preset() -> None:
    preset_id = get_active_global_preset_id()
    if preset_id is None:
        return
    try:
        preset = get_llm_preset(preset_id, mask_api_key=False)
    except KeyError:
        clear_global_llm_override()
        return
    set_runtime_config(
        provider=str(preset["provider"]),
        base_url=str(preset["base_url"]),
        model=str(preset["model"]),
        api_key=str(preset["api_key"]),
    )


def get_admin_llm_settings_snapshot() -> dict[str, Any]:
    active_id = get_active_global_preset_id()
    active_label = None
    if active_id is not None:
        try:
            active_label = get_llm_preset(active_id, mask_api_key=True).get("label")
        except KeyError:
            active_label = None
    return {
        "settings": get_default_config(mask_api_key=True),
        "active_preset_id": active_id,
        "active_preset_label": active_label,
        "presets": list_llm_presets(mask_api_key=True),
    }
