"""AUDIT #1427 + #1428 — serwerowy autorytet kości (gracz nie narzuca wyniku rzutu).

#1427: resolve_attack(authoritative=True) losuje d20 gracza SERWEROWO; client raw_d20/
       roll_result są display-only. Cap na _margin_damage_bonus.
#1428: /roll — non-admin nie może narzucić jawnego raw_roll ani DC ataku (serwer losuje,
       DC z celu/silnika). Admin (testy/replay) zachowuje możliwość.
"""
import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["httpx"] = MagicMock()

from _fixtures_schema import table_sql  # noqa: E402
from app.services import admin_config  # noqa: E402
from app.services import combat_service as cs  # noqa: E402
from app.services.combat_service import (  # noqa: E402
    MARGIN_DAMAGE_BONUS_CAP,
    _margin_damage_bonus,
)
from app.api import turns  # noqa: E402


# ─────────────────────────── #1427 pkt.1: margin cap (pure) ───────────────────────────

def test_margin_bonus_capped():
    """Nawet skrajnie wysoki attack_total nie skaluje bonusu marginesowego bez granicy —
    _margin_damage_bonus jest twardo ograniczony przez MARGIN_DAMAGE_BONUS_CAP (#1427)."""
    # attack_total 500 vs obrona 10 → margines 490 → dziesiątki progów bez capu.
    assert _margin_damage_bonus(attack_total=500, defense_stat=10) == MARGIN_DAMAGE_BONUS_CAP
    # Tuż poniżej capu-punktu skalowanie normalne (regresja: cap nie tnie za wcześnie).
    below = _margin_damage_bonus(attack_total=10 + 5 * (MARGIN_DAMAGE_BONUS_CAP - 1), defense_stat=10)
    assert below == MARGIN_DAMAGE_BONUS_CAP - 1
    # Dokładnie na capie i powyżej — zawsze cap, nigdy więcej.
    assert _margin_damage_bonus(attack_total=10 + 5 * MARGIN_DAMAGE_BONUS_CAP, defense_stat=10) == MARGIN_DAMAGE_BONUS_CAP
    assert _margin_damage_bonus(attack_total=10 + 5 * (MARGIN_DAMAGE_BONUS_CAP + 20), defense_stat=10) == MARGIN_DAMAGE_BONUS_CAP


# ─────────────────────────── #1427 pkt.2: server dice authority ───────────────────────

