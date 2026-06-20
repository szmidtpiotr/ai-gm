"""TDD: Issue #865 — POST /dungeons/{key}/enter musi zwracać zresolvowane riddle.

Bug: świeże wejście do lochu zwraca dungeon_run z gołymi kluczami riddle
(np. "riddle_silence"). Frontend wyświetla wtedy goły klucz zamiast treści zagadki.
Endpoint resume (GET /campaigns/{id}/dungeon-run) rozwija je przez _resolve_run_riddles,
ale endpoint enter — NIE. Asymetria.

Fix: enter_dungeon() musi wołać _resolve_run_riddles(conn, instance) przed zwrotem,
tak samo jak robi to resume.

Weryfikuje:
- enter zwraca dungeon_run z content.riddle jako dict (nie string key)
- dict ma text/answer/hints (gotowe dla frontendu i akcji)
- backward compat: enter nadal zwraca ok=True + room_narrative
- nieznany klucz riddle → None (nie crash, nie goły string)
"""
from __future__ import annotations

import sqlite3

import pytest

import app.api.dungeons as dungeons_mod
from app.api.dungeons import enter_dungeon, DungeonEnterReq


SCHEMA = """
CREATE TABLE game_config_riddles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]',
    hints TEXT DEFAULT '["Wskazówka pierwsza"]',
    difficulty TEXT DEFAULT 'medium',
    theme TEXT DEFAULT 'general',
    is_active INTEGER DEFAULT 1
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer, hints, is_active) VALUES (?, ?, ?, ?, 1)",
        ("riddle_silence", "Im więcej mnie zabierasz, tym większa się staję. Czym jestem?",
         "cisza", '["Posłuchaj uważnie"]'),
    )
    conn.commit()
    return conn


def _make_instance(riddle_value="riddle_silence") -> dict:
    """Symuluje run zwrócony przez enter_dungeon_tiles (riddle jako goły klucz)."""
    return {
        "system": "tiles_v2",
        "dungeon_label": "Krypta Próbna",
        "loot_tier": 1,
        "positions": {"1": "node_entry"},
        "graph": {
            "entry_node": "node_entry",
            "nodes": {
                "node_entry": {
                    "visited": True,
                    "cleared": False,
                    "content": {
                        "riddle": riddle_value,  # bare string key — the bug
                        "enemies": [],
                        "label": "Wejście",
                        "room_description": "Mroczna komnata.",
                    },
                },
            },
        },
    }


@pytest.fixture
def patched_enter(monkeypatch):
    """Mock zależności endpointu enter, tak by przeszedł bez prawdziwej bazy."""
    conn_holder = {"riddle": "riddle_silence"}

    monkeypatch.setattr(dungeons_mod, "_is_dungeon_enabled", lambda: True)
    monkeypatch.setattr(dungeons_mod, "_get_hero_level", lambda cid: 5)
    monkeypatch.setattr(dungeons_mod, "_save_dungeon_entry_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(dungeons_mod, "_get_db", lambda: _make_conn())

    import app.services.dungeon_service as ds
    monkeypatch.setattr(ds, "get_dungeon", lambda key: {"key": key, "min_level": 1})

    import app.services.dungeon_tile_service as dts
    monkeypatch.setattr(
        dts, "enter_dungeon_tiles",
        lambda *a, **k: _make_instance(conn_holder["riddle"]),
    )
    return conn_holder


# ─── RED: musi failować zanim enter zacznie wołać _resolve_run_riddles ───────

def test_enter_resolves_riddle_key_to_dict(patched_enter):
    """Świeże wejście do lochu → content.riddle jest dict z treścią, nie goły klucz.

    BEZ fixa endpoint zwraca {"riddle": "riddle_silence"} i frontend pokazuje klucz.
    """
    resp = enter_dungeon("krypta_probna", DungeonEnterReq(character_id=1, campaign_id=1))

    content = resp["dungeon_run"]["graph"]["nodes"]["node_entry"]["content"]
    riddle = content["riddle"]
    assert isinstance(riddle, dict), (
        f"#865: enter musi zwracać content.riddle jako dict, jest: "
        f"{type(riddle).__name__} = {riddle!r}. Frontend dostaje goły klucz."
    )
    assert riddle.get("text") == "Im więcej mnie zabierasz, tym większa się staję. Czym jestem?", (
        f"Brak treści zagadki: {riddle}"
    )
    assert riddle.get("answer") == "cisza", f"Brak answer: {riddle}"
    assert isinstance(riddle.get("hints"), list), f"Brak hints: {riddle}"


def test_enter_unknown_riddle_key_becomes_none(patched_enter):
    """Nieznany klucz riddle → None (nie crash, nie goły string)."""
    patched_enter["riddle"] = "riddle_nonexistent"
    resp = enter_dungeon("krypta_probna", DungeonEnterReq(character_id=1, campaign_id=1))

    content = resp["dungeon_run"]["graph"]["nodes"]["node_entry"]["content"]
    assert content["riddle"] is None, f"Nieznany klucz powinien dać None: {content['riddle']!r}"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_enter_still_returns_ok_and_narrative(patched_enter):
    """Enter nadal zwraca ok=True + room_narrative (kontrakt niezmieniony)."""
    resp = enter_dungeon("krypta_probna", DungeonEnterReq(character_id=1, campaign_id=1))

    assert resp["ok"] is True
    assert "Krypta Próbna" in resp["room_narrative"]
    assert "dungeon_run" in resp
    assert "onboarding_cards" in resp
