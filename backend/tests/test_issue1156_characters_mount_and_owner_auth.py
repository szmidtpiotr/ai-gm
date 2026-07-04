"""TDD: Issue #1156 — characters router podwójnie zamontowany + brak owner-auth na status/sheet.

1. characters.router był montowany na /api/* ORAZ bare /* → ~39 tras podwojonych,
   w tym nieautoryzowany /characters/{id}/sheet poza prefiksem. Bare mount usuwamy.
2. update_character_status i get_character_sheet nie brały user_id/właściciela —
   dodajemy owner-check wzorem delete_character (row.user_id != user_id → 403).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

WRONG_OWNER = 99999999  # użytkownik który na pewno nie jest właścicielem


def _a_char_owned_by_user1():
    """Zwraca id aktywnego bohatera usera 1 (pomija Mizela 999420 — konto Piotra)."""
    r = client.get("/api/heroes", params={"user_id": 1})
    assert r.status_code == 200, "GET /api/heroes nie działa"
    heroes = r.json().get("heroes") or r.json().get("characters") or []
    for h in heroes:
        if int(h["id"]) != 999420:
            return int(h["id"])
    raise RuntimeError("brak testowego bohatera usera 1")


# ─── Test główny #1 — podwójny bare mount usunięty ───────────────────────────

def test_bare_heroes_mount_removed():
    """Bare /heroes (bez prefiksu /api) nie może już istnieć."""
    r = client.get("/heroes", params={"user_id": 1})
    assert r.status_code == 404, f"bare /heroes wciąż zamontowane (status {r.status_code})"


def test_api_heroes_still_works():
    """Prefiksowane /api/heroes działa dalej."""
    r = client.get("/api/heroes", params={"user_id": 1})
    assert r.status_code == 200


# ─── Test główny #2 — owner-auth na status ───────────────────────────────────

def test_status_requires_user_id():
    """PATCH status bez user_id → 422 (parametr wymagany)."""
    cid = _a_char_owned_by_user1()
    r = client.patch(f"/api/characters/{cid}/status", json={"status": "idle"})
    assert r.status_code == 422, f"status bez user_id przeszło (status {r.status_code})"


def test_status_wrong_owner_403():
    """PATCH status z cudzym user_id → 403 (bez mutacji)."""
    cid = _a_char_owned_by_user1()
    r = client.patch(f"/api/characters/{cid}/status",
                     params={"user_id": WRONG_OWNER}, json={"status": "idle"})
    assert r.status_code == 403, f"status obcego właściciela nie zablokowany (status {r.status_code})"


# ─── Test główny #3 — owner-auth na sheet ────────────────────────────────────

def test_sheet_requires_user_id():
    """GET sheet bez user_id → 422."""
    cid = _a_char_owned_by_user1()
    r = client.get(f"/api/characters/{cid}/sheet")
    assert r.status_code == 422, f"sheet bez user_id przeszło (status {r.status_code})"


def test_sheet_wrong_owner_403():
    """GET sheet z cudzym user_id → 403."""
    cid = _a_char_owned_by_user1()
    r = client.get(f"/api/characters/{cid}/sheet", params={"user_id": WRONG_OWNER})
    assert r.status_code == 403


# ─── Backward compat — właściciel dalej ma dostęp ────────────────────────────

def test_sheet_owner_ok():
    """Właściciel (user 1) dalej dostaje sheet."""
    cid = _a_char_owned_by_user1()
    r = client.get(f"/api/characters/{cid}/sheet", params={"user_id": 1})
    assert r.status_code == 200
