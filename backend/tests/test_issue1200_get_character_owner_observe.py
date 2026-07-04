"""TDD: Issue #1200 — get_character owner-check w trybie OBSERWACJI (nie blokuje).

get_character jest wołany z 11 miejsc player-UI bez user_id → twardy 403 zepsułby grę.
Zamiast tego: gdy przychodzi JWT innego usera niż właściciel bohatera, logujemy
`owner_check_would_block`, ale ZWRACAMY 200. Enforcement (403) dopiero w Fazie 2.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.jwt_service import issue_access_token

client = TestClient(app)

OWNER_UID = 1
STRANGER_UID = 99999999


def _char_owned_by_user1():
    r = client.get("/api/heroes", params={"user_id": OWNER_UID})
    assert r.status_code == 200
    heroes = r.json().get("heroes") or r.json().get("characters") or []
    for h in heroes:
        if int(h["id"]) != 999420:  # pomiń Mizela (konto Piotra)
            return int(h["id"])
    raise RuntimeError("brak testowego bohatera usera 1")


def _tok(uid):
    return issue_access_token(user_id=uid, username=f"u{uid}", role="player", is_admin=0)


# ─── Test główny — cudzy JWT NIE blokuje (obserwacja), ale loguje ────────────

def test_wrong_jwt_still_returns_200(caplog):
    """Bohater usera 1 + JWT obcego usera → 200 (NIE 403) i wpis would_block w logach."""
    cid = _char_owned_by_user1()
    with caplog.at_level("WARNING"):
        r = client.get(f"/api/characters/{cid}",
                       headers={"Authorization": f"Bearer {_tok(STRANGER_UID)}"})
    assert r.status_code == 200, f"tryb obserwacji nie może blokować (status {r.status_code})"
    assert "owner_check_would_block" in caplog.text, "brak logu owner_check_would_block"


def test_owner_jwt_ok_no_log(caplog):
    """Właściciel z własnym JWT → 200 i BRAK wpisu would_block."""
    cid = _char_owned_by_user1()
    with caplog.at_level("WARNING"):
        r = client.get(f"/api/characters/{cid}",
                       headers={"Authorization": f"Bearer {_tok(OWNER_UID)}"})
    assert r.status_code == 200
    assert "owner_check_would_block" not in caplog.text


# ─── Backward compat — bez tokena dalej działa (11 callerów UI) ──────────────

def test_no_auth_still_returns_200():
    """Brak nagłówka (stary caller bez JWT) → 200 jak dotąd."""
    cid = _char_owned_by_user1()
    r = client.get(f"/api/characters/{cid}")
    assert r.status_code == 200
