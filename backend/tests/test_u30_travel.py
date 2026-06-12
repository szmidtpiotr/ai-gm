"""TDD: Issue #544 (U30) — Ruch jako akcja mechaniczna pierwszej klasy.

Testy pokrywają:
1. Hex-resolve dla ruchu z tekstu — fix w _update_hex_world_state (#518)
2. resolve_location_key_to_hex — lookup lokacja → hex
3. POST /travel z target_location_key
4. Anty-desync guard — log travel_narrated_without_move
5. Keyword fast-path MOVE (kierunki kardynalne)
"""
import json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, "/app")

# ── helpers ────────────────────────────────────────────────���─────────────────

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'forest',
            location_key TEXT, label TEXT, is_active INTEGER DEFAULT 1,
            terrain_tags TEXT DEFAULT '[]', atmosphere TEXT DEFAULT '',
            is_discovered INTEGER DEFAULT 0, extra_data TEXT DEFAULT '{}'
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT,
            hex_q INTEGER, hex_r INTEGER, is_active INTEGER DEFAULT 1,
            location_type TEXT DEFAULT 'generic', terrain_tags TEXT DEFAULT '[]',
            description TEXT DEFAULT '', created_by TEXT DEFAULT 'test'
        );
        CREATE TABLE hex_teleport_connections (
            id INTEGER PRIMARY KEY, from_q INTEGER, from_r INTEGER,
            to_q INTEGER, to_r INTEGER, travel_hours REAL DEFAULT 8.0
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY, label TEXT, travel_hours REAL DEFAULT 1.0
        );
    """)
    return conn


def _seed_world(conn, hexes=None, locations=None):
    if hexes:
        for h in hexes:
            conn.execute(
                "INSERT INTO world_hexes (q,r,hex_type,location_key,label,is_active,is_discovered) "
                "VALUES (?,?,?,?,?,?,?)",
                (h["q"], h["r"], h.get("hex_type","forest"),
                 h.get("location_key"), h.get("label",""), 1, h.get("is_discovered",1))
            )
    if locations:
        for l in locations:
            conn.execute(
                "INSERT INTO game_locations (key,label,hex_q,hex_r,is_active) VALUES (?,?,?,?,?)",
                (l["key"], l["label"], l.get("hex_q"), l.get("hex_r"), 1)
            )
    conn.execute("INSERT INTO hex_type_config (hex_type,label,travel_hours) VALUES ('forest','Las',1.0)")
    conn.execute("INSERT INTO hex_type_config (hex_type,label,travel_hours) VALUES ('plains','Równiny',1.0)")
    conn.commit()


# ── Test 1: resolve_location_key_to_hex — nowa funkcja ──────────────────────

def test_resolve_location_key_to_hex_returns_coords():
    """resolve_location_key_to_hex(key, conn) → (q, r) gdy lokacja na hexie."""
    from app.services.hex_travel_service import resolve_location_key_to_hex
    conn = _make_conn()
    _seed_world(conn, hexes=[{"q": 2, "r": 3, "location_key": "karczma_stara"}])

    result = resolve_location_key_to_hex("karczma_stara", conn)
    assert result == (2, 3), f"Oczekiwano (2,3), dostano {result}"


def test_resolve_location_key_to_hex_returns_none_when_missing():
    """Gdy lokacja nie jest na żadnym hexie → None."""
    from app.services.hex_travel_service import resolve_location_key_to_hex
    conn = _make_conn()
    _seed_world(conn, hexes=[{"q": 0, "r": 0, "location_key": None}])

    result = resolve_location_key_to_hex("nieistniejaca_lokacja", conn)
    assert result is None


# ── Test 2: _update_hex_world_state — fix #518 ───────────────────────────────

def test_update_hex_world_state_resolves_location_key_to_hex():
    """#518 FIX: Ruch z tekstu (brak q/r w result) → current_hex aktualizuje się przez location_key."""
    from app.services.turn_pipeline import _update_hex_world_state
    conn = _make_conn()
    _seed_world(conn, hexes=[{"q": 3, "r": 5, "location_key": "las_mglisty"}])
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()

    session_flags = {"current_hex": {"q": 0, "r": 0}}
    mechanic_result = {
        "action_type": "MOVEMENT",
        "outcome": "SUCCESS",
        "to_location_key": "las_mglisty",
        # brak destination_q i destination_r — tak jak z LLM intent parser
    }

    _update_hex_world_state(mechanic_result, session_flags, conn, 1)

    assert session_flags["current_hex"] == {"q": 3, "r": 5}, \
        f"current_hex powinno być (3,5), jest {session_flags['current_hex']}"


