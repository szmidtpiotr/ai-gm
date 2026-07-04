"""TDD: Issue #1187 — domyślny guard na prefiksie /api/admin (jedna warstwa auth).

Twardnienie po #1154: zamiast per-router Depends (łatwo zapomnieć — stąd 7 gołych
routerów) wspólna warstwa chroni CAŁY namespace /api/admin/* domyślnie, ze świadomym
opt-outem (allowlist, np. dev-login).
"""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import admin_guard  # noqa: E402
from app.core.admin_guard import (  # noqa: E402
    ADMIN_AUTH_ALLOWLIST,
    admin_namespace_guard,
    is_admin_namespace,
    is_allowlisted,
)


def _build_app() -> FastAPI:
    """Minimalna aplikacja z samą warstwą — bez żadnego per-route Depends.

    Kluczowe: /api/admin/_probe NIE ma jawnej ochrony. Jeśli i tak zwraca 401
    bez tokena, to dowód że chroni WARSTWA, nie endpoint.
    """
    app = FastAPI()
    app.middleware("http")(admin_namespace_guard)

    @app.get("/api/admin/_probe")
    def _probe():
        return {"ok": True}

    @app.post("/api/admin/dev-login")
    def _dev_login():
        return {"token": "fake"}

    @app.get("/api/health")
    def _health():
        return {"status": "ok"}

    @app.get("/api/admin-spectate/users")
    def _spectate():
        return {"users": []}

    return app


# ─── Test główny: bramka namespace ───────────────────────────────────────────

def test_bare_admin_endpoint_without_token_is_401(monkeypatch):
    """Nowy /api/admin/_probe bez jawnego Depends → 401 bez tokena (chroni warstwa)."""
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: False)
    client = TestClient(_build_app())
    r = client.get("/api/admin/_probe")
    assert r.status_code == 401


def test_bare_admin_endpoint_with_valid_token_is_200(monkeypatch):
    """Ten sam endpoint z ważnym tokenem → 200."""
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: t == "good")
    client = TestClient(_build_app())
    r = client.get("/api/admin/_probe", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_invalid_token_is_401(monkeypatch):
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: t == "good")
    client = TestClient(_build_app())
    r = client.get("/api/admin/_probe", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


# ─── Świadomy opt-out (allowlist) ────────────────────────────────────────────

def test_dev_login_is_allowlisted_open_without_token(monkeypatch):
    """dev-login wydaje token — musi być osiągalny zanim token istnieje."""
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: False)
    client = TestClient(_build_app())
    r = client.post("/api/admin/dev-login")
    assert r.status_code == 200


def test_dev_login_in_allowlist_set():
    assert "/api/admin/dev-login" in ADMIN_AUTH_ALLOWLIST


# ─── Scoping: warstwa nie dotyka niczego poza /api/admin ─────────────────────

def test_non_admin_path_open_without_token(monkeypatch):
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: False)
    client = TestClient(_build_app())
    assert client.get("/api/health").status_code == 200


def test_admin_spectate_is_not_admin_namespace(monkeypatch):
    """'/api/admin-spectate' NIE jest pod '/api/admin/' — gracz-obserwator wolny."""
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: False)
    client = TestClient(_build_app())
    assert client.get("/api/admin-spectate/users").status_code == 200


def test_is_admin_namespace_boundary():
    assert is_admin_namespace("/api/admin")
    assert is_admin_namespace("/api/admin/")
    assert is_admin_namespace("/api/admin/sandbox/heroes")
    assert not is_admin_namespace("/api/admin-spectate/users")
    assert not is_admin_namespace("/api/administration")
    assert not is_admin_namespace("/api/health")


def test_options_preflight_bypasses_guard(monkeypatch):
    """CORS preflight (OPTIONS, bez auth) nie może dostać 401."""
    monkeypatch.setattr(admin_guard, "verify_admin_token", lambda t: False)
    app = _build_app()

    @app.options("/api/admin/_probe")
    def _probe_options():
        return {}

    client = TestClient(app)
    r = client.options("/api/admin/_probe")
    assert r.status_code != 401


def test_is_allowlisted_exact_match():
    assert is_allowlisted("/api/admin/dev-login")
    assert not is_allowlisted("/api/admin/dev-login/extra")
    assert not is_allowlisted("/api/admin/sandbox/heroes")


# ─── Backward compat: warstwa faktycznie wpięta w produkcyjną aplikację ──────

def test_guard_registered_on_main_app():
    """Warstwa musi być zarejestrowana w app.main — inaczej nie chroni nic."""
    from app.main import app as main_app

    dispatchers = [mw.kwargs.get("dispatch") for mw in main_app.user_middleware]
    assert admin_namespace_guard in dispatchers
