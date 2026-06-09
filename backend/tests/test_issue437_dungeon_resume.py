"""TDD: Issue #437 — E22 Resume niedokończonego runu lochu.

Backend: GET /api/dungeons/active-run?character_id=X
Zwraca aktywny, niedokończony run lochu dla danego bohatera (jeśli istnieje).
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_demo_hero_id():
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT ch.id FROM characters ch WHERE ch.campaign_id IS NOT NULL LIMIT 1"
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _inject_dungeon_run(campaign_id: int, dungeon_key: str = "rat_tunnels") -> dict:
    """Wstrzyknij fake dungeon_run do session_flags dla kampanii."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((row["session_flags"] if row else None) or "{}")
        run = {
            "dungeon_key": dungeon_key,
            "current_room": 2,
            "rooms": [
                {"room_number": 1, "type": "combat", "cleared": True},
                {"room_number": 2, "type": "chest", "cleared": False},
                {"room_number": 3, "type": "boss", "cleared": False},
            ],
            "completed": False,
            "failed": False,
        }
        flags["dungeon_run"] = run
        if row:
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(flags), campaign_id),
            )
        else:
            conn.execute(
                "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
                (campaign_id, json.dumps(flags)),
            )
        conn.commit()
        return run
    finally:
        conn.close()


def _cleanup_dungeon_run(campaign_id: int) -> None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row:
            flags = json.loads(row["session_flags"] or "{}")
            flags.pop("dungeon_run", None)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(flags), campaign_id),
            )
            conn.commit()
    finally:
        conn.close()


def _get_demo_dungeon_campaign():
    """Zwróć (campaign_id, character_id) dla kampanii dungeon demo usera lub None."""
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT c.id, ch.id AS char_id
               FROM campaigns c
               JOIN characters ch ON ch.campaign_id = c.id
               WHERE c.owner_user_id = 1 AND c.mode = 'dungeon' AND c.status = 'active'
               LIMIT 1"""
        ).fetchone()
        if row:
            return row["id"], row["char_id"]
        return None, None
    finally:
        conn.close()


def _create_temp_dungeon_campaign(character_id: int) -> int:
    """Utwórz tymczasową kampanię dungeon dla testów."""
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO campaigns (title, system_id, mode, status, owner_user_id)
               VALUES ('TDD E22 Test', 'fantasy', 'dungeon', 'active', 1)"""
        )
        campaign_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            "UPDATE characters SET campaign_id = ? WHERE id = ?",
            (campaign_id, character_id),
        )
        conn.commit()
        return campaign_id
    finally:
        conn.close()


def _cleanup_temp_campaign(campaign_id: int, original_campaign_id: int | None, character_id: int) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        if original_campaign_id:
            conn.execute(
                "UPDATE characters SET campaign_id = ? WHERE id = ?",
                (original_campaign_id, character_id),
            )
        conn.commit()
    finally:
        conn.close()


# ─── Test główny — endpoint active-run ───────────────────────────────────────

def test_active_run_endpoint_exists():
    """GET /api/dungeons/active-run?character_id=X musi istnieć (404 nie ok)."""
    from app.main import app
    client = TestClient(app)

    resp = client.get("/api/dungeons/active-run?character_id=1")
    assert resp.status_code != 404, (
        "Endpoint GET /api/dungeons/active-run nie istnieje. "
        "E22 wymaga tego endpointu żeby frontend mógł pokazać przycisk Resume."
    )


def test_active_run_returns_null_when_no_run():
    """active-run zwraca null gdy bohater nie ma aktywnego runu."""
    from app.main import app
    client = TestClient(app)

    # character_id=0 na pewno nie ma runu
    resp = client.get("/api/dungeons/active-run?character_id=0")
    assert resp.status_code == 200
    body = resp.json()
    assert "active_run" in body, "Odpowiedź musi zawierać klucz 'active_run'"
    assert body["active_run"] is None, f"Dla nieistniejącego bohatera active_run powinno być null, got: {body['active_run']}"


def test_active_run_returns_run_when_dungeon_campaign_active():
    """active-run zwraca run gdy bohater ma kampanię dungeon z aktywnym runem."""
    from app.main import app
    client = TestClient(app)

    # Znajdź bohatera demo
    conn = _get_db()
    try:
        hero_row = conn.execute(
            "SELECT id, campaign_id FROM characters WHERE campaign_id IS NOT NULL LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    if not hero_row:
        pytest.skip("Brak bohatera z kampanią")

    char_id = hero_row["id"]
    orig_campaign_id = hero_row["campaign_id"]

    # Utwórz tymczasową kampanię dungeon
    temp_campaign_id = _create_temp_dungeon_campaign(char_id)

    try:
        # Wstrzyknij aktywny run
        _inject_dungeon_run(temp_campaign_id, "rat_tunnels")

        # Teraz wywołaj endpoint
        resp = client.get(f"/api/dungeons/active-run?character_id={char_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert "active_run" in body, "Odpowiedź musi zawierać 'active_run'"
        run = body["active_run"]
        assert run is not None, "active_run powinno być non-null gdy run istnieje"
        assert "campaign_id" in run, "active_run musi zawierać campaign_id"
        assert run["campaign_id"] == temp_campaign_id
        assert "dungeon_key" in run, "active_run musi zawierać dungeon_key"
        assert run["dungeon_key"] == "rat_tunnels"
        assert "current_room" in run, "active_run musi zawierać current_room"

    finally:
        _cleanup_temp_campaign(temp_campaign_id, orig_campaign_id, char_id)


# ─── Test — completed run nie jest zwracany jako active ───────────────────────

def test_active_run_ignores_completed_run():
    """active-run nie zwraca zakończonego runu (completed=True)."""
    from app.main import app
    client = TestClient(app)

    conn = _get_db()
    try:
        hero_row = conn.execute(
            "SELECT id, campaign_id FROM characters WHERE campaign_id IS NOT NULL LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    if not hero_row:
        pytest.skip("Brak bohatera z kampanią")

    char_id = hero_row["id"]
    orig_campaign_id = hero_row["campaign_id"]
    temp_campaign_id = _create_temp_dungeon_campaign(char_id)

    try:
        # Wstrzyknij UKOŃCZONY run
        run = _inject_dungeon_run(temp_campaign_id, "rat_tunnels")
        # Oznacz jako completed
        conn2 = _get_db()
        try:
            row = conn2.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (temp_campaign_id,),
            ).fetchone()
            flags = json.loads(row["session_flags"] or "{}")
            flags["dungeon_run"]["completed"] = True
            conn2.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(flags), temp_campaign_id),
            )
            conn2.commit()
        finally:
            conn2.close()

        resp = client.get(f"/api/dungeons/active-run?character_id={char_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("active_run") is None, (
            "Ukończony run nie powinien być zwracany jako active_run"
        )

    finally:
        _cleanup_temp_campaign(temp_campaign_id, orig_campaign_id, char_id)