def test_update_hex_world_state_direct_coords_still_work():
    """Backward compat: gdy destination_q/r są podane (klik mapy) → nadal działa."""
    from app.services.turn_pipeline import _update_hex_world_state
    conn = _make_conn()
    _seed_world(conn, hexes=[{"q": 1, "r": 2, "location_key": None}])
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()

    session_flags = {"current_hex": {"q": 0, "r": 0}}
    mechanic_result = {
        "action_type": "MOVEMENT",
        "outcome": "SUCCESS",
        "destination_q": 1,
        "destination_r": 2,
        "to_location_key": "",
    }

    _update_hex_world_state(mechanic_result, session_flags, conn, 1)
    assert session_flags["current_hex"] == {"q": 1, "r": 2}


# ── Test 3: POST /travel endpoint ────────────────────────────────────────────

def test_travel_endpoint_accepts_target_location_key(monkeypatch):
    """POST /travel z target_location_key → 200 OK + arrived_hex set."""
    import importlib
    from fastapi.testclient import TestClient
    from app.main import app

    # Przygotuj bazę z hexem i lokacją
    import sqlite3 as _sq
    test_conn = _sq.connect("/data/ai_gm.db")
    test_conn.row_factory = _sq.Row

    # Sprawdź czy kampania testowa istnieje
    camp = test_conn.execute(
        "SELECT id FROM campaigns LIMIT 1"
    ).fetchone()
    if not camp:
        test_conn.close()
        pytest.skip("Brak kampanii w bazie — test wymaga aktywnej kampanii")

    campaign_id = camp["id"]
    char = test_conn.execute(
        "SELECT id FROM characters WHERE campaign_id = ? AND status = 'active' LIMIT 1",
        (campaign_id,)
    ).fetchone()
    if not char:
        test_conn.close()
        pytest.skip("Brak aktywnej postaci w kampanii")

    # Sprawdź czy jest hex z location_key
    hex_with_loc = test_conn.execute(
        "SELECT q, r, location_key FROM world_hexes "
        "WHERE location_key IS NOT NULL AND is_active = 1 LIMIT 1"
    ).fetchone()
    test_conn.close()

    if not hex_with_loc:
        pytest.skip("Brak hexa z location_key w bazie")

    client = TestClient(app)
    resp = client.post(
        f"/api/campaigns/{campaign_id}/travel",
        json={
            "character_id": char["id"],
            "target_location_key": hex_with_loc["location_key"]
        },
        headers={"Authorization": "Bearer test"}
    )
    # Endpoint musi istnieć (nie 404) i zwrócić poprawną odpowiedź lub known error
    assert resp.status_code != 404, f"Endpoint /travel nie istnieje (404). Zaimplementuj go."
    # Akceptujemy też 200 lub 400 (np. nie-sąsiad)
    assert resp.status_code in (200, 400, 422), f"Unexpected status {resp.status_code}"


# ── Test 4: Anty-desync guard ────────────────────────────────────────────────

def test_travel_narrated_without_move_logged():
    """Anty-desync: narracja zawiera marker podróży ale action_type != MOVEMENT → log + True."""
    from unittest.mock import patch, MagicMock
    import app.services.turn_pipeline as _tp

    narrative_with_travel = "Wyruszasz z karczmy i podróżujesz przez las do wioski."

    mock_logger = MagicMock()
    with patch.object(_tp, "logger", mock_logger):
        result = _tp._check_travel_desync(
            narrative=narrative_with_travel,
            action_type="DIALOGUE",  # nie MOVEMENT
            campaign_id=99,
        )

    assert result is True, "Guard powinien wykryć desync (True = wykryto)"
    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert "travel_narrated_without_move" in call_args[0], \
        f"Oczekiwano 'travel_narrated_without_move' w logu, args={call_args}"


