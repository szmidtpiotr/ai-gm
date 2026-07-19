"""Krok G2 AUDIT — mechaniki krasnoluda (Rdzeń-magia + Wzrok górnika + Reperuj).

Pokrywa 3 issue (Faza AUDIT):

#1460 — efekty czarów Rdzenia DATA-DRIVEN przez effect_json (nie hardcode):
        rdzen_pulse/deep_quake = attack_aoe; vein_bleed = ignore_armor; on_hit_conditions
        prone/stunned/rdzen_poison przez _build_condition_entry; deep_quake self-damage.
#1461 — Wzrok górnika: get_darkvision_bonus wpięty w rzut percepcji w lochu
        (krasnolud +3, człowiek −4; poza lochem 0).
#1462 (Wariant B — decyzja Piotra) — Reperuj przywraca durability_current sprzętu
        (nie leczy PŻ), ownership-check, ZERO złota przy no-op.
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
from app.services import dungeon_service  # noqa: E402
from app.services import skill_service  # noqa: E402
from app.services import spell_service  # noqa: E402


# ─────────────────────────────── combat schema / helpers ─────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT
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
      name TEXT, system_id TEXT, race TEXT DEFAULT 'human', sheet_json TEXT,
      location TEXT, is_active INTEGER DEFAULT 1
    );

    CREATE TABLE game_config_spells (
      key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1, mana_cost INTEGER DEFAULT 2,
      spell_type TEXT DEFAULT 'attack', damage_die TEXT, heal_die TEXT, effect_stat TEXT,
      effect_type TEXT, effect_duration INTEGER DEFAULT 1, target_zone TEXT DEFAULT 'any',
      aoe INTEGER DEFAULT 0, description TEXT, race_lock TEXT,
      rank2_json TEXT, rank3_json TEXT, is_active INTEGER DEFAULT 1, effect_json TEXT
    );

    CREATE TABLE character_spells (
      id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, spell_key TEXT,
      rank INTEGER DEFAULT 1, use_count INTEGER DEFAULT 0, learned_at_level INTEGER DEFAULT 1
    );

    CREATE TABLE game_config_conditions (
      key TEXT PRIMARY KEY, label TEXT, effect_json TEXT, description TEXT,
      is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0, auto_remove TEXT
    );
    INSERT INTO game_config_conditions (key, label, effect_json, is_active) VALUES
      ('stunned', 'Ogłuszony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"skip_turn","chance":1.0,"expires":"duration_rounds:1"}]}', 1),
      ('prone', 'Powalony', '{"schema_version":1,"effect_category":"character_condition","grants_attacker_bonus":{"atk_bonus":2},"effects":[{"type":"static_stat_modifier","stat":"DEX","value":-2,"expires":"duration_rounds:1"}]}', 1),
      ('rdzen_poison', 'Zatrucie Rdzenia', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"dot","value":2,"damage_type":"poison","tick":"start_turn","expires":"duration_rounds:3"}]}', 1);

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, xp_award, skills_json, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 60, 10, 3, -10, '1d8', 25, '{}', NULL, 0.0);

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


def _sheet(*, archetype="scholar", level=5, hp=30, mana=10):
    return json.dumps({
        "archetype": archetype, "level": level,
        "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
        "current_hp": hp, "max_hp": 30, "defense": {"base": 14},
        "current_mana": mana, "max_mana": 10,
    })


def _fresh_db(name: str, *, race="dwarf", sheet=None) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_schema_sql())
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, race, sheet_json) "
        "VALUES (1, 1, 1, 'Krasnal', 'fantasy', ?, ?)",
        (race, sheet if sheet is not None else _sheet()),
    )
    conn.commit()
    conn.close()
    return tmp


def _add_spell(tmp: Path, key, **cols):
    conn = sqlite3.connect(str(tmp))
    cols.setdefault("label", key)
    keys = ["key"] + list(cols.keys())
    vals = [key] + list(cols.values())
    conn.execute(
        f"INSERT INTO game_config_spells ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})",
        vals,
    )
    conn.commit()
    conn.close()


def _learn(tmp: Path, spell_key, rank=1, char_id=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (?,?,?)",
        (char_id, spell_key, rank),
    )
    conn.commit()
    conn.close()


def _write_combat(tmp: Path, *, current_turn="player", combatants=None, character_id=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, turn_order, current_turn, combatants, status)
           VALUES (1, ?, 1, ?, ?, ?, 'active')""",
        (character_id, json.dumps(["player", "bandit_01"]), current_turn,
         json.dumps(combatants if combatants is not None else [_player(), _enemy()])),
    )
    conn.commit()
    conn.close()


