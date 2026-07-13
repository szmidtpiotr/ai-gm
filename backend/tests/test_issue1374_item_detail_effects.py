"""TDD: Issue #1374 — modal szczegółów przedmiotu pokazuje wartości efektów.

Defekt: player-UI modal renderował tylko opis. Parametry (AC zbroi, staty relikta,
kondycje broni) siedziały w effect_json / ac_bonus i nigdy nie były prezentowane.

Test sprawdza `_humanize_equip_effects` — czysta funkcja zamieniająca effect_json
(+ ac_bonus zbroi) na listę czytelnych PL chipów [{text, kind}].
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.loot_service import _humanize_equip_effects  # noqa: E402


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT)"
    )
    c.execute(
        "INSERT INTO game_config_conditions (key, label) VALUES ('bleeding', 'Krwawienie')"
    )
    c.commit()
    yield c
    c.close()


def _texts(effects):
    return [e["text"] for e in effects]


def test_apply_condition_resolves_label_and_polish_plural(conn):
    ej = ('{"schema_version":1,"effect_category":"gear_bonus","effects":'
          '[{"type":"apply_condition","condition_key":"bleeding","duration_rounds":1}]}')
    out = _humanize_equip_effects(ej, conn)
    assert out == [{"text": "Nakłada: Krwawienie (1 runda)", "kind": "condition"}]


def test_polish_plural_variants(conn):
    def dur(n):
        ej = ('{"effects":[{"type":"apply_condition","condition_key":"bleeding",'
              f'"duration_rounds":{n}}}]}}')
        return _humanize_equip_effects(ej, conn)[0]["text"]
    assert "1 runda" in dur(1)
    assert "3 rundy" in dur(3)
    assert "5 rund" in dur(5)
    assert "12 rund" in dur(12)


def test_static_stat_modifier_polish_name(conn):
    ej = ('{"effects":[{"type":"static_stat_modifier","stat":"CHA","value":1}]}')
    out = _humanize_equip_effects(ej, conn)
    assert out == [{"text": "Charyzma +1", "kind": "stat"}]


def test_negative_stat_modifier_shows_minus(conn):
    ej = ('{"effects":[{"type":"static_stat_modifier","stat":"STR","value":-2}]}')
    assert _texts(_humanize_equip_effects(ej, conn)) == ["Siła -2"]


def test_ac_bonus_column_folded_in(conn):
    # Zbroja: AC z kolumny ac_bonus, brak effect_json.
    out = _humanize_equip_effects(None, conn, ac_bonus=1)
    assert out == [{"text": "Pancerz +1", "kind": "ac"}]


def test_skill_modifier_has_star(conn):
    ej = ('{"effects":[{"type":"static_skill_modifier","skill":"survival","value":1}]}')
    out = _humanize_equip_effects(ej, conn)
    assert out[0]["kind"] == "skill"
    assert "survival +1" in out[0]["text"] and "⭐" in out[0]["text"]


def test_garbage_json_returns_empty(conn):
    assert _humanize_equip_effects("not json", conn) == []
    assert _humanize_equip_effects(None, conn) == []


def test_unknown_condition_key_falls_back_to_key(conn):
    ej = ('{"effects":[{"type":"apply_condition","condition_key":"mystery","duration_rounds":2}]}')
    out = _humanize_equip_effects(ej, conn)
    assert out == [{"text": "Nakłada: mystery (2 rundy)", "kind": "condition"}]
