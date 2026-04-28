"""Phase 8D — Location Validator Hook + Auto-Create tests."""

import json
import sqlite3

from fastapi.testclient import TestClient

from app.api import turns as turns_api
from app.main import app
from app.services.location_intent_parser import FALLBACK_PARSER_PROMPT, LocationIntent
from app.services.location_validator import validate_move


client = TestClient(app)


def _admin_headers() -> dict:
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code != 200:
        resp = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    return conn


def _set_flag(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def _session(conn: sqlite3.Connection, campaign_id: int = 88001) -> str:
    session_id = f"phase8d-hook-{campaign_id}"
    conn.execute(
        """
        INSERT OR REPLACE INTO game_sessions (id, campaign_id, session_flags)
        VALUES (?, ?, '{}')
        """,
        (session_id, campaign_id),
    )
    conn.commit()
    return session_id


def _location(conn: sqlite3.Connection, key: str, label: str, approved: int = 1) -> int:
    conn.execute("DELETE FROM game_locations WHERE key = ?", (key,))
    cur = conn.execute(
        """
        INSERT INTO game_locations (key, label, location_type, is_active, ai_generated, approved)
        VALUES (?, ?, 'macro', 1, 0, ?)
        """,
        (key, label, approved),
    )
    conn.commit()
    return int(cur.lastrowid)


def _gm_json(label: str, key: str | None = None) -> str:
    intent = {"action": "move", "target_label": label}
    if key:
        intent["target_key"] = key
    return json.dumps({"narrative": f"Idziesz do {label}.", "location_intent": intent}, ensure_ascii=False)


def _gm_fenced_json(label: str, key: str | None = None) -> str:
    return f"```json\n{_gm_json(label, key)}\n```"


def test_hook_skips_validation_when_integrity_disabled():
    conn = _conn()
    try:
        campaign_id = 88101
        session_id = _session(conn, campaign_id)
        _set_flag(conn, "location_integrity_enabled", "0")
        response = _gm_json("Miejsce Bez Walidacji")

        out = turns_api._process_location_intent(conn, campaign_id, response)

        assert out == response
        assert conn.execute(
            "SELECT current_location_id FROM game_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()["current_location_id"] is None
    finally:
        _set_flag(conn, "location_integrity_enabled", "1")
        conn.close()


def test_hook_updates_current_location_on_fuzzy_match():
    conn = _conn()
    try:
        campaign_id = 88102
        session_id = _session(conn, campaign_id)
        loc_id = _location(conn, "hook_karczma", "Karczma")
        _set_flag(conn, "location_integrity_enabled", "1")

        out = turns_api._process_location_intent(conn, campaign_id, _gm_json("Karczma", "hook_karczma"))

        assert "LOCATION_BLOCKED" not in out
        row = conn.execute(
            "SELECT current_location_id FROM game_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        assert row["current_location_id"] == loc_id
    finally:
        conn.close()


def test_hook_accepts_markdown_fenced_json_response():
    conn = _conn()
    try:
        campaign_id = 88109
        session_id = _session(conn, campaign_id)
        loc_id = _location(conn, "hook_fenced_karczma", "Karczma Fenced")
        _set_flag(conn, "location_integrity_enabled", "1")

        out = turns_api._process_location_intent(
            conn,
            campaign_id,
            _gm_fenced_json("Karczma Fenced", "hook_fenced_karczma"),
        )

        assert "LOCATION_BLOCKED" not in out
        row = conn.execute(
            "SELECT current_location_id FROM game_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        assert row["current_location_id"] == loc_id
    finally:
        conn.close()


def test_validate_move_auto_create_unknown_location():
    import time

    conn = _conn()
    try:
        campaign_id = 88103
        session_id = _session(conn, campaign_id)
        _set_flag(conn, "location_auto_create_enabled", "1")
        target_label = f"Nowa Wieza Auto Create {time.time_ns()}"

        result = validate_move(
            session_id,
            LocationIntent(action="move", target_label=target_label),
            campaign_id=campaign_id,
        )

        assert result.allowed is True
        assert result.is_new_location is True
        row = conn.execute(
            "SELECT ai_generated, approved FROM game_locations WHERE id = ?",
            (result.resolved_location_id,),
        ).fetchone()
        assert row["ai_generated"] == 1
        assert row["approved"] == 0
    finally:
        conn.close()


def test_hook_blocks_unknown_location_when_auto_create_disabled():
    conn = _conn()
    try:
        campaign_id = 88104
        _session(conn, campaign_id)
        _set_flag(conn, "location_integrity_enabled", "1")
        _set_flag(conn, "location_auto_create_enabled", "0")

        out = turns_api._process_location_intent(conn, campaign_id, _gm_json("Nieznany Zamek Blokada"))

        parsed = json.loads(out)
        assert parsed["location_intent"] is None
        assert "[LOCATION_BLOCKED:" in parsed["narrative"]
    finally:
        _set_flag(conn, "location_auto_create_enabled", "1")
        conn.close()


def test_pending_locations_endpoint_returns_only_unapproved_ai_locations():
    headers = _admin_headers()
    conn = _conn()
    try:
        conn.execute("DELETE FROM game_locations WHERE key IN ('pending_ai_loc', 'approved_ai_loc')")
        conn.execute(
            """
            INSERT INTO game_locations (key, label, location_type, ai_generated, approved, is_active)
            VALUES ('pending_ai_loc', 'Pending AI Loc', 'macro', 1, 0, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO game_locations (key, label, location_type, ai_generated, approved, is_active)
            VALUES ('approved_ai_loc', 'Approved AI Loc', 'macro', 1, 1, 1)
            """
        )
        conn.commit()

        resp = client.get("/api/admin/locations/pending", headers=headers)

        assert resp.status_code == 200
        keys = {row["key"] for row in resp.json()["locations"]}
        assert "pending_ai_loc" in keys
        assert "approved_ai_loc" not in keys
    finally:
        conn.close()


def test_approve_location_endpoint_sets_approved():
    headers = _admin_headers()
    conn = _conn()
    try:
        loc_id = _location(conn, "approve_ai_loc", "Approve AI Loc", approved=0)
        conn.execute("UPDATE game_locations SET ai_generated = 1 WHERE id = ?", (loc_id,))
        conn.commit()

        resp = client.post(f"/api/admin/locations/{loc_id}/approve", headers=headers)

        assert resp.status_code == 200
        row = conn.execute("SELECT approved FROM game_locations WHERE id = ?", (loc_id,)).fetchone()
        assert row["approved"] == 1
    finally:
        conn.close()


def test_reject_location_endpoint_sets_inactive():
    headers = _admin_headers()
    conn = _conn()
    try:
        loc_id = _location(conn, "reject_ai_loc", "Reject AI Loc", approved=0)
        conn.execute("UPDATE game_locations SET ai_generated = 1 WHERE id = ?", (loc_id,))
        conn.commit()

        resp = client.post(f"/api/admin/locations/{loc_id}/reject", headers=headers)

        assert resp.status_code == 200
        row = conn.execute("SELECT is_active FROM game_locations WHERE id = ?", (loc_id,)).fetchone()
        assert row["is_active"] == 0
    finally:
        conn.close()


def test_location_integrity_log_records_successful_moves():
    conn = _conn()
    try:
        campaign_id = 88108
        session_id = _session(conn, campaign_id)
        _location(conn, "log_success_loc", "Log Success Location")
        before = conn.execute("SELECT COUNT(*) FROM location_integrity_log").fetchone()[0]

        result = validate_move(
            session_id,
            LocationIntent(action="move", target_label="Log Success Location"),
            campaign_id=campaign_id,
        )

        after = conn.execute("SELECT COUNT(*) FROM location_integrity_log").fetchone()[0]
        assert result.allowed is True
        assert after == before + 1
    finally:
        conn.close()


def test_fallback_parser_prompt_escapes_json_braces():
    prompt = FALLBACK_PARSER_PROMPT.format(text="Wchodzę do karczmy")

    assert '"moved"' in prompt
    assert "Wchodzę do karczmy" in prompt
