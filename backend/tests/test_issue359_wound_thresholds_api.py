"""TDD: Issue #359 — C6 Ujednolicenie progów ran: endpoint + frontend sync."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─── Backend: endpoint GET /api/config/wound-thresholds ──────────────────────

def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_wound_threshold_endpoint_exists():
    """GET /api/config/wound-thresholds musi zwracać HTTP 200."""
    resp = _client().get("/api/config/wound-thresholds")
    assert resp.status_code == 200, (
        f"Endpoint nie istnieje lub błąd: status={resp.status_code}"
    )


def test_wound_threshold_endpoint_returns_json():
    """Endpoint zwraca JSON."""
    resp = _client().get("/api/config/wound-thresholds")
    assert resp.headers["content-type"].startswith("application/json"), (
        f"Content-Type: {resp.headers.get('content-type')}"
    )
    data = resp.json()
    assert isinstance(data, dict)


def test_wound_threshold_has_required_keys():
    """Odpowiedź ma klucze: healthy_pct, moderate_pct, critical_pct."""
    resp = _client().get("/api/config/wound-thresholds")
    data = resp.json()
    for key in ("healthy_pct", "moderate_pct", "critical_pct"):
        assert key in data, f"Brak klucza '{key}' w odpowiedzi: {data}"


def test_wound_threshold_values_match_wound_utils():
    """Progi muszą odpowiadać wartościom z wound_utils.py (75, 50, 25)."""
    resp = _client().get("/api/config/wound-thresholds")
    data = resp.json()
    assert data["healthy_pct"] == 75, f"healthy_pct: oczekiwano 75, dostaliśmy {data.get('healthy_pct')}"
    assert data["moderate_pct"] == 50, f"moderate_pct: oczekiwano 50, dostaliśmy {data.get('moderate_pct')}"
    assert data["critical_pct"] == 25, f"critical_pct: oczekiwano 25, dostaliśmy {data.get('critical_pct')}"


# ─── Backend: wound_utils eksportuje stałe ────────────────────────────────────

def test_wound_utils_exports_healthy_threshold():
    """wound_utils.py eksportuje WOUND_HEALTHY_PCT = 75."""
    from app.services.wound_utils import WOUND_HEALTHY_PCT
    assert WOUND_HEALTHY_PCT == 75


def test_wound_utils_exports_moderate_threshold():
    """wound_utils.py eksportuje WOUND_MODERATE_PCT = 50."""
    from app.services.wound_utils import WOUND_MODERATE_PCT
    assert WOUND_MODERATE_PCT == 50


def test_wound_utils_exports_critical_threshold():
    """wound_utils.py eksportuje WOUND_CRITICAL_PCT = 25."""
    from app.services.wound_utils import WOUND_CRITICAL_PCT
    assert WOUND_CRITICAL_PCT == 25


# ─── Backend: wound_penalty nadal działa poprawnie po refaktorze ──────────────

def test_wound_penalty_still_works_after_constants_extracted():
    """wound_penalty(hp, max) nadal zwraca poprawne wartości po wyciągnięciu stałych."""
    from app.services.wound_utils import wound_penalty
    assert wound_penalty(80, 100) == 0   # >75% → 0
    assert wound_penalty(60, 100) == -1  # >50% → -1
    assert wound_penalty(35, 100) == -2  # >25% → -2
    assert wound_penalty(20, 100) == -4  # ≤25% → -4


# Frontendowe testy statyczne (app.js starego UI) usunięte —
# legacy frontend/front/ skasowany 2026-07-18, ŻAR (front-v2) jest jedynym UI gracza.
