"""TDD: Issue #1349 (WALKA-T1) — modal zasadzki w drodze niesie dane wroga.

`_travel_notice_for(reason=encounter)` dokłada:
  enemy {key,label,image_url,count} + relative_threat {glyph,label,tier}
i buduje message z labela. Fallback (enemy_key pusty/nieznany) → generyczny string,
bez bloku enemy. dusk/forced_camp nietknięte. Bez conn/campaign_id (stara sygnatura)
→ zachowanie jak dotąd (backward compat).
"""
from _fixtures_schema import table_sql
import json
import sqlite3

from app.api import turns


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


def _hero(c, cid, campaign_id, level):
    c.execute(
        "INSERT INTO characters (id, sheet_json, campaign_id, is_active) VALUES (?, ?, ?, 1)",
        (cid, json.dumps({"level": level, "skills": {}, "archetype": "warrior"}), campaign_id),
    )


def _enemy(c, key, label, hp, ac, atk, die, img=None):
    c.execute(
        "INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, "
        "damage_die, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (key, label, hp, ac, atk, die, img),
    )


def _sf(reason, enemy_key=None):
    tp = {
        "interrupt_reason": reason,
        "step_index": 2,
        "hours_remaining": 3.0,
        "destination_label": "Wioska Dąb",
    }
    if enemy_key is not None:
        tp["enemy_key"] = enemy_key
    return {"travel_plan": tp}


# ── Główny: zasadzka niesie dane wroga + wskaźnik + message z labela ──────────

def test_encounter_notice_carries_enemy_and_threat():
    c = _db()
    _hero(c, 1, 100, level=1)  # goły lvl1 → power ≈ 1
    _enemy(c, "smok", "Prastary Smok", hp=120, ac=16, atk=8, die="d12", img="/img/smok.png")
    notice = turns._travel_notice_for(_sf("encounter", "smok"), conn=c, campaign_id=100)
    assert notice is not None
    assert notice["enemy"]["key"] == "smok"
    assert notice["enemy"]["label"] == "Prastary Smok"
    assert notice["enemy"]["image_url"] == "/img/smok.png"
    assert notice["enemy"]["count"] == 1
    rt = notice["relative_threat"]
    # surowy ratio/threat/budget UKRYTY przed graczem — tylko glyph+label+tier
    assert set(rt.keys()) == {"glyph", "label", "tier"}
    assert rt["glyph"] == "💀"
    assert "Prastary Smok" in notice["message"]
    assert "Stań do walki" in notice["message"]


# ── Fallback: brak/nieznany enemy_key → generyczny string, bez bloku enemy ────

def test_encounter_missing_enemy_key_generic():
    c = _db()
    _hero(c, 1, 100, level=1)
    notice = turns._travel_notice_for(_sf("encounter", None), conn=c, campaign_id=100)
    assert "enemy" not in notice
    assert "relative_threat" not in notice
    assert notice["message"] == "Ktoś zagrodził ci drogę — dochodzi do starcia. Stań do walki."


def test_encounter_unknown_enemy_key_generic():
    c = _db()
    _hero(c, 1, 100, level=1)
    # enemy_key ustawiony, ale brak rekordu w game_config_enemies → generyczny fallback
    notice = turns._travel_notice_for(_sf("encounter", "nie_ma_takiego"), conn=c, campaign_id=100)
    assert "enemy" not in notice
    assert notice["message"] == "Ktoś zagrodził ci drogę — dochodzi do starcia. Stań do walki."


# ── Backward compat: bez conn/campaign_id → jak dotąd (żadnego bloku enemy) ────

def test_backward_compat_no_conn():
    notice = turns._travel_notice_for(_sf("encounter", "smok"))
    assert notice is not None
    assert "enemy" not in notice
    assert notice["title"] == "Zasadzka w drodze"


# ── dusk/forced_camp nietknięte (nie-encounter → bez enemy nawet z conn) ──────

def test_dusk_notice_unaffected():
    c = _db()
    _hero(c, 1, 100, level=1)
    notice = turns._travel_notice_for(
        {"travel_plan": {"interrupt_reason": "dusk", "step_index": 1}},
        conn=c,
        campaign_id=100,
    )
    assert notice["title"] == "Zapada zmierzch"
    assert "enemy" not in notice


# ── PO wygranej walce (encounter_prompted): własny szablon, bez danych wroga ──
# Bez tego notice wpadał w bazowy szablon "encounter" — modal po walce wyglądał
# jak NOWA zasadzka z jednym przyciskiem „Walcz" (wznawiał podróż), zero opcji
# odpoczynku i regeneracji HP/many.

def test_encounter_prompted_notice_offers_rest_not_fight():
    c = _db()
    _hero(c, 1, 100, level=1)
    _enemy(c, "bandit", "Bandyta", hp=20, ac=12, atk=3, die="d6")
    notice = turns._travel_notice_for(_sf("encounter_prompted", "bandit"), conn=c, campaign_id=100)
    assert notice is not None
    assert notice["reason"] == "encounter_prompted"
    # własny szablon post-walkowy, NIE zasadzka
    assert notice["title"] == "Walka za tobą"
    assert "Zasadzka" not in notice["title"]
    assert notice["severity"] == "warn"
    assert notice["can_resume"] is True
    # wróg pokonany — bez bloku enemy/relative_threat (mylące po walce)
    assert "enemy" not in notice
    assert "relative_threat" not in notice


def test_encounter_notice_unchanged_before_combat():
    # regresja: pre-walkowy encounter dalej niesie wroga i szablon zasadzki
    c = _db()
    _hero(c, 1, 100, level=1)
    _enemy(c, "bandit", "Bandyta", hp=20, ac=12, atk=3, die="d6")
    notice = turns._travel_notice_for(_sf("encounter", "bandit"), conn=c, campaign_id=100)
    assert notice["title"] == "Zasadzka w drodze"
    assert notice["enemy"]["key"] == "bandit"
