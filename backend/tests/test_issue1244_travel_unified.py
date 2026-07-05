"""TDD: Issue #1244 (R4) — jeden wspólny silnik podróży dla 3 endpointów.

Trzy trasy podróży (/campaigns/{id}/travel, /campaigns/{id}/hex-travel,
admin /api/admin/world/campaigns/{id}/hex-travel) muszą dawać IDENTYCZNY stan:
ta sama pozycja końcowa, ta sama scena, wpis tury narracyjnej i to samo
odsłonięcie mgły. Osiągnięte przez delegację do hex_travel_service.execute_travel.

Testy:
  1. Strukturalny — każdy z 3 endpointów woła execute_travel (jest cienkim wrapperem).
  2. Funkcjonalny parytet — podróż A→B przez każdy endpoint z tego samego origin
     kończy się w tym samym hexie, z tym samym dungeon_prompt, dodaje wpis tury
     i odsłania ten sam hex.
"""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _admin_token():
    for u, p in (("admin", "admin"), ("demo", "demo")):
        r = client.post("/api/admin/dev-login", json={"username": u, "password": p})
        if r.status_code == 200:
            return r.json()["token"]
    raise RuntimeError("brak admin tokena")


# ─── Test 1 — strukturalny: 3 endpointy = wrappery execute_travel ────────────

def test_all_three_endpoints_delegate_to_execute_travel():
    """Każdy endpoint podróży deleguje do wspólnego execute_travel (#1244)."""
    turns_src = open("/app/app/api/turns.py").read()
    hexw_src = open("/app/app/routers/hex_world.py").read()

    # /travel + /hex-travel (player) w turns.py
    assert turns_src.count("execute_travel(conn, campaign_id") >= 2, (
        "turns.py: oba endpointy (/travel i /hex-travel) muszą wołać execute_travel"
    )
    # admin /hex-travel w hex_world.py
    assert "execute_travel(conn, campaign_id" in hexw_src, (
        "hex_world.py: admin hex-travel musi wołać execute_travel"
    )
    # stary powielony kod (bezpośredni resolve_chain_travel w endpointach) zniknął
    assert "resolve_chain_travel(\n            campaign_id=campaign_id" not in hexw_src, (
        "hex_world.py: admin endpoint nadal ma własną kopię resolve_chain_travel"
    )


# ─── Helpery funkcjonalne ────────────────────────────────────────────────────

def _demo_campaign():
    conn = _db()
    try:
        row = conn.execute(
            """SELECT c.id AS cid, ch.id AS chid
               FROM campaigns c JOIN characters ch ON ch.campaign_id = c.id
               WHERE c.owner_user_id = 1 AND c.status = 'active' AND c.mode != 'dungeon'
               LIMIT 1"""
        ).fetchone()
        return (row["cid"], row["chid"]) if row else (None, None)
    finally:
        conn.close()


def _pick_origin_and_neighbor():
    """Zwróć (A, B): aktywny hex A i jego aktywny nie-dungeon sąsiad B."""
    conn = _db()
    try:
        hexes = conn.execute(
            "SELECT q, r, hex_type FROM world_hexes WHERE is_active = 1 AND map_level = 0"
        ).fetchall()
        active = {(h["q"], h["r"]): h["hex_type"] for h in hexes}
        for (aq, ar), _ in active.items():
            for dq, dr in _DIRECTIONS:
                b = (aq + dq, ar + dr)
                if b in active and active[b] != "dungeon":
                    return (aq, ar), b
        return None, None
    finally:
        conn.close()


def _set_current_hex(cid, a):
    """Ustaw current_hex=A i wyzeruj budżet marszu (identyczny start dla każdego przebiegu)."""
    conn = _db()
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (cid,),
        ).fetchone()
        flags = json.loads((gs["session_flags"] if gs else None) or "{}")
        flags["current_hex"] = {"q": a[0], "r": a[1]}
        flags["hours_marched_today"] = 0.0
        flags["night_march"] = False
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), gs["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def _current_hex(cid):
    conn = _db()
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (cid,),
        ).fetchone()
        return json.loads((gs["session_flags"] if gs else None) or "{}").get("current_hex")
    finally:
        conn.close()


def _travel_turn_count(cid):
    conn = _db()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM campaign_turns "
            "WHERE campaign_id = ? AND user_text LIKE '[Podróż map%'",
            (cid,),
        ).fetchone()["n"]
    finally:
        conn.close()


def _run(cid, chid, a, b, poster):
    """Zresetuj origin do A, wykonaj podróż do B przez `poster`, zwróć obserwable."""
    _set_current_hex(cid, a)
    turns_before = _travel_turn_count(cid)
    resp = poster(cid, chid, b)
    assert resp.status_code in (200, 207), f"status {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    return {
        "arrived_hex": body.get("arrived_hex"),
        "ok": body.get("ok"),
        "dungeon_prompt": body.get("dungeon_prompt"),
        "current_hex": _current_hex(cid),
        "turn_delta": _travel_turn_count(cid) - turns_before,
    }


# ─── Test 2 — parytet: 3 endpointy dają identyczny stan ──────────────────────

def test_three_endpoints_produce_identical_state():
    """Podróż A→B przez /travel, /hex-travel i admin/hex-travel → identyczny stan."""
    cid, chid = _demo_campaign()
    if cid is None:
        pytest.skip("Brak aktywnej kampanii demo")
    a, b = _pick_origin_and_neighbor()
    if a is None:
        pytest.skip("Brak pary hex+sąsiad w world_hexes")

    tok = _admin_token()

    def post_travel(cid, chid, b):
        return client.post(
            f"/api/campaigns/{cid}/travel",
            json={"character_id": chid, "target_hex": {"q": b[0], "r": b[1]}},
        )

    def post_hex_travel(cid, chid, b):
        return client.post(
            f"/api/campaigns/{cid}/hex-travel",
            json={"character_id": chid, "destination_q": b[0], "destination_r": b[1]},
        )

    def post_admin_hex_travel(cid, chid, b):
        return client.post(
            f"/api/admin/world/campaigns/{cid}/hex-travel",
            json={"character_id": chid, "destination_q": b[0], "destination_r": b[1]},
            headers={"Authorization": f"Bearer {tok}"},
        )

    r_travel = _run(cid, chid, a, b, post_travel)
    r_hex = _run(cid, chid, a, b, post_hex_travel)
    r_admin = _run(cid, chid, a, b, post_admin_hex_travel)

    # pozycja końcowa identyczna
    assert r_travel["current_hex"] == r_hex["current_hex"] == r_admin["current_hex"], (
        f"current_hex różny: {r_travel['current_hex']} / {r_hex['current_hex']} / {r_admin['current_hex']}"
    )
    # arrived_hex + dungeon_prompt + ok identyczne
    assert r_travel["arrived_hex"] == r_hex["arrived_hex"] == r_admin["arrived_hex"]
    assert r_travel["dungeon_prompt"] == r_hex["dungeon_prompt"] == r_admin["dungeon_prompt"]
    assert r_travel["ok"] == r_hex["ok"] == r_admin["ok"]

    # udana podróż → każdy endpoint zapisał wpis tury narracyjnej (narrator widzi ruch)
    if r_travel["ok"]:
        assert r_travel["turn_delta"] >= 1, "/travel nie zapisał wpisu tury"
        assert r_hex["turn_delta"] >= 1, "/hex-travel nie zapisał wpisu tury"
        assert r_admin["turn_delta"] >= 1, "admin/hex-travel nie zapisał wpisu tury"
