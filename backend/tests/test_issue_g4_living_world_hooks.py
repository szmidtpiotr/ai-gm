"""TDD: Krok G4 — „żywy świat", który nie odpalał (#1463 / #1464 / #1473).

Wspólny motyw: hooki istniały i były przetestowane jednostkowo, ale nikt ich nie
wołał. Te testy pilnują SAMEGO WPIĘCIA:

  #1463 — pora dnia w silniku:
    test_dawn_initiative_bonus       → combat_service wpina +1 inicjatywy o świcie
    test_night_perception_penalty    → skill_service podbija DC percepcji nocą

  #1464 — wydarzenie regionalne w łupie:
    test_world_event_boosts_loot_gold → loot_service skaluje złoto mnożnikiem eventu

  #1473 — moneta walka/scena w podróży overworld:
    test_overworld_encounter_can_be_social → wspólny helper daje CZYSTĄ scenę social
"""
import os
import sys
import json
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.migrations_admin import ADMIN_MIGRATIONS, ADMIN_SEEDS


REGION = "kresy"


def _sessions_db(ingame_hours: int) -> sqlite3.Connection:
    """In-memory DB z jedną kampanią (id=1) i zegarem ustawionym na daną godzinę."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)"
    )
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 1, ?)",
        (json.dumps({"ingame_hours": int(ingame_hours)}),),
    )
    conn.commit()
    return conn


# ─────────────────────────── #1463 — inicjatywa o świcie ──────────────────────

def test_dawn_initiative_bonus():
    """Świt (dawn) → +1 do inicjatywy; dzień/noc → 0. Wpięte w combat_service."""
    from app.services import combat_service

    dawn = _sessions_db(8)      # 08:00 → dawn
    day = _sessions_db(14)      # 14:00 → day
    night = _sessions_db(23)    # 23:00 → night

    assert combat_service._time_of_day_initiative_bonus(dawn, 1) == 1
    assert combat_service._time_of_day_initiative_bonus(day, 1) == 0
    assert combat_service._time_of_day_initiative_bonus(night, 1) == 0


# ─────────────────────── #1463 — DC percepcji o zmierzchu/nocy ─────────────────

def _perception_pending():
    return {
        "skill_key": "perception",
        "skill_label": "Percepcja",
        "counter": {"counter_type": "dc", "counter_key": None, "dc": 12},
        "modifier_breakdown": {"total": 0},
    }


def test_night_perception_penalty():
    """Nocą test percepcji ma wyższe DC (o +2) niż w dzień — kara wpięta w silnik."""
    from app.services import skill_service

    day = _sessions_db(14)
    night = _sessions_db(23)

    res_day = skill_service.resolve_skill_test(
        d20_roll=10, pending=_perception_pending(), conn=day,
        campaign_id=1, character_id=1, session_flags=None,
    )
    res_night = skill_service.resolve_skill_test(
        d20_roll=10, pending=_perception_pending(), conn=night,
        campaign_id=1, character_id=1, session_flags=None,
    )

    assert res_day["tod_perception_dc_bonus"] == 0
    assert res_night["tod_perception_dc_bonus"] == 2
    # DC (opponent_total) nocą jest o 2 wyższe → trudniej trafić.
    assert res_night["opponent_total"] == res_day["opponent_total"] + 2


def test_night_stealth_bonus():
    """Nocą skradanie dostaje +2 do rzutu (stealth_bonus) — wpięte w silnik."""
    from app.services import skill_service

    def _stealth_pending():
        return {
            "skill_key": "stealth",
            "skill_label": "Skradanie",
            "counter": {"counter_type": "dc", "counter_key": None, "dc": 12},
            "modifier_breakdown": {"total": 0},
        }

    day = _sessions_db(14)
    night = _sessions_db(23)

    res_day = skill_service.resolve_skill_test(
        d20_roll=10, pending=_stealth_pending(), conn=day,
        campaign_id=1, character_id=1, session_flags=None,
    )
    res_night = skill_service.resolve_skill_test(
        d20_roll=10, pending=_stealth_pending(), conn=night,
        campaign_id=1, character_id=1, session_flags=None,
    )

    assert res_day["tod_stealth_bonus"] == 0
    assert res_night["tod_stealth_bonus"] == 2
    # +2 do modyfikatora gracza → wyższy player_total przy tym samym d20.
    assert res_night["player_total"] == res_day["player_total"] + 2


# ─────────────────────────── #1464 — złoto z eventu ───────────────────────────

def _loot_db_file() -> str:
    """Plikowa baza z enemy+tabelą łupu (stałe 100 gp) oraz schematem eventów."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    for sql in ADMIN_MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    for sql in ADMIN_SEEDS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    # ADMIN_MIGRATIONS zakłada bogatsze schematy content-tabel (label/hp_base NOT NULL);
    # roll_gold_drop czyta tylko gold_min/max + drop_chance, więc zastępujemy minimalną
    # wersją (świeży plik tymczasowy — brak FK w grze).
    conn.execute("DROP TABLE IF EXISTS game_config_loot_tables")
    conn.execute("DROP TABLE IF EXISTS game_config_enemies")
    conn.execute(
        "CREATE TABLE game_config_loot_tables "
        "(key TEXT PRIMARY KEY, label TEXT, gold_min INTEGER, gold_max INTEGER, is_active INTEGER DEFAULT 1)"
    )
    conn.execute(
        "CREATE TABLE game_config_enemies "
        "(key TEXT PRIMARY KEY, loot_table_key TEXT, drop_chance REAL DEFAULT 1.0)"
    )
    conn.execute(
        "INSERT INTO game_config_loot_tables (key, label, gold_min, gold_max, is_active) "
        "VALUES ('loot_goblin', 'Goblin', 100, 100, 1)"
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key, loot_table_key, drop_chance) "
        "VALUES ('goblin', 'loot_goblin', 1.0)"
    )
    conn.commit()
    conn.close()
    return path


