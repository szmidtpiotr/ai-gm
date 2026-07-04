"""#1132 (opcja B) — konwersacyjny autoring encounterów w Katalogu Kuźni.

Admin OPISUJE encounter własnymi słowami; agent dopytuje i buduje draft z tym
samym kontraktem FK-enum co generate. Testy na czystej funkcji serwisu z
wstrzykniętym `generate_fn` (bez LLM, deterministycznie).
"""
import json
import sqlite3

import pytest

from app.services import encounter_catalog_service as cat


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    # Minimalne katalogi FK: 1 wróg + 1 umiejętność
    c.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT)")
    c.execute("INSERT INTO game_config_enemies VALUES ('goblin','Goblin')")
    c.execute("CREATE TABLE game_config_skills (key TEXT PRIMARY KEY, label TEXT)")
    c.execute("INSERT INTO game_config_skills VALUES ('persuasion','Perswazja')")
    c.execute("CREATE TABLE npcs (key TEXT PRIMARY KEY, label TEXT)")
    cat.ensure_catalog_schema(c)
    return c


def _stub(reply, draft):
    payload = {"reply": reply, "draft": draft}
    return lambda messages: "```json\n" + json.dumps(payload) + "\n```"


def test_chat_asks_clarifying_when_draft_null(conn):
    """Agent dopytuje → draft=None, reply przekazany."""
    out = cat.chat_encounter_draft(
        conn, "combat",
        [{"role": "user", "content": "zrób coś w lesie"}],
        generate_fn=_stub("W jakim biomie i na jaki poziom?", None),
    )
    assert out["draft"] is None
    assert "biomie" in out["reply"]
    assert out["fk_valid"] is None


def test_chat_builds_valid_combat_draft(conn):
    """Opis → draft z realnym enemy_key → fk_valid=True, wpada w flow akceptacji."""
    draft = {
        "kind": "combat", "title": "Zasadzka goblinów", "biome": "forest",
        "level_min": 1, "level_max": 4, "weight": 100,
        "payload": {"enemies": [{"enemy_key": "goblin", "count": 2}],
                    "scene_setup": "Cień między drzewami.", "rewards": {"gold_pct": 15}},
    }
    out = cat.chat_encounter_draft(
        conn, "combat",
        [{"role": "user", "content": "napięta zasadzka goblinów w gęstym lesie"}],
        generate_fn=_stub("Złożyłem draft — zaakceptuj.", draft),
    )
    assert out["draft"] is not None
    assert out["fk_valid"] is True
    assert out["draft"]["status"] == "pending"
    assert out["draft"]["payload"]["enemies"][0]["enemy_key"] == "goblin"


def test_chat_flags_invented_fk_key(conn):
    """Wymyślony enemy_key → fk_valid=False (anty-halucynacja, admin poprawia przed zapisem)."""
    draft = {
        "kind": "combat", "title": "Smok", "biome": "mountain", "weight": 50,
        "payload": {"enemies": [{"enemy_key": "ancient_dragon_xxx", "count": 1}]},
    }
    out = cat.chat_encounter_draft(
        conn, "combat",
        [{"role": "user", "content": "starożytny smok w górach"}],
        generate_fn=_stub("Draft gotowy.", draft),
    )
    assert out["draft"] is not None
    assert out["fk_valid"] is False


def test_chat_social_draft_clamps_dc(conn):
    """Social draft z realnym skill → fk_valid; DC poza skalą docięte przez normalize_payload."""
    draft = {
        "kind": "social", "title": "Przekupstwo na rogatce", "subtype": "gate", "weight": 100,
        "payload": {"stat": "CHA", "skill": "persuasion", "dc": 99,
                    "resolution_kind": "soft", "soft_outcome": "Strażnik odpuszcza."},
    }
    out = cat.chat_encounter_draft(
        conn, "social",
        [{"role": "user", "content": "nerwowy strażnik na rogatce, da się przekupić albo zagadać"}],
        generate_fn=_stub("Gotowe.", draft),
    )
    assert out["fk_valid"] is True
    assert out["draft"]["payload"]["dc"] == cat.DC_MAX  # 99 → docięte do 24


def test_chat_generate_fn_exception_is_graceful(conn):
    """Wyjątek LLM → łagodny reply, brak wywrotki."""
    def boom(messages):
        raise RuntimeError("llm down")
    out = cat.chat_encounter_draft(
        conn, "combat", [{"role": "user", "content": "cokolwiek"}], generate_fn=boom,
    )
    assert out["draft"] is None
    assert out["reply"]
