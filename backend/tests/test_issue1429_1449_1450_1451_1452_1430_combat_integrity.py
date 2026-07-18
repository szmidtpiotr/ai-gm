"""Krok 3 AUDIT — integralność silnika walki (combat_service.py).

Pokrywa 6 issue naraz (wszystkie dotykają combat_service.py):

#1429 (P0) — bramka tury na ataku gracza (atak tylko w swojej turze).
#1449 (P0) — anti-spoof attacker="player:N" (musi być combatantem) + /combat/start
             odrzuca nieznane enemy_keys (allow_pending domyślnie False).
#1450 (P1) — flee wymaga tury gracza + blokada przy otwartym pending_reaction;
             pojedynczy route /combat/flee (druga martwa definicja usunięta).
#1451 (P1) — licznik rundy podbija się względem PIERWSZEGO ŻYWEGO, nie order[0].
#1452 (P1) — dobicia przez DoT / towarzysza / summona dają nagrody (XP+złoto+łup).
#1430 (P1) — idempotencja loot-claim (loot_persisted) + turn_lock serializuje.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from _fixtures_schema import table_sql  # noqa: E402
from app.services import admin_config  # noqa: E402
from app.services import combat_service as cs  # noqa: E402
from app.services import turn_lock  # noqa: E402


# ─────────────────────────────── schema / helpers ────────────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT,
      display_name TEXT, is_admin INTEGER DEFAULT 0
    );
    INSERT INTO users (id, username, password_hash) VALUES (1, 'u', 'x');

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
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, xp_award, skills_json, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', 25, '{}', NULL, 0.0);

    """ + table_sql("game_config_meta") + """

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE, character_id INTEGER,
      round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT, combatants TEXT,
      status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT, loot_pool TEXT,
      loot_persisted INTEGER DEFAULT 0, post_combat_loot_json TEXT, boss_defeated INTEGER DEFAULT 0,
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


def _fresh_db(name: str) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_schema_sql())
    conn.close()
    return tmp


def _write_combat(tmp: Path, *, turn_order, current_turn, combatants, round_n=1,
                  status="active", ended_reason=None, loot_pool=None, loot_persisted=0,
                  post_combat_loot_json=None, character_id=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, turn_order, current_turn, combatants,
            status, ended_reason, loot_pool, loot_persisted, post_combat_loot_json)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (character_id, round_n, json.dumps(turn_order), current_turn,
         json.dumps(combatants), status, ended_reason,
         json.dumps(loot_pool) if loot_pool is not None else None,
         loot_persisted,
         json.dumps(post_combat_loot_json) if post_combat_loot_json is not None else None),
    )
    conn.commit()
    conn.close()


def _read_row(tmp: Path):
    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()
    return r


def _player():
    return {"id": "player", "type": "player", "name": "Aldric", "hp_current": 20,
            "hp_max": 20, "defense": 15, "zone": "engaged",
            "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10}}


def _enemy(cid="bandit_01", hp=12, zone="engaged"):
    return {"id": cid, "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
            "hp_current": hp, "hp_max": 12, "defense": 13, "attack_bonus": 3,
            "xp_award": 25, "tier": "standard", "zone": zone}


# ═══════════════════════════════ #1429 — bramka tury ══════════════════════════════

@patch("app.services.combat_service.roll_damage_dice", return_value=5)
def test_attack_out_of_turn_rejected(_dmg):
    """Atak gracza gdy current_turn należy do wroga → ValueError('not_player_turn'),
    HP wroga BEZ zmian (klient nie może wybić starcia poza kolejnością)."""
    tmp = _fresh_db("_c3_1429.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        _write_combat(tmp, turn_order=["bandit_01", "player"], current_turn="bandit_01",
                      combatants=[_player(), _enemy(hp=12)])
        with pytest.raises(ValueError, match="not_player_turn"):
            cs.resolve_attack(1, roll_result=999, attacker="player", raw_d20=20, authoritative=True)
        # HP wroga nietknięte
        combatants = json.loads(_read_row(tmp)["combatants"])
        enemy = next(c for c in combatants if c["id"] == "bandit_01")
        assert enemy["hp_current"] == 12


@patch("app.services.combat_service.roll_damage_dice", return_value=5)
def test_attack_on_player_turn_allowed(_dmg):
    """Regresja: gdy JEST tura gracza, atak przechodzi (bramka nie blokuje legalnej tury)."""
    tmp = _fresh_db("_c3_1429b.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.combat_service.roll_d20", return_value=15):
        _write_combat(tmp, turn_order=["player", "bandit_01"], current_turn="player",
                      combatants=[_player(), _enemy(hp=12)])
        res = cs.resolve_attack(1, roll_result=None, attacker="player", authoritative=True)
        assert "hit" in res
        assert res.get("blocked") is not True


# ═══════════════════════════════ #1449 — spoof / start ════════════════════════════

@patch("app.services.combat_service.roll_damage_dice", return_value=5)
def test_attacker_spoof_rejected(_dmg):
    """Solo-walka + attacker='player:999' (player:999 NIE jest combatantem) →
    ValueError('attacker_not_in_combat'). Bez tego = farm XP na cudzą postać."""
    tmp = _fresh_db("_c3_1449a.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        _write_combat(tmp, turn_order=["player", "bandit_01"], current_turn="player",
                      combatants=[_player(), _enemy(hp=12)])
        with pytest.raises(ValueError, match="attacker_not_in_combat"):
            cs.resolve_attack(1, roll_result=None, attacker="player:999", authoritative=True)


def test_api_resolve_attack_rejects_non_enum_attacker():
    """Endpoint /resolve-attack akceptuje tylko attacker ∈ {player,enemy}; 'player:5' → 400
    (obrona-w-głąb; spoof MP-ida odcięty na warstwie API, PRZED lockiem)."""
    from app.api import combat as combat_api
    body = combat_api.ResolveAttackRequest(attacker="player:5")
    with patch.object(combat_api, "assert_campaign_owner", lambda *a, **k: None):
        with pytest.raises(combat_api.HTTPException) as ei:
            combat_api.post_resolve_attack(1, body, authorization="x")
    assert ei.value.status_code == 400


def test_combat_start_rejects_unknown_enemy_key_via_api():
    """initiate_combat domyślnie allow_pending=False (ścieżka klienta /combat/start):
    nieznany enemy_key → ValueError (mapowany na 400), zero nowych wierszy w konfigu."""
    tmp = _fresh_db("_c3_1449b.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        with pytest.raises(ValueError, match="unknown enemy key"):
            cs.initiate_combat(1, 1, ["totalnie_fejkowy_wrog_xyz"])
        # katalog nie spuchł — brak pending template
        conn = sqlite3.connect(str(tmp))
        n = conn.execute("SELECT COUNT(*) FROM game_config_enemies WHERE key='totalnie_fejkowy_wrog_xyz'").fetchone()[0]
        conn.close()
        assert n == 0


def test_llm_tag_path_still_creates_pending():
    """Zaufana ścieżka (turn-pipeline / tag LLM) → allow_pending=True → nieznany klucz
    NADAL tworzy pending_review template i walka rusza (regres D2/#377 nie może wrócić)."""
    tmp = _fresh_db("_c3_1449c.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.world_service._auto_populate_enemy_loot", lambda *a, **k: None):
        state = cs.initiate_combat(1, 1, ["goblin_szaman_x"], allow_pending=True)
        assert state and state.get("status") == "active"
        conn = sqlite3.connect(str(tmp))
        row = conn.execute("SELECT review_status FROM game_config_enemies WHERE key='goblin_szaman_x'").fetchone()
        conn.close()
        assert row is not None and row[0] == "pending_review"


# ═══════════════════════════════ #1450 — ucieczka ════════════════════════════════

def test_flee_requires_player_turn():
    """resolve_player_flee w turze wroga → ok=False reason='not_player_turn'."""
    tmp = _fresh_db("_c3_1450a.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        _write_combat(tmp, turn_order=["bandit_01", "player"], current_turn="bandit_01",
                      combatants=[_player(), _enemy(hp=12)])
        res = cs.resolve_player_flee(1)
        assert res["ok"] is False and res["reason"] == "not_player_turn"


def test_flee_blocked_during_reaction_window():
    """Otwarte pending_reaction → flee zablokowana (reason='pending_reaction_open'),
    inaczej dmg z reakcji ginie i osierocone okno blokuje kolejne reakcje."""
    tmp = _fresh_db("_c3_1450b.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        p = _player()
        p["pending_reaction"] = {"attack_roll": 18, "damage": 6, "round": 1, "enemy_name": "Bandit"}
        _write_combat(tmp, turn_order=["player", "bandit_01"], current_turn="player",
                      combatants=[p, _enemy(hp=12)])
        res = cs.resolve_player_flee(1)
        assert res["ok"] is False and res["reason"] == "pending_reaction_open"


def test_flee_route_single_and_rolls():
    """Tylko JEDNA definicja route /combat/flee (druga martwa usunięta), i wywołuje
    resolve_player_flee (rzut #1210), a nie bezwarunkowe end_combat('fled')."""
    from app.api import combat as combat_api
    flee_routes = [r for r in combat_api.router.routes
                   if getattr(r, "path", "").endswith("/combat/flee")]
    assert len(flee_routes) == 1, f"oczekiwano 1 route flee, jest {len(flee_routes)}"
    src = Path(combat_api.__file__).read_text()
    # martwa druga definicja z bezwarunkowym end_combat("fled") nie może istnieć
    assert src.count('def post_flee(') == 1


# ═══════════════════════════════ #1451 — licznik rundy ═══════════════════════════

def test_round_increments_after_first_initiative_actor_dies():
    """2 wrogów, order[0]=wróg (wygrał inicjatywę), ginie. Pełny cykl kolejki po jego
    śmierci → round rośnie do 2 (wrap liczony wg living[0], nie martwego order[0])."""
    tmp = _fresh_db("_c3_1451.db")
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        dead_enemy = _enemy("bandit_01", hp=0)   # order[0] martwy
        alive_enemy = _enemy("bandit_02", hp=12)
        _write_combat(tmp, turn_order=["bandit_01", "player", "bandit_02"],
                      current_turn="player", round_n=1,
                      combatants=[dead_enemy, _player(), alive_enemy])
        # player -> bandit_02 (brak wrapu: player == first_in_order żywych)
        cs.advance_turn(1)
        assert _read_row(tmp)["current_turn"] == "bandit_02"
        assert int(_read_row(tmp)["round"]) == 1
        # bandit_02 -> player = wrap do first_in_order → round bump
        cs.advance_turn(1)
        assert _read_row(tmp)["current_turn"] == "player"
        assert int(_read_row(tmp)["round"]) == 2


# ═══════════════════════════════ #1452 — dobicia nie-ręką ════════════════════════

def _patch_rewards():
    """Patchuje granty (bestiariusz/XP/łup) na lekkie mocki — testujemy WYWOŁANIE nagrody."""
    return [
        patch("app.services.combat_service._credit_bestiary_kill", lambda *a, **k: None),
        patch("app.services.xp_service.resolve_enemy_defeat_xp_amount", return_value=(25, "flat")),
        patch("app.services.xp_service.grant_character_xp",
              return_value={"xp_available": 25}),
        patch("app.services.loot_service.roll_loot_with_consolation", return_value=[]),
        patch("app.services.loot_service.roll_gold_drop", return_value=7),
        patch("app.services.loot_service.apply_character_gold_delta", MagicMock()),
    ]


def test_companion_kill_grants_rewards():
    """Towarzysz dobija wroga → XP+złoto przyznane (grant_character_xp wywołane z xp wroga,
    gold delta na postać). Wcześniej HP→0 bez żadnej nagrody."""
    tmp = _fresh_db("_c3_1452a.db")
    patches = _patch_rewards()
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.combat_service.roll_d20", return_value=20), \
         patch("app.services.combat_service.roll_damage_dice", return_value=5):
        for p in patches:
            p.start()
        try:
            comp = {"id": "companion_merc", "type": "companion", "name": "Najemnik",
                    "attack_bonus": 5, "damage_dice": "1d6", "hp_current": 10, "hp_max": 10,
                    "zone": "engaged"}
            enemy = _enemy("bandit_01", hp=2)
            combatants = [_player(), comp, enemy]
            _write_combat(tmp, turn_order=["player", "companion_merc", "bandit_01"],
                          current_turn="companion_merc", combatants=combatants)
            row = _read_row(tmp)
            conn = cs._conn()
            try:
                cs._resolve_companion_attack_inline(conn, row, 1, combatants, comp)
                conn.commit()
            finally:
                conn.close()
            import app.services.xp_service as xps
            import app.services.loot_service as lts
            assert xps.grant_character_xp.called, "brak grantu XP za dobicie towarzysza"
            _, args, kwargs = xps.grant_character_xp.mock_calls[0]
            assert args[2] == 25  # xpa = xp wroga
            assert lts.apply_character_gold_delta.called
            assert enemy.get("dead") is True
        finally:
            for p in patches:
                p.stop()


def test_dot_kill_grants_rewards():
    """DoT (podpalenie) dobija wroga w jego turze → XP+złoto przyznane
    (evaluate_current_turn_conditions woła _process_enemy_death dla type=='enemy')."""
    tmp = _fresh_db("_c3_1452b.db")
    patches = _patch_rewards()
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)):
        for p in patches:
            p.start()
        try:
            enemy = _enemy("bandit_01", hp=3)
            enemy["conditions"] = [{
                "key": "on_fire", "label": "Podpalenie",
                "effect_json": json.dumps({"effects": [
                    {"type": "dot", "tick": "start_turn", "value": 5, "damage_type": "fire"}
                ]}),
            }]
            combatants = [_player(), enemy]
            _write_combat(tmp, turn_order=["bandit_01", "player"], current_turn="bandit_01",
                          combatants=combatants)
            cs.evaluate_current_turn_conditions(1)
            import app.services.xp_service as xps
            import app.services.loot_service as lts
            assert xps.grant_character_xp.called, "brak grantu XP za dobicie DoT"
            assert lts.apply_character_gold_delta.called
            # wróg oznaczony martwym w combatants
            row = _read_row(tmp)
            e = next(c for c in json.loads(row["combatants"]) if c["id"] == "bandit_01")
            assert int(e["hp_current"]) <= 0
            assert e.get("dead") is True
        finally:
            for p in patches:
                p.stop()


