import json
import os
import sqlite3
import time
from typing import Any

DB_PATH = "/data/ai_gm.db"
_CACHE_TTL_SECONDS = 60
_CACHE: dict[str, Any] = {"expires_at": 0.0, "value": None}


def _use_db_config() -> bool:
    raw = (os.getenv("USE_DB_CONFIG", "false") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _default_config() -> dict[str, Any]:
    return {
        "stats": ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"],
        "skills": [
            "athletics",
            "stealth",
            "initiative",
            "attack",
            "awareness",
            "persuasion",
            "intimidation",
            "survival",
            "lore",
            "arcana",
            "medicine",
            "investigation",
        ],
        "dc_tiers": [
            {"key": "easy", "value": 8},
            {"key": "medium", "value": 12},
            {"key": "hard", "value": 16},
            {"key": "extreme", "value": 20},
            {"key": "legendary", "value": 24},
        ],
        "source": "constants",
    }


def _load_from_db() -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        stats = conn.execute(
            "SELECT key FROM game_config_stats ORDER BY sort_order ASC, key ASC"
        ).fetchall()
        skills = conn.execute(
            "SELECT key FROM game_config_skills ORDER BY sort_order ASC, key ASC"
        ).fetchall()
        dc_rows = conn.execute(
            "SELECT key, value FROM game_config_dc ORDER BY sort_order ASC, key ASC"
        ).fetchall()
        return {
            "stats": [r["key"] for r in stats],
            "skills": [r["key"] for r in skills],
            "dc_tiers": [{"key": r["key"], "value": int(r["value"])} for r in dc_rows],
            "source": "db",
        }
    finally:
        conn.close()


def get_runtime_config() -> dict[str, Any]:
    if not _use_db_config():
        return _default_config()

    now = time.time()
    cached_value = _CACHE.get("value")
    if cached_value is not None and now < float(_CACHE.get("expires_at") or 0.0):
        return cached_value

    try:
        value = _load_from_db()
    except Exception:
        value = _default_config()
    _CACHE["value"] = value
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return value


def build_runtime_config_block() -> str:
    cfg = get_runtime_config()
    return (
        "Konfiguracja mechanik (runtime):\n"
        f"{json.dumps(cfg, ensure_ascii=False)}\n"
        "Używaj tych statystyk/umiejętności/progów jako źródła prawdy."
    )
