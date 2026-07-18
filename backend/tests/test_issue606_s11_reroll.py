"""TDD: Issue #606 — FAZA S / S11: prymityw `reroll` (nadany i wymuszony) +
kondycje `inspired` (player_keep_best) i `cursed` (pełny: forced_keep_worst).

Pokrywa:
- nowy, schema-zgodny typ efektu `reroll` (mode/uses/scope) waliduje się U10;
  seed `inspired` i rozszerzony `cursed` walidują się; zły mode/scope odrzucony,
- prymityw reroll_service: keep_better/keep_worse, ekstrakcja efektów reroll z kondycji
  (klucz danymi, zero `if key==`), budżet "zły omen" 1×/scenę + reset przy zmianie lokacji,
- resolve_skill_test forced_keep_worst: udany test gracza z `cursed` → przerzut na gorszy
  (omen_applied), budżet konsumowany; drugi udany test w tej samej scenie bez omenu;
  nat 20 / ścieżka walki NIETYKALNE,
- resolve_skill_test player_keep_best: nieudany test z `inspired` → wynik niesie
  `reroll_available`; bez kondycji brak oferty; konsumpcja zdejmuje inspired,
- backward compat: resolve_skill_test bez session_flags działa jak dotąd (zero omenu).
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

from app.services import skill_service as ss
from app.services import reroll_service as rr
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakty (identyczne z seedami) ──────────────────────────────

INSPIRED = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "CHA", "value": 2},
        {"type": "static_stat_modifier", "stat": "WIS", "value": 2},
        {"type": "reroll", "mode": "player_keep_best", "uses": 1, "scope": "skill_test"},
    ],
}

CURSED = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "STR", "value": -2},
        {"type": "static_stat_modifier", "stat": "DEX", "value": -2},
        {"type": "static_stat_modifier", "stat": "CON", "value": -2},
        {"type": "static_stat_modifier", "stat": "INT", "value": -2},
        {"type": "static_stat_modifier", "stat": "WIS", "value": -2},
        {"type": "static_stat_modifier", "stat": "CHA", "value": -2},
        {"type": "reroll", "mode": "forced_keep_worst", "scope": "skill_test"},
    ],
}


# ─── 1. Schemat U10 akceptuje reroll; seedy inspired/cursed; złe wartości ───────

class TestRerollSchema:
    def test_inspired_validates(self):
        assert validate_effect_json_payload(INSPIRED) == []

    def test_cursed_validates(self):
        assert validate_effect_json_payload(CURSED) == []

    def test_bad_mode_rejected(self):
        bad = json.loads(json.dumps(INSPIRED))
        bad["effects"][2]["mode"] = "keep_average"
        assert validate_effect_json_payload(bad) != []

    def test_bad_scope_rejected(self):
        bad = json.loads(json.dumps(INSPIRED))
        bad["effects"][2]["scope"] = "everything"
        assert validate_effect_json_payload(bad) != []

    def test_mode_required(self):
        bad = json.loads(json.dumps(INSPIRED))
        bad["effects"][2].pop("mode")
        assert validate_effect_json_payload(bad) != []

    def test_negative_uses_rejected(self):
        bad = json.loads(json.dumps(INSPIRED))
        bad["effects"][2]["uses"] = -1
        assert validate_effect_json_payload(bad) != []

    def test_reroll_allowed_for_character_condition_category(self):
        # reroll musi być na liście typów kategorii character_condition
        assert validate_effect_json_payload(INSPIRED) == []


# ─── 2. Prymityw reroll_service — czyste funkcje ───────────────────────────────

class TestRerollPrimitive:
    def test_keep_better_worse(self):
        assert rr.keep_better(17, 9) == 17
        assert rr.keep_better(9, 17) == 17
        assert rr.keep_worse(17, 9) == 9
        assert rr.keep_worse(9, 17) == 9

    def test_extract_player_keep_best(self):
        conds = [{"key": "inspired", "effect_json": json.dumps(INSPIRED)}]
        hits = rr.extract_reroll_effects(conds, mode="player_keep_best")
        assert len(hits) == 1
        assert hits[0][1]["mode"] == "player_keep_best"

    def test_extract_forced_keep_worst(self):
        conds = [{"key": "cursed", "effect_json": json.dumps(CURSED)}]
        hits = rr.extract_reroll_effects(conds, mode="forced_keep_worst")
        assert len(hits) == 1

    def test_extract_mode_filter_excludes_other_mode(self):
        conds = [{"key": "inspired", "effect_json": json.dumps(INSPIRED)}]
        assert rr.extract_reroll_effects(conds, mode="forced_keep_worst") == []

    def test_extract_ignores_non_reroll_conditions(self):
        plain = {"schema_version": 1, "effect_category": "character_condition",
                 "effects": [{"type": "static_stat_modifier", "stat": "STR", "value": -1}]}
        conds = [{"key": "poisoned", "effect_json": json.dumps(plain)}]
        assert rr.extract_reroll_effects(conds, mode="player_keep_best") == []

    def test_scope_all_matches_skill_test(self):
        ej = {"schema_version": 1, "effect_category": "character_condition",
              "effects": [{"type": "reroll", "mode": "player_keep_best", "scope": "all"}]}
        conds = [{"key": "x", "effect_json": json.dumps(ej)}]
        assert len(rr.extract_reroll_effects(conds, mode="player_keep_best", scope="skill_test")) == 1


# ─── 3. Budżet "zły omen" — 1×/scenę + reset przy zmianie lokacji ──────────────

class TestOmenBudget:
    def test_available_on_fresh_scene(self):
        assert rr.omen_available({}, "tawerna") is True

    def test_consume_blocks_same_scene(self):
        flags: dict = {}
        rr.consume_omen(flags, "tawerna")
        assert rr.omen_available(flags, "tawerna") is False

    def test_location_change_resets(self):
        flags: dict = {}
        rr.consume_omen(flags, "tawerna")
        assert rr.omen_available(flags, "las") is True


# ─── 4. resolve_skill_test forced_keep_worst (cursed "zły omen") ──────────────

def _conn_with_cursed(d20_committed_unused=None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        """ + table_sql("game_config_conditions") + """
        CREATE TABLE game_sessions (campaign_id INTEGER PRIMARY KEY, session_flags TEXT,
          current_location_id INTEGER);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT);
        """ + table_sql("game_config_skills") + """
        CREATE TABLE skill_counters (player_skill_key TEXT, counter_type TEXT, counter_key TEXT, default_dc INTEGER);
    """)
    conn.execute("INSERT INTO game_config_conditions (key,label,effect_json) VALUES (?,?,?)",
                 ("cursed", "Przeklęty", json.dumps(CURSED)))
    conn.execute("INSERT INTO game_config_conditions (key,label,effect_json) VALUES (?,?,?)",
                 ("inspired", "Zainspirowany", json.dumps(INSPIRED)))
    conn.execute("INSERT INTO game_config_skills (key,linked_stat,label) VALUES ('persuasion','CHA','Perswazja')")
    return conn