def _read_char_sheet(tmp: Path, char_id=1):
    conn = sqlite3.connect(str(tmp))
    r = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()
    conn.close()
    return json.loads(r[0]) if r and r[0] else {}


def _read_combatants(tmp: Path):
    conn = sqlite3.connect(str(tmp))
    r = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()
    return json.loads(r[0]) if r and r[0] else []


def _player():
    return {"id": "player", "type": "player", "name": "Krasnal", "hp_current": 30,
            "hp_max": 30, "defense": 14, "zone": "engaged",
            "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10}}


def _enemy(cid="bandit_01", hp=60, zone="engaged", defense=10):
    return {"id": cid, "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
            "hp_current": hp, "hp_max": 60, "defense": defense, "attack_bonus": 3,
            "dex_modifier": -10, "con_modifier": 0, "xp_award": 25, "tier": "standard", "zone": zone,
            "stats": {"STR": 12, "DEX": 8, "CON": 10, "INT": 8, "WIS": 8, "CHA": 8}}


def _ctx(tmp):
    return [
        patch.object(cs, "COMBAT_DB_PATH", str(tmp)),
        patch.object(admin_config, "DB_PATH", str(tmp)),
        patch.object(spell_service, "DB_PATH", str(tmp)),
    ]


def _cast(tmp, spell_key, raw_d20, *, target_id="bandit_01"):
    ctxs = _ctx(tmp) + [patch("app.services.combat_service.roll_d20", return_value=raw_d20)]
    for c in ctxs:
        c.start()
    try:
        return cs.resolve_attack(1, None, "player", raw_d20=raw_d20,
                                 spell_key=spell_key, target_id=target_id, authoritative=False)
    finally:
        for c in ctxs:
            c.stop()


# ═══════════════════════════ #1460 — efekty czarów Rdzenia ═══════════════════════

def test_rdzen_pulse_aoe_stun():
    """rdzen_pulse (attack_aoe, effect_json on_hit stunned) trafia WSZYSTKICH wrogów
    i nakłada każdemu kondycję `stunned` z KATALOGU (effect_json skip_turn — silnik
    faktycznie pomija turę). Data-driven z effect_json, nie hardcode per spell_key."""
    tmp = _fresh_db("_g2_1460_pulse.db")
    _add_spell(tmp, "rdzen_pulse", tier=2, mana_cost=2, spell_type="attack_aoe",
               damage_die="2d4", aoe=1, race_lock="dwarf",
               effect_json='{"on_hit_conditions":[{"key":"stunned"}]}')
    _learn(tmp, "rdzen_pulse", rank=1)
    _write_combat(tmp, combatants=[_player(), _enemy("bandit_01"), _enemy("bandit_02")])
    res = _cast(tmp, "rdzen_pulse", 15)
    assert res.get("hit") is True, res
    assert res.get("spell_type") == "attack_aoe", res
    assert int(res.get("aoe_targets") or 0) >= 2, res
    combatants = _read_combatants(tmp)
    for cid in ("bandit_01", "bandit_02"):
        enemy = next(c for c in combatants if c["id"] == cid)
        stun = next((c for c in (enemy.get("conditions") or [])
                     if str(c.get("key")).lower() == "stunned"), None)
        assert stun is not None, f"{cid} bez kondycji stunned"
        assert "skip_turn" in json.dumps(stun.get("effect_json")), f"{cid} stunned bez skip_turn"


def test_vein_bleed_ignores_armor():
    """vein_bleed (effect_json ignore_armor) przebija pancerz — brak redukcji zbroją.
    Kontrola: identyczny czar bez ignore_armor DOSTAJE redukcję pancerza."""
    fixed = {"die": "3d6", "rolls": [6, 6, 6]}  # 18 bazowe, deterministyczne
    # vein_bleed → ignore_armor
    t1 = _fresh_db("_g2_1460_bleed.db")
    _add_spell(t1, "vein_bleed", tier=3, mana_cost=3, spell_type="attack", damage_die="3d6",
               race_lock="dwarf", effect_json='{"ignore_armor":true}')
    _learn(t1, "vein_bleed", rank=1)
    _write_combat(t1, combatants=[_player(), _enemy("bandit_01", defense=20)])
    with patch("app.services.combat_service.roll_dice_detailed", return_value=fixed):
        res_bleed = _cast(t1, "vein_bleed", 15)
    # kontrola → zwykły atak (pancerz redukuje)
    t2 = _fresh_db("_g2_1460_ctrl.db")
    _add_spell(t2, "plain_bolt", tier=3, mana_cost=3, spell_type="attack", damage_die="3d6",
               race_lock="dwarf")
    _learn(t2, "plain_bolt", rank=1)
    _write_combat(t2, combatants=[_player(), _enemy("bandit_01", defense=20)])
    with patch("app.services.combat_service.roll_dice_detailed", return_value=fixed):
        res_ctrl = _cast(t2, "plain_bolt", 15)

    assert res_bleed.get("hit") is True and res_ctrl.get("hit") is True
    assert int(res_bleed.get("armor_reduction") or 0) == 0, res_bleed
    assert int(res_ctrl.get("armor_reduction") or 0) > 0, res_ctrl
    assert int(res_bleed["damage"]) > int(res_ctrl["damage"]), (res_bleed, res_ctrl)


def test_black_vein_poison():
    """black_vein nakłada kondycję DoT `rdzen_poison` z katalogu; na turze wroga
    DoT tyka −2 PŻ (evaluate_current_turn_conditions faktycznie zdejmuje HP)."""
    tmp = _fresh_db("_g2_1460_poison.db")
    _add_spell(tmp, "black_vein", tier=5, mana_cost=5, spell_type="attack", damage_die="4d8",
               race_lock="dwarf", effect_json='{"on_hit_conditions":[{"key":"rdzen_poison"}]}')
    _learn(tmp, "black_vein", rank=1)
    _write_combat(tmp, combatants=[_player(), _enemy("bandit_01", hp=60)])
    res = _cast(tmp, "black_vein", 15)
    assert res.get("hit") is True, res
    combatants = _read_combatants(tmp)
    enemy = next(c for c in combatants if c["id"] == "bandit_01")
    poison = next((c for c in (enemy.get("conditions") or [])
                   if str(c.get("key")).lower() == "rdzen_poison"), None)
    assert poison is not None, "wróg bez kondycji rdzen_poison"
    assert '"dot"' in str(poison.get("effect_json") or ""), "rdzen_poison bez prymitywu dot"

    # DoT tyka na turze wroga: przełącz current_turn na wroga i wywołaj tick.
    hp_before = int(enemy.get("hp_current"))
    conn = sqlite3.connect(str(tmp))
    conn.execute("UPDATE active_combat SET current_turn='bandit_01', round=2 WHERE campaign_id=1")
    conn.commit()
    conn.close()
    ctxs = _ctx(tmp)
    for c in ctxs:
        c.start()
    try:
        cs.evaluate_current_turn_conditions(1)
    finally:
        for c in ctxs:
            c.stop()
    enemy2 = next(c for c in _read_combatants(tmp) if c["id"] == "bandit_01")
    assert int(enemy2.get("hp_current")) == hp_before - 2, (hp_before, enemy2.get("hp_current"))


def test_deep_quake_self_damage():
    """deep_quake (attack_aoe) zadaje prone wrogom i ZAWSZE rani rzucającego 1d4
    (effect_json.self_damage_die) — HP casteru spada."""
    tmp = _fresh_db("_g2_1460_quake.db", sheet=_sheet(hp=30))
    _add_spell(tmp, "deep_quake", tier=4, mana_cost=4, spell_type="attack_aoe", damage_die="2d8",
               aoe=1, race_lock="dwarf",
               effect_json='{"on_hit_conditions":[{"key":"prone"}],"self_damage_die":"1d4"}')
    _learn(tmp, "deep_quake", rank=1)
    _write_combat(tmp, combatants=[_player(), _enemy("bandit_01")])
    res = _cast(tmp, "deep_quake", 15)
    assert res.get("hit") is True, res
    assert 1 <= int(res.get("self_damage") or 0) <= 4, res
    assert int(_read_char_sheet(tmp).get("current_hp")) < 30
    enemy = next(c for c in _read_combatants(tmp) if c["id"] == "bandit_01")
    prone = next((c for c in (enemy.get("conditions") or [])
                  if str(c.get("key")).lower() == "prone"), None)
    assert prone is not None, "wróg nie został powalony (prone) przez deep_quake"


# ═══════════════════════════ #1461 — Wzrok górnika (darkvision) ══════════════════

def _darkvision_db(name: str, *, race: str) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, race TEXT, sheet_json TEXT)"
    )
    conn.execute("INSERT INTO characters (id, race, sheet_json) VALUES (1, ?, '{}')", (race,))
    conn.commit()
    conn.close()
    return tmp


