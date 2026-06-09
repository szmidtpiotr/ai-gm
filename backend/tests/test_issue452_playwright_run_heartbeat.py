"""TDD: Issue #452 (FADM-P16 follow-up) — group run SSE heartbeat / immediate hello.

Group run (`spec='regression'`) odpala ~114 testów; Playwright milczy ~90s na starcie
(zbieranie testów + launch przeglądarki). Proxy NPM (~60s idle timeout) zrywał SSE w ciszy
→ frontend "Błąd: network error". Fix: backend wysyła natychmiastowy hello event + heartbeat
podczas ciszy, by połączenie nigdy nie idle'owało ponad timeout proxy.
"""
import sys
sys.path.insert(0, '/app')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _admin_token():
    r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_playwright_run_emits_immediate_hello():
    """SSE strumień zaczyna się od natychmiastowego 'Uruchamianie…' (feedback + karmi proxy
    zanim Playwright wyśle cokolwiek po ~90s ciszy)."""
    token = _admin_token()
    # spec celowo taki, by agent szybko skończył/odrzucił — interesuje nas PIERWSZY event.
    r = client.post(
        "/api/test_runner/playwright-run",
        json={"spec": "regression/__nonexistent__.spec.js"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.text
    # Pierwszy event MUSI być hello — emitowany natychmiast, przed kontaktem z agentem.
    first_data = body.split("\n\n")[0]
    assert "Uruchamianie" in first_data, f"brak natychmiastowego hello; start strumienia: {body[:200]!r}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_playwright_run_still_streams_sse():
    """Endpoint nadal zwraca text/event-stream i kończy eventem done (kontrakt frontendu)."""
    token = _admin_token()
    r = client.post(
        "/api/test_runner/playwright-run",
        json={"spec": "regression/__nonexistent__.spec.js"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    # Strumień zawiera co najmniej jeden event 'data:' (hello i/lub done).
    assert "data:" in r.text


def test_playwright_run_requires_auth():
    """Bez tokenu admina → 401 (kontrakt bez zmian)."""
    r = client.post("/api/test_runner/playwright-run", json={"spec": "x.spec.js"})
    assert r.status_code == 401
