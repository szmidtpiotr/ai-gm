"""TDD: Issue #1193 — Wydarzenia regionalne ("żywy świat").

Pokrywa: schemat DB + seedy szablonów, aktywacja/wygasanie eventów, max 1/region,
akcesory modyfikatorów (sklep/encounter/podróż/zaraza), losowanie, flaga
auto-roll, linia narratora, oraz choroba (kara do testów + apply/cure).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.migrations_admin import ADMIN_MIGRATIONS, ADMIN_SEEDS
from app.services import world_event_service as wes
from app.services import disease_service


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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
    conn.commit()
    return conn


REGION = "kresy"


# ─── Schemat + seedy ─────────────────────────────────────────────────────────

def test_tables_exist():
    conn = _make_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "game_config_event_templates" in tables
    assert "world_events" in tables


def test_templates_seeded():
    conn = _make_db()
    tpls = {t["key"] for t in wes.list_templates(conn)}
    for k in ("jarmark", "zaraza", "rajdy", "zima", "susza"):
        assert k in tpls, f"szablon {k} nie zaseedowany"


# ─── Aktywacja / wygasanie / max 1 ───────────────────────────────────────────

def test_start_event_creates_active():
    conn = _make_db()
    ev = wes.start_event(conn, REGION, "jarmark", source="manual")
    assert ev["state"] == "active"
    active = wes.get_active_event(conn, REGION)
    assert active is not None
    assert active["template_key"] == "jarmark"
    assert active["modifiers"].get("shop_price_mult") == {"*": 0.8}


def test_max_one_active_per_region():
    conn = _make_db()
    wes.start_event(conn, REGION, "jarmark")
    wes.start_event(conn, REGION, "zaraza")
    active = wes.list_events(conn, REGION)  # tylko aktywne
    assert len(active) == 1
    assert active[0]["template_key"] == "zaraza"


def test_expire_due_flips_past_events():
    conn = _make_db()
    conn.execute(
        """INSERT INTO world_events (region, template_key, started_at, ends_at, state, source)
           VALUES (?, 'jarmark', datetime('now','-3 days'), datetime('now','-1 day'), 'active', 'manual')""",
        (REGION,),
    )
    conn.commit()
    assert wes.get_active_event(conn, REGION) is None  # leniwe wygasanie
    n = conn.execute("SELECT COUNT(*) FROM world_events WHERE state='ended'").fetchone()[0]
    assert n == 1


def test_end_event():
    conn = _make_db()
    ev = wes.start_event(conn, REGION, "jarmark")
    assert wes.end_event(conn, ev["id"]) is True
    assert wes.get_active_event(conn, REGION) is None


# ─── Akcesory modyfikatorów ──────────────────────────────────────────────────

def test_price_multiplier_jarmark_wildcard():
    conn = _make_db()
    wes.start_event(conn, REGION, "jarmark")
    assert wes.price_multiplier(conn, REGION, "weapon") == 0.8
    assert wes.price_multiplier(conn, REGION, "consumable") == 0.8


def test_price_multiplier_zaraza_category_specific():
    conn = _make_db()
    wes.start_event(conn, REGION, "zaraza")
    assert wes.price_multiplier(conn, REGION, "consumable") == 1.5
    assert wes.price_multiplier(conn, REGION, "weapon") == 1.0  # brak kategorii → 1.0


def test_no_event_multipliers_are_neutral():
    conn = _make_db()
    assert wes.price_multiplier(conn, REGION, "consumable") == 1.0
    assert wes.encounter_chance_multiplier(conn, REGION) == 1.0
    assert wes.travel_hours_multiplier(conn, REGION) == 1.0
    assert wes.disease_dc(conn, REGION) is None


def test_encounter_multiplier_rajdy():
    conn = _make_db()
    wes.start_event(conn, REGION, "rajdy")
    assert wes.encounter_chance_multiplier(conn, REGION) == 1.5
    assert wes.loot_gold_multiplier(conn, REGION) == 1.3


def test_travel_multiplier_zima():
    conn = _make_db()
    wes.start_event(conn, REGION, "zima")
    assert wes.travel_hours_multiplier(conn, REGION) == 1.25


def test_disease_dc_zaraza():
    conn = _make_db()
    wes.start_event(conn, REGION, "zaraza")
    assert wes.disease_dc(conn, REGION) == 12
    # jarmark nie ma zarazy
    wes.start_event(conn, REGION, "jarmark")
    assert wes.disease_dc(conn, REGION) is None


# ─── Losowanie ───────────────────────────────────────────────────────────────

def test_roll_event_picks_and_respects_busy():
    conn = _make_db()
    ev = wes.roll_event(conn, REGION)
    assert ev is not None
    assert ev["state"] == "active"
    # region zajęty → kolejne losowanie no-op
    assert wes.roll_event(conn, REGION) is None


# ─── Linia narratora ─────────────────────────────────────────────────────────

def test_build_event_line():
    conn = _make_db()
    wes.start_event(conn, REGION, "jarmark")
    line = wes.build_event_line(conn, campaign_id=1, region=REGION)
    assert line.startswith("WYDARZENIE:")
    assert "Jarmark" in line


def test_build_event_line_empty_without_event():
    conn = _make_db()
    assert wes.build_event_line(conn, campaign_id=1, region=REGION) == ""


# ─── Flaga auto-roll ─────────────────────────────────────────────────────────

def test_auto_roll_flag_default_off(monkeypatch):
    monkeypatch.setattr(wes, "get_global_flag", lambda k, d="0": d)
    assert wes.is_auto_roll_enabled() is False


def test_auto_roll_flag_on(monkeypatch):
    monkeypatch.setattr(wes, "get_global_flag",
                        lambda k, d="0": "1" if k == wes.AUTO_ROLL_FLAG else d)
    assert wes.is_auto_roll_enabled() is True


# ─── Choroba ─────────────────────────────────────────────────────────────────

def test_chory_condition_seeded():
    conn = _make_db()
    row = conn.execute(
        "SELECT key FROM game_config_conditions WHERE key='chory'"
    ).fetchone()
    assert row is not None


def test_disease_penalty():
    chory = {"key": "chory", "effect_json":
             {"effects": [{"type": "flat_test_penalty", "value": -2}]}}
    assert disease_service.compute_disease_penalty([chory]) == -2
    assert disease_service.compute_disease_penalty([]) == 0


def test_apply_and_cure_disease():
    conn = _make_db()
    sheet = {"conditions": []}
    assert disease_service.apply_disease(conn, sheet) is True
    assert disease_service.has_disease(sheet["conditions"]) is True
    # idempotent
    assert disease_service.apply_disease(conn, sheet) is False
    assert disease_service.cure_disease(sheet) is True
    assert disease_service.has_disease(sheet["conditions"]) is False


# ─── Dymek system_events (#1193 follow-up) ───────────────────────────────────

def test_notify_emits_once_and_dedupes():
    from app.services import system_events as se
    conn = _make_db()
    wes.start_event(conn, REGION, "zima")
    with se.use_turn_bus() as bus:
        wes.notify_if_new(conn, campaign_id=1)
        wes.notify_if_new(conn, campaign_id=1)  # drugi raz — już seen
        events = bus.drain()
    # jeden dymek (dedupe przez world_event_seen), z badge zimy
    assert len(events) == 1
    assert events[0]["icon"] == "❄"
    assert "zima" in events[0]["text"].lower()
    # marker zapisany
    n = conn.execute("SELECT COUNT(*) FROM world_event_seen WHERE campaign_id=1").fetchone()[0]
    assert n == 1


def test_notify_noop_outside_turn_bus():
    conn = _make_db()
    wes.start_event(conn, REGION, "zima")
    # brak busa → nie zużywa powiadomienia, nie zapisuje markera
    wes.notify_if_new(conn, campaign_id=1)
    n = conn.execute("SELECT COUNT(*) FROM world_event_seen").fetchone()[0]
    assert n == 0


def test_notify_new_event_after_first_seen():
    from app.services import system_events as se
    conn = _make_db()
    wes.start_event(conn, REGION, "zima")
    with se.use_turn_bus() as bus:
        wes.notify_if_new(conn, campaign_id=1)
        bus.drain()
    # nowe wydarzenie (kończy zimę) → nowy dymek
    wes.start_event(conn, REGION, "jarmark")
    with se.use_turn_bus() as bus2:
        wes.notify_if_new(conn, campaign_id=1)
        events = bus2.drain()
    assert len(events) == 1
    assert events[0]["icon"] == "🎪"


def test_disease_survives_clear_all_fatigue():
    """Choroba używa flat_test_penalty, nie stacking → długi odpoczynek jej nie zdejmuje."""
    from app.services.fatigue_service import clear_all_fatigue
    conn = _make_db()
    sheet = {"conditions": []}
    disease_service.apply_disease(conn, sheet)
    remaining = clear_all_fatigue(sheet["conditions"])
    assert disease_service.has_disease(remaining) is True
