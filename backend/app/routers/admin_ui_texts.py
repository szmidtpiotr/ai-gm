"""UI Texts CMS — admin-editable text overrides for the player frontend.

Allows admins to override any catalogued text string in the player UI and
apply optional font/colour/CSS styling to it.

Storage: `ui_texts` table — one row per text key.
- `custom_text` NULL → use the original hardcoded string
- CSS columns NULL → no style override applied

Two router pairs:
- admin_router  prefix `/admin/ui-texts`   (requires x-admin-token)
- public_router prefix `/ui/texts`         (no auth — read-only subset)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.admin import require_admin_token
from app.core.db_runtime import resolve_db_path

DB_PATH = Path(resolve_db_path())

admin_router = APIRouter(prefix="/admin/ui-texts", tags=["admin-ui-texts"])  # auth: warstwa /api/admin (#1187)
public_router = APIRouter(prefix="/ui/texts", tags=["ui-texts"])

# ── Seed catalogue ────────────────────────────────────────────────────────────
# These are the text strings exposed for editing. Update here when adding new
# trackable strings to the player frontend (and add matching data-ui-text= attrs).

SEED_CATALOGUE: list[dict[str, str]] = [
    # Login screen
    dict(key="login.title",    screen="login",    description="Tytuł ekranu logowania",         original_text="AI-GM"),
    dict(key="login.subtitle", screen="login",    description="Podtytuł ekranu logowania",       original_text="Mroczna kraina czeka na bohatera"),
    dict(key="login.quote",    screen="login",    description="Cytat u dołu strony logowania",   original_text='"W mroku świec, historie się rodzą..."'),
    # Heroes screen
    dict(key="heroes.title",   screen="heroes",   description="Tytuł ekranu bohaterów",          original_text="Moi Bohaterowie"),
    # Campaigns screen
    dict(key="campaigns.title", screen="campaigns", description="Tytuł ekranu kampanii",         original_text="Kampanie"),
    # Game screen — composer
    dict(key="game.composer_placeholder",        screen="game", description="Placeholder pola wiadomości",          original_text="Co robisz? Możesz pisać swobodnie..."),
    dict(key="game.composer_combat_placeholder", screen="game", description="Placeholder pola wiadomości w walce",  original_text="Co robi Twoja postać w tej rundzie?"),
    # Game screen — special overlays
    dict(key="game.death_title",   screen="game", description="Tytuł ekranu śmierci bohatera",  original_text="poległ..."),
    dict(key="game.victory_title", screen="game", description="Tytuł ekranu zwycięstwa",        original_text="triumfalnego końca"),
    # Onboarding
    dict(key="onboarding.greeting", screen="onboarding", description="Powitanie na onboardingu", original_text="wędrowcze"),
]


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    return d


@admin_router.get("")
def list_ui_texts() -> dict[str, Any]:
    """All catalogue entries with their current overrides."""
    with _conn() as c:
        rows = c.execute(
            "SELECT key, screen, description, original_text, custom_text, "
            "font_family, font_size, font_weight, color, text_transform, "
            "letter_spacing, extra_css, updated_at FROM ui_texts ORDER BY screen, key"
        ).fetchall()
    return {"texts": [_row_to_dict(r) for r in rows]}


@admin_router.patch("/{key:path}")
def update_ui_text(key: str, payload: dict = Body(...)) -> dict[str, Any]:
    """Update one text entry. Accepts any subset of editable columns.

    Accepted fields: custom_text, font_family, font_size, font_weight,
                     color, text_transform, letter_spacing, extra_css
    Pass null to clear a field (revert to default/none).
    """
    allowed = {"custom_text", "font_family", "font_size", "font_weight",
               "color", "text_transform", "letter_spacing", "extra_css"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields provided")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [key]

    with _conn() as c:
        c.execute(
            f"UPDATE ui_texts SET {sets}, updated_at = datetime('now') WHERE key = ?",
            values,
        )
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail=f"Text key '{key}' not found")
        c.commit()
        row = c.execute("SELECT * FROM ui_texts WHERE key = ?", (key,)).fetchone()
    return _row_to_dict(row)


@admin_router.post("/{key:path}/reset")
def reset_ui_text(key: str) -> dict[str, Any]:
    """Clear all overrides for a key (revert to original hardcoded text)."""
    with _conn() as c:
        c.execute(
            """UPDATE ui_texts SET custom_text = NULL, font_family = NULL,
               font_size = NULL, font_weight = NULL, color = NULL,
               text_transform = NULL, letter_spacing = NULL, extra_css = NULL,
               updated_at = datetime('now') WHERE key = ?""",
            (key,),
        )
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail=f"Text key '{key}' not found")
        c.commit()
        row = c.execute("SELECT * FROM ui_texts WHERE key = ?", (key,)).fetchone()
    return _row_to_dict(row)


@public_router.get("")
def get_public_texts() -> dict[str, Any]:
    """Player-side snapshot — returns only entries that have at least one override.
    No auth required. Called by the player frontend on init."""
    with _conn() as c:
        rows = c.execute(
            """SELECT key, custom_text, font_family, font_size, font_weight,
               color, text_transform, letter_spacing, extra_css
               FROM ui_texts
               WHERE custom_text IS NOT NULL
                  OR font_family IS NOT NULL OR font_size IS NOT NULL
                  OR font_weight IS NOT NULL OR color IS NOT NULL
                  OR text_transform IS NOT NULL OR letter_spacing IS NOT NULL
                  OR extra_css IS NOT NULL"""
        ).fetchall()
    return {"texts": [_row_to_dict(r) for r in rows]}