def test_world_event_boosts_loot_gold(monkeypatch):
    """Aktywny event 'rajdy' (loot_gold_mult=1.3) skaluje złoto z ubicia: 100 → 130."""
    from app.services import loot_service
    from app.services import world_event_service as wes
    from app.services import reputation_service

    path = _loot_db_file()
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", path)
    # region postaci → kresy (bez pełnego grafu lokacji w tej bazie testowej).
    monkeypatch.setattr(reputation_service, "resolve_region", lambda conn, cid: REGION)

    # Bez eventu: pełne 100 gp (stała tabela).
    assert loot_service.roll_gold_drop("goblin", campaign_id=1) == 100

    # Włącz event 'rajdy' w regionie kresy → mnożnik 1.3.
    ev_conn = sqlite3.connect(path)
    ev_conn.row_factory = sqlite3.Row
    wes.start_event(ev_conn, REGION, "rajdy")
    ev_conn.commit()
    ev_conn.close()

    _chk = sqlite3.connect(path)
    _chk.row_factory = sqlite3.Row
    assert wes.loot_gold_multiplier(_chk, REGION) == 1.3
    _chk.close()
    # 100 * 1.3 = 130 — mnożnik faktycznie wpięty w roll_gold_drop.
    assert loot_service.roll_gold_drop("goblin", campaign_id=1) == 130

    # Bez campaign_id mnożnik się nie stosuje (kompatybilność wstecz).
    assert loot_service.roll_gold_drop("goblin") == 100

    os.remove(path)


# ─────────────────────── #1473 — scena społeczna w podróży ─────────────────────

def test_overworld_encounter_can_be_social():
    """Trafiony rzut ryzyka może dać CZYSTĄ scenę społeczną (bez walki, #1455)."""
    from app.services import social_encounter_service as ses

    # Moneta: roll ≥ 0.5 → 'social' (Sandbox-tunable ENCOUNTER_SOCIAL_SPLIT).
    assert ses.classify_encounter_kind(0.9) == "social"
    assert ses.classify_encounter_kind(0.1) == "combat"

    # Wspólny helper buduje scenę overworld (handlarz/patrol/uchodźcy).
    scene = ses.build_travel_social_scene()
    assert scene["kind"] == "social"
    assert scene["subtype"] == "wilderness"
    assert scene["social_event"] in ("traveling_merchant", "patrol", "refugees")
    # CZYSTY stan — żaden klucz walki, więc nie ma „walki nie odbytej".
    assert "enemy_key" not in scene
    assert "enemies" not in scene