def test_no_desync_when_movement(caplog):
    """Brak desyncu gdy action_type = MOVEMENT → guard nie loguje."""
    import logging
    from app.services.turn_pipeline import _check_travel_desync

    with caplog.at_level(logging.WARNING):
        result = _check_travel_desync(
            narrative="Wyruszasz na północ przez las.",
            action_type="MOVEMENT",
            campaign_id=99,
        )

    assert result is False, "Brak desyncu gdy MOVEMENT — guard powinien zwrócić False"


# ── Test 5: Keyword fast-path MOVE ──────────────────────────────────────────

def test_keyword_move_north_detected():
    """detect_move_intent('idę na północ', neighbors) → ('MOVEMENT', {direction: 'north'})."""
    from app.services.turn_pipeline import detect_move_intent

    neighbors = {
        "north": (0, -1), "south": (0, 1),
        "northeast": (1, -1), "northwest": (-1, 0),
        "southeast": (1, 0), "southwest": (-1, 1),
    }
    result = detect_move_intent("idę na północ", current_hex={"q": 0, "r": 0}, neighbors=neighbors)

    assert result is not None, "Kierunek 'północ' powinien być wykryty"
    assert result["action_type"] == "MOVEMENT"
    assert "destination_q" in result["params"] or "direction" in result["params"]


def test_keyword_no_false_positive():
    """detect_move_intent('atakuję goblina') → None (nie MOVEMENT)."""
    from app.services.turn_pipeline import detect_move_intent

    result = detect_move_intent("atakuję goblina", current_hex={"q": 0, "r": 0}, neighbors={})
    assert result is None, "Atak nie powinien być wykryty jako ruch"


# ── Test 6: [DONE] SSE payload zawiera current_hex ──────────────────────────

def test_done_payload_includes_current_hex():
    """_build_done_payload zwraca current_hex z session_flags."""
    from app.api.turns import _build_done_extra_payload

    conn = _make_conn()
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (42, ?)",
                 (json.dumps({"current_hex": {"q": 7, "r": -3}}),))
    conn.commit()

    payload = _build_done_extra_payload(campaign_id=42, conn=conn)
    assert "current_hex" in payload, "Brak current_hex w [DONE] payload"
    assert payload["current_hex"] == {"q": 7, "r": -3}


# ── Test 7: Onboarding — karta world_map (jak się poruszać) ──────────────────

def test_world_map_onboarding_triggers_on_hex_world():
    """Świat z hexem (current_hex) → karta 'world_map' raz, potem seen → brak."""
    from app.services.onboarding_service import inject_onboarding_to_out, MECHANIC_CARDS
    assert "world_map" in MECHANIC_CARDS

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE seen_mechanics (user_id INTEGER, mechanic_key TEXT)")
    conn.commit()

    # 1) Pierwsza tura z hexem → karta pokazana
    out = {"current_hex": {"q": 0, "r": -1}}
    inject_onboarding_to_out(out, user_id=777, conn=conn)
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "world_map" in keys, f"Brak karty world_map, dostano {keys}"

    # 2) Po oznaczeniu jako seen → już się nie pokazuje
    conn.execute("INSERT INTO seen_mechanics VALUES (777, 'world_map')")
    conn.commit()
    out2 = {"current_hex": {"q": 1, "r": -1}}
    inject_onboarding_to_out(out2, user_id=777, conn=conn)
    keys2 = [c["mechanic_key"] for c in out2["onboarding_cards"]]
    assert "world_map" not in keys2


def test_world_map_onboarding_skipped_without_hex():
    """Kampania bez świata hex (brak current_hex) → brak karty world_map."""
    from app.services.onboarding_service import inject_onboarding_to_out

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE seen_mechanics (user_id INTEGER, mechanic_key TEXT)")
    conn.commit()

    out = {}  # brak current_hex
    inject_onboarding_to_out(out, user_id=778, conn=conn)
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "world_map" not in keys