def _combat_schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT,
      display_name TEXT, is_admin INTEGER DEFAULT 0
    );
    INSERT INTO users (id, username, password_hash, display_name, is_admin)
    VALUES (1, 'u', 'x', 'U', 0);

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 'T', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT, location TEXT, is_active INTEGER DEFAULT 1
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (1, 1, 1, 'Aldric', 'fantasy',
      '{"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}');

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, skills_json, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', '{}', NULL, 0.0);

    """ + table_sql("game_config_meta") + """

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE, character_id INTEGER,
      round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT, combatants TEXT,
      status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT, loot_pool TEXT,
      created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
      turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER,
      hp_after INTEGER, target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );
    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
      user_text TEXT, route TEXT, assistant_text TEXT, turn_number INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY, campaign_id INTEGER, session_flags TEXT DEFAULT '{}',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """


def _setup_combat_db(tmp: Path):
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_combat_schema_sql())
    conn.close()


def _force_player_turn(tmp: Path):
    """Po initiate_combat inicjatywa może dać pierwszą turę wrogowi. Ten test bada wyłącznie
    autorytet kości (#1427), więc wymuszamy turę gracza, by ominąć bramkę tury z #1429
    (Krok 3) — inaczej resolve_attack słusznie rzuca not_player_turn."""
    conn = sqlite3.connect(str(tmp))
    row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    pid = "player"
    if row and row[0]:
        for c in json.loads(row[0]):
            if str(c.get("id", "")).startswith("player"):
                pid = c["id"]
                break
    conn.execute("UPDATE active_combat SET current_turn=? WHERE campaign_id=1", (pid,))
    conn.commit()
    conn.close()


@patch("app.services.loot_service.roll_loot", return_value=[])
@patch("app.services.combat_service.roll_damage_dice", return_value=5)
def test_player_attack_ignores_client_dice(_dmg, _loot):
    """resolve_attack(authoritative=True) IGNORUJE client raw_d20 / roll_result i losuje d20
    serwerowo. Wstrzyknięty raw_d20=1 (Nat1 = auto-pudło) + roll_result=999 nie mogą narzucić
    wyniku — serwer rzuca 20 (Nat20 auto-trafienie), a attack_total pochodzi z karty postaci."""
    tmp = Path("/tmp") / "_issue1427_combat_test.db"
    _setup_combat_db(tmp)
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.combat_service._create_pending_combat_enemy", return_value=None):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(tmp)
        with patch("app.services.combat_service.roll_d20", return_value=20):
            res = cs.resolve_attack(
                1,
                roll_result=999,          # client-forced total — MUSI być zignorowany
                attacker="player",
                raw_d20=1,                # client-forced Nat1 — MUSI być zignorowany
                authoritative=True,
            )
    # Serwer rzucił 20 — nie client 1:
    assert res["player_raw_d20"] == 20, res
    assert res["player_nat20"] is True
    assert res["player_nat1"] is False
    # Nat1 klienta narzuciłby pudło; serwerowy Nat20 = trafienie:
    assert res["hit"] is True
    # Client roll_result=999 zignorowany — total policzony z karty (14 STR mod + broń), << 999:
    assert res["attack_total"] != 999
    assert res["attack_total"] < 100


@patch("app.services.loot_service.roll_loot", return_value=[])
@patch("app.services.combat_service.roll_damage_dice", return_value=5)
def test_non_authoritative_default_still_trusts_caller(_dmg, _loot):
    """Guard: domyślnie authoritative=False (off-hand/enemy/testy) nadal ufa podanemu rzutowi —
    fix zamyka WYŁĄCZNIE ścieżki żądań, które jawnie opt-in (authoritative=True)."""
    tmp = Path("/tmp") / "_issue1427_combat_default.db"
    _setup_combat_db(tmp)
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.combat_service._create_pending_combat_enemy", return_value=None):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(tmp)
        res = cs.resolve_attack(1, roll_result=None, attacker="player", raw_d20=1)
    assert res["player_raw_d20"] == 1  # podany raw uszanowany w trybie nie-autorytatywnym


# ─────────────────────────── #1428: /roll server authority ────────────────────────────

def _roll_db(is_admin: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, is_admin INTEGER DEFAULT 0)")
    conn.execute("INSERT INTO users (id, is_admin) VALUES (7, ?)", (is_admin,))
    return conn


_SHEET = json.dumps({
    "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
    "skills": {}, "current_hp": 20, "max_hp": 20,
})
_CHAR = {"user_id": 7, "sheet_json": _SHEET, "name": "Aldric"}
_PAYLOAD = types.SimpleNamespace(character_id=1)
_WEAPON = {"key": "sword", "label": "Sword", "weapon_type": "melee", "damage_die": "1d8", "linked_stat": "STR"}


def _run_roll(conn, text):
    with patch.object(turns, "is_slash_command_enabled", return_value=True), \
         patch.object(turns, "resolve_sheet_weapon", return_value=_WEAPON), \
         patch.object(turns, "roll_d20", return_value=7):
        return turns._ct_roll_and_death_save(conn, 1, _PAYLOAD, _CHAR, text, turn_id="t1")


def test_roll_command_rejects_client_raw_roll_for_non_admin():
    """Non-admin '/roll Attack 20 dc 5': jawny raw_roll=20 i dc=5 są ODRZUCONE. Serwer losuje
    d20 (mock=7), a DC ataku pochodzi z silnika/celu (None) — brak wymuszonego Nat20 auto-sukcesu."""
    conn = _roll_db(is_admin=0)
    roll_data, _msg, _stored, _death = _run_roll(conn, "/roll Attack 20 dc 5")
    assert roll_data is not None
    assert roll_data["raw"] == 7, roll_data          # serwer, nie client 20
    assert roll_data["is_nat20"] is False
    assert roll_data.get("dc") is None                # client dc=5 zignorowany dla ataku


def test_roll_command_admin_may_still_force_raw_and_dc():
    """Admin (testy/replay) zachowuje możliwość podania jawnego raw_roll i DC — guard is_admin."""
    conn = _roll_db(is_admin=1)
    roll_data, _msg, _stored, _death = _run_roll(conn, "/roll Attack 20 dc 30")
    assert roll_data["raw"] == 20                      # admin: client raw uszanowany
    assert roll_data["is_nat20"] is True
    assert roll_data.get("dc") == 30                   # admin: client dc uszanowany
