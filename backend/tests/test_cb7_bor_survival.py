"""CB-7 (#1490) — smaczki Czarnoboru: próchno świetlne + dziegieć czarnodrzewny.

Testy samowystarczalne (własne sqlite in-memory / czyste funkcje) — nie zależą od
żywego katalogu DEV. Weryfikują silnik z bor_survival_service oraz integrację
z rzutem szansy spotkania w hex_travel_service (docs/.../czarnobor.md §6).
"""

import sqlite3

import pytest

from app.services import bor_survival_service as bor
from app.services.hex_travel_service import _encounter_chance, NIGHT_ENCOUNTER_MULT


# ── próchno vs pochodnia: klasyfikacja źródła światła ─────────────────────────

def test_torch_is_open_flame_by_effect_json():
    ej = '{"effect_category": "light_source", "light_kind": "open_flame", "attracts_encounters": true}'
    assert bor.item_is_open_flame("torch", ej) is True


def test_prochno_is_cold_light_not_open_flame():
    ej = '{"effect_category": "light_source", "light_kind": "cold", "attracts_encounters": false}'
    assert bor.item_is_open_flame("prochno_swietlne", ej) is False


def test_torch_open_flame_fallback_by_key_when_no_effect_json():
    # stara baza: torch bez effect_json → fallback po znanym kluczu
    assert bor.item_is_open_flame("torch", None) is True
    assert bor.item_is_open_flame("prochno_swietlne", None) is False


# ── mnożnik szansy spotkania od światła ──────────────────────────────────────

def test_light_mult_torch_only_at_night():
    assert bor.light_encounter_mult(has_open_flame=True, night_march=False) == 1.0
    assert bor.light_encounter_mult(has_open_flame=True, night_march=True) == bor.TORCH_NIGHT_ENCOUNTER_MULT


def test_light_mult_prochno_never_penalises():
    assert bor.light_encounter_mult(has_open_flame=False, night_march=True) == 1.0
    assert bor.light_encounter_mult(has_open_flame=False, night_march=False) == 1.0


def test_night_travel_torch_vs_prochno_encounter_chance_differs():
    """WERYFIKACJA §6: nocny marsz z pochodnią daje WYŻSZĄ szansę niż z próchnem."""
    hex_data = {"hex_type": "czarny_las", "encounter_chance": 0.30}
    cfg: dict[str, dict] = {}  # brak tabeli terenu → używa per-hex 0.30

    night = NIGHT_ENCOUNTER_MULT  # 1.5
    torch_mult = night * bor.light_encounter_mult(has_open_flame=True, night_march=True)
    prochno_mult = night * bor.light_encounter_mult(has_open_flame=False, night_march=True)

    p_torch = _encounter_chance(hex_data, cfg, chance_mult=torch_mult)
    p_prochno = _encounter_chance(hex_data, cfg, chance_mult=prochno_mult)

    # liczby do raportu: 0.30 × 1.5 × 1.5 = 0.675 (pochodnia) vs 0.30 × 1.5 = 0.45 (próchno)
    assert p_torch == pytest.approx(0.675)
    assert p_prochno == pytest.approx(0.45)
    assert p_torch > p_prochno


def test_carries_open_flame_light_reads_inventory():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_config_items (key TEXT PRIMARY KEY, effect_json TEXT)")
    conn.execute("CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER, item_key TEXT)")
    conn.execute(
        "INSERT INTO game_config_items (key, effect_json) VALUES (?, ?)",
        ("torch", '{"effect_category":"light_source","light_kind":"open_flame"}'),
    )
    conn.execute(
        "INSERT INTO game_config_items (key, effect_json) VALUES (?, ?)",
        ("prochno_swietlne", '{"effect_category":"light_source","light_kind":"cold"}'),
    )

    # tylko próchno w plecaku → brak otwartego ognia
    conn.execute("INSERT INTO character_inventory (id, character_id, item_key) VALUES (1, 7, 'prochno_swietlne')")
    assert bor.carries_open_flame_light(conn, 7) is False

    # dorzuć pochodnię → otwarty ogień obecny
    conn.execute("INSERT INTO character_inventory (id, character_id, item_key) VALUES (2, 7, 'torch')")
    assert bor.carries_open_flame_light(conn, 7) is True