def _set_conditions(conn, keys: list[str]):
    sheet = {"stats": {"CHA": 14, "WIS": 12}, "skills": {},
             "conditions": [{"key": k, "label": k.title()} for k in keys]}
    conn.execute("INSERT OR REPLACE INTO characters (id, sheet_json) VALUES (1, ?)",
                 (json.dumps(sheet, ensure_ascii=False),))
    conn.commit()


def _pending(skill="persuasion", mod_total=3, dc=12):
    return {
        "skill_test_id": "st-test",
        "skill_key": skill,
        "skill_label": "Perswazja",
        "counter": {"counter_type": "dc", "counter_key": None, "dc": dc},
        "modifier_breakdown": {"total": mod_total},
    }


class TestForcedKeepWorst:
    def test_cursed_success_rerolled_to_worse(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["cursed"])
        flags: dict = {}
        # Gracz rzuca 18 (sukces). Wymuszony przerzut wypada 2 → gorszy total → omen.
        with patch.object(ss.random, "randint", return_value=2):
            res = ss.resolve_skill_test(
                d20_roll=18, pending=_pending(), conn=conn, campaign_id=1,
                character_id=1, session_flags=flags,
            )
        assert res.get("omen_applied") is True
        assert res["d20_roll"] == 2  # gorszy rzut zachowany
        assert res["success"] is False
        # Budżet skonsumowany
        assert flags.get("omen_state", {}).get("used") is True

    def test_omen_only_once_per_scene(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["cursed"])
        flags: dict = {}
        rr.consume_omen(flags, "")  # już zużyty w tej scenie
        with patch.object(ss.random, "randint", return_value=2):
            res = ss.resolve_skill_test(
                d20_roll=18, pending=_pending(), conn=conn, campaign_id=1,
                character_id=1, session_flags=flags,
            )
        assert res.get("omen_applied") is not True
        assert res["d20_roll"] == 18  # bez przerzutu

    def test_no_omen_on_failed_test(self):
        # Zły omen psuje tylko KORZYSTNY (udany) test — nieudany nie jest przerzucany.
        conn = _conn_with_cursed()
        _set_conditions(conn, ["cursed"])
        flags: dict = {}
        with patch.object(ss.random, "randint", return_value=20):
            res = ss.resolve_skill_test(
                d20_roll=3, pending=_pending(), conn=conn, campaign_id=1,
                character_id=1, session_flags=flags,
            )
        assert res.get("omen_applied") is not True
        assert res["d20_roll"] == 3

    def test_nat20_untouched_by_omen(self):
        # Rzuty krytyczne pozostają nietknięte — nat 20 to absolutny sukces.
        conn = _conn_with_cursed()
        _set_conditions(conn, ["cursed"])
        flags: dict = {}
        with patch.object(ss.random, "randint", return_value=1):
            res = ss.resolve_skill_test(
                d20_roll=20, pending=_pending(), conn=conn, campaign_id=1,
                character_id=1, session_flags=flags,
            )
        assert res["d20_roll"] == 20
        assert res["outcome"] == "CRITICAL_SUCCESS"
        assert res.get("omen_applied") is not True


