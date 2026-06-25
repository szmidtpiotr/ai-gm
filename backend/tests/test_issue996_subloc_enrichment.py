"""TDD: Issue #996 — LLM enrichment of auto-generated sub-location labels."""
import pytest
import sqlite3
from unittest.mock import patch

import sys
sys.path.insert(0, '/app')

from app.services.world_service import (
    generate_sublocs_for_settlement,
    enrich_sublocs_labels,
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
            ('vilnograd', 'Vilnograd', 'Stara osada nad rzeką Siwą. Domy z drewna i kamienia.',
             'settlement', 'village', 1, 1, 'permanent', 'admin_manual', 0)
    """)
    conn.commit()
    return conn


_MOCK_LLM_RESP = """{
  "sublocs": [
    {"key": "vilnograd_tavern", "label": "Karczma Pod Złotym Kłosem", "description": "Gwarny przybytek przy rynku."},
    {"key": "vilnograd_smithy", "label": "Kuźnia Żelaznego Mistrza", "description": "Ciemna kuźnia pełna żaru."}
  ]
}"""


# ── Testy główne ──────────────────────────────────────────────────────────────

def test_enrich_updates_label_and_sets_ai_generated(mem_db):
    """Enrichment stores thematic labels and flips ai_generated to 1."""
    generate_sublocs_for_settlement(mem_db, 'vilnograd', ['tavern', 'smithy'])

    with patch('app.services.world_service.generate_chat', return_value=_MOCK_LLM_RESP):
        result = enrich_sublocs_labels(mem_db, 'vilnograd')

    assert len(result) == 2

    tavern = mem_db.execute(
        "SELECT label, description, ai_generated FROM game_locations WHERE key='vilnograd_tavern'"
    ).fetchone()
    assert tavern['ai_generated'] == 1
    assert tavern['label'] == 'Karczma Pod Złotym Kłosem'
    assert tavern['description'] == 'Gwarny przybytek przy rynku.'


def test_enrich_idempotent_skips_already_enriched(mem_db):
    """Sub-locs with ai_generated=1 are skipped (idempotent)."""
    generate_sublocs_for_settlement(mem_db, 'vilnograd', ['tavern', 'smithy'])
    mem_db.execute(
        "UPDATE game_locations SET ai_generated=1, label='Karczma Pod Lipą' WHERE key='vilnograd_tavern'"
    )
    mem_db.commit()

    mock_only_smithy = '{"sublocs": [{"key": "vilnograd_smithy", "label": "Kuźnia Mistrza Bogdana", "description": "desc"}]}'

    with patch('app.services.world_service.generate_chat', return_value=mock_only_smithy):
        result = enrich_sublocs_labels(mem_db, 'vilnograd')

    assert len(result) == 1
    assert result[0]['key'] == 'vilnograd_smithy'

    untouched = mem_db.execute(
        "SELECT label FROM game_locations WHERE key='vilnograd_tavern'"
    ).fetchone()
    assert untouched['label'] == 'Karczma Pod Lipą'


def test_enrich_specific_subloc_keys_only(mem_db):
    """subloc_keys param limits enrichment to given keys only."""
    generate_sublocs_for_settlement(mem_db, 'vilnograd', ['tavern', 'smithy', 'market'])

    mock_one = '{"sublocs": [{"key": "vilnograd_tavern", "label": "Karczma Stara Baszta", "description": "desc"}]}'

    with patch('app.services.world_service.generate_chat', return_value=mock_one):
        result = enrich_sublocs_labels(mem_db, 'vilnograd', subloc_keys=['vilnograd_tavern'])

    assert len(result) == 1
    assert result[0]['key'] == 'vilnograd_tavern'

    smithy = mem_db.execute(
        "SELECT ai_generated FROM game_locations WHERE key='vilnograd_smithy'"
    ).fetchone()
    assert smithy['ai_generated'] == 0


def test_enrich_unknown_parent_returns_empty(mem_db):
    """Unknown parent_key → returns [] without error."""
    result = enrich_sublocs_labels(mem_db, 'nonexistent_key')
    assert result == []


def test_enrich_no_unenriched_sublocs_returns_empty(mem_db):
    """If all sub-locs already ai_generated=1, returns []."""
    generate_sublocs_for_settlement(mem_db, 'vilnograd', ['tavern'])
    mem_db.execute("UPDATE game_locations SET ai_generated=1 WHERE key='vilnograd_tavern'")
    mem_db.commit()

    with patch('app.services.world_service.generate_chat', return_value='{"sublocs": []}'):
        result = enrich_sublocs_labels(mem_db, 'vilnograd')

    assert result == []


# ── Backward compatibility ────────────────────────────────────────────────────

def test_generate_sublocs_still_sets_ai_generated_0(mem_db):
    """generate_sublocs_for_settlement sets ai_generated=0 (raw, unenriched state)."""
    result = generate_sublocs_for_settlement(mem_db, 'vilnograd', ['tavern'])
    assert len(result) == 1

    row = mem_db.execute(
        "SELECT ai_generated FROM game_locations WHERE key='vilnograd_tavern'"
    ).fetchone()
    assert row['ai_generated'] == 0
