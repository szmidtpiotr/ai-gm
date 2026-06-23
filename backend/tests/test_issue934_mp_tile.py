"""TDD: Issue #934 — kafelek Multiplayer musi pojawić się w ekranie Kampanii."""
import sys
import sqlite3
import pytest

sys.path.insert(0, "/app")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_campaign_modes_returns_multiplayer():
    """API /campaign-modes musi zwracać klucz 'multiplayer' w liście trybów."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200, f"endpoint failed: {r.status_code}"
    data = r.json()
    assert "modes" in data, "brak klucza 'modes' w response"
    keys = [m["key"] for m in data["modes"]]
    assert "multiplayer" in keys, f"brak klucza 'multiplayer' w modes: {keys}"


def test_campaign_modes_multiplayer_has_required_fields():
    """Tryb multiplayer musi mieć pola: key, label, available, description."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200
    modes = {m["key"]: m for m in r.json().get("modes", [])}
    assert "multiplayer" in modes, "brak trybu multiplayer"
    mp = modes["multiplayer"]
    assert "available" in mp, "brak pola 'available'"
    assert "label" in mp, "brak pola 'label'"
    assert isinstance(mp["available"], bool), "available musi być bool"


def test_campaign_modes_existing_modes_still_present():
    """Tryby nowa/gotowa/loch nadal muszą być w response (backward compat)."""
    r = client.get("/api/campaign-modes")
    assert r.status_code == 200
    keys = [m["key"] for m in r.json().get("modes", [])]
    for expected in ("nowa", "gotowa", "loch"):
        assert expected in keys, f"brakujący tryb backward-compat: {expected}"