# ── dziegieć: buff dzienny ───────────────────────────────────────────────────

def test_salve_payload_detects_scent_mask():
    ej = '{"effect_category": "scent_mask", "forest_encounter_mult": 0.5, "stealth_bonus": 2, "duration_hours": 24}'
    assert bor.salve_payload_from_item(ej) is not None
    assert bor.salve_payload_from_item('{"effect_category": "consumable_immediate"}') is None
    assert bor.salve_payload_from_item(None) is None


def test_scent_mask_active_window():
    sf = {bor.SCENT_MASK_FLAG: 100}
    assert bor.scent_mask_active(sf, 99) is True     # przed wygaśnięciem
    assert bor.scent_mask_active(sf, 100) is False    # dokładnie na progu = już nie
    assert bor.scent_mask_active(sf, 101) is False    # po
    assert bor.scent_mask_active({}, 50) is False     # brak buffa


def test_dziegiec_stealth_bonus_only_while_active():
    sf = {bor.SCENT_MASK_FLAG: 30}
    assert bor.dziegiec_stealth_bonus(sf, 10) == bor.DZIEGIEC_STEALTH_BONUS
    assert bor.dziegiec_stealth_bonus(sf, 40) == 0


def test_dziegiec_forest_only_and_reduces_chance():
    sf = {bor.SCENT_MASK_FLAG: 30}
    # las → obniżka
    assert bor.forest_encounter_mult(sf, 10, "czarny_las") == bor.DZIEGIEC_FOREST_ENCOUNTER_MULT
    assert bor.forest_encounter_mult(sf, 10, "las_iglasty") == bor.DZIEGIEC_FOREST_ENCOUNTER_MULT
    # step/góry → bez efektu
    assert bor.forest_encounter_mult(sf, 10, "step") == 1.0
    # buff wygasł → bez efektu nawet w lesie
    assert bor.forest_encounter_mult(sf, 40, "czarny_las") == 1.0


def test_apply_scent_mask_buff_writes_session_flags(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT)")
    conn.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 42, '{}')")

    # zegar gry: 100h → buff do 124h (1 dzień = 24h)
    monkeypatch.setattr(bor, "_ingame_hours", lambda c, cid: 100)
    out = bor.apply_scent_mask_buff(conn, 42)
    assert out["expires_ingame_hours"] == 100 + bor.DZIEGIEC_DURATION_HOURS
    assert out["stealth_bonus"] == bor.DZIEGIEC_STEALTH_BONUS

    import json
    sf = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE id=1").fetchone()["session_flags"])
    assert sf[bor.SCENT_MASK_FLAG] == 124
    # aktywny o 120h, wygasły o 124h
    assert bor.scent_mask_active(sf, 120) is True
    assert bor.scent_mask_active(sf, 124) is False


def test_dziegiec_forest_encounter_full_chain():
    """Dziegieć na hexie leśnym w nocnym marszu z próchnem = jeszcze niższa szansa."""
    hex_data = {"hex_type": "czarny_las", "encounter_chance": 0.30}
    cfg: dict[str, dict] = {}
    sf = {bor.SCENT_MASK_FLAG: 999}

    night = NIGHT_ENCOUNTER_MULT
    prochno = bor.light_encounter_mult(has_open_flame=False, night_march=True)
    dziegiec = bor.forest_encounter_mult(sf, 10, "czarny_las")
    mult = night * prochno * dziegiec  # 1.5 × 1.0 × 0.5 = 0.75

    p = _encounter_chance(hex_data, cfg, chance_mult=mult)
    assert p == pytest.approx(0.225)  # 0.30 × 0.75
