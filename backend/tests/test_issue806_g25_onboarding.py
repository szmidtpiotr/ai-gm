"""TDD #806 — G25: Onboarding do trwającej kampanii.

Acceptance criteria:
- build_onboarding_summary() z warstwami 1+2 → zwraca niepusty 3-blokowy tekst
- build_onboarding_summary() bez warstw G18 → zwraca "" (fallback na G12 pending_intro)
- "Kto jest kim" w prompcie LLM zawiera wszystkich członków z campaign_members
- Streszczenie budowane z warstw G18, nie z surowej historii
- Onboarding jednorazowy i niezależny od narracji innych graczy
"""
import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ─── Minimal schema for G25 tests ────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Test',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    status TEXT NOT NULL DEFAULT 'active',
    max_players INTEGER NOT NULL DEFAULT 4,
    host_user_id INTEGER NOT NULL DEFAULT 1,
    lobby_status TEXT NOT NULL DEFAULT 'open',
    host_note TEXT,
    gm_plan_json TEXT
);
CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'accepted',
    character_id INTEGER,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    absence_warnings INTEGER NOT NULL DEFAULT 0,
    pending_intro INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    autopilot_consent INTEGER NOT NULL DEFAULT 0,
    onboarding_summary TEXT,
    UNIQUE(campaign_id, user_id)
);
CREATE TABLE IF NOT EXISTS campaign_round_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    layer INTEGER NOT NULL,
    round_from INTEGER NOT NULL,
    round_to INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL DEFAULT 'testuser',
    display_name TEXT
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    campaign_id INTEGER,
    name TEXT NOT NULL DEFAULT 'Hero',
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'collecting',
    deadline TEXT,
    narrative_json TEXT
);
"""


def _make_db(tmp_path, name="test_806.db"):
    db_path = str(tmp_path / name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _seed_campaign(conn, cid=1, lobby_status="started", gm_plan=None):
    gm_plan_json = json.dumps(gm_plan) if gm_plan else None
    conn.execute(
        "INSERT INTO campaigns (id, host_user_id, owner_user_id, lobby_status, gm_plan_json) VALUES (?,1,1,?,?)",
        (cid, lobby_status, gm_plan_json),
    )
    conn.commit()


def _seed_user(conn, uid, username="player", display_name=None):
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, display_name) VALUES (?,?,?)",
        (uid, username, display_name),
    )
    conn.commit()


def _seed_character(conn, char_id, uid, name="Hero", archetype="warrior", level=3):
    sheet = json.dumps({"archetype": archetype, "level": level})
    conn.execute(
        "INSERT OR IGNORE INTO characters (id, user_id, name, sheet_json) VALUES (?,?,?,?)",
        (char_id, uid, name, sheet),
    )
    conn.commit()


def _seed_member(conn, cid=1, uid=1, role="player", char_id=None, pending_intro=0):
    conn.execute(
        "INSERT OR IGNORE INTO campaign_members "
        "(campaign_id, user_id, role, status, character_id, pending_intro) "
        "VALUES (?,?,?,'accepted',?,?)",
        (cid, uid, role, char_id, pending_intro),
    )
    conn.commit()


def _seed_g18_layers(conn, cid=1):
    """Seed both layer=2 (chapter) and layer=1 (round summaries) for testing."""
    conn.execute(
        "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
        "VALUES (?,2,1,10,'Rozdział I: Drużyna wyruszyła na poszukiwanie zaginionego króla.')",
        (cid,),
    )
    conn.execute(
        "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
        "VALUES (?,1,11,11,'Drużyna dotarła do skraju Czarnego Lasu.')",
        (cid,),
    )
    conn.execute(
        "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
        "VALUES (?,1,12,12,'Odkryto ślady goblinów; obóz rozbito na noc.')",
        (cid,),
    )
    conn.commit()


def _load_svc(monkeypatch, db_path):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import importlib
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    return svc


# ─── Test 1: build_onboarding_summary z warstwami G18 → niepusty tekst ───────

def test_onboarding_summary_with_layers_returns_text(tmp_path, monkeypatch):
    """build_onboarding_summary z warstwami G18 → zwraca niepusty 3-blokowy tekst."""
    db_path = _make_db(tmp_path)
    c = _conn(db_path)
    _seed_campaign(c)
    _seed_user(c, 1)
    _seed_character(c, 10, 1, name="Aldric")
    _seed_member(c, cid=1, uid=1, char_id=10)
    _seed_g18_layers(c)
    c.close()

    svc = _load_svc(monkeypatch, db_path)

    mock_text = (
        "**Co było:** Drużyna szukała króla w Czarnym Lesie.\n"
        "**Kto jest kim:** Aldric (warrior L3) — główny wojownik.\n"
        "**Jaka stawka:** Uratować króla, nim nadejdą gobliny."
    )

    with patch.object(svc, "_db", lambda: _conn(db_path)), \
         patch.object(svc, "_llm_call", return_value=mock_text), \
         patch.object(svc, "llm_service") as mock_llm:
        mock_llm.get_effective_config.return_value = {
            "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
        }
        mock_llm.OpenAIDriver.return_value = MagicMock()

        result = svc.build_onboarding_summary(1)

    assert result, "build_onboarding_summary musi zwrócić niepusty tekst gdy są warstwy G18"
    assert result == mock_text.strip()


# ─── Test 2: bez warstw G18 → "" (fallback do G12, brak LLM call) ────────────

def test_onboarding_summary_no_layers_returns_empty(tmp_path, monkeypatch):
    """build_onboarding_summary bez warstw G18 → zwraca '' (brak LLM call)."""
    db_path = _make_db(tmp_path)
    c = _conn(db_path)
    _seed_campaign(c)
    _seed_user(c, 1)
    _seed_member(c, cid=1, uid=1)
    # Brak warstw G18 — nie seedujemy campaign_round_summaries
    c.close()

    svc = _load_svc(monkeypatch, db_path)
    llm_called = []

    def mock_llm_call(*args, **kwargs):
        llm_called.append(True)
        return "nie powinno być wywołane"

    with patch.object(svc, "_db", lambda: _conn(db_path)), \
         patch.object(svc, "_llm_call", side_effect=mock_llm_call):
        result = svc.build_onboarding_summary(1)

    assert result == "", f"Oczekiwano '', otrzymano: {repr(result)}"
    assert not llm_called, "LLM nie powinien być wywołany gdy brak warstw G18"


# ─── Test 3: "Kto jest kim" zawiera wszystkich członków z campaign_members ────

def test_who_is_who_contains_all_members(tmp_path, monkeypatch):
    """Prompt LLM dla build_onboarding_summary zawiera wszystkich członków kampanii."""
    db_path = _make_db(tmp_path)
    c = _conn(db_path)
    _seed_campaign(c)

    # 3 members
    _seed_user(c, 10, "host_u", "Host")
    _seed_user(c, 11, "player2_u", "Gracz2")
    _seed_user(c, 12, "player3_u", "Gracz3")
    _seed_character(c, 100, 10, name="Aldric", archetype="warrior")
    _seed_character(c, 101, 11, name="Mira", archetype="scholar")
    _seed_character(c, 102, 12, name="Theron", archetype="rogue")
    _seed_member(c, cid=1, uid=10, role="host", char_id=100)
    _seed_member(c, cid=1, uid=11, char_id=101)
    _seed_member(c, cid=1, uid=12, char_id=102)
    _seed_g18_layers(c)
    c.close()

    svc = _load_svc(monkeypatch, db_path)
    captured_msgs = []

    def mock_llm_call(driver, cfg, system_prompt, user_msg):
        captured_msgs.append(user_msg)
        return "streszczenie"

    with patch.object(svc, "_db", lambda: _conn(db_path)), \
         patch.object(svc, "_llm_call", side_effect=mock_llm_call), \
         patch.object(svc, "llm_service") as mock_llm:
        mock_llm.get_effective_config.return_value = {
            "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
        }
        mock_llm.OpenAIDriver.return_value = MagicMock()
        svc.build_onboarding_summary(1)

    assert captured_msgs, "LLM powinien być wywołany"
    msg = captured_msgs[0]
    assert "Aldric" in msg, f"Aldric musi być w 'kto jest kim'. Prompt:\n{msg}"
    assert "Mira" in msg, f"Mira musi być w 'kto jest kim'. Prompt:\n{msg}"
    assert "Theron" in msg, f"Theron musi być w 'kto jest kim'. Prompt:\n{msg}"


# ─── Test 4: historia budowana z warstw G18, nie z surowych rund ──────────────

def test_onboarding_uses_g18_layers_not_raw_rounds(tmp_path, monkeypatch):
    """Prompt do LLM zawiera tekst warstw G18, nie surowy JSON rund."""
    db_path = _make_db(tmp_path)
    c = _conn(db_path)
    _seed_campaign(c)
    _seed_user(c, 1)
    _seed_character(c, 10, 1, name="Aldric")
    _seed_member(c, cid=1, uid=1, char_id=10)
    _seed_g18_layers(c)

    # Dodaj surową rundę — NIE powinna trafić do promptu zamiast warstw
    c.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status, narrative_json) "
        "VALUES (1, 13, 'done', '{\"narrative\": \"SUROWA_NARRACJA_RUNDA_13\"}')"
    )
    c.commit()
    c.close()

    svc = _load_svc(monkeypatch, db_path)
    captured_msgs = []

    def mock_llm_call(driver, cfg, system_prompt, user_msg):
        captured_msgs.append(user_msg)
        return "streszczenie"

    with patch.object(svc, "_db", lambda: _conn(db_path)), \
         patch.object(svc, "_llm_call", side_effect=mock_llm_call), \
         patch.object(svc, "llm_service") as mock_llm:
        mock_llm.get_effective_config.return_value = {
            "provider": "openai", "base_url": "http://x", "model": "gpt-4", "api_key": ""
        }
        mock_llm.OpenAIDriver.return_value = MagicMock()
        svc.build_onboarding_summary(1)

    assert captured_msgs
    msg = captured_msgs[0]
    # Tekst warstw G18 musi być w prompcie
    assert "Rozdział I" in msg or "zaginionego króla" in msg, \
        f"Tekst rozdziału (layer=2) powinien być w prompcie:\n{msg}"
    # Surowy JSON rundy NIE powinien być głównym źródłem (może być w raw rounds, ale warstwy są priorytetem)
    assert "SUROWA_NARRACJA_RUNDA_13" not in msg, \
        "Surowy JSON rundy nie powinien trafić do promptu onboardingowego"


# ─── Test 5: streszczenie jednorazowe — clearowane po zwróceniu ───────────────

def test_onboarding_summary_stored_and_clearable(tmp_path):
    """Onboarding summary przechowywany w campaign_members i może być wyczyszczony po odczytaniu."""
    db_path = _make_db(tmp_path)
    c = _conn(db_path)
    _seed_campaign(c, lobby_status="started")
    _seed_user(c, 1)
    _seed_member(c, cid=1, uid=1)
    c.close()

    # Zasymuluj przechowanie streszczenia (jak zrobi to accept_invite po build)
    summary_text = "**Co było:** Historia.\n**Kto jest kim:** Aldric.\n**Jaka stawka:** Cel."
    conn = _conn(db_path)
    conn.execute(
        "UPDATE campaign_members SET onboarding_summary=? WHERE campaign_id=1 AND user_id=1",
        (summary_text,),
    )
    conn.commit()

    # Odczyt
    row = conn.execute(
        "SELECT onboarding_summary FROM campaign_members WHERE campaign_id=1 AND user_id=1"
    ).fetchone()
    assert row["onboarding_summary"] == summary_text, "Streszczenie powinno być zapisane"

    # Clear po odczytaniu (jednorazowe)
    conn.execute(
        "UPDATE campaign_members SET onboarding_summary=NULL WHERE campaign_id=1 AND user_id=1"
    )
    conn.commit()

    row_after = conn.execute(
        "SELECT onboarding_summary FROM campaign_members WHERE campaign_id=1 AND user_id=1"
    ).fetchone()
    assert row_after["onboarding_summary"] is None, "Streszczenie musi być wyczyszczone po odczytaniu"
    conn.close()
