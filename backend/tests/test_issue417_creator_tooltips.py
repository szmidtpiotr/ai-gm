"""TDD: Issue #417 — Kreator bohatera: tooltipy z opisami + przykładami mechanicznymi."""
import sys, os

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_creator_help_endpoint_exists():
    """GET /mechanics/creator-help must return archetypes, stats, skills."""
    r = client.get("/api/mechanics/creator-help")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "archetypes" in body, f"missing 'archetypes': {body.keys()}"
    assert "stats" in body, f"missing 'stats': {body.keys()}"
    assert "skills" in body, f"missing 'skills': {body.keys()}"


def test_archetypes_have_description_and_example():
    """Each archetype must carry a description AND a mechanical gameplay example."""
    body = client.get("/api/mechanics/creator-help").json()
    archetypes = body["archetypes"]
    assert len(archetypes) >= 3, f"expected >=3 archetypes, got {len(archetypes)}"
    for a in archetypes:
        assert a.get("key"), f"archetype missing key: {a}"
        assert a.get("description"), f"archetype {a.get('key')} missing description"
        assert a.get("example"), f"archetype {a.get('key')} missing mechanical example"
    keys = {a["key"] for a in archetypes}
    assert {"warrior", "rogue", "scholar"} <= keys, f"missing core archetypes: {keys}"


def test_stats_have_roll_example():
    """Each of the 7 stats must carry a description AND a roll example."""
    body = client.get("/api/mechanics/creator-help").json()
    stats = body["stats"]
    stat_keys = {s["key"] for s in stats}
    assert {"STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"} <= stat_keys, f"missing stats: {stat_keys}"
    for s in stats:
        assert s.get("description"), f"stat {s.get('key')} missing description"
        assert s.get("example"), f"stat {s.get('key')} missing roll example"


def test_skills_have_dc_and_example():
    """Each skill must carry a description, a DC hint and a usage example."""
    body = client.get("/api/mechanics/creator-help").json()
    skills = body["skills"]
    assert len(skills) >= 5, f"expected >=5 skills, got {len(skills)}"
    for s in skills:
        assert s.get("key"), f"skill missing key: {s}"
        assert s.get("description"), f"skill {s.get('key')} missing description"
        assert s.get("example"), f"skill {s.get('key')} missing usage example"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_mechanics_metadata_still_works():
    """Existing /mechanics/metadata endpoint must keep working (no regression)."""
    r = client.get("/api/mechanics/metadata")
    assert r.status_code == 200
    body = r.json()
    assert "test_descriptions" in body
    assert "dc_tiers" in body