def _resolve_perception(tmp: Path, *, in_dungeon: bool, d20=12):
    pending = {
        "skill_key": "perception",
        "modifier_breakdown": {"total": 0},
        "counter": {"counter_type": "dc", "dc": 12},
    }
    session_flags = {"dungeon_run": {"key": "krypta"}} if in_dungeon else {}
    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    try:
        with patch.object(dungeon_service, "DB_PATH", str(tmp)):
            return skill_service.resolve_skill_test(
                d20_roll=d20, pending=pending, conn=conn,
                campaign_id=1, character_id=1, session_flags=session_flags,
            )
    finally:
        conn.close()


def test_dwarf_darkvision_perception():
    """Krasnolud w lochu: percepcja +3 (Wzrok górnika). Człowiek: −4. Poza lochem: 0."""
    dwarf = _darkvision_db("_g2_1461_dwarf.db", race="dwarf")
    res = _resolve_perception(dwarf, in_dungeon=True)
    assert res.get("darkvision_bonus") == 3, res
    assert res.get("modifier") == 3, res  # mod_total podbity o darkvision

    human = _darkvision_db("_g2_1461_human.db", race="human")
    res_h = _resolve_perception(human, in_dungeon=True)
    assert res_h.get("darkvision_bonus") == -4, res_h

    # Poza lochem (brak dungeon_run) — bonus 0 dla obu ras.
    res_out = _resolve_perception(dwarf, in_dungeon=False)
    assert res_out.get("darkvision_bonus") == 0, res_out


