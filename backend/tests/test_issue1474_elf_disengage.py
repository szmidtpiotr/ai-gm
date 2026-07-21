"""Issue #1474 — odskok elfa: darmowe wyjście ze ZWARCIA po własnym ataku.

Test: ``d20 + DEX_mod + rank(acrobatics) + proficiency ≥ DC 12``.
Sukces → strefa DYSTANS bez zużycia tury; porażka → zostaje w zwarciu, bez kary.
Raz na rundę. Odskok jest bramkowany rasą — dla nie-elfa `resolve_elf_disengage`
zwraca None, więc wpięcie w endpoint ataku nie dotyka pozostałych ras.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import combat_service as cs


def _schema_sql(race: str, acrobatics_rank: int = 0) -> str:
    player_sheet = {
        "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 12, "CHA": 10},
        "current_hp": 30,
        "max_hp": 30,
        "defense": {"base": 14},
        "equipped_weapon": "bow",
        "archetype": "rogue",
        "skills": {"acrobatics": acrobatics_rank},
        "conditions": [],
    }
    psj = json.dumps(player_sheet, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL, display_name TEXT NOT NULL
    );
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, system_id TEXT NOT NULL,
      model_id TEXT NOT NULL, owner_user_id INTEGER NOT NULL,
      language TEXT NOT NULL DEFAULT 'pl', mode TEXT NOT NULL DEFAULT 'solo',
      status TEXT NOT NULL DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1,'I1474','fantasy','m',1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL, name TEXT NOT NULL, system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL, race TEXT
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, race)
    VALUES (1,1,1,'Ilwen','fantasy','{psj}','{race}');

    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key, label, damage_die, weapon_type, linked_stat, allowed_classes)
    VALUES ('bow','Bow','1d6','ranged','DEX','rogue');

    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, drop_chance, skills_json)
    VALUES ('bandit','Bandit',30,13,3,1,'1d4',0.0,'{{}}');

    CREATE TABLE active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL, round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL, current_turn TEXT NOT NULL, combatants TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT,
      location_tag TEXT DEFAULT NULL, loot_pool TEXT DEFAULT NULL,
      created_at TEXT, updated_at TEXT
    );

    CREATE TABLE combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL, turn_number REAL NOT NULL, actor TEXT NOT NULL,
      event_type TEXT NOT NULL, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
      target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );
    """


def _make_db(tmp_path, race: str, acrobatics_rank: int = 0) -> Path:
    p = tmp_path / f"i1474_{race}_{acrobatics_rank}.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql(race, acrobatics_rank))
        conn.commit()
    finally:
        conn.close()
    return p


def _force_state(db: Path, *, player_zone: str, turn: str = "player") -> None:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id = 1").fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        enemy_id = ""
        for c in combatants:
            if c.get("type") == "player":
                c["zone"] = player_zone
                c.pop("elf_disengage_marker", None)
            else:
                c["zone"] = cs.ZONE_ENGAGED
                enemy_id = str(c.get("id"))
        conn.execute(
            "UPDATE active_combat SET combatants = ?, current_turn = ? WHERE campaign_id = 1",
            (json.dumps(combatants, ensure_ascii=False), "player" if turn == "player" else enemy_id),
        )
        conn.commit()
    finally:
        conn.close()


def _player_zone(db: Path) -> str:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id = 1").fetchone()
        for c in json.loads(row["combatants"] or "[]"):
            if c.get("type") == "player":
                return str(c.get("zone") or "")
        return ""
    finally:
        conn.close()


def _current_turn(db: Path) -> str:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return str(conn.execute(
            "SELECT current_turn FROM active_combat WHERE campaign_id = 1"
        ).fetchone()["current_turn"])
    finally:
        conn.close()


# ─── Sukces / porażka ────────────────────────────────────────────────────────

