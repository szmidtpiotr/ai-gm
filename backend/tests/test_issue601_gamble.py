"""TDD: Issue #601 (S7) — Gamble: hazard z prawdziwą stawką złota.

Sędzią mechaniki jest czysty serwis ``gamble_service``: walidacja stawki
(≥1 gp, ≤ aktualne złoto), wypłata wg stopnia testu (S1), limit gier na scenę
(reset przy zmianie lokacji) i sygnał oskarżenia o oszustwo przy krytycznej
porażce. Złoto wędruje przez ``change_gold`` (U26) — tu testujemy NETTO delty.
Liczby = wartości startowe (Numbers Policy).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services import gamble_service as gs


# ─── Walidacja stawki (wzorzec [SPEND_GOLD] F4) ──────────────────────────────

def test_validate_stake_ok():
    stake, err = gs.validate_stake(20, current_gold=100)
    assert stake == 20
    assert err is None


def test_validate_stake_below_min():
    stake, err = gs.validate_stake(0, current_gold=100)
    assert err == "stake_below_min"


def test_validate_stake_exceeds_gold():
    stake, err = gs.validate_stake(150, current_gold=100)
    assert err == "stake_exceeds_gold"


def test_validate_stake_non_numeric():
    stake, err = gs.validate_stake("abc", current_gold=100)
    assert err == "invalid_stake"


def test_validate_stake_equal_to_gold_allowed():
    """Można postawić całe złoto (≤ aktualne złoto)."""
    stake, err = gs.validate_stake(100, current_gold=100)
    assert stake == 100 and err is None


# ─── Wypłata wg stopnia testu (S1) ───────────────────────────────────────────

def test_payout_delta_steps():
    """Sukces +stawka, krytyk +2×, porażka −stawka, krytporażka −stawka."""
    assert gs.payout_delta("CRITICAL_SUCCESS", 20) == 40
    assert gs.payout_delta("SUCCESS", 20) == 20
    assert gs.payout_delta("FAILURE", 20) == -20
    assert gs.payout_delta("CRITICAL_FAILURE", 20) == -20


def test_payout_delta_unknown_is_loss():
    """Nieznany stopień traktowany jak porażka (bezpieczny default — gracz nie zyskuje)."""
    assert gs.payout_delta("WHATEVER", 20) == -20


# ─── Limit gier na scenę/lokację (anti-abuse) ────────────────────────────────

def test_can_gamble_until_limit():
    flags: dict = {}
    loc = "tavern_a"
    assert gs.can_gamble(flags, loc) is True
    gs.record_gamble(flags, loc)
    gs.record_gamble(flags, loc)
    assert gs.can_gamble(flags, loc) is True   # 2 < 3
    gs.record_gamble(flags, loc)
    assert gs.can_gamble(flags, loc) is False   # 3 osiągnięte


def test_gamble_count_resets_on_location_change():
    """Zmiana lokacji = nowa scena → licznik startuje od zera."""
    flags: dict = {}
    gs.record_gamble(flags, "tavern_a")
    gs.record_gamble(flags, "tavern_a")
    gs.record_gamble(flags, "tavern_a")
    assert gs.can_gamble(flags, "tavern_a") is False
    assert gs.can_gamble(flags, "tavern_b") is True   # inna lokacja → reset
    assert gs.gamble_count(flags, "tavern_b") == 0


# ─── apply_gamble_outcome — netto + licznik + oskarżenie ──────────────────────

def test_apply_success_returns_positive_delta_and_counts():
    flags: dict = {}
    res = gs.apply_gamble_outcome(flags, "SUCCESS", stake=20, location_key="tavern_a")
    assert res["delta"] == 20
    assert res["cheat_accused"] is False
    assert gs.gamble_count(flags, "tavern_a") == 1


def test_apply_critical_failure_sets_cheat_flag():
    flags: dict = {}
    res = gs.apply_gamble_outcome(flags, "CRITICAL_FAILURE", stake=30, location_key="tavern_a")
    assert res["delta"] == -30
    assert res["cheat_accused"] is True
    assert gs.consume_cheat_accusation(flags) is True
    # jednorazowy — drugi odczyt już pusty
    assert gs.consume_cheat_accusation(flags) is False


def test_apply_success_does_not_set_cheat_flag():
    flags: dict = {}
    gs.apply_gamble_outcome(flags, "CRITICAL_SUCCESS", stake=10, location_key="tavern_a")
    assert gs.consume_cheat_accusation(flags) is False


# ─── Backward compat: brak gry = brak zmian ──────────────────────────────────

def test_no_gamble_means_neutral():
    flags: dict = {}
    assert gs.gamble_count(flags, "tavern_a") == 0
    assert gs.can_gamble(flags, "tavern_a") is True
    assert gs.consume_cheat_accusation(flags) is False


# ─── Integracja: rozpoznanie tagu [GAMBLE:...] w intercept_skill_test_tag ─────

import json
import sqlite3

from app.services.skill_service import intercept_skill_test_tag


def _setup_conn(gold: int = 100, location_key: str = "tavern_a", flags: dict | None = None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER, sheet_json TEXT);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT, current_location_id INTEGER);
        CREATE TABLE skill_counters (player_skill_key TEXT PRIMARY KEY, counter_type TEXT, counter_key TEXT, default_dc INTEGER);
        """
    )
    conn.execute("INSERT INTO characters VALUES (1, ?, ?)",
                 (gold, json.dumps({"stats": {"CHA": 12}, "skills": {}})))
    conn.execute("INSERT INTO game_locations VALUES (5, ?)", (location_key,))
    conn.execute("INSERT INTO game_sessions VALUES (1, ?, 5)",
                 (json.dumps(flags or {}),))
    conn.execute("INSERT INTO skill_counters VALUES ('gamble','opposed','CHA',12)")
    conn.commit()
    return conn


