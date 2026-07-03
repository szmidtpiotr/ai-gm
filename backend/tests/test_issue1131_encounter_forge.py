"""TDD: Issue #1131 (PT-D4b) — Forge autoring AI encounterów (FK-enum, anty-halucynacja).

Testujemy warstwę serwisową (czysta, in-memory sqlite):
- build_schema zwraca dozwolone enumy z realnych katalogów (schema-enum)
- save odrzuca payload z wymyślonym kluczem FK (400 → ValueError)
- save happy-path dla combat (enemy_key) i social (skill)
- generate (batch) zwraca listę draftów status='pending' referencujących realne klucze
- normalize egzekwuje skalę DC 8-24 i cap złota
- backward-compat: validate_fk/draw_* z pod-taska A nadal działają
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
    c.execute("CREATE TABLE npcs (key TEXT PRIMARY KEY, label TEXT)")
    c.executemany("INSERT INTO game_config_enemies VALUES (?,?)",
                  [("goblin", "Goblin"), ("bandyta", "Bandyta")])
    c.executemany("INSERT INTO game_config_skills VALUES (?,?)",
                  [("stealth", "Skradanie"), ("persuasion", "Perswazja")])
    c.execute("INSERT INTO npcs VALUES ('karczmarz','Karczmarz')")
    cat.ensure_catalog_schema(c)
    return c


# ── Test główny: schema-enum ─────────────────────────────────────────────────

def test_schema_combat_exposes_real_enemy_enum(conn):
    """build_schema(combat) zwraca enum enemy_key z realnymi kluczami z katalogu."""
    schema = cat.build_schema(conn, "combat")
    enum_keys = {e["key"] for e in schema["enums"]["enemy_key"]}
    assert "goblin" in enum_keys and "bandyta" in enum_keys
    field_names = {f["name"] for f in schema["fields"]}
    assert "enemies" in field_names


def test_schema_social_exposes_real_skill_enum(conn):
    """build_schema(social) zwraca enum skill z realnymi kluczami."""
    schema = cat.build_schema(conn, "social")
    enum_keys = {s["key"] for s in schema["enums"]["skill"]}
    assert "stealth" in enum_keys and "persuasion" in enum_keys


# ── Test główny: walidacja FK (anty-halucynacja) ──────────────────────────────

def test_save_rejects_invented_enemy_key(conn):
    """Zapis combat z wymyślonym enemy_key → ValueError (router → 400)."""
    draft = {
        "kind": "combat", "title": "Zasadzka smoka", "biome": "forest",
        "payload": {"enemies": [{"enemy_key": "smok_cienia", "count": 1}],
                    "scene_setup": "..."},
    }
    with pytest.raises(ValueError):
        cat.save_encounter_from_draft(conn, draft)


def test_save_rejects_invented_skill(conn):
    """Zapis social z wymyślonym skill → ValueError."""
    draft = {
        "kind": "social", "title": "Wróżba", "subtype": "market",
        "payload": {"stat": "WIS", "skill": "czytanie_z_gwiazd", "dc": 12,
                    "resolution_kind": "soft"},
    }
    with pytest.raises(ValueError):
        cat.save_encounter_from_draft(conn, draft)


# ── Test główny: save happy-path ──────────────────────────────────────────────

def test_save_combat_happy_path(conn):
    """Combat z realnym enemy_key → wiersz w katalogu."""
    draft = {
        "kind": "combat", "title": "Napad goblinów", "biome": "forest",
        "level_min": 1, "level_max": 5, "weight": 80,
        "payload": {"enemies": [{"enemy_key": "goblin", "count": 2}],
                    "scene_setup": "Z krzaków wyskakują gobliny."},
    }
    key = cat.save_encounter_from_draft(conn, draft)
    row = conn.execute(
        "SELECT kind, biome, source FROM game_config_encounters WHERE key=?", (key,)
    ).fetchone()
    assert row is not None
    assert row["kind"] == "combat" and row["biome"] == "forest"
    assert row["source"] == "ai_forge"


def test_save_social_happy_path(conn):
    """Social z realnym skill → wiersz w katalogu."""
    draft = {
        "kind": "social", "title": "Podejrzany kupiec", "subtype": "market",
        "payload": {"stat": "CHA", "skill": "persuasion", "dc": 14,
                    "resolution_kind": "soft", "flavor": "kupiec"},
    }
    key = cat.save_encounter_from_draft(conn, draft)
    row = conn.execute(
        "SELECT kind, subtype FROM game_config_encounters WHERE key=?", (key,)
    ).fetchone()
    assert row is not None and row["kind"] == "social" and row["subtype"] == "market"


# ── Test główny: generate batch ──────────────────────────────────────────────

def test_generate_batch_returns_pending_drafts(conn):
    """Batch generate → lista draftów status='pending' referencujących realny klucz."""
    canned = (
        '```json\n{"kind":"combat","title":"Zasadzka","biome":"forest",'
        '"level_min":1,"level_max":3,"weight":100,'
        '"payload":{"enemies":[{"enemy_key":"goblin","count":2}],'
        '"scene_setup":"...","gm_notes":"...","rewards":{"gold_pct":20}}}\n```'
    )
    drafts = cat.generate_encounter_drafts(
        conn, "combat", count=3, biome="forest",
        generate_fn=lambda messages: canned,
    )
    assert len(drafts) == 3
    assert all(d["status"] == "pending" for d in drafts)
    assert all(d["payload"]["enemies"][0]["enemy_key"] == "goblin" for d in drafts)
    assert all(d["fk_valid"] is True for d in drafts)


def test_generate_flags_hallucinated_key_as_invalid(conn):
    """Draft z wymyślonym enemy_key ma fk_valid=False (do odrzucenia w panelu)."""
    canned = (
        '```json\n{"kind":"combat","title":"X","biome":"forest",'
        '"payload":{"enemies":[{"enemy_key":"lich_krwi","count":1}]}}\n```'
    )
    drafts = cat.generate_encounter_drafts(
        conn, "combat", count=1, generate_fn=lambda messages: canned,
    )
    assert len(drafts) == 1 and drafts[0]["fk_valid"] is False


# ── Test główny: normalize DC / gold ─────────────────────────────────────────

def test_normalize_clamps_dc_to_scale(conn):
    """DC poza skalą 8-24 → przycięte do granic."""
    assert cat.normalize_payload("social", {"dc": 40})["dc"] == cat.DC_MAX
    assert cat.normalize_payload("social", {"dc": 2})["dc"] == cat.DC_MIN


def test_normalize_clamps_gold_pct_to_cap(conn):
    """gold_pct powyżej capu → przycięte do capu."""
    out = cat.normalize_payload("combat", {"rewards": {"gold_pct": 90}})
    assert out["rewards"]["gold_pct"] == cat.GOLD_PCT_CAP


# ── Backward compatibility (pod-task A) ───────────────────────────────────────

def test_validate_fk_still_works(conn):
    """validate_fk z pod-taska A: dobry klucz przechodzi, zły rzuca."""
    cat.validate_fk(conn, kind="combat",
                    payload={"enemies": [{"enemy_key": "goblin"}]})
    with pytest.raises(ValueError):
        cat.validate_fk(conn, kind="combat",
                        payload={"enemies": [{"enemy_key": "nieistnieje"}]})


def test_draw_combat_still_returns_none_when_empty(conn):
    """draw_combat na pustym katalogu → None (fallback do hardcode)."""
    assert cat.draw_combat(conn, "tundra", 1) is None
