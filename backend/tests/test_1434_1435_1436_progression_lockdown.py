"""AUDIT Krok 5 — domknięcie god-mode progresji postaci.

Covers:
  #1434  test_sheet_patch_ignores_authoritative_fields   — PATCH /sheet whitelist/blacklist
  #1435  test_finalize_sheet_once                          — finalize one-shot → 409
  #1436  test_xp_spend_race                                — BEGIN IMMEDIATE double-spend guard
  #1436  test_spell_spend_single_conn                      — learn on one connection (no free spell)
  #1436  test_int_bump_recomputes_mana                     — INT → max_mana for scholar
  #1436  test_grant_mg_strict_auth                         — grant-mg requires signed JWT

Run inside the DEV backend container:
    docker exec ai-gm-dev-backend-1 pytest tests/test_1434_1435_1436_progression_lockdown.py -v
"""
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

DB_PATH = "/data/ai_gm.db"


# ── helpers ──────────────────────────────────────────────────────────────────

def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _token(user_id: int) -> str:
    from app.services import jwt_service
    return jwt_service.issue_access_token(
        user_id=user_id, username=f"u{user_id}", role="player", is_admin=0
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _insert_char(char_id: int, user_id: int, sheet: dict, campaign_id=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, campaign_id, user_id, name, system_id, race, sheet_json)
               VALUES (?, ?, ?, ?, 'v1', 'human', ?)""",
            (char_id, campaign_id, user_id, f"[AUDIT_K5] {char_id}",
             json.dumps(sheet, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _read_sheet(char_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else {}
    finally:
        conn.close()


def _set_sheet_field(char_id: int, **fields):
    sheet = _read_sheet(char_id)
    sheet.update(fields)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                     (json.dumps(sheet, ensure_ascii=False), char_id))
        conn.commit()
    finally:
        conn.close()


def _cleanup(*char_ids: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        for cid in char_ids:
            conn.execute("DELETE FROM characters WHERE id = ?", (cid,))
            conn.execute("DELETE FROM character_spells WHERE character_id = ?", (cid,))
            conn.execute("DELETE FROM character_xp_grants WHERE character_id = ?", (cid,))
            conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (cid,))
        conn.commit()
    finally:
        conn.close()


def _base_sheet(archetype="warrior", **over):
    sheet = {
        "archetype": archetype,
        "level": 3,
        "xp_available": 100,
        "xp_lifetime_earned": 300,
        "max_hp": 20,
        "current_hp": 20,
        "max_mana": 20,
        "current_mana": 20,
        "arcane_points": 1,
        "gold_gp": 50,
        "stats": {"STR": 12, "DEX": 10, "CON": 12, "INT": 13, "WIS": 10, "CHA": 10, "LCK": 10},
        "skills": {"athletics": 0},
    }
    sheet.update(over)
    return sheet


# ── #1434 — PATCH /sheet ignores authoritative fields ────────────────────────

def test_sheet_patch_ignores_authoritative_fields():
    cid, owner, intruder = 999_434_001, 770_434, 770_435
    _insert_char(cid, owner, _base_sheet())
    try:
        c = _client()
        # Mixed body: authoritative keys + one legit cosmetic key.
        r = c.patch(
            f"/api/characters/{cid}/sheet",
            headers=_auth(owner),
            json={"sheet_json": {
                "xp_available": 999999, "level": 20, "max_hp": 9999,
                "stats": {"STR": 20}, "skills": {"athletics": 5},
                "gold_gp": 999999, "notes": "moja notatka",
            }},
        )
        assert r.status_code == 200, r.text
        s = _read_sheet(cid)
        # Authoritative fields untouched.
        assert s["xp_available"] == 100, s["xp_available"]
        assert s["level"] == 3
        assert s["max_hp"] == 20
        assert s["stats"]["STR"] == 12
        assert s["skills"]["athletics"] == 0
        assert s["gold_gp"] == 50
        # Whitelisted cosmetic field written.
        assert s["notes"] == "moja notatka"

        # Body with ONLY forbidden keys → 422 (nothing editable).
        r2 = c.patch(
            f"/api/characters/{cid}/sheet",
            headers=_auth(owner),
            json={"sheet_json": {"level": 50, "xp_available": 1}},
        )
        assert r2.status_code == 422, r2.text
        assert _read_sheet(cid)["level"] == 3

        # Patching someone else's hero → 403.
        r3 = c.patch(
            f"/api/characters/{cid}/sheet",
            headers=_auth(intruder),
            json={"sheet_json": {"notes": "hijack"}},
        )
        assert r3.status_code == 403, r3.text
    finally:
        _cleanup(cid)


# ── #1435 — finalize-sheet one-shot ──────────────────────────────────────────

def test_finalize_sheet_once():
    cid, owner = 999_435_001, 770_436
    _insert_char(cid, owner, _base_sheet(current_hp=5))
    try:
        c = _client()
        # First finalize succeeds and stamps the flag.
        r1 = c.post(f"/api/characters/{cid}/finalize-sheet", json={})
        assert r1.status_code == 200, r1.text
        assert _read_sheet(cid).get("creation_finalized") is True

        # Re-wound the character mid-campaign.
        _set_sheet_field(cid, current_hp=5)

        # Second finalize is rejected — no free heal / respec.
        r2 = c.post(f"/api/characters/{cid}/finalize-sheet", json={})
        assert r2.status_code == 409, r2.text
        assert _read_sheet(cid)["current_hp"] == 5
    finally:
        _cleanup(cid)


# ── #1436(1) — double-spend race guarded by BEGIN IMMEDIATE ──────────────────

def test_xp_spend_race():
    cid, owner = 999_436_001, 770_437
    # Exactly enough XP for ONE rank-1 skill purchase (cost 100).
    _insert_char(cid, owner, _base_sheet(xp_available=100, skills={"athletics": 0}))
    try:
        headers = _auth(owner)

        def _buy():
            # Fresh client per thread (independent request pipeline).
            return _client().post(
                f"/api/characters/{cid}/xp/spend-skill",
                headers=headers, json={"skill_key": "athletics"},
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as ex:
            codes = sorted(f.result() for f in [ex.submit(_buy), ex.submit(_buy)])

        # Exactly one success, one rejected — never two ranks for one payment.
        assert codes.count(200) == 1, f"codes={codes}"
        assert codes.count(200) + sum(1 for x in codes if x == 400) == 2, f"codes={codes}"
        s = _read_sheet(cid)
        assert s["xp_available"] == 0, s["xp_available"]
        assert s["skills"]["athletics"] == 1
    finally:
        _cleanup(cid)


# ── #1436(2) — spell learn on a single connection (no free spell) ────────────

def test_spell_spend_single_conn():
    cid, owner = 999_436_002, 770_438
    # campaign_id must be non-null for the XP-grant ledger (FK enforcement is off).
    _insert_char(cid, owner, _base_sheet(archetype="scholar", xp_available=100),
                 campaign_id=999_436_902)
    try:
        c = _client()
        r = c.post(
            f"/api/characters/{cid}/xp/spend-spell-learn",
            headers=_auth(owner),
            json={"spell_key": "magic_bolt", "user_id": owner},
        )
        assert r.status_code == 200, r.text
        # XP debited exactly once (75) …
        assert _read_sheet(cid)["xp_available"] == 25
        # … AND the spell row + ledger entry both committed on the same conn.
        conn = sqlite3.connect(DB_PATH)
        try:
            spell = conn.execute(
                "SELECT rank FROM character_spells WHERE character_id = ? AND spell_key = 'magic_bolt'",
                (cid,),
            ).fetchone()
            grant = conn.execute(
                "SELECT amount FROM character_xp_grants WHERE character_id = ? AND source = 'spell_learn'",
                (cid,),
            ).fetchone()
        finally:
            conn.close()
        assert spell is not None and int(spell[0]) == 1
        assert grant is not None and int(grant[0]) == -75
    finally:
        _cleanup(cid)


# ── #1436(3) — INT bump recomputes scholar max_mana ──────────────────────────

def test_int_bump_recomputes_mana():
    cid, owner = 999_436_003, 770_439
    # INT 13 (mod +1) → 14 (mod +2): delta +1 mod × level 3 = +3 mana.
    _insert_char(cid, owner, _base_sheet(
        archetype="scholar", xp_available=99999, max_mana=20,
        stats={"STR": 10, "DEX": 10, "CON": 10, "INT": 13, "WIS": 10, "CHA": 10, "LCK": 10},
    ))
    try:
        r = _client().post(
            f"/api/characters/{cid}/xp/spend-stat",
            headers=_auth(owner), json={"stat_key": "INT"},
        )
        if r.status_code == 400 and "cost" in r.text.lower():
            pytest.skip("stat point cost not configured in this DB")
        assert r.status_code == 200, r.text
        s = _read_sheet(cid)
        assert s["stats"]["INT"] == 14
        assert s["max_mana"] == 23, s["max_mana"]
    finally:
        _cleanup(cid)


# ── #1436(4) — grant-mg requires a signed JWT (legacy ?user_id ignored) ───────

def test_grant_mg_strict_auth():
    cid, owner = 999_436_004, 770_440
    _insert_char(cid, owner, _base_sheet())
    try:
        c = _client()
        # No Authorization header, spoofable ?user_id only → 401 (not trusted).
        r = c.post(
            f"/api/characters/{cid}/xp/grant-mg",
            params={"user_id": owner},
            json={"amount": 500, "reason": "test grant"},
        )
        assert r.status_code == 401, r.text

        # A valid signed token gets PAST the auth gate (no campaign → 403/404,
        # but crucially NOT 401).
        r2 = c.post(
            f"/api/characters/{cid}/xp/grant-mg",
            headers=_auth(owner),
            json={"amount": 500, "reason": "test grant"},
        )
        assert r2.status_code != 401, r2.text
    finally:
        _cleanup(cid)
