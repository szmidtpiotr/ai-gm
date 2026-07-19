"""AUDIT #1437 (P0) — POST /characters/{id}/gold is SPEND-ONLY.

Ownership alone does NOT close the hole: a player owns their own hero, so a
positive `delta` was a master self-cheat (unlimited gold on your own character).
Grants must be server-authoritative (economy_service.change_gold) only; the client
endpoint may DEBIT (negative delta) but never CREDIT (positive delta).
"""
import sqlite3
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/app")

from app.api.inventory import GoldDeltaRequest, post_character_gold_delta
from app.services import jwt_service, loot_service


def _seed(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, user_id INTEGER)")
        conn.execute("INSERT INTO characters(id, user_id) VALUES (10, 1)")  # owned by user 1
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "game.db"
    _seed(str(p))
    import app.core.db_runtime as db_runtime
    monkeypatch.setattr(db_runtime, "resolve_db_path", lambda: str(p))
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-key-32-characters-long")
    monkeypatch.delenv("ALLOW_LEGACY_USERID", raising=False)
    return str(p)


def _token(uid: int) -> str:
    return "Bearer " + jwt_service.issue_access_token(
        user_id=uid, username="u", role="player", is_admin=0
    )


def test_gold_delta_endpoint_no_positive_grant(db):
    """Owner posting a POSITIVE delta on their OWN character → 403 (self-cheat closed)."""
    with pytest.raises(HTTPException) as ei:
        post_character_gold_delta(10, GoldDeltaRequest(delta=100_000_000, reason="cheat"), _token(1))
    assert ei.value.status_code == 403


def test_gold_delta_endpoint_spend_allowed(db, monkeypatch):
    """Owner posting a NEGATIVE delta (spend) passes the guard and reaches the economy."""
    monkeypatch.setattr(
        loot_service, "apply_character_gold_delta",
        lambda cid, d, r=None: 40,
    )
    out = post_character_gold_delta(10, GoldDeltaRequest(delta=-60, reason="spend"), _token(1))
    assert out["ok"] is True
    assert out["data"]["gold_gp"] == 40


def test_gold_delta_endpoint_cross_user_rejected(db):
    """A non-owner is still rejected by the ownership guard (spend attempt too)."""
    with pytest.raises(HTTPException) as ei:
        post_character_gold_delta(10, GoldDeltaRequest(delta=-10, reason="x"), _token(2))
    assert ei.value.status_code == 403
