"""TDD: Issue #1423 (BL-A7) — skalowanie spotkań w podróży + pokrętło trudności.

Zasadzka w podróży (`hex_travel_service`) losowała POJEDYNCZEGO wroga poz. 1-2 z
zaszytej puli terenowej — bez skalowania do poziomu bohatera. BL-A7 przepina to na
composer (budżet f(Power/level) → wataha/herszt) i wystawia mnożnik TRUDNOŚCI
(`encounter_difficulty_mult`) do strojenia z admina.

Testy używają in-memory sqlite — nie dotykają /data/ai_gm.db.
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import encounter_service as enc
from app.services import encounter_config_service as cfg


def _mem() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_enemies(conn: sqlite3.Connection) -> None:
    conn.executescript(table_sql("game_config_enemies") + table_sql("game_config_meta"))
    # min_size=1 → testuj rdzeń bez poszerzania puli
    conn.execute("INSERT INTO game_config_meta (key,value) VALUES ('encounter_pool_min_size','1')")
    rows = [
        ("wolf", "Wilk", 10, 12, 3, "1d6", 0, 1, "standard", 1, 2, "forest,road"),
        ("goblin", "Goblin", 8, 11, 2, "1d6", 1, 1, "weak", 1, 2, "forest,road"),
        ("bandit", "Bandyta", 12, 13, 4, "1d8", 0, 1, "standard", 1, 2, "forest,road"),
        ("bandit_thug", "Oprych", 10, 11, 2, "1d6", 0, 1, "weak", 1, 2, "forest,road"),
        ("bandit_chief", "Herszt", 22, 13, 5, "1d10", 2, 1, "elite", 1, 3, "road"),
        ("boar", "Dzik", 14, 12, 3, "1d8", 1, 1, "elite", 1, 3, "forest"),
    ]
    for r in rows:
        conn.execute(
            "INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,"
            "damage_die,damage_bonus,attacks_per_turn,tier,min_level,max_level,terrain_tags,"
            "world_scope,review_status,is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*r, "global", "permanent", 1),
        )
    conn.commit()


# ── Trudność: mnożnik skaluje budżet zagrożenia ──────────────────────────────

def test_difficulty_mult_scales_level_budget():
    conn = _mem()
    conn.executescript(table_sql("game_config_meta"))
    base = enc.threat_budget_for_level(conn, 5)
    conn.execute("INSERT INTO game_config_meta (key,value) VALUES ('encounter_difficulty_mult','2.0')")
    hard = enc.threat_budget_for_level(conn, 5)
    assert hard == pytest.approx(base * 2.0, rel=1e-6)


def test_difficulty_mult_scales_power_budget():
    conn = _mem()
    conn.executescript(table_sql("game_config_meta"))
    base = enc.threat_budget_for_power(conn, 4.0)
    conn.execute("INSERT INTO game_config_meta (key,value) VALUES ('encounter_difficulty_mult','0.5')")
    easy = enc.threat_budget_for_power(conn, 4.0)
    assert easy == pytest.approx(base * 0.5, rel=1e-6)


def test_difficulty_mult_clamped():
    conn = _mem()
    conn.executescript(table_sql("game_config_meta"))
    conn.execute("INSERT INTO game_config_meta (key,value) VALUES ('encounter_difficulty_mult','99')")
    # clamp 3.0 → budżet nie przekracza base × 3
    b0 = enc.threat_budget_for_level(_mem_with_meta(), 3)
    assert enc.threat_budget_for_level(conn, 3) <= b0 * 3.0 + 0.01


def _mem_with_meta() -> sqlite3.Connection:
    c = _mem(); c.executescript(table_sql("game_config_meta")); return c


# ── pool_keys: autorska pula hexa zawęża miękko ──────────────────────────────

def test_pool_keys_intersection():
    conn = _mem(); _seed_enemies(conn)
    pool = enc.eligible_enemy_pool(conn, level=1, hex_type="road", pool_keys={"bandit", "wolf"})
    keys = {d["key"] for d in pool}
    assert keys == {"bandit", "wolf"}


def test_pool_keys_empty_intersection_ignored():
    conn = _mem(); _seed_enemies(conn)
    # klucz spoza puli terenowej → przecięcie puste → ignoruj (pełna pula)
    pool = enc.eligible_enemy_pool(conn, level=1, hex_type="road", pool_keys={"dragon_ancient"})
    assert len(pool) >= 3


# ── config service: roundtrip + walidacja ────────────────────────────────────

def test_config_roundtrip():
    conn = _mem(); conn.executescript(table_sql("game_config_meta"))
    out = cfg.set_encounter_config(
        conn=conn, difficulty_mult=1.35, threat_budget_base=40, pool_min_size=8,
    )
    assert out["difficulty_mult"] == 1.35
    assert out["threat_budget_base"] == 40.0
    assert out["pool_min_size"] == 8
    # ponowny odczyt widzi zapisane
    again = cfg.get_encounter_config(conn=conn)
    assert again["difficulty_mult"] == 1.35


def test_config_difficulty_out_of_range_raises():
    conn = _mem(); conn.executescript(table_sql("game_config_meta"))
    with pytest.raises(ValueError):
        cfg.set_encounter_config(conn=conn, difficulty_mult=5.0)


def test_config_defaults_parity_with_service():
    conn = _mem(); conn.executescript(table_sql("game_config_meta"))
    c = cfg.get_encounter_config(conn=conn)
    assert c["difficulty_mult"] == 1.0
    assert c["threat_budget_base"] == enc.THREAT_BUDGET_BASE
    assert c["threat_budget_per_power"] == enc.THREAT_BUDGET_PER_POWER


# ── compose_travel_encounter: grupa zamiast pojedynczego wroga ───────────────

def _seed_session(conn: sqlite3.Connection, campaign_id: int, flags: dict | None = None) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1, sheet_json TEXT, user_id INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS campaign_members (campaign_id INTEGER, status TEXT, character_id INTEGER)")
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
                 (campaign_id, json.dumps(flags or {})))
    conn.commit()


def test_compose_travel_returns_valid_pool_enemies():
    """Każde spotkanie ma niepustą listę enemies z KLUCZY PULI (nie legacy 1 wróg
    spoza composera). Wzorzec (solo/wataha/herszt) jest losowy — patrz test poniżej."""
    conn = _mem(); _seed_enemies(conn); _seed_session(conn, 1)
    out = enc.compose_travel_encounter(conn, 1, {"hex_type": "road"}, rng=random.Random(3))
    assert out is not None
    assert out.get("enemies"), "brak listy enemies"
    assert out.get("composition_pattern") in ("solo", "wataha", "herszt")
    for e in out["enemies"]:
        assert e["enemy_key"] in {"wolf", "goblin", "bandit", "bandit_thug", "bandit_chief", "boar"}


def test_compose_travel_groups_appear_over_rolls():
    """BL-A7 sedno: na trakcie POJAWIAJĄ się grupy (wataha/herszt), nie tylko soliści.
    Przy wysokim budżecie w serii rzutów co najmniej jedno spotkanie ma ≥2 wrogów —
    czego stary single-pick NIGDY nie robił."""
    conn = _mem(); _seed_enemies(conn); _seed_session(conn, 1)
    conn.execute("INSERT INTO game_config_meta (key,value) VALUES ('encounter_difficulty_mult','3.0')")
    conn.commit()
    max_total = 0
    for seed in range(30):
        out = enc.compose_travel_encounter(conn, 1, {"hex_type": "road"}, rng=random.Random(seed))
        if out and out.get("enemies"):
            max_total = max(max_total, sum(e.get("count", 1) for e in out["enemies"]))
    assert max_total >= 2, f"żadna grupa nie powstała w 30 rzutach (max {max_total})"


def test_compose_travel_empty_pool_returns_none():
    conn = _mem()
    conn.executescript(table_sql("game_config_enemies") + table_sql("game_config_meta"))
    _seed_session(conn, 1)
    out = enc.compose_travel_encounter(conn, 1, {"hex_type": "road"}, rng=random.Random(0))
    assert out is None  # pusta pula → caller robi legacy fallback


def test_compose_travel_respects_authored_pool():
    conn = _mem(); _seed_enemies(conn); _seed_session(conn, 1)
    out = enc.compose_travel_encounter(
        conn, 1, {"hex_type": "road", "encounter_pool": ["wolf"]}, rng=random.Random(1),
    )
    assert out is not None
    assert {e["enemy_key"] for e in out["enemies"]} == {"wolf"}


# ── _authored_pool_keys: parsowanie ──────────────────────────────────────────

def test_authored_pool_keys_parsing():
    assert enc._authored_pool_keys({"encounter_pool": ["a", "b"]}) == {"a", "b"}
    assert enc._authored_pool_keys({"encounter_pool": '["a","b"]'}) == {"a", "b"}
    assert enc._authored_pool_keys({"encounter_pool": "a, b"}) == {"a", "b"}
    assert enc._authored_pool_keys({"encounter_pool": []}) is None
    assert enc._authored_pool_keys({"encounter_pool": ""}) is None
    assert enc._authored_pool_keys({}) is None


# ── turns: injection rozwija grupę do wielu kluczy ───────────────────────────

def test_pending_enemies_expands_group_by_count():
    from app.api import turns
    conn = _mem()
    conn.execute("CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    flags = {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False,
        "enemy_key": "bandit_chief",
        "enemies": [
            {"enemy_key": "bandit_chief", "count": 1},
            {"enemy_key": "bandit", "count": 2},
        ],
    }}
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
                 (7, json.dumps(flags)))
    conn.commit()
    keys = turns._pending_engine_encounter_enemies(conn, 7)
    assert keys == ["bandit_chief", "bandit", "bandit"]


def test_pending_enemies_fallback_single_key():
    from app.api import turns
    conn = _mem()
    conn.execute("CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    flags = {"travel_plan": {"interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "wolf"}}
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
                 (7, json.dumps(flags)))
    conn.commit()
    assert turns._pending_engine_encounter_enemies(conn, 7) == ["wolf"]


def test_pending_enemies_cap():
    from app.api import turns
    conn = _mem()
    conn.execute("CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    flags = {"travel_plan": {
        "interrupt_reason": "encounter", "combat_seen": False, "enemy_key": "goblin",
        "enemies": [{"enemy_key": "goblin", "count": 99}],
    }}
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
                 (7, json.dumps(flags)))
    conn.commit()
    keys = turns._pending_engine_encounter_enemies(conn, 7)
    assert len(keys) == turns._TRAVEL_GROUP_ENEMY_CAP


def test_pending_enemies_none_when_combat_seen():
    from app.api import turns
    conn = _mem()
    conn.execute("CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    flags = {"travel_plan": {"interrupt_reason": "encounter", "combat_seen": True, "enemy_key": "wolf"}}
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?,?)",
                 (7, json.dumps(flags)))
    conn.commit()
    assert turns._pending_engine_encounter_enemies(conn, 7) is None