# ═══════════════════════════ #1462 — Reperuj (Wariant B: durability) ═════════════

def _repair_db(name: str, *, owner_id=1, gold=100, items=None) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, race TEXT, user_id INTEGER, gold_gp INTEGER)"
    )
    conn.execute(
        "INSERT INTO characters (id, race, user_id, gold_gp) VALUES (1, 'dwarf', ?, ?)",
        (owner_id, gold),
    )
    conn.execute(
        """CREATE TABLE character_inventory (
             id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, weapon_key TEXT,
             armor_key TEXT, meta_json TEXT, durability_current INTEGER, durability_max INTEGER
           )"""
    )
    for it in (items or []):
        conn.execute(
            "INSERT INTO character_inventory (character_id, weapon_key, armor_key, durability_current, durability_max) "
            "VALUES (1, ?, ?, ?, ?)",
            (it.get("weapon_key"), it.get("armor_key"), it["cur"], it["max"]),
        )
    conn.commit()
    conn.close()
    return tmp


class _GoldSpy:
    """Zastępuje economy_service.change_gold — śledzi wywołania, mutuje gold_gp."""
    def __init__(self):
        self.calls = []

    def __call__(self, conn, character_id, delta, source, **kw):
        self.calls.append((character_id, delta, source))
        conn.execute("UPDATE characters SET gold_gp = gold_gp + ? WHERE id = ?", (delta, character_id))
        row = conn.execute("SELECT gold_gp FROM characters WHERE id=?", (character_id,)).fetchone()
        return int(row[0])


