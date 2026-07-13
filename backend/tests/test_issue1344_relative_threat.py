"""BL-A7 (#1344) — relatywny wskaźnik zagrożenia (karta pojawienia wroga).

Rytuał końca sesji: słaby wróg vs silny gracz → 🟢; boss vs słaby gracz → 💀.
Wskaźnik porównuje STAŁY statblock grupy do rosnącego Power Score (nie rubber-band).
Grupa liczona sumarycznie (nie per-sztuka). Surowy ratio ukryty przed graczem —
snapshot walki odsłania tylko glyph+label+tier.
"""
from _fixtures_schema import table_sql
import json
import sqlite3

import pytest

from app.services import threat_display_service as tds


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT,
            campaign_id INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT, game_item_key TEXT,
            quantity INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0, slot TEXT);
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_spells") + """
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1);
        """ + table_sql("game_config_meta") + """
        """ + table_sql("game_config_enemies") + """
        """
    )
    return c


def _hero(c, cid, campaign_id, level, skills=None, weapon=None, armor_ac=0):
    sheet = {"level": level, "skills": skills or {}, "archetype": "warrior"}
    c.execute(
        "INSERT INTO characters (id, sheet_json, campaign_id, is_active) VALUES (?, ?, ?, 1)",
        (cid, json.dumps(sheet), campaign_id),
    )
    if weapon:
        c.execute("INSERT INTO game_config_weapons (key, damage_die) VALUES (?, ?)", ("wpn", weapon))
        c.execute(
            "INSERT INTO character_inventory (character_id, weapon_key, equipped, slot) "
            "VALUES (?, 'wpn', 1, 'main_hand')",
            (cid,),
        )
    if armor_ac:
        c.execute("INSERT INTO game_config_items (key, ac_bonus) VALUES ('arm', ?)", (armor_ac,))
        c.execute(
            "INSERT INTO character_inventory (character_id, item_key, equipped) VALUES (?, 'arm', 1)",
            (cid,),
        )


def _enemy(c, key, hp, ac, atk, die, dmg=0, apt=1, img=None):
    c.execute(
        "INSERT INTO game_config_enemies (key, hp_base, ac_base, attack_bonus, damage_die, "
        "damage_bonus, attacks_per_turn, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (key, hp, ac, atk, die, dmg, apt, img),
    )


def _cbt(key, **over):
    d = {"type": "enemy", "enemy_key": key, "hp_current": 999, "hp_max": 999}
    d.update(over)
    return d


# ── Acceptance: słaby wróg vs silny gracz → 🟢 ────────────────────────────────

def test_weak_enemy_vs_strong_player_green():
    c = _db()
    _hero(c, 1, 100, level=8, skills={"attack": 3, "dodge": 3}, weapon="d10", armor_ac=4)
    _enemy(c, "szczur", hp=8, ac=10, atk=1, die="d4")
    rt = tds.relative_threat(c, 100, [_cbt("szczur")])
    assert rt["tier"] == "trivial"
    assert rt["glyph"] == "🟢"
    assert rt["ratio"] < 0.5


# ── Acceptance: boss vs słaby gracz → 💀 ──────────────────────────────────────

def test_boss_vs_weak_player_deadly():
    c = _db()
    _hero(c, 1, 100, level=1)  # goły lvl1 → power ≈ 1
    _enemy(c, "smok", hp=120, ac=16, atk=8, die="d12", dmg=4)
    rt = tds.relative_threat(c, 100, [_cbt("smok")])
    assert rt["tier"] == "deadly"
    assert rt["glyph"] == "💀"
    assert rt["ratio"] > 1.4


# ── Grupa liczona SUMARYCZNIE (nie per-sztuka) ────────────────────────────────

def test_group_sums_not_per_piece():
    c = _db()
    _hero(c, 1, 100, level=1)  # budżet ≈ 30
    _enemy(c, "goblin", hp=8, ac=10, atk=1, die="d4")  # threat ≈ 14
    one = tds.relative_threat(c, 100, [_cbt("goblin")])
    two = tds.relative_threat(c, 100, [_cbt("goblin"), _cbt("goblin")])
    assert two["count"] == 2
    assert two["ratio"] == pytest.approx(one["ratio"] * 2, rel=0.01)
    # jeden goblin nieszkodliwy (🟢), dwa robią realne zagrożenie (wyższe pasmo)
    assert one["tier"] == "trivial"
    assert two["tier"] in ("even", "dangerous", "deadly")


# ── STAŁY statblock: wskaźnik z bazowego rekordu, nie z ranked combatanta ─────

def test_uses_base_statblock_not_combatant():
    c = _db()
    _hero(c, 1, 100, level=1)
    _enemy(c, "ork", hp=20, ac=12, atk=3, die="d6")
    # combatant podaje napompowane hp (ranga) — wskaźnik ma je zignorować.
    rt_base = tds.relative_threat(c, 100, [_cbt("ork")])
    rt_ranked = tds.relative_threat(c, 100, [_cbt("ork", hp_max=9999, hp_current=9999)])
    assert rt_base["enemy_threat"] == rt_ranked["enemy_threat"]


# ── Progi pasm stroją się z game_config_meta (Numbers Policy) ─────────────────

def test_bands_from_meta_override():
    c = _db()
    _hero(c, 1, 100, level=1)
    _enemy(c, "mysz", hp=8, ac=10, atk=1, die="d4")  # ratio ≈ 0.47 → domyślnie 🟢
    # Zaostrz próg: wszystko powyżej 0.1 = groźne.
    c.execute(
        "INSERT INTO game_config_meta (key, value) VALUES ('threat_indicator_bands', ?)",
        (json.dumps([
            {"tier": "trivial", "max": 0.1, "glyph": "🟢", "label": "słaby"},
            {"tier": "dangerous", "max": None, "glyph": "🔴", "label": "groźny"},
        ]),),
    )
    rt = tds.relative_threat(c, 100, [_cbt("mysz")])
    assert rt["tier"] == "dangerous"
    assert rt["glyph"] == "🔴"


# ── Brak wrogów → None; brak enemy_key → fallback na pola combatanta ──────────

def test_empty_and_fallback():
    c = _db()
    _hero(c, 1, 100, level=3)
    assert tds.relative_threat(c, 100, []) is None
    # combatant bez enemy_key → wycena z jego pól (nie wywraca karty)
    rt = tds.relative_threat(c, 100, [{"type": "enemy", "hp_max": 30, "defense": 12,
                                       "attack_bonus": 2, "damage_dice": "d6"}])
    assert rt is not None
    assert rt["enemy_threat"] > 0
