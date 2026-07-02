"""TDD: Issue #1072 — auto GM narration ('powrót do życia') after resurrection.

Today the chat window stays silent after a hero is revived — the player must
type something themselves to get the story moving again. This fix makes
apply_resurrection() insert an automatic GM turn describing the awakening,
using the death_reason/epitaph/location/cost as LLM context.
"""
from _fixtures_schema import table_sql
import json
import sqlite3
import pytest

import app.services.resurrection_service as svc
from app.services.resurrection_service import (
    apply_resurrection,
    set_global_resurrection_config,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_meta") + """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            resurrection_enabled INTEGER NOT NULL DEFAULT 0,
            resurrection_cost_mode TEXT NOT NULL DEFAULT 'admin_free',
            resurrection_cost_value INTEGER NOT NULL DEFAULT 25,
            resurrection_cost_cap_percent INTEGER NOT NULL DEFAULT 50,
            resurrection_uses_remaining INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            user_id INTEGER,
            name TEXT,
            location TEXT,
            sheet_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            gold_gp INTEGER DEFAULT 0
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT,
            system_id TEXT,
            model_id TEXT,
            language TEXT DEFAULT 'pl',
            owner_user_id INTEGER,
            user_id INTEGER,
            status TEXT DEFAULT 'active',
            death_reason TEXT,
            ended_at TEXT,
            epitaph TEXT
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            character_id INTEGER,
            user_text TEXT,
            assistant_text TEXT,
            route TEXT,
            turn_number INTEGER
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            amount INTEGER,
            created_at TEXT DEFAULT '2026-01-01',
            reverted_at TEXT
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER,
            wall_clock_at TEXT DEFAULT '2026-01-01',
            reverted_at TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            slot TEXT,
            label TEXT,
            meta_json TEXT
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            spell_key TEXT,
            rank INTEGER DEFAULT 1,
            learned_at_level INTEGER
        );
        CREATE TABLE character_dungeon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            dungeon_key TEXT,
            cooldown_until TEXT
        );
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """
        INSERT INTO users (id, username) VALUES (1, 'tester');
        INSERT INTO characters (id, user_id, campaign_id, name, location, status, gold_gp, sheet_json)
            VALUES (10, 1, 100, 'Alaric', 'Mroczny Las', 'dead', 200,
                '{"stats":{"CON":12,"INT":10},"archetype":"warrior","level":3,"xp":250,"current_hp":0,"max_hp":12,"max_mana":0}');
        INSERT INTO campaigns (id, title, system_id, model_id, language, owner_user_id, user_id, status, death_reason, ended_at, epitaph)
            VALUES (100, 'Testowa Kampania', 'fantasy', 'gpt-4.1-mini', 'pl', 1, 1, 'ended',
                'Poległ w walce z goblinami.', '2026-06-18T10:00:00', 'Był dzielny.');
    """)
    conn.commit()

    import app.services.clock_service as _clock
    _orig = _clock.get_clock_state
    _clock.get_clock_state = lambda cid, conn=None: {
        "day": 1, "hour": 6, "ingame_hours": 6,
        "hour_str": "06:00", "period": "Rano", "display": "Dzień 1"
    }
    yield conn
    _clock.get_clock_state = _orig
    conn.close()


def _fake_narration(messages, **kw):
    _fake_narration.last_prompt = messages[-1]["content"]
    return "Alaric otwiera oczy w Mrocznym Lesie. Blizna po goblińskim ostrzu piecze, ale żyje."


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_resurrection_inserts_auto_gm_narration_turn(db, monkeypatch):
    """Po wskrzeszeniu MG automatycznie dopisuje turę narracyjną — gracz nie musi nic pisać."""
    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {"model": "gpt-4.1-mini"})
    monkeypatch.setattr(svc, "generate_chat", _fake_narration)
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    result = apply_resurrection(10, 1, db, force=True)

    turn = db.execute(
        "SELECT * FROM campaign_turns WHERE campaign_id = 100 ORDER BY turn_number DESC LIMIT 1"
    ).fetchone()
    assert turn is not None, "Wskrzeszenie musi automatycznie dopisać turę narracyjną do czatu"
    assert turn["assistant_text"] == (
        "Alaric otwiera oczy w Mrocznym Lesie. Blizna po goblińskim ostrzu piecze, ale żyje."
    )
    assert turn["route"] == "narrative"
    assert result.get("narration") == turn["assistant_text"], (
        "apply_resurrection powinno zwrócić tekst narracji w odpowiedzi dla frontendu"
    )

    prompt = _fake_narration.last_prompt
    assert "Poległ w walce z goblinami." in prompt, "prompt musi zawierać death_reason"
    assert "Był dzielny." in prompt, "prompt musi zawierać epitafium"
    assert "Mroczny Las" in prompt, "prompt musi zawierać lokację bohatera"


def test_resurrection_narration_context_reflects_cost(db, monkeypatch):
    """Ton narracji ma dostać kontekst kosztu wskrzeszenia (np. utracone złoto)."""
    calls = {}

    def _capture(messages, **kw):
        calls["prompt"] = messages[-1]["content"]
        return "Narracja bolesnego powrotu."

    monkeypatch.setattr(svc, "get_user_llm_settings_full", lambda uid: {"model": "gpt-4.1-mini"})
    monkeypatch.setattr(svc, "generate_chat", _capture)
    set_global_resurrection_config(db, mode="gold_percent", value=50, enabled=True)

    apply_resurrection(10, 1, db, force=False)

    assert "złot" in calls["prompt"].lower(), "prompt powinien wspominać koszt w złocie"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_resurrection_without_campaign_no_narration_no_crash(db, monkeypatch):
    """Bohater bez kampanii (idle) — wskrzeszenie działa dalej, LLM nie jest wołany."""
    def _boom(*a, **k):
        raise AssertionError("LLM nie powinien być wołany bez kampanii")

    monkeypatch.setattr(svc, "generate_chat", _boom)
    db.execute("UPDATE characters SET campaign_id = NULL WHERE id = 10")
    db.commit()
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    result = apply_resurrection(10, 1, db, force=True)

    assert result["character_id"] == 10
    assert result.get("narration") is None
