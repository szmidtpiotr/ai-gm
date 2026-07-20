"""SG-7 (#1481) — sól jako materiał przeciw-Rdzeniowy (docs/world/regions/siwe_granie.md §6).

Trzy efekty, jedna zasada fikcji: sól nie jest magiczna, jest OBOJĘTNA na Rdzeń.
Stąd każdy test ma bliźniaka na żywym wrogu — na trollu sól nie może zrobić nic.

  * Krąg soli     — istota Rdzenia nie wchodzi do zwarcia (i zostaje wypchnięta przy użyciu),
  * Solona klinga — +1k4 obrażeń istocie Rdzenia,
  * Szczypta soli — miscast o 1 stopień łagodniejszy (raz), −1 do obrażeń czarów.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import salt_service
from app.services import spell_service


# ── fikstury ─────────────────────────────────────────────────────────────────

def _enemies_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, creature_type TEXT)"
    )
    c.executemany(
        "INSERT INTO game_config_enemies (key, label, creature_type) VALUES (?, ?, ?)",
        [
            ("widmo_lodowe", "Widmo Lodowe", "undead"),
            ("straznik_rdzenia", "Strażnik Rdzenia", "rdzen"),
            ("imp", "Imp", "demon"),
            ("troll_gorski", "Troll Górski", None),
        ],
    )
    c.commit()
    return c


def _cond(key: str, effect_json: dict, runtime: dict | None = None) -> dict:
    return {
        "key": key,
        "label": key,
        "effect_json": json.dumps(effect_json, ensure_ascii=False),
        "runtime": runtime or {},
    }


SALT_CIRCLE_JSON = {"clear_on": "combat_end", "on_apply": "push_core_beings",
                    "effects": [{"type": "salt_ward", "expires": "duration_rounds:3"}]}
SALT_BLADE_JSON = {"clear_on": "combat_end", "effects": [{"type": "salt_edge", "bonus_dice": "1d4"}]}
SALT_PINCH_JSON = {"clear_on": "combat_end",
                   "effects": [{"type": "salt_miscast_softening"}, {"type": "salt_spell_damping"}]}


def _player(*conditions: dict) -> dict:
    return {"id": "player", "type": "player", "conditions": list(conditions)}


# ── klasyfikacja istot ───────────────────────────────────────────────────────

def test_creature_type_read_from_combatant_field_first():
    assert salt_service.is_core_being(None, {"creature_type": "undead"}) is True
    assert salt_service.is_core_being(None, {"creature_type": "beast"}) is False


def test_creature_type_falls_back_to_catalog_for_old_combats():
    """Walki zapisane przed tą falą nie mają pola w JSON-ie — musi zadziałać dociąg z bazy."""
    salt_service._CREATURE_TYPE_CACHE.clear()
    conn = _enemies_conn()
    assert salt_service.is_core_being(conn, {"enemy_key": "widmo_lodowe"}) is True
    assert salt_service.is_core_being(conn, {"enemy_key": "straznik_rdzenia"}) is True
    assert salt_service.is_core_being(conn, {"enemy_key": "imp"}) is True
    assert salt_service.is_core_being(conn, {"enemy_key": "troll_gorski"}) is False


def test_old_database_without_column_is_not_an_error():
    salt_service._CREATURE_TYPE_CACHE.clear()
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT)")
    c.execute("INSERT INTO game_config_enemies VALUES ('widmo_lodowe', 'Widmo')")
    c.commit()
    assert salt_service.is_core_being(c, {"enemy_key": "widmo_lodowe"}) is False


# ── Krąg soli ────────────────────────────────────────────────────────────────

def test_salt_circle_blocks_core_being_charge():
    player = _player(_cond("salt_circle", SALT_CIRCLE_JSON))
    assert salt_service.salt_circle_blocks_charge(
        None, player, {"creature_type": "undead"}
    ) is True


def test_salt_circle_does_not_block_a_living_enemy():
    player = _player(_cond("salt_circle", SALT_CIRCLE_JSON))
    assert salt_service.salt_circle_blocks_charge(
        None, player, {"creature_type": None, "enemy_key": "troll_gorski"}
    ) is False


def test_without_the_circle_nothing_is_blocked():
    assert salt_service.salt_circle_blocks_charge(
        None, _player(), {"creature_type": "undead"}
    ) is False


def test_salt_circle_push_moves_only_engaged_core_beings_to_ranged():
    """Rytuał wypycha nieumarłego ze zwarcia już przy użyciu — inaczej przedmiot byłby
    martwy, gdy widmo już stoi przy bohaterze. Troll i trup zostają, gdzie są."""
    from app.services import loot_service

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE active_combat (id INTEGER PRIMARY KEY, campaign_id INTEGER, "
        "character_id INTEGER, status TEXT, combatants TEXT, updated_at TEXT)"
    )
    c.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, creature_type TEXT)")
    combatants = [
        {"id": "player", "type": "player", "zone": "engaged", "hp_current": 20},
        {"id": "e1", "type": "enemy", "enemy_key": "widmo_lodowe", "name": "Widmo Lodowe",
         "creature_type": "undead", "zone": "engaged", "hp_current": 10},
        {"id": "e2", "type": "enemy", "enemy_key": "troll_gorski", "name": "Troll",
         "creature_type": None, "zone": "engaged", "hp_current": 30},
        {"id": "e3", "type": "enemy", "enemy_key": "widmo_lodowe", "name": "Martwe widmo",
         "creature_type": "undead", "zone": "engaged", "hp_current": 0},
    ]
    c.execute(
        "INSERT INTO active_combat (id, campaign_id, character_id, status, combatants) "
        "VALUES (1, 7, 3, 'active', ?)",
        (json.dumps(combatants),),
    )
    c.commit()

    pushed = loot_service._apply_on_apply_zone_push(
        c, campaign_id=7, character_id=3, condition=_cond("salt_circle", SALT_CIRCLE_JSON),
    )
    assert pushed == ["Widmo Lodowe"], pushed
    after = {x["id"]: x["zone"] for x in json.loads(
        c.execute("SELECT combatants FROM active_combat WHERE id = 1").fetchone()[0]
    )}
    assert after["e1"] == "ranged"
    assert after["e2"] == "engaged"   # żywy troll przechodzi przez sól bez wrażenia
    assert after["e3"] == "engaged"   # trup nigdzie nie idzie


def test_zone_push_ignored_for_conditions_without_the_flag():
    from app.services import loot_service

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    assert loot_service._apply_on_apply_zone_push(
        c, campaign_id=1, character_id=1, condition=_cond("hasted", {"effects": []}),
    ) == []


# ── Solona klinga ────────────────────────────────────────────────────────────

def test_salted_blade_adds_dice_against_core_being():
    player = _player(_cond("salted_blade", SALT_BLADE_JSON))
    bonus = salt_service.salted_blade_bonus(
        None, player, {"creature_type": "undead"}, roller=lambda expr: 4,
    )
    assert bonus == 4


def test_salted_blade_does_nothing_to_a_living_enemy():
    player = _player(_cond("salted_blade", SALT_BLADE_JSON))
    assert salt_service.salted_blade_bonus(
        None, player, {"creature_type": None}, roller=lambda expr: 4,
    ) == 0


def test_salted_blade_uses_the_declared_die():
    seen: list[str] = []

    def roller(expr: str) -> int:
        seen.append(expr)
        return 1

    salt_service.salted_blade_bonus(
        None, _player(_cond("salted_blade", SALT_BLADE_JSON)),
        {"creature_type": "demon"}, roller=roller,
    )
    assert seen == [salt_service.SALT_BLADE_DIE] == ["1d4"]


def test_no_blade_condition_means_no_bonus():
    assert salt_service.salted_blade_bonus(
        None, _player(), {"creature_type": "undead"}, roller=lambda expr: 4,
    ) == 0


# ── Szczypta soli ────────────────────────────────────────────────────────────

def test_pinch_penalises_own_spell_damage():
    assert salt_service.spell_damage_penalty(_player(_cond("salt_pinch", SALT_PINCH_JSON))) == 1
    assert salt_service.spell_damage_penalty(_player()) == 0


def test_miscast_softening_is_consumed_once_per_combat():
    sheet = {"conditions": [_cond("salt_pinch", SALT_PINCH_JSON)]}
    assert salt_service.consume_miscast_softening(sheet) is True
    assert salt_service.consume_miscast_softening(sheet) is False
    # kara do obrażeń czarów zostaje mimo zużytego łagodzenia
    assert salt_service.spell_damage_penalty(None, sheet=sheet) == 1


def test_softened_miscast_drops_exactly_one_step():
    """L8+ (1k8 + ogłuszenie + wtórny) złagodzony schodzi na stopień L5-7 (1k6 + ogłuszenie)."""
    sheet = {"level": 9, "current_hp": 40}
    res = spell_service.resolve_miscast(sheet, {}, None, race="human", soften=True)
    assert res["softened"] is True
    assert 1 <= res["self_damage"] <= 6
    assert res["stun"] is True
    assert "secondary" not in res


def test_softened_miscast_at_the_lowest_step_costs_nothing():
    sheet = {"level": 2, "current_hp": 30}
    res = spell_service.resolve_miscast(sheet, {}, None, race="human", soften=True)
    assert res["self_damage"] == 0
    assert res["stun"] is False
    assert res["hp_after"] == 30
    assert "sól" in res["narrative"].lower()


def test_unsoftened_miscast_is_unchanged():
    sheet = {"level": 9, "current_hp": 40}
    res = spell_service.resolve_miscast(sheet, {}, None, race="human")
    assert res.get("softened") is None
    assert 1 <= res["self_damage"] <= 8
    assert res["stun"] is True
    assert "secondary" in res


def test_dwarf_softening_keeps_rdzen_flavour():
    sheet = {"level": 1, "current_hp": 12}
    res = spell_service.resolve_miscast(sheet, {}, None, race="dwarf", soften=True)
    assert res["rdzen_miscast"] is True
    assert res["self_damage"] == 0


# ── sprzątanie po walce ──────────────────────────────────────────────────────

def test_one_combat_conditions_are_stripped_at_combat_end():
    conds = [
        _cond("salted_blade", SALT_BLADE_JSON),
        _cond("salt_pinch", SALT_PINCH_JSON),
        _cond("arm_wound", {"effects": [{"type": "static_stat_modifier"}]}),
    ]
    kept, changed = salt_service.strip_combat_end_conditions(conds)
    assert changed is True
    assert [c["key"] for c in kept] == ["arm_wound"]


def test_nothing_to_strip_reports_no_change():
    conds = [_cond("arm_wound", {"effects": []})]
    kept, changed = salt_service.strip_combat_end_conditions(conds)
    assert changed is False
    assert len(kept) == 1