def test_successful_disengage_moves_to_ranged_without_costing_the_turn(tmp_path):
    db = _make_db(tmp_path, "elf")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=10):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED)

        out = cs.resolve_elf_disengage(1)

    # d20 10 + DEX_mod(+2) = 12 ≥ DC 12
    assert out is not None and out["success"] is True
    assert out["roll"]["total"] == 12 and out["dc"] == cs.ELF_DISENGAGE_DC
    assert out["to"] == cs.ZONE_RANGED
    assert _player_zone(db) == cs.ZONE_RANGED
    # Darmowa akcja — tura wciąż należy do gracza (advance robi endpoint po ataku).
    assert _current_turn(db) == "player"


def test_failed_disengage_keeps_elf_engaged(tmp_path):
    db = _make_db(tmp_path, "elf")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=5):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED)

        out = cs.resolve_elf_disengage(1)

    assert out is not None and out["success"] is False
    assert out["to"] == cs.ZONE_ENGAGED
    assert _player_zone(db) == cs.ZONE_ENGAGED
    # Porażka bez dodatkowej kary — tura nadal gracza, żadnych obrażeń.
    assert _current_turn(db) == "player"


def test_acrobatics_rank_and_proficiency_count(tmp_path):
    """Ranga 3 daje +3 rangi i +2 biegłości — ten sam rzut wystarcza z zapasem."""
    db = _make_db(tmp_path, "elf", acrobatics_rank=3)
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=5):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED)

        out = cs.resolve_elf_disengage(1)

    assert out["roll"] == {"raw": 5, "dex_mod": 2, "skill_rank": 3, "proficiency": 2, "total": 12}
    assert out["success"] is True


# ─── Bramki ──────────────────────────────────────────────────────────────────

def test_non_elf_never_disengages(tmp_path):
    db = _make_db(tmp_path, "human")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=20):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED)

        assert cs.resolve_elf_disengage(1) is None
    assert _player_zone(db) == cs.ZONE_ENGAGED


def test_no_disengage_when_already_at_range(tmp_path):
    db = _make_db(tmp_path, "elf")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=20):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_RANGED)

        assert cs.resolve_elf_disengage(1) is None


def test_only_once_per_round(tmp_path):
    db = _make_db(tmp_path, "elf")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=5):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED)

        first = cs.resolve_elf_disengage(1)
        second = cs.resolve_elf_disengage(1)

    assert first is not None and first["success"] is False
    assert second is None, "druga próba w tej samej rundzie nie może się odbyć"


def test_no_disengage_outside_player_turn(tmp_path):
    db = _make_db(tmp_path, "elf")
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
         patch.object(cs, "roll_d20", return_value=20):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_state(db, player_zone=cs.ZONE_ENGAGED, turn="enemy")

        assert cs.resolve_elf_disengage(1) is None


def test_elf_gets_ranged_attack_bonus(tmp_path):
    """#1474 — łuk to elfia droga: +1 do rzutu ataku bronią dystansową."""
    bow = {"key": "bow", "label": "Łuk", "weapon_type": "ranged", "damage_die": "1d6",
           "linked_stat": "DEX", "attack_bonus": 0, "damage_bonus": 0}

    def _attack(race: str) -> dict:
        db = _make_db(tmp_path, race)
        with patch.object(cs, "COMBAT_DB_PATH", str(db)), \
             patch.object(cs, "roll_d20", return_value=10):
            cs.initiate_combat(1, 1, ["bandit"])
            _force_state(db, player_zone=cs.ZONE_RANGED)
            return cs.resolve_attack(1, None, attacker="player", raw_d20=12, weapon_override=bow)

    elf_out = _attack("elf")
    human_out = _attack("human")

    assert elf_out.get("elf_ranged_bonus") == cs.ELF_RANGED_ATTACK_BONUS
    assert human_out.get("elf_ranged_bonus") is None
    assert cs.ELF_RANGED_ATTACK_BONUS == 1


def test_dc_is_documented_starting_value():
    assert cs.ELF_DISENGAGE_DC == 12
    assert cs.ELF_DISENGAGE_SKILL == "acrobatics"
