"""TDD: Issue #1132 (PT-D4c) — Panel Kuźnia: lista/edycja/akceptacja encounterów.

Warstwa serwisowa dla panelu (czysta, in-memory sqlite):
- list_catalog zwraca rekordy z metadanymi panelu (kind, times_used, quality_rating, title)
- filtr kind (combat/social) + biome/subtype zawęża wynik
- delete_encounter usuwa rekord po kluczu
- edycja istniejącego = save_encounter_from_draft z key+replace (UPDATE)
- backward-compat: draw_*/build_schema/save z pod-tasków A/B nadal działają
"""
from __future__ import annotations

import sqlite3

import pytest

from app.services import encounter_catalog_service as cat


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT)")
    c.execute("CREATE TABLE game_config_skills (key TEXT PRIMARY KEY, label TEXT)")
    c.executemany("INSERT INTO game_config_enemies VALUES (?,?)",
                  [("goblin", "Goblin"), ("bandyta", "Bandyta")])
    c.executemany("INSERT INTO game_config_skills VALUES (?,?)",
                  [("stealth", "Skradanie")])
    cat.ensure_catalog_schema(c)
    # dwa combat (różne biomy) + jeden social
    cat.insert_encounter(c, key="c_forest", kind="combat", biome="forest",
                         weight=100.0, payload={"title": "Zasadzka w lesie",
                         "enemies": [{"enemy_key": "goblin", "count": 2}]},
                         quality_rating=4, times_used=7, source="seed")
    cat.insert_encounter(c, key="c_swamp", kind="combat", biome="swamp",
                         weight=50.0, payload={"title": "Bagienny napad"},
                         quality_rating=2, times_used=0, source="ai_forge")
    cat.insert_encounter(c, key="s_market", kind="social", subtype="market",
                         weight=100.0, payload={"title": "Kieszonkowiec", "skill": "stealth"},
                         quality_rating=3, times_used=3, source="seed")
    return c


# ── Test główny: lista z metadanymi panelu ───────────────────────────────────

def test_list_catalog_returns_panel_metadata(conn):
    """list_catalog zwraca rekordy z kind/times_used/quality_rating/title dla panelu."""
    rows = cat.list_catalog(conn)
    assert len(rows) == 3
    by_key = {r["key"]: r for r in rows}
    forest = by_key["c_forest"]
    assert forest["kind"] == "combat"
    assert forest["times_used"] == 7
    assert forest["quality_rating"] == 4
    # tytuł wyciągnięty z payloadu dla nagłówka karty
    assert forest["title"] == "Zasadzka w lesie"


def test_list_catalog_filters_by_kind(conn):
    """Filtr kind='combat' zwraca tylko encountery bojowe."""
    combat = cat.list_catalog(conn, kind="combat")
    assert {r["key"] for r in combat} == {"c_forest", "c_swamp"}
    social = cat.list_catalog(conn, kind="social")
    assert {r["key"] for r in social} == {"s_market"}


def test_list_catalog_empty_kind_returns_all(conn):
    """Pusty string kind = brak filtra (nie wysypuje na walidacji) — bug z UI edycji."""
    assert len(cat.list_catalog(conn, kind="")) == 3
    assert len(cat.list_catalog(conn, kind=None)) == 3


def test_list_catalog_filters_by_biome_and_subtype(conn):
    """Filtr biome zawęża combat; subtype zawęża social."""
    assert {r["key"] for r in cat.list_catalog(conn, kind="combat", biome="forest")} == {"c_forest"}
    assert {r["key"] for r in cat.list_catalog(conn, kind="social", subtype="market")} == {"s_market"}


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_encounter_removes_row(conn):
    """delete_encounter usuwa rekord po kluczu i zwraca True."""
    assert cat.delete_encounter(conn, "c_swamp") is True
    keys = {r["key"] for r in cat.list_catalog(conn)}
    assert "c_swamp" not in keys and len(keys) == 2


def test_delete_missing_key_returns_false(conn):
    """Usunięcie nieistniejącego klucza → False (idempotencja)."""
    assert cat.delete_encounter(conn, "nie_ma") is False


# ── Edycja istniejącego = UPDATE przez save + replace ────────────────────────

def test_edit_existing_via_save_replace(conn):
    """Zapis z key istniejącego rekordu + replace=True nadpisuje (UPDATE)."""
    draft = {
        "kind": "combat", "key": "c_forest", "replace": True,
        "biome": "forest", "weight": 100.0,
        "payload": {"title": "Zasadzka POPRAWIONA",
                    "enemies": [{"enemy_key": "bandyta", "count": 3}]},
    }
    key = cat.save_encounter_from_draft(conn, draft)
    assert key == "c_forest"
    rows = cat.list_catalog(conn, kind="combat")
    forest = next(r for r in rows if r["key"] == "c_forest")
    assert forest["title"] == "Zasadzka POPRAWIONA"
    # nie powstał duplikat
    assert len([r for r in rows if r["key"] == "c_forest"]) == 1


# ── Backward compatibility ───────────────────────────────────────────────────

def test_draw_and_schema_still_work(conn):
    """Pod-taski A/B nietknięte: draw_combat + build_schema działają jak wcześniej."""
    picked = cat.draw_combat(conn, "forest", level=1)
    assert picked is not None and picked["key"] == "c_forest"
    schema = cat.build_schema(conn, "combat")
    assert "enemies" in {f["name"] for f in schema["fields"]}
