"""Dice config — admin GET/POST + public GET.

Stores the 3D dice appearance config as a single JSON blob under key
'dice_config' in game_config_visual table (reuses existing key-value store).

Admin endpoints require admin token. Public endpoint is auth-free (player
frontend reads it on game init to configure dice appearance).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token

DB_PATH = Path("/data/ai_gm.db")

admin_router = APIRouter(prefix="/admin/dice-config", tags=["admin-dice"])
public_router = APIRouter(prefix="/game/dice-config", tags=["dice-public"])

_STORAGE_KEY = "dice_config"

_DEFAULT_CONFIG: dict[str, Any] = {
    "customColorset": {
        "foreground": "#ffd76a",
        "background": ["#1b1107", "#3a2410"],
        "outline": "#c08020",
        "texture": "fire",
        "material": "plastic",
    },
    "gravity_multiplier": 400,
    "strength": 1.4,
    "baseScale": 100,
    "light_intensity": 0.9,
}


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _load_config() -> dict[str, Any]:
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT value FROM game_config_visual WHERE key = ?", (_STORAGE_KEY,)
            ).fetchone()
        if row:
            return json.loads(row["value"])
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)


class DiceConfigReq(BaseModel):
    config: dict[str, Any]


@admin_router.get("")
def get_dice_config(_: None = Depends(_require_admin)) -> dict[str, Any]:
    """Admin — return current dice config (defaults if never saved)."""
    cfg = _load_config()
    for k, v in _DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return {"config": cfg}


@admin_router.post("")
def save_dice_config(req: DiceConfigReq, _: None = Depends(_require_admin)) -> dict[str, Any]:
    """Admin — persist dice config."""
    value_json = json.dumps(req.config, ensure_ascii=False)
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """INSERT INTO game_config_visual (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')""",
            (_STORAGE_KEY, value_json),
        )
        c.commit()
    return {"ok": True}


@public_router.get("")
def get_dice_config_public() -> dict[str, Any]:
    """Public (no auth) — player frontend reads this on game init."""
    cfg = _load_config()
    for k, v in _DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return {"config": cfg}