# ─── 5. resolve_skill_test player_keep_best (inspired) ────────────────────────

class TestPlayerKeepBest:
    def test_failed_test_offers_reroll_when_inspired(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["inspired"])
        res = ss.resolve_skill_test(
            d20_roll=2, pending=_pending(), conn=conn, campaign_id=1,
            character_id=1, session_flags={},
        )
        assert res["success"] is False
        offer = res.get("reroll_available")
        assert offer and offer["condition_key"] == "inspired"
        assert offer["mode"] == "player_keep_best"

    def test_no_offer_without_inspired(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, [])
        res = ss.resolve_skill_test(
            d20_roll=2, pending=_pending(), conn=conn, campaign_id=1,
            character_id=1, session_flags={},
        )
        assert res.get("reroll_available") is None

    def test_no_offer_on_success(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["inspired"])
        res = ss.resolve_skill_test(
            d20_roll=18, pending=_pending(), conn=conn, campaign_id=1,
            character_id=1, session_flags={},
        )
        assert res.get("reroll_available") is None

    def test_consume_player_reroll_removes_inspired(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["inspired"])
        consumed = rr.consume_player_reroll(conn, 1, 1)
        assert consumed == "inspired"
        row = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
        sheet = json.loads(row[0])
        keys = [c["key"] for c in sheet.get("conditions", [])]
        assert "inspired" not in keys


# ─── 6. Backward compat ────────────────────────────────────────────────────────

class TestBackwardCompat:
    def test_resolve_without_session_flags_unchanged(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, ["cursed"])
        with patch.object(ss.random, "randint", return_value=2):
            res = ss.resolve_skill_test(
                d20_roll=18, pending=_pending(), conn=conn, campaign_id=1,
                character_id=1,
            )
        # bez session_flags żaden omen nie procuje
        assert res.get("omen_applied") is not True
        assert res["d20_roll"] == 18

    def test_resolve_no_conditions_plain_success(self):
        conn = _conn_with_cursed()
        _set_conditions(conn, [])
        res = ss.resolve_skill_test(
            d20_roll=15, pending=_pending(), conn=conn, campaign_id=1,
            character_id=1, session_flags={},
        )
        assert res["success"] is True
        assert res.get("omen_applied") is not True
        assert res.get("reroll_available") is None