def _call_repair(tmp: Path, *, authed_uid=1):
    from app.api import characters as chars_api
    spy = _GoldSpy()
    with patch.object(chars_api, "DB_PATH", str(tmp)), \
         patch.object(chars_api, "resolve_authed_user_id", return_value=authed_uid), \
         patch("app.services.economy_service.change_gold", spy):
        result = chars_api.dwarf_repair(1, user_id=authed_uid, authorization=None)
    return result, spy


def _read_gold(tmp: Path):
    conn = sqlite3.connect(str(tmp))
    g = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    conn.close()
    return int(g)


def _read_durabilities(tmp: Path):
    conn = sqlite3.connect(str(tmp))
    rows = conn.execute("SELECT durability_current, durability_max FROM character_inventory ORDER BY id").fetchall()
    conn.close()
    return [(int(a), int(b)) for a, b in rows]


def test_dwarf_repair_effect():
    """Wariant B: Reperuj przywraca durability_current=durability_max uszkodzonemu
    sprzętowi (broń+zbroja) za 20 gp. No-op (nic uszkodzonego) → ZERO złota.
    Ownership: cudzy bohater → 403."""
    from fastapi import HTTPException

    # 1) uszkodzony sprzęt → naprawa + pobranie 20 gp
    tmp = _repair_db("_g2_1462_ok.db", gold=100, items=[
        {"weapon_key": "sword", "cur": 3, "max": 10},
        {"armor_key": "mail", "cur": 5, "max": 12},
    ])
    res, spy = _call_repair(tmp)
    assert res["ok"] is True and res["cost_gp"] == 20, res
    assert res["repaired_count"] == 2, res
    assert _read_durabilities(tmp) == [(10, 10), (12, 12)], "trwałość nieprzywrócona do max"
    assert _read_gold(tmp) == 80, "nie pobrano 20 gp"
    assert spy.calls == [(1, -20, "dwarf_repair")], spy.calls

    # 2) no-op — nic uszkodzonego → ZERO złota, change_gold nie wołany
    tmp2 = _repair_db("_g2_1462_noop.db", gold=100, items=[
        {"weapon_key": "sword", "cur": 10, "max": 10},
    ])
    res2, spy2 = _call_repair(tmp2)
    assert res2["ok"] is True and res2["cost_gp"] == 0, res2
    assert _read_gold(tmp2) == 100, "pobrano złoto przy no-op"
    assert spy2.calls == [], "change_gold wołany przy no-op"

    # 3) ownership — authed user != owner → 403, brak naprawy/pobrania
    tmp3 = _repair_db("_g2_1462_idor.db", owner_id=1, gold=100, items=[
        {"weapon_key": "sword", "cur": 1, "max": 10},
    ])
    with pytest.raises(HTTPException) as exc:
        _call_repair(tmp3, authed_uid=999)
    assert exc.value.status_code == 403
    assert _read_gold(tmp3) == 100
    assert _read_durabilities(tmp3) == [(1, 10)], "trwałość zmieniona mimo braku uprawnień"
