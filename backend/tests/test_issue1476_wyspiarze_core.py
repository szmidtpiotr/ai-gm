"""Issue #1476 — Wyspiarze: rdzeń rasy (staty, bramka archetypu, diaspora, Morska krew,
kit Wojownika-Zabijaki — bramka dostępu).

Zakres „rasa istnieje i jest spójna" — BEZ krainy rodowej (Wybrzeże Łez #1504/#1505
wdrażane osobno). Kluczowe różnice od poprzednich ras:
  * STR +1 / CHA +2 / INT −1 — krzepcy cwaniacy portowi,
  * diaspora bez domu → brak kotwicy krainy (RACE_HOME_REGION None) → dostępna zawsze,
  * Uczony zamknięty (INT −1 + kultura), droga = Łotrzyk-Kombinator / Wojownik-Zabijaka,
  * Morska krew — `sailing` liczone od CHA (bo INT −1 psułoby lud marynarzy),
  * kit Zabijaki (Groźba bosmana / Chwyt sztauera / Brudny cios) tylko dla
    rasy=wyspiarze ∧ archetyp=warrior.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import race_start_service as rss
from app.services.actor_stats import RACIAL_STAT_MODS, apply_racial_modifiers
from app.services.combat_service import _zabijaka_ok
from app.services.skill_access_service import RACE_SKILL_WEIGHTS
from app.services.skill_service import _skill_stat_for, calc_skill_modifier_info
from app.services.world_region_service import (
    RACE_HOME_REGION,
    RACE_LABELS,
    race_availability,
)


# ─── Staty rasowe ────────────────────────────────────────────────────────────

def test_wyspiarze_stat_modifiers():
    assert RACIAL_STAT_MODS["wyspiarze"] == {"STR": +1, "CHA": +2, "INT": -1}


def test_apply_racial_modifiers_wyspiarze():
    sheet = {"stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 12, "WIS": 10, "CHA": 12, "LCK": 10}}
    out = apply_racial_modifiers(sheet, "wyspiarze")
    assert out["stats"]["STR"] == 11
    assert out["stats"]["CHA"] == 14
    assert out["stats"]["INT"] == 11
    assert out["stats"]["DEX"] == 10 and out["stats"]["CON"] == 10


def test_other_races_unchanged():
    assert RACIAL_STAT_MODS["human"] == {}
    assert RACIAL_STAT_MODS["dwarf"] == {"CON": +2, "STR": +1, "CHA": -1, "DEX": -1}
    assert RACIAL_STAT_MODS["elf"] == {"DEX": +2, "WIS": +1, "CON": -1}
    assert RACIAL_STAT_MODS["pietnowani"] == {"INT": +2, "WIS": +1, "CON": -1}


# ─── Bramka archetypu ────────────────────────────────────────────────────────

@pytest.mark.parametrize("arch", ["warrior", "rogue"])
def test_wyspiarze_can_be_warrior_or_rogue(arch):
    assert rss.archetype_allowed("wyspiarze", arch) is True


def test_wyspiarze_cannot_be_scholar():
    assert rss.archetype_allowed("wyspiarze", "scholar") is False
    reason = rss.archetype_block_reason("wyspiarze", "scholar")
    assert reason and "Kombinator" in reason


def test_wyspiarze_cannot_be_gish():
    assert rss.archetype_allowed("wyspiarze", "wojownik_mag") is False


def test_blocked_list_for_creator():
    assert set(rss.blocked_archetypes_for_race("wyspiarze")) == {"scholar", "wojownik_mag"}


# ─── Diaspora: brak kotwicy krainy, dostępna zawsze ──────────────────────────

def test_wyspiarze_have_no_home_region():
    assert RACE_HOME_REGION["wyspiarze"] is None
    assert RACE_LABELS["wyspiarze"] == "Wyspiarz"


def test_wyspiarze_start_anchor_added_in_wl9():
    """WL-9 (#1504 §10) — kampania wyspiarza domyślnie startuje w Czarnogrodzie.
    Kotwica startu NIE zmienia dostępności rasy (patrz test niżej: home_region None,
    dostępna wszędzie). Szczegóły whitelisty: tests/test_wl9_wyspiarze_start.py."""
    assert "wyspiarze" in rss.RACE_START
    assert rss.RACE_START["wyspiarze"]["region"] == "wybrzeze_lez"
    assert rss.RACE_START["wyspiarze"]["default"] == "czarnogrod_dzielnica_wyspiarzy"


def _regions_conn(status: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE world_regions (key TEXT PRIMARY KEY, label TEXT, status TEXT)")
    conn.execute(
        "INSERT INTO world_regions (key, label, status) VALUES ('siwe_granie','Siwe Granie',?)",
        (status,),
    )
    conn.commit()
    return conn


def _entry(rows: list[dict], key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


def test_wyspiarze_available_for_everyone_diaspora():
    """Brak kotwicy → dostępny publicznie niezależnie od statusu krain."""
    conn = _regions_conn("coming")
    try:
        wy = _entry(race_availability(conn, include_coming=False), "wyspiarze")
        assert wy["available"] is True
        assert wy["home_region"] is None
        assert set(wy["blocked_archetypes"]) == {"scholar", "wojownik_mag"}
    finally:
        conn.close()


def test_wyspiarze_plan_hint_anchors_czarnogrod_keeps_diaspora_thread():
    # WL-9: hint wskazuje start w Czarnogrodzie (key_locations[0]) ORAZ zachowuje
    # wątek §7 diaspory obecnej wszędzie.
    hint = rss.RACE_PLAN_HINT["wyspiarze"]
    assert "Sztormem Wiecznym" in hint
    assert "key_locations[0]" in hint
    assert "Dzielnica Wyspiarzy" in hint
    assert "WSZĘDZIE" in hint or "wszędzie" in hint


# ─── Morska krew — sailing liczone od CHA ────────────────────────────────────

def test_morska_krew_sailing_governed_by_cha():
    assert _skill_stat_for("sailing", "wyspiarze") == "CHA"


def test_sailing_stays_int_for_other_races():
    # Bez override → wartość katalogowa (fallback INT, gdy DB niedostępne w teście jednostkowym).
    assert _skill_stat_for("sailing", "human") == "INT"
    assert _skill_stat_for("sailing", None) == "INT"


def test_morska_krew_only_touches_sailing():
    # Inne skille wyspiarza pozostają na katalogowej statystyce (perswazja = CHA tak czy siak).
    assert _skill_stat_for("persuasion", "wyspiarze") == "CHA"
    assert _skill_stat_for("athletics", "wyspiarze") == "STR"


def test_calc_modifier_uses_cha_for_sailing_wyspiarz():
    sheet = {
        "race": "wyspiarze",
        "stats": {"STR": 12, "DEX": 10, "CON": 10, "INT": 8, "WIS": 10, "CHA": 16, "LCK": 10},
        "skills": {"sailing": 2},
    }
    info = calc_skill_modifier_info(sheet, "sailing")
    assert info["governing_stat"] == "CHA"


def test_wyspiarze_skill_bias():
    bias = set(RACE_SKILL_WEIGHTS["wyspiarze"])
    assert bias == {"persuasion", "intimidation", "pickpocket", "sailing"}


# ─── Kit Zabijaki — bramka dostępu (rasa ∧ archetyp) ─────────────────────────

def _char_conn(race: str, archetype: str | None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE characters (id INTEGER PRIMARY KEY, race TEXT, sheet_json TEXT)")
    import json as _json
    conn.execute(
        "INSERT INTO characters (id, race, sheet_json) VALUES (1, ?, ?)",
        (race, _json.dumps({"archetype": archetype} if archetype else {})),
    )
    conn.commit()
    return conn


def test_zabijaka_gate_wyspiarz_warrior_ok():
    conn = _char_conn("wyspiarze", "warrior")
    try:
        assert _zabijaka_ok(conn, 1, {"archetype": "warrior"}) is True
        # Także gdy archetyp trzeba doczytać z sheet_json w DB (brak w przekazanym sheet).
        assert _zabijaka_ok(conn, 1, None) is True
    finally:
        conn.close()


@pytest.mark.parametrize(
    "race,arch",
    [("wyspiarze", "rogue"), ("wyspiarze", "scholar"), ("human", "warrior"), ("dwarf", "warrior")],
)
def test_zabijaka_gate_rejects_non_wyspiarz_warrior(race, arch):
    conn = _char_conn(race, arch)
    try:
        assert _zabijaka_ok(conn, 1, {"archetype": arch}) is False
    finally:
        conn.close()
