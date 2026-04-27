"""Phase 8E-2 — default fold states for player sheet sections (game_config_meta)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

DB_PATH = "/data/ai_gm.db"
META_KEY = "ui_panel_defaults"
ALLOWED_PANELS = frozenset({"stats", "skills", "identity", "inventory"})
BUILTIN_DEFAULTS: dict[str, str] = {
    "stats": "expanded",
    "skills": "expanded",
    "identity": "expanded",
    "inventory": "expanded",
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _normalize_state(value: Any) -> str | None:
    s = str(value or "").strip().lower()
    if s in ("expanded", "collapsed"):
        return s
    return None


def get_ui_panels_merged() -> dict[str, str]:
    """Defaults from DB merged over builtins; unknown JSON keys ignored."""
    out = dict(BUILTIN_DEFAULTS)
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
                (META_KEY,),
            ).fetchone()
    except sqlite3.Error:
        return out
    if not row or row["value"] is None:
        return out
    try:
        data = json.loads(str(row["value"]))
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if k not in ALLOWED_PANELS:
            continue
        ns = _normalize_state(v)
        if ns:
            out[k] = ns
    return out


def merge_ui_panels_patch(patch: dict[str, Any]) -> dict[str, str]:
    """Merge allowed keys into stored JSON; invalid values skipped."""
    current = get_ui_panels_merged()
    for k, v in (patch or {}).items():
        if k not in ALLOWED_PANELS:
            continue
        ns = _normalize_state(v)
        if ns:
            current[k] = ns
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
            (META_KEY, json.dumps(current, ensure_ascii=False)),
        )
        conn.commit()
    return current
