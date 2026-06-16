"""TDD L10 (#679) — Flaga dungeon_enabled dla graczy.

Weryfikuje:
- POST /dungeons/{key}/enter → 403 gdy dungeon_enabled=False w game_mode_flags
- POST /dungeons/{key}/enter → nie 403 gdy dungeon_enabled=True (może 404 — nie ma klucza)
- GET /campaign-modes → brak klucza 'loch_kafelki' w odpowiedzi
- GET /campaign-modes → 'loch' mode disabled gdy dungeon_enabled=False
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"
_META_KEY = "game_mode_flags"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _set_dungeon_flag(enabled: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ?", (_META_KEY,)
        ).fetchone()
        flags = {}
        if row and row[0]:
            try:
                flags = json.loads(row[0])
            except Exception:
                pass
        flags["dungeon_enabled"] = enabled
        conn.execute(
            "INSERT INTO game_config_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_META_KEY, json.dumps(flags)),
        )
        conn.commit()
    finally:
        conn.close()


def _restore_dungeon_flag():
    """Restore dungeon_enabled=True after each test."""
    _set_dungeon_flag(True)


# ─── 1. 403 gdy flaga OFF ─────────────────────────────────────────────────────

def test_enter_returns_403_when_dungeon_disabled():
    """POST /dungeons/x/enter → 403 gdy dungeon_enabled=False."""
    _set_dungeon_flag(False)
    try:
        r = client.post(
            "/api/dungeons/nonexistent_dungeon_key/enter",
            json={"campaign_id": 1, "character_id": 1},
        )
        assert r.status_code == 403, (
            f"Oczekiwano 403 gdy flaga OFF, dostano {r.status_code}: {r.text}"
        )
        body = r.json()
        assert body.get("detail", {}).get("error") == "dungeon_disabled", (
            f"Oczekiwano error='dungeon_disabled', dostano: {body}"
        )
    finally:
        _restore_dungeon_flag()


# ─── 2. Nie 403 gdy flaga ON ─────────────────────────────────────────────────

def test_enter_not_403_when_dungeon_enabled():
    """POST /dungeons/x/enter → nie 403 gdy dungeon_enabled=True (może 404/422)."""
    _set_dungeon_flag(True)
    r = client.post(
        "/api/dungeons/nonexistent_dungeon_key_xyz/enter",
        json={"campaign_id": 1, "character_id": 1},
    )
    assert r.status_code != 403, (
        f"Nie powinno być 403 gdy flaga ON, dostano {r.status_code}: {r.text}"
    )


# ─── 3. Brak loch_kafelki w campaign-modes ───────────────────────────────────

def test_campaign_modes_no_loch_kafelki():
    """GET /campaign-modes → brak klucza 'loch_kafelki' (usunięty po L9/L10)."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200, f"Błąd endpoint: {r.status_code}"
    keys = [m["key"] for m in r.json().get("modes", [])]
    assert "loch_kafelki" not in keys, (
        f"'loch_kafelki' nadal w campaign-modes — nie usunięto martwego trybu: {keys}"
    )


# ─── 4. loch disabled gdy flaga OFF ──────────────────────────────────────────

def test_campaign_modes_loch_disabled_when_flag_off():
    """GET /campaign-modes → modes.loch.available=False gdy dungeon_enabled=False."""
    _set_dungeon_flag(False)
    try:
        r = client.get("/api/campaign-modes")
        assert r.status_code == 200
        modes = {m["key"]: m for m in r.json().get("modes", [])}
        assert "loch" in modes, f"Brak trybu 'loch' w odpowiedzi: {list(modes.keys())}"
        assert not modes["loch"]["available"], (
            f"modes.loch.available powinno być False gdy dungeon_enabled=False: {modes['loch']}"
        )
    finally:
        _restore_dungeon_flag()
