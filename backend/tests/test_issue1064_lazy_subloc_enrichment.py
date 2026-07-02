"""TDD: Issue #1064 — Lazy LLM-enrichment sub-lokacji przy pierwszym wejściu gracza (FAZA ML-2)."""
import pytest
import sqlite3
from unittest.mock import patch

import sys
sys.path.insert(0, '/app')

from app.services.world_service import (
    generate_sublocs_for_settlement,
    maybe_lazy_enrich_subloc,
)


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            label TEXT,
            description TEXT DEFAULT '',
            location_type TEXT,
            location_subtype TEXT,
            parent_key TEXT,
            safe_for_rest INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 0,
            review_status TEXT DEFAULT 'pending_review',
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'auto_generated',
            ai_generated INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO game_locations
            (key, label, description, location_type, location_subtype,
             is_active, approved, review_status, created_by, ai_generated)
        VALUES
            ('wolanka', 'Wolanka', 'Osada nad Rudą Gnilą.',
             'settlement', 'village', 1, 1, 'permanent', 'admin_manual', 0)
    """)
    conn.commit()
    return conn


_MOCK_LLM_RESP = """{
  "sublocs": [
    {"key": "wolanka_smithy", "label": "Kuźnia Pod Czarnym Kowadłem", "description": "Mistrz Wulfgar, zapach wypalanych metali."}
  ]
}"""


# ── Test główny ────────────────────────────────────────────────────────────────

def test_lazy_enrich_triggers_on_generic_subloc_first_entry(mem_db):
    """First entry into a generic (ai_generated=0) sub-loc triggers LLM enrichment."""
    generate_sublocs_for_settlement(mem_db, 'wolanka', ['smithy'])

    with patch('app.services.world_service.generate_chat', return_value=_MOCK_LLM_RESP) as mock_llm:
        result = maybe_lazy_enrich_subloc(mem_db, 'wolanka_smithy')

    assert result is True
    assert mock_llm.called

    row = mem_db.execute(
        "SELECT label, description, ai_generated FROM game_locations WHERE key='wolanka_smithy'"
    ).fetchone()
    assert row['ai_generated'] == 1
    assert row['label'] == 'Kuźnia Pod Czarnym Kowadłem'
    assert 'Wulfgar' in row['description']


def test_lazy_enrich_second_entry_does_not_call_llm_again(mem_db):
    """Lazy = once. Second entry on an already-enriched sub-loc must NOT call the LLM."""
    generate_sublocs_for_settlement(mem_db, 'wolanka', ['smithy'])

    with patch('app.services.world_service.generate_chat', return_value=_MOCK_LLM_RESP):
        maybe_lazy_enrich_subloc(mem_db, 'wolanka_smithy')

    with patch('app.services.world_service.generate_chat', return_value=_MOCK_LLM_RESP) as mock_llm_2:
        result = maybe_lazy_enrich_subloc(mem_db, 'wolanka_smithy')

    assert result is False
    assert not mock_llm_2.called


def test_lazy_enrich_skips_macro_location(mem_db):
    """Only location_type='sub' rows are lazy-enriched; macro (settlement) entries are a no-op."""
    with patch('app.services.world_service.generate_chat') as mock_llm:
        result = maybe_lazy_enrich_subloc(mem_db, 'wolanka')

    assert result is False
    assert not mock_llm.called


def test_lazy_enrich_unknown_key_returns_false(mem_db):
    """Unknown location_key → no-op, no crash, no LLM call."""
    with patch('app.services.world_service.generate_chat') as mock_llm:
        result = maybe_lazy_enrich_subloc(mem_db, 'does_not_exist')

    assert result is False
    assert not mock_llm.called


def test_lazy_enrich_llm_failure_keeps_generic_for_retry(mem_db):
    """LLM failure keeps ai_generated=0 so the next entry retries (does not poison state)."""
    generate_sublocs_for_settlement(mem_db, 'wolanka', ['smithy'])

    with patch('app.services.world_service.generate_chat', side_effect=RuntimeError("llm down")):
        result = maybe_lazy_enrich_subloc(mem_db, 'wolanka_smithy')

    assert result is False
    row = mem_db.execute(
        "SELECT ai_generated FROM game_locations WHERE key='wolanka_smithy'"
    ).fetchone()
    assert row['ai_generated'] == 0


# ── Backward compatibility ────────────────────────────────────────────────────

def test_generate_sublocs_still_sets_ai_generated_0(mem_db):
    """generate_sublocs_for_settlement behavior is unchanged by this issue."""
    result = generate_sublocs_for_settlement(mem_db, 'wolanka', ['smithy'])
    assert len(result) == 1

    row = mem_db.execute(
        "SELECT ai_generated FROM game_locations WHERE key='wolanka_smithy'"
    ).fetchone()
    assert row['ai_generated'] == 0


# ── Admin manual override protection (HTTP, real DEV DB) ─────────────────────

import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _get_admin_token():
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    return resp2.json()["token"]


@pytest.fixture
def admin_token():
    return _get_admin_token()


@pytest.fixture
def test_subloc(admin_token):
    """A generic (ai_generated=0) sub-location, as generate_sublocs_for_settlement produces."""
    unique = f"test_loc_{time.time()}"
    h = {"Authorization": f"Bearer {admin_token}"}
    resp = client.post(
        "/api/locations",
        json={"key": unique, "label": "Test Sub", "location_type": "sub"},
        headers=h,
    )
    created = resp.json() if resp.status_code == 201 else None
    yield created
    if created:
        client.delete(f"/api/locations/{created['key']}", headers=h)
        client.delete(f"/api/locations/{created['key']}?force=true", headers=h)


def test_patch_location_manual_edit_marks_ai_generated_so_lazy_enrich_wont_overwrite(test_subloc, admin_token):
    """Admin manually editing label/description of a generic sub-loc must flip
    ai_generated to 1 — otherwise a later player entry's lazy-enrichment call
    would silently overwrite the admin's manual text (#1064)."""
    assert test_subloc is not None
    h = {"Authorization": f"Bearer {admin_token}"}

    r = client.patch(
        f"/api/locations/admin/locations/{test_subloc['key']}",
        json={"description": "Ręcznie wpisany opis admina."},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["ai_generated"] == 1
