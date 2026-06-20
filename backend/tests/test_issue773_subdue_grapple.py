"""TDD: Issue #773 — Mechanika obezwładnienia (grapple/schwytanie poza walką).

Decyzje Piotra: 1A (bramka #780, nie COMBAT_START) + 2A (nowa kondycja `schwytany`)
+ 3A (porażka → COMBAT_START).

Pokrywane kontrakty:
- 1A: `_subdue_intent` wykrywa deklarację obezwładnienia (+ filtr negacji jak #535),
      a subdue ≠ śmiertelny atak (`_player_combat_intent` go nie łapie → brak COMBAT_START).
- 1A: `build_advantage_gate("grapple")` zwraca bramkę intencji (atak/zastraszenie/wycofaj)
      + deterministyczną mapę rozwiązania (`subdue_resolution`).
- 3A: `subdue_outcome_to_effect` — sukces → `schwytany`, porażka → COMBAT_START.
- 2A: kondycja `schwytany` (block_action) blokuje turę wroga (nie atakuje, nie ucieka).
"""
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from app.api.turns import _subdue_intent, _player_combat_intent
from app.services import combat_service as cs


# ─── 1A — wykrywanie intencji obezwładnienia ─────────────────────────────────

@pytest.mark.parametrize("text", [
    "obezwładniam strażnika",
    "chcę go schwytać żywcem",
    "chwytam napastnika za ramię",
    "przyciskam go do ściany",
    "przypieram bandytę do muru",
    "zakuwam go w kajdany",
    "unieruchamiam przeciwnika",
    "przytrzymuję go, żeby nie uciekł",
])
def test_subdue_intent_detected(text):
    """Deklaracje obezwładnienia muszą być wykryte."""
    assert _subdue_intent(text) is True


@pytest.mark.parametrize("text", [
    "nie chwytam go, tylko rozmawiam",
    "nie obezwładniam strażnika",
    "nie zamierzam go schwytać",
])
def test_subdue_intent_negation_suppressed(text):
    """Negacja (#535-style) musi wyłączyć trigger."""
    assert _subdue_intent(text) is False


@pytest.mark.parametrize("text", [
    "rozmawiam ze strażnikiem o pogodzie",
    "kupuję miecz u kowala",          # 'zaku' NIE może łapać 'zakupu'
    "skupiam się na celu",            # 'sku' NIE może łapać 'skupiam'
    "rozglądam się po sali",
])
def test_subdue_intent_plain_false(text):
    """Zwykły tekst (bez intencji obezwładnienia) — brak triggera + brak kolizji fragmentów."""
    assert _subdue_intent(text) is False


def test_subdue_is_not_lethal_combat_intent():
    """1A: obezwładnienie ≠ śmiertelny atak — nie wywołuje ścieżki COMBAT_START."""
    assert _player_combat_intent("obezwładniam strażnika") is False
    assert _player_combat_intent("przyciskam go do ściany") is False


def test_real_attack_still_combat_intent():
    """Backward compat: prawdziwy atak nadal wykrywany jako combat intent."""
    assert _player_combat_intent("atakuję mieczem goblina") is True


# ─── 1A — bramka grapple + mapa rozwiązania ──────────────────────────────────

def test_advantage_gate_grapple_source():
    """`grapple` jako źródło przewagi zwraca bramkę 3 opcji + mapę rozwiązania (3A)."""
    gate = cs.build_advantage_gate("grapple")
    assert gate is not None
    opts = {o["id"] for o in gate["options"]}
    assert opts == {"strike", "intimidate", "withdraw"}
    # zastraszenie nigdy nie niesie COMBAT_START (casus Mizela #99791)
    intim = next(o for o in gate["options"] if o["id"] == "intimidate")
    assert "COMBAT_START" not in intim["action"].upper()
    # deterministyczna mapa: sukces → schwytany, porażka → walka (3A)
    res = gate.get("subdue_resolution")
    assert res is not None
    assert res["success"].get("apply_condition") == "schwytany"
    assert res["failure"].get("combat_start") is True


def test_stealth_gate_still_works():
    """Backward compat: bramka stealth (#780) nie zmieniona — bez subdue_resolution."""
    gate = cs.build_advantage_gate("stealth")
    assert gate is not None
    assert {o["id"] for o in gate["options"]} == {"strike", "intimidate", "withdraw"}
    assert gate.get("subdue_resolution") is None


# ─── 3A — mapowanie wyniku obezwładnienia ────────────────────────────────────

def test_subdue_outcome_success_applies_schwytany():
    eff = cs.subdue_outcome_to_effect("SUCCESS")
    assert eff["apply_condition"] == "schwytany"
    assert not eff.get("combat_start")


def test_subdue_outcome_crit_success_bonus():
    eff = cs.subdue_outcome_to_effect("CRITICAL_SUCCESS")
    assert eff["apply_condition"] == "schwytany"
    assert eff.get("bonus") is True


def test_subdue_outcome_failure_starts_combat():
    """3A: porażka zawsze → COMBAT_START."""
    eff = cs.subdue_outcome_to_effect("FAILURE")
    assert eff.get("combat_start") is True
    assert eff.get("enemy_initiative") is False


def test_subdue_outcome_critfail_enemy_initiative():
    """Krytyczna porażka → wróg kontratakuje z inicjatywą."""
    eff = cs.subdue_outcome_to_effect("CRITICAL_FAILURE")
    assert eff.get("combat_start") is True
    assert eff.get("enemy_initiative") is True


# ─── 2A — kondycja schwytany blokuje turę wroga ──────────────────────────────

def _combat_db_with_schwytany(tmp_path):
    db = tmp_path / "subdue.db"
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandyta",
        "hp_current": 40, "hp_max": 40, "defense": 10, "zone": "engaged",
        "conditions": [{"key": "schwytany", "label": "Schwytany",
                        "effect_json": '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"block_action"}]}'}],
    }
    player = {"id": "player", "type": "player", "name": "Aldric",
              "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
              "conditions": []}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","bandit"]','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def test_schwytany_blocks_enemy_turn(tmp_path):
    """2A: wróg `schwytany` (block_action) ma zablokowaną turę — nie atakuje, nie ucieka."""
    db = _combat_db_with_schwytany(tmp_path)
    with patch.object(cs, "COMBAT_DB_PATH", str(db)):
        out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is True


# ─── 2A — seed kondycji (RED dopóki migracja nie wejdzie na /data) ────────────

def test_schwytany_condition_seeded():
    """Kondycja `schwytany` zaseedowana z efektem block_action."""
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        row = conn.execute(
            "SELECT effect_json FROM game_config_conditions WHERE key='schwytany'").fetchone()
        assert row is not None, "kondycja 'schwytany' nie zaseedowana"
        assert "block_action" in str(row[0]), "schwytany musi mieć efekt block_action"
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