def test_gamble_tag_creates_pending_with_stake():
    conn = _setup_conn(gold=100)
    prose = "Siadasz do stołu. [GAMBLE:20:DC:12] Kości turkoczą w kubku."
    cleaned, pending = intercept_skill_test_tag(prose, conn, campaign_id=1, character_id=1)
    assert "[GAMBLE" not in cleaned                 # tag zdjęty z narracji
    assert pending is not None
    assert pending["skill_key"] == "gamble"
    assert pending["gamble"]["stake"] == 20
    assert pending["counter"]["dc"] == 12


def test_gamble_tag_rejected_when_stake_exceeds_gold():
    conn = _setup_conn(gold=10)                     # gracz ma tylko 10 zł
    prose = "Stawiasz fortunę. [GAMBLE:500:DC:12] Stół milknie."
    cleaned, pending = intercept_skill_test_tag(prose, conn, campaign_id=1, character_id=1)
    assert pending is None                          # brak karty rzutu
    assert "[GAMBLE" not in cleaned                 # ale narracja zostaje


def test_gamble_tag_rejected_when_scene_limit_reached():
    # 3 gry już rozegrane w tej samej lokacji → 4. próba odrzucona.
    conn = _setup_conn(gold=100, location_key="tavern_a",
                       flags={"gamble_scene_loc": "tavern_a", "gamble_scene_count": 3})
    prose = "Znowu sięgasz po kubek. [GAMBLE:5:DC:12]"
    cleaned, pending = intercept_skill_test_tag(prose, conn, campaign_id=1, character_id=1)
    assert pending is None


def test_no_gamble_tag_passes_through():
    conn = _setup_conn()
    prose = "Spokojny wieczór w karczmie, nikt nie gra."
    cleaned, pending = intercept_skill_test_tag(prose, conn, campaign_id=1, character_id=1)
    assert pending is None
    assert cleaned == prose


# ─── Seed: żywa baza DEV (skipif gdy brak /data/ai_gm.db) ─────────────────────

import os

_DB_PATH = os.environ.get("AIGM_DB_PATH", "/data/ai_gm.db")
_live = pytest.mark.skipif(
    not os.path.exists(_DB_PATH),
    reason=f"żywa baza DEV niedostępna ({_DB_PATH}) — uruchom w kontenerze backendu",
)


@_live
def test_gamble_skill_seeded():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT linked_stat, label FROM game_config_skills WHERE key = 'gamble'"
    ).fetchone()
    conn.close()
    assert row is not None, "skill 'gamble' nie zaseedowany"
    assert row["linked_stat"] == "CHA"


@_live
def test_gamble_counter_seeded():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT counter_type, counter_key, default_dc FROM skill_counters WHERE player_skill_key = 'gamble'"
    ).fetchone()
    conn.close()
    assert row is not None, "counter 'gamble' nie zaseedowany"
    assert row["counter_type"] == "opposed"
    assert row["counter_key"] == "CHA"
