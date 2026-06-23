"""TDD: Issue #920 — Admin CMS panel for showcase content (GET/PUT JSON files)."""
import json
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app.routers.showcase as _showcase_mod
from app.main import app

client = TestClient(app)


def get_admin_token():
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    if resp2.status_code == 200:
        return resp2.json()["token"]
    raise RuntimeError("Cannot get admin token")


@pytest.fixture
def admin_token():
    return get_admin_token()


_SAMPLE_HISTORIA = {
    "intro": "Historia projektu.",
    "stages": [{"when": "kwiecień 2026", "title": "Start", "body": "Początki."}],
}

_SAMPLE_SWIAT = {
    "intro": "Świat gry.",
    "krainy": [{"name": "Kresy", "tag": "Pogranicze", "img": "x.webp", "desc": "Opis.", "anchor": "kresy", "available": True}],
}

_SAMPLES = {
    "historia": _SAMPLE_HISTORIA,
    "swiat": _SAMPLE_SWIAT,
    "changelog": {"entries": []},
    "faq": {"faq": []},
    "roadmap": {"kolumny": []},
}


@pytest.fixture
def data_dir(monkeypatch, tmp_path):
    """Patch SHOWCASE_DATA_DIR to a temp dir with sample data files."""
    for key, data in _SAMPLES.items():
        (tmp_path / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(_showcase_mod, "SHOWCASE_DATA_DIR", tmp_path)
    return tmp_path


# ─── Auth guard ──────────────────────────────────────────────────────────────

def test_showcase_get_requires_auth(data_dir):
    """GET /api/admin/showcase/{content} rejects unauthenticated."""
    r = client.get("/api/admin/showcase/historia")
    assert r.status_code == 401


def test_showcase_put_requires_auth(data_dir):
    """PUT /api/admin/showcase/{content} rejects unauthenticated."""
    r = client.put("/api/admin/showcase/historia", json={"data": []})
    assert r.status_code == 401


# ─── Valid content keys ──────────────────────────────────────────────────────

@pytest.mark.parametrize("content_key", ["historia", "swiat", "changelog", "faq", "roadmap"])
def test_showcase_get_returns_200_for_valid_keys(admin_token, data_dir, content_key):
    """GET returns 200 + JSON for all supported content keys."""
    r = client.get(
        f"/api/admin/showcase/{content_key}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert isinstance(body, dict)


def test_showcase_get_invalid_key_returns_404(admin_token, data_dir):
    """GET for unknown content key returns 404."""
    r = client.get(
        "/api/admin/showcase/nonexistent_key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


# ─── PUT saves data ──────────────────────────────────────────────────────────

def test_showcase_put_historia_saves(admin_token, data_dir):
    """PUT /api/admin/showcase/historia saves data and GET returns it back."""
    modified = dict(_SAMPLE_HISTORIA)
    modified["intro"] = "TEST_INTRO_920"

    r_put = client.put(
        "/api/admin/showcase/historia",
        json=modified,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_put.status_code == 200
    assert r_put.json().get("ok") is True

    r_check = client.get(
        "/api/admin/showcase/historia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_check.status_code == 200
    assert r_check.json().get("intro") == "TEST_INTRO_920"


def test_showcase_put_persists_to_file(admin_token, data_dir):
    """PUT actually writes file to disk (not just in-memory)."""
    modified = dict(_SAMPLE_HISTORIA)
    modified["intro"] = "DISK_TEST_920"

    client.put(
        "/api/admin/showcase/historia",
        json=modified,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    raw = (data_dir / "historia.json").read_text(encoding="utf-8")
    saved = json.loads(raw)
    assert saved.get("intro") == "DISK_TEST_920"


def test_showcase_put_invalid_key_returns_404(admin_token, data_dir):
    """PUT for unknown content key returns 404."""
    r = client.put(
        "/api/admin/showcase/hacker_key",
        json={"evil": "data"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


# ─── Backward compat — existing subscribe endpoint still works ────────────────

def test_showcase_subscribe_backward_compat():
    """POST /api/showcase/subscribe still returns 200 (existing W13 endpoint)."""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/showcase/subscribe", json={"email": email})
    assert r.status_code == 200
    assert r.json().get("ok") is True
