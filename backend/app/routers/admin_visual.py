"""Visual settings — admin-editable visual configuration for the player UI.

Currently scoped to time-of-day chat overlay (Stage 2A follow-up). Designed
to grow: future subtabs will add fonts, UI themes, particle effects, etc.

Storage: `game_config_visual` (key TEXT PK, value TEXT JSON). Values stored
as JSON strings so admins can mix scalars, hex colors, structured objects
without schema churn.

Two endpoints:
- `GET /api/admin/visual`           — full settings dict (admin token required)
- `PATCH /api/admin/visual/{key}`    — update one setting (admin token required)
- `GET /api/visual/public`           — read-only player snapshot (no auth);
                                       only keys safe to expose are returned
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.admin import require_admin_token

DB_PATH = Path("/data/ai_gm.db")

admin_router = APIRouter(prefix="/admin/visual", tags=["admin-visual"], dependencies=[Depends(require_admin_token)])
public_router = APIRouter(prefix="/visual", tags=["visual"])


# Seeds — also seeded by RAW_MIGRATIONS but kept here as canonical reference.
_DEFAULT_SEEDS: dict[str, Any] = {
    "time_of_day.enabled": True,
    "time_of_day.mode": "frame",   # "frame" | "bg" | "both" | "off"
    "time_of_day.intensity": 60,   # 0-100 — opacity multiplier for the effect
    "time_of_day.rano":       {"color": "#ffd97a", "accent": "#f7e7a3", "label": "Rano"},
    "time_of_day.popoludnie": {"color": "#c9a54a", "accent": "#d4b65e", "label": "Popołudnie"},
    "time_of_day.wieczor":    {"color": "#c95c2e", "accent": "#e07555", "label": "Wieczór"},
    "time_of_day.noc":        {"color": "#5a6d99", "accent": "#7a8cb8", "label": "Noc"},
}

# Keys exposed to the player UI without auth. Add to this set carefully —
# anything here is world-readable.
_PUBLIC_KEY_PREFIXES = ("time_of_day.",)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _parse_value(raw: str) -> Any:
    """JSON-parse a stored value, falling back to the raw string on failure
    (defensive — admins editing directly in SQLite may leave non-JSON values)."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _all_settings_dict() -> dict[str, Any]:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM game_config_visual").fetchall()
    out: dict[str, Any] = {}
    for r in rows:
        out[r["key"]] = _parse_value(r["value"])
    # Backfill defaults for any seed not yet in DB (defensive against partial
    # migrations or admin-deleted rows)
    for k, v in _DEFAULT_SEEDS.items():
        out.setdefault(k, v)
    return out


@admin_router.get("")
def list_visual_settings() -> dict[str, Any]:
    """Admin endpoint — all visual settings as a flat dict."""
    return {"settings": _all_settings_dict()}


@admin_router.patch("/{key:path}")
def update_visual_setting(key: str, payload: dict = Body(...)) -> dict[str, Any]:
    """Update a single setting. Body: `{value: <any JSON>}`.

    Stored as canonical JSON. Use this for both scalars and objects:
      PATCH /admin/visual/time_of_day.enabled            body: {"value": false}
      PATCH /admin/visual/time_of_day.rano               body: {"value": {"color":"#ffd97a","accent":"#f7e7a3","label":"Rano"}}
    """
    if "value" not in payload:
        raise HTTPException(status_code=400, detail="Body must contain 'value' key")
    value_json = json.dumps(payload["value"], ensure_ascii=False)

    with _conn() as c:
        c.execute(
            """INSERT INTO game_config_visual (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')""",
            (key, value_json),
        )
        c.commit()
    return {"ok": True, "key": key, "value": payload["value"]}


@public_router.get("/public")
def get_visual_public() -> dict[str, Any]:
    """Player-side read of visual settings. No auth. Returns only the keys
    whitelisted in `_PUBLIC_KEY_PREFIXES`. Player UI reads this on game enter
    and re-evaluates the overlay on every clock tick."""
    full = _all_settings_dict()
    public = {k: v for k, v in full.items() if any(k.startswith(p) for p in _PUBLIC_KEY_PREFIXES)}
    return {"settings": public}
