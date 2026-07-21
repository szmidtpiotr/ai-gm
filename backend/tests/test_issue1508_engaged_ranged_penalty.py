"""Issue #1508 (BALANS) — −2 do ataków dystansowych i czarów ze strefy ZWARCIE.

Bez tej kary strefa nic nie kosztuje dystansowca: wróg walczący wręcz pali całą turę
na doskok (kontrakt #232), a gracz strzela/czaruje w zwarciu bez konsekwencji. Każdy
mechanizm oddalania się (odskok elfa #1474, Chwyt sztauera #1476) zamieniał wtedy
walkę w nieskończony kiting.

Zakres testu:
  * matryca helpera ``engaged_ranged_penalty`` (strefa × typ broni),
  * tor gracza — ten sam rzut d20 daje total mniejszy o 2 w ZWARCIU niż na DYSTANSIE,
  * melee gracza nietknięte,
  * symetria — wróg dystansowy (łucznik) w ZWARCIU strzela z tą samą karą,
  * wróg walczący wręcz bez kary.
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


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _schema_sql() -> str:
    player_sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 12, "CHA": 10},
        "current_hp": 40,
        "max_hp": 40,
        "defense": {"base": 15},
        # Łuk na arkuszu: bramka strefy w `_attack_target_select` czyta broń z arkusza
        # (nie `weapon_override`), więc bez tego strzał z DYSTANSU odbijał się jako
        # out_of_range i test porównywał tylko jedną stronę.
        "equipped_weapon": "bow",
        "archetype": "warrior",
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
    VALUES (1,'I1508','fantasy','m',1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL, name TEXT NOT NULL, system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (1,1,1,'Aldric','fantasy','{psj}');

    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key, label, damage_die, weapon_type, linked_stat, allowed_classes)
    VALUES ('sword','Sword','1d8','melee','STR','warrior');
    INSERT INTO game_config_weapons (key, label, damage_die, weapon_type, linked_stat, allowed_classes)
    VALUES ('bow','Bow','1d6','ranged','DEX','warrior');

    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, drop_chance, skills_json)
    VALUES ('bandit','Bandit',40,13,3,1,'1d4',0.0,'{{}}');
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, drop_chance, skills_json)
    VALUES ('archer','Archer',40,13,3,1,'1d4',0.0,'{{}}');

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


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "i1508.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(p)):
        yield p


def _set_zones(db: Path, *, player_zone: str, enemy_zone: str, whose_turn: str) -> str:
    """Ustawia strefy obu stron i czyją jest tura. Zwraca id wroga."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT combatants FROM active_combat WHERE campaign_id = 1"
        ).fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        enemy_id = ""
        for c in combatants:
            if c.get("type") == "player":
                c["zone"] = player_zone
            else:
                c["zone"] = enemy_zone
                enemy_id = str(c.get("id"))
        turn = "player" if whose_turn == "player" else enemy_id
        conn.execute(
            "UPDATE active_combat SET combatants = ?, current_turn = ? WHERE campaign_id = 1",
            (json.dumps(combatants, ensure_ascii=False), turn),
        )
        conn.commit()
        return enemy_id
    finally:
        conn.close()


_BOW = {
    "key": "bow", "label": "Łuk", "weapon_type": "ranged", "damage_die": "1d6",
    "linked_stat": "DEX", "attack_bonus": 0, "damage_bonus": 0,
}
_SWORD = {
    "key": "sword", "label": "Miecz", "weapon_type": "melee", "damage_die": "1d8",
    "linked_stat": "STR", "attack_bonus": 0, "damage_bonus": 0,
}


# ─── Helper (matryca) ────────────────────────────────────────────────────────