# ═══════════════════════════════ #1430 — lock / idempotencja ═════════════════════

def test_double_loot_claim_grants_once():
    """Drugi claim po rozliczonym łupie (loot_persisted=1) NIE przyznaje ponownie —
    zwraca already_claimed, grant_loot_to_character wołane dokładnie raz."""
    tmp = _fresh_db("_c3_1430a.db")
    pool = [{"key": "gold_coin", "item_type": "item", "quantity": 1}]
    with patch.object(cs, "COMBAT_DB_PATH", str(tmp)), \
         patch.object(admin_config, "DB_PATH", str(tmp)), \
         patch("app.services.loot_service.grant_loot_to_character",
               return_value=[{"key": "gold_coin", "inventory_id": None}]) as gmock, \
         patch("app.services.loot_service.build_drop_comparison", return_value=None):
        _write_combat(tmp, turn_order=["player"], current_turn="player",
                      combatants=[_player()], status="ended", ended_reason="victory",
                      loot_pool=pool)
        first = cs.claim_post_combat_loot(1, character_id=1, selected_indexes=[0])
        assert first["claimed"], first
        assert gmock.call_count == 1
        # drugi claim: loot_persisted=1 → already_claimed, brak drugiego grantu
        second = cs.claim_post_combat_loot(1, character_id=1, selected_indexes=[0])
        assert second.get("claimed") == []
        assert "already_claimed" in second
        assert gmock.call_count == 1, "grant wywołany drugi raz → duplikacja łupu"


def test_double_consumable_heals_once():
    """turn_lock serializuje mutujące endpointy: drugie równoległe acquire tej samej
    kampanii → 409 (proxy: podwójne leczenie z jednej mikstury odcięte)."""
    turn_lock._reset_for_tests()
    from app.api import combat as combat_api
    lock = turn_lock.acquire_or_409(1)
    try:
        with pytest.raises(combat_api.HTTPException) as ei:
            turn_lock.acquire_or_409(1)
        assert ei.value.status_code == 409
    finally:
        turn_lock.release(lock)
    # po zwolnieniu ponowne acquire przechodzi (lock nie zabrickowany)
    k2 = turn_lock.acquire_or_409(1)
    turn_lock.release(k2)
