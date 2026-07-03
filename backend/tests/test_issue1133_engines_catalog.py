"""TDD: Issue #1133 (PT-D4d) — przepięcie silników social+world na katalog.

`social_encounter_service.pick_social_event` i `encounter_service.maybe_inject_encounter`
losują z `game_config_encounters` (katalog z #1130), a przy pustym katalogu spadają
do dotychczasowego hardcode (`_EVENT_DEFS` / GENERIC_ENCOUNTERS). Przy użyciu rośnie
`times_used`. Reguły rozstrzygania (split 50/50, d20+stat+skill, Nat1, kieszonkowiec)
BEZ zmian.

Testy używają in-memory sqlite — nie dotykają /data/ai_gm.db (deterministyczne).
"""
import json
import random
import sqlite3

import pytest

from app.services import encounter_catalog_service as cat
from app.services import social_encounter_service as ses
from app.services import encounter_service as enc_svc


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


# ─── SOCIAL: draw z katalogu ──────────────────────────────────────────────────

def test_pick_social_event_draws_from_catalog():
    """Z conn+zaseedowanym katalogiem pick_social_event bierze rekord z katalogu."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)

    ev = ses.pick_social_event("market", conn=conn, rng=random.Random(0))
    # klucze z katalogu dla subtypu market (seed z _SUBTYPE_EVENTS)
    assert ev["key"] in ("tout", "guard_check"), ev["key"]
    # kształt zgodny z silnikiem: stat/skill/dc/kind obecne
    assert ev.get("stat") and ev.get("skill") and ev.get("dc")
    assert ev.get("kind") in ("soft", "pickpocket")


def test_pick_social_event_increments_times_used():
    """Użycie rekordu z katalogu podbija times_used tego rekordu."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.seed_catalog(conn)

    ev = ses.pick_social_event("alley", conn=conn, rng=random.Random(1))
    used = conn.execute(
        "SELECT times_used FROM game_config_encounters WHERE key=?", (ev["key"],)
    ).fetchone()["times_used"]
    assert used >= 1, f"times_used nie wzrósł dla {ev['key']}"


def test_pick_social_event_fallback_when_catalog_empty():
    """Pusty katalog → fallback do hardcode _EVENT_DEFS (nic się nie psuje)."""
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)  # tabela istnieje, ale pusta
    ev = ses.pick_social_event("tavern", conn=conn, rng=random.Random(0))
    assert ev["key"] in ses._SUBTYPE_EVENTS["tavern"]
    assert ev.get("stat") and ev.get("dc")


def test_pick_social_event_backward_compat_no_conn():
    """Bez conn stary interfejs (roll) działa jak dotychczas (hardcode)."""
    ev = ses.pick_social_event("alley", roll=0.0)
    assert ev["key"] in ("pickpocket", "drunk_harassment")


# ─── SOCIAL: build_social_outcome z jawnym kind (encounter AI z nowym kluczem) ─

def test_build_social_outcome_accepts_explicit_kind():
    """Encounter z katalogu z NOWYM kluczem (spoza _EVENT_DEFS) i kind='pickpocket'
    nadal liczy stratę złota — dzięki jawnemu przekazaniu kind."""
    flags: dict = {}
    check = {"success": False, "escalate_combat": False}
    out = ses.build_social_outcome(
        event_key="ai_generated_pickpocket_xyz",  # spoza _EVENT_DEFS
        subtype="market",
        gold=1000,
        skill_check=check,
        flags=flags,
        delay_turns=2,
        kind="pickpocket",
    )
    assert out["kind"] == "pickpocket"
    assert out["gold_loss"] == 50  # 10% z 1000, cap 50


def test_build_social_outcome_backward_compat_kind_from_defs():
    """Bez jawnego kind — kind wyprowadzany z _EVENT_DEFS (stare zachowanie)."""
    flags: dict = {}
    check = {"success": False, "escalate_combat": False}
    out = ses.build_social_outcome(
        event_key="pickpocket", subtype="alley", gold=1000,
        skill_check=check, flags=flags, delay_turns=1,
    )
    assert out["kind"] == "pickpocket"
    assert out["gold_loss"] == 50


# ─── COMBAT: maybe_inject_encounter serwuje z katalogu ────────────────────────

def _setup_combat_db() -> sqlite3.Connection:
    conn = _mem_conn()
    # sesja gry (pusty session_flags → brak blokad lokacji/stanu)
    conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    # hex forest
    conn.execute(
        "CREATE TABLE world_hexes (q INTEGER, r INTEGER, hex_type TEXT, "
        "forge_encounter_pool TEXT, is_active INTEGER)"
    )
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, forge_encounter_pool, is_active) "
        "VALUES (0, 0, 'forest', '[]', 1)"
    )
    # wróg już istnieje (ensure_encounter_enemies_in_db nie musi wstawiać pełnego schematu)
    conn.execute("CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO game_config_enemies (key) VALUES ('wolf')")
    # katalog z jednym combatem forest
    cat.ensure_catalog_schema(conn)
    cat.insert_encounter(
        conn, key="cat_wolves__forest", kind="combat", biome="forest",
        level_min=1, level_max=5, weight=100,
        payload={"title": "Wataha z katalogu",
                 "enemies": [{"enemy_key": "wolf", "name": "wilk", "count": 2}],
                 "scene_setup": "Wilki z katalogu."},
    )
    conn.commit()
    return conn


def test_maybe_inject_encounter_uses_catalog(monkeypatch):
    """Silnik combat serwuje encounter z katalogu wg biomu/poziomu + times_used++."""
    conn = _setup_combat_db()
    monkeypatch.setattr(enc_svc.random, "random", lambda: 0.0)  # wymuś trafienie

    fired = enc_svc.maybe_inject_encounter(conn, campaign_id=1, trigger="hex_enter", q=0, r=0)
    assert fired is True

    sf = json.loads(
        conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()["session_flags"]
    )
    ae = sf.get("active_encounter")
    assert ae, "brak active_encounter"
    assert ae.get("source") == "catalog"
    assert ae.get("catalog_key") == "cat_wolves__forest"

    used = conn.execute(
        "SELECT times_used FROM game_config_encounters WHERE key='cat_wolves__forest'"
    ).fetchone()["times_used"]
    assert used == 1, f"times_used nie wzrósł: {used}"


def test_maybe_inject_encounter_empty_catalog_falls_back(monkeypatch):
    """Pusty katalog → silnik nie wywala się i wraca do legacy (brak crashu)."""
    conn = _setup_combat_db()
    conn.execute("DELETE FROM game_config_encounters")  # pusty katalog
    # brak adventure_hooks → legacy zwróci False, ale bez wyjątku
    monkeypatch.setattr(enc_svc.random, "random", lambda: 0.0)
    # nie może rzucić; brak katalogu i brak hooków → False
    result = enc_svc.maybe_inject_encounter(conn, campaign_id=1, trigger="hex_enter", q=0, r=0)
    assert result is False


# ─── Katalog: increment_times_used unit ───────────────────────────────────────

def test_increment_times_used():
    conn = _mem_conn()
    cat.ensure_catalog_schema(conn)
    cat.insert_encounter(conn, key="x", kind="combat", biome="forest", weight=1,
                         payload={"enemies": []})
    cat.increment_times_used(conn, "x")
    cat.increment_times_used(conn, "x")
    n = conn.execute("SELECT times_used FROM game_config_encounters WHERE key='x'").fetchone()["times_used"]
    assert n == 2