def test_helper_penalty_matrix():
    assert cs.engaged_ranged_penalty(cs.ZONE_ENGAGED, "ranged") == cs.ENGAGED_RANGED_ATTACK_PENALTY
    assert cs.engaged_ranged_penalty(cs.ZONE_ENGAGED, "spell") == cs.ENGAGED_RANGED_ATTACK_PENALTY
    # Melee w zwarciu — bez kary (to jego strefa).
    assert cs.engaged_ranged_penalty(cs.ZONE_ENGAGED, "melee") == 0
    # Dystans ze strefy DYSTANS — bez kary.
    assert cs.engaged_ranged_penalty(cs.ZONE_RANGED, "ranged") == 0
    assert cs.engaged_ranged_penalty(cs.ZONE_RANGED, "spell") == 0
    # Kara jest ujemna i wynosi −2 (wartość STARTOWA, Sandbox-tunable).
    assert cs.ENGAGED_RANGED_ATTACK_PENALTY == -2


def test_helper_defaults_are_safe():
    """Brak danych → traktujemy jak melee w zwarciu, czyli zero kary (bez regresji)."""
    assert cs.engaged_ranged_penalty(None, None) == 0
    assert cs.engaged_ranged_penalty("", "") == 0


# ─── Tor gracza ──────────────────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_player_ranged_attack_from_engaged_is_penalized(mock_r20, db):
    mock_r20.return_value = 10
    cs.initiate_combat(1, 1, ["bandit"])

    _set_zones(db, player_zone=cs.ZONE_ENGAGED, enemy_zone=cs.ZONE_ENGAGED, whose_turn="player")
    engaged = cs.resolve_attack(1, None, attacker="player", raw_d20=12, weapon_override=_BOW)

    _set_zones(db, player_zone=cs.ZONE_RANGED, enemy_zone=cs.ZONE_ENGAGED, whose_turn="player")
    ranged = cs.resolve_attack(1, None, attacker="player", raw_d20=12, weapon_override=_BOW)

    assert engaged.get("engaged_ranged_penalty") == cs.ENGAGED_RANGED_ATTACK_PENALTY
    assert ranged.get("engaged_ranged_penalty") is None
    assert int(engaged["attack_roll"]["total"]) == int(ranged["attack_roll"]["total"]) - 2


@patch("app.services.combat_service.roll_d20")
def test_player_melee_attack_from_engaged_is_not_penalized(mock_r20, db):
    mock_r20.return_value = 10
    cs.initiate_combat(1, 1, ["bandit"])
    _set_zones(db, player_zone=cs.ZONE_ENGAGED, enemy_zone=cs.ZONE_ENGAGED, whose_turn="player")

    out = cs.resolve_attack(1, None, attacker="player", raw_d20=12, weapon_override=_SWORD)

    assert out.get("engaged_ranged_penalty") is None
    assert "engaged_ranged_penalty" not in (out.get("attack_roll") or {})


# ─── Symetria: tor wroga ─────────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_ranged_enemy_in_engaged_zone_is_penalized(mock_r20, db):
    """Łucznik wciągnięty do zwarcia strzela z −2 — ta sama zasada co u gracza."""
    mock_r20.return_value = 10
    cs.initiate_combat(1, 1, ["archer"])

    _set_zones(db, player_zone=cs.ZONE_ENGAGED, enemy_zone=cs.ZONE_ENGAGED, whose_turn="enemy")
    engaged = cs.resolve_attack(1, 0, attacker="enemy")

    _set_zones(db, player_zone=cs.ZONE_ENGAGED, enemy_zone=cs.ZONE_RANGED, whose_turn="enemy")
    ranged = cs.resolve_attack(1, 0, attacker="enemy")

    assert engaged.get("engaged_ranged_penalty") == cs.ENGAGED_RANGED_ATTACK_PENALTY
    assert ranged.get("engaged_ranged_penalty") is None
    assert int(engaged["attack_roll"]) == int(ranged["attack_roll"]) - 2


@patch("app.services.combat_service.roll_d20")
def test_melee_enemy_is_not_penalized(mock_r20, db):
    mock_r20.return_value = 10
    cs.initiate_combat(1, 1, ["bandit"])
    _set_zones(db, player_zone=cs.ZONE_ENGAGED, enemy_zone=cs.ZONE_ENGAGED, whose_turn="enemy")

    out = cs.resolve_attack(1, 0, attacker="enemy")

    assert out.get("engaged_ranged_penalty") is None
