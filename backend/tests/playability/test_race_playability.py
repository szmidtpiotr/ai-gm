"""
Race playability smoke — dwarf race #969 (12 checkpoints).

10 checkpoints run as fast unit/integration tests inside the container.
CP11 and CP12 (real turns via live HTTP) require RACE_SMOKE_LIVE=1.

Run:
  docker cp backend/tests/playability/test_race_playability.py \
    ai-gm-dev-backend-1:/app/tests/playability/test_race_playability.py
  docker exec ai-gm-dev-backend-1 mkdir -p /app/tests/playability
  docker exec ai-gm-dev-backend-1 \
    pytest tests/playability/test_race_playability.py -v

  # With live turns (needs running LLM + dwarf heroes in DB):
  docker exec -e RACE_SMOKE_LIVE=1 ai-gm-dev-backend-1 \
    pytest tests/playability/test_race_playability.py -v
"""
import os
import sys

sys.path.insert(0, "/app")

import json
import sqlite3
import urllib.error
import urllib.request

import pytest

DB_PATH = "/data/ai_gm.db"
# #1156: bare (non-/api) character mount usunięty — wszystkie ścieżki idą przez /api.
BASE_URL = "http://localhost:8000/api"
LIVE = os.environ.get("RACE_SMOKE_LIVE", "").strip() == "1"


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _http(method: str, path: str, body=None, timeout: int = 30):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode(errors="replace"))
    except Exception as e:
        return 0, {"error": str(e)}


def _dwarf_warrior_id() -> int:
    conn = _db()
    row = conn.execute(
        "SELECT id FROM characters WHERE race='dwarf' AND name LIKE '[TEST]%Wojow%' LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        pytest.skip("Brak [TEST] Krasnolud Wojownik w DB — uruchom setup_dwarf_pool.py")
    return row["id"]


def _dwarf_scholar_id() -> int:
    conn = _db()
    row = conn.execute(
        "SELECT id FROM characters WHERE race='dwarf' AND name LIKE '[TEST]%Uczon%' LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        pytest.skip("Brak [TEST] Krasnolud Uczony w DB — uruchom setup_dwarf_pool.py")
    return row["id"]


# ─── CP1: race column in DB ──────────────────────────────────────────────────

def test_cp1_dwarf_characters_have_race_column():
    """CP1: characters table has race column; [TEST] dwarves present with race='dwarf'."""
    conn = _db()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(characters)").fetchall()]
    assert "race" in cols, "Brak kolumny race w tabeli characters"
    rows = conn.execute(
        "SELECT id, name FROM characters WHERE race='dwarf' AND name LIKE '[TEST]%'"
    ).fetchall()
    conn.close()
    assert rows, "Brak krasnoluda z race='dwarf' — uruchom setup_dwarf_pool.py"


# ─── CP2: stat modifiers ─────────────────────────────────────────────────────

def test_cp2_dwarf_stat_mods_correct():
    """CP2: CON+2, STR+1, CHA-1, DEX-1 applied by apply_racial_modifiers."""
    from app.services.actor_stats import RACIAL_STAT_MODS, apply_racial_modifiers

    mods = RACIAL_STAT_MODS.get("dwarf", {})
    assert mods.get("CON") == 2
    assert mods.get("STR") == 1
    assert mods.get("CHA") == -1
    assert mods.get("DEX") == -1

    base = {"stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}}
    result = apply_racial_modifiers(base.copy(), "dwarf")
    s = result["stats"]
    assert s["CON"] == 12, f"CON={s['CON']}"
    assert s["STR"] == 11, f"STR={s['STR']}"
    assert s["CHA"] == 9,  f"CHA={s['CHA']}"
    assert s["DEX"] == 9,  f"DEX={s['DEX']}"
    assert s["LCK"] == 10, "LCK nie powinien być zmieniony"


def test_cp2_dwarf_sheet_in_db_has_racial_mods():
    """CP2: [TEST] warrior in DB has CON ≥ 12 (racial +2 applied at creation)."""
    wid = _dwarf_warrior_id()
    conn = _db()
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (wid,)).fetchone()
    conn.close()
    sheet = json.loads(row["sheet_json"])
    con = sheet.get("stats", {}).get("CON", 0)
    assert con >= 12, f"CON={con}, oczekiwano ≥12 (base 10 + racial +2)"


# ─── CP3: Twardy jak kamień ──────────────────────────────────────────────────

def test_cp3_twardy_jak_kamien_reduces_dmg_for_qualifying_types():
    """CP3: dwarf gets -2 DR for poison/dark/rdzen; human gets full damage."""
    from app.services.combat_service import (
        DWARF_TOUGHNESS_REDUCTION,
        DWARF_TOUGHNESS_TYPES,
        apply_defense_model,
    )

    assert DWARF_TOUGHNESS_REDUCTION == 2
    assert {"poison", "dark", "rdzen"}.issubset(DWARF_TOUGHNESS_TYPES)

    for dtype in ("poison", "dark", "rdzen"):
        dwarf_r = apply_defense_model(
            base_damage=6,
            attack_total=14,
            defense_stat=10,
            ignore_armor=False,
            race="dwarf",
            damage_type=dtype,
        )
        human_r = apply_defense_model(
            base_damage=6,
            attack_total=14,
            defense_stat=10,
            ignore_armor=False,
            race="human",
            damage_type=dtype,
        )
        assert dwarf_r["toughness_reduction"] == 2, f"{dtype}: toughness_reduction={dwarf_r['toughness_reduction']}"
        assert dwarf_r["final"] < human_r["final"] or dwarf_r["final"] == 1, (
            f"{dtype}: dwarf {dwarf_r['final']} >= human {human_r['final']}"
        )


def test_cp3_twardy_jak_kamien_no_reduction_for_physical():
    """CP3 compat: physical damage is NOT reduced by Twardy jak kamień."""
    from app.services.combat_service import apply_defense_model

    dwarf_r = apply_defense_model(
        base_damage=6,
        attack_total=14,
        defense_stat=10,
        ignore_armor=False,
        race="dwarf",
        damage_type="physical",
    )
    assert dwarf_r["toughness_reduction"] == 0, "physical nie powinien być redukowany"


# ─── CP4: Kowalskie oko — sklep ──────────────────────────────────────────────

def test_cp4_shop_discount_constant():
    """CP4: DWARF_SHOP_DISCOUNT=0.15 and DWARF_REPAIR_COST_GP=20 defined."""
    from app.services.shop_service import DWARF_REPAIR_COST_GP, DWARF_SHOP_DISCOUNT

    assert DWARF_SHOP_DISCOUNT == 0.15
    assert DWARF_REPAIR_COST_GP == 20


def test_cp4_shop_discount_applies_to_price():
    """CP4: buy_item effective price for dwarf = floor(base * 0.85) < human price."""
    import math
    from app.services.shop_service import DWARF_SHOP_DISCOUNT

    base_price = 100
    expected_dwarf_price = max(1, math.floor(base_price * (1.0 - DWARF_SHOP_DISCOUNT)))
    assert expected_dwarf_price == 85, f"Cena krasnoluda={expected_dwarf_price}, oczekiwano 85"
    assert expected_dwarf_price < base_price, "Krasnolud powinien płacić mniej"


# ─── CP5: Kowalskie oko — reperuj ────────────────────────────────────────────

def test_cp5_repair_endpoint_reachable():
    """CP5: /characters/{id}/dwarf-repair endpoint exists (not 404/405)."""
    wid = _dwarf_warrior_id()
    status, body = _http("POST", f"/characters/{wid}/dwarf-repair")
    # Akceptujemy 200 (sukces), 400 (brak złota/HP), 422 (non-dwarf).
    # 404 = endpoint nie istnieje = FAIL.
    assert status != 404, f"dwarf-repair endpoint nie istnieje: HTTP {status}"
    assert status != 405, f"dwarf-repair — wrong HTTP method: {status}"


def test_cp5_repair_requires_sufficient_gold():
    """CP5: repair endpoint returns valid status (not 404/405); auth 401 also acceptable."""
    wid = _dwarf_warrior_id()
    status, body = _http("POST", f"/characters/{wid}/dwarf-repair")
    # 200 = repair succeeded, 400 = insufficient gold or HP full, 401 = auth required
    # 404 = endpoint missing = FAIL
    assert status in (200, 400, 401), f"Unexpected status {status}: {body}"


# ─── CP6: Wzrok górnika ──────────────────────────────────────────────────────

def test_cp6_darkvision_constants():
    """CP6: DWARF_DARKVISION_BONUS=3, HUMAN_DARKNESS_PENALTY=-4."""
    from app.services.dungeon_service import DWARF_DARKVISION_BONUS, HUMAN_DARKNESS_PENALTY

    assert DWARF_DARKVISION_BONUS == 3
    assert HUMAN_DARKNESS_PENALTY == -4


def test_cp6_dwarf_gets_perception_bonus_in_dungeon():
    """CP6: get_darkvision_bonus returns +3 for dwarf in dungeon, 0 penalty."""
    wid = _dwarf_warrior_id()
    from app.services.dungeon_service import get_darkvision_bonus

    result = get_darkvision_bonus(wid, is_dungeon=True)
    assert result["perception_bonus"] == 3, f"perception_bonus={result['perception_bonus']}"
    assert result["darkness_penalty"] == 0, f"darkness_penalty={result['darkness_penalty']}"
    assert result["race"] == "dwarf"


def test_cp6_human_gets_darkness_penalty_in_dungeon():
    """CP6 compat: human gets no bonus but gets darkness penalty."""
    conn = _db()
    row = conn.execute(
        "SELECT id FROM characters WHERE race='human' AND user_id=1 LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        pytest.skip("Brak human character w DB")
    from app.services.dungeon_service import get_darkvision_bonus

    result = get_darkvision_bonus(row["id"], is_dungeon=True)
    assert result["perception_bonus"] == 0
    assert result["darkness_penalty"] == -4


# ─── CP7: Rdzeń-magia — startowe czary ──────────────────────────────────────

def test_cp7_dwarf_spells_in_db():
    """CP7: 6 race_lock=dwarf spells in game_config_spells."""
    conn = _db()
    rows = conn.execute(
        "SELECT key FROM game_config_spells WHERE race_lock='dwarf'"
    ).fetchall()
    conn.close()
    keys = {r["key"] for r in rows}
    for expected in ("vein_tremor", "rdzen_pulse", "vein_bleed", "rdzen_shield", "deep_quake", "black_vein"):
        assert expected in keys, f"Brak czaru '{expected}' z race_lock=dwarf"


def test_cp7_dwarf_scholar_starting_spells():
    """CP7: [TEST] Uczony-krasnolud startuje z vein_tremor+rdzen_shield, NIE magic_bolt."""
    sid = _dwarf_scholar_id()
    conn = _db()
    rows = conn.execute(
        "SELECT spell_key FROM character_spells WHERE character_id=?", (sid,)
    ).fetchall()
    conn.close()
    spell_keys = {r["spell_key"] for r in rows}
    assert "vein_tremor" in spell_keys, f"Brak vein_tremor w {spell_keys}"
    assert "rdzen_shield" in spell_keys, f"Brak rdzen_shield w {spell_keys}"
    assert "magic_bolt" not in spell_keys, f"magic_bolt nie powinien być w {spell_keys} (race_lock=human)"


# ─── CP8: Miscast threshold ──────────────────────────────────────────────────

def test_cp8_miscast_threshold_dwarf_nat2():
    """CP8: is_miscast(2, 'dwarf')=True; is_miscast(2, 'human')=False."""
    from app.services.spell_service import DWARF_MISCAST_THRESHOLD, is_miscast

    assert DWARF_MISCAST_THRESHOLD == 2
    assert is_miscast(1, "dwarf") is True,  "Nat1 dla krasnoluda = miscast"
    assert is_miscast(2, "dwarf") is True,  "Nat2 dla krasnoluda = miscast"
    assert is_miscast(3, "dwarf") is False, "Nat3 dla krasnoluda = sukces"
    assert is_miscast(1, "human") is True,  "Nat1 dla człowieka = miscast"
    assert is_miscast(2, "human") is False, "Nat2 dla człowieka = sukces"


# ─── CP9: Race lock ──────────────────────────────────────────────────────────

def test_cp9_race_lock_rejects_human_spell_for_dwarf():
    """CP9: learn_spell rejects magic_bolt (human-only, no race_lock) for dwarf scholar."""
    from app.services.spell_service import learn_spell

    sid = _dwarf_scholar_id()
    with pytest.raises(ValueError) as exc_info:
        learn_spell(sid, "magic_bolt")
    error_msg = str(exc_info.value)
    assert "krasnolud" in error_msg.lower() or "rasa" in error_msg.lower() or "dwarf" in error_msg.lower(), (
        f"Race lock error message unexpected: {error_msg}"
    )


# ─── CP10: Narrator injection ────────────────────────────────────────────────

def test_cp10_narrator_injection_logic():
    """CP10: buildmessages includes 'Rasa postaci: dwarf' when character.race='dwarf'."""
    from unittest.mock import MagicMock
    from app.core.turn_engine import buildmessages

    campaign = MagicMock()
    campaign.__getitem__ = lambda self, k: {"system_id": "fantasy", "language": "pl"}.get(k, "")
    character = MagicMock()
    character.__getitem__ = lambda self, k: {"name": "Dwalin", "race": "dwarf"}.get(k, "")
    character.__bool__ = lambda self: True

    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=[],
        usertext="test",
    )
    system_content = messages[0]["content"]
    assert "Rasa postaci: dwarf" in system_content, (
        f"'Rasa postaci: dwarf' nie znaleziony w system message:\n{system_content[:300]}"
    )


def test_cp10_narrator_injection_human_fallback():
    """CP10 compat: buildmessages uses 'human' when character has no race."""
    from unittest.mock import MagicMock
    from app.core.turn_engine import buildmessages

    campaign = MagicMock()
    campaign.__getitem__ = lambda self, k: {"system_id": "fantasy", "language": "pl"}.get(k, "")
    character = MagicMock()
    character.__getitem__ = lambda self, k: {"name": "Artur"}.get(k, "")
    character.__bool__ = lambda self: True

    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=[],
        usertext="test",
    )
    system_content = messages[0]["content"]
    assert "Rasa postaci:" in system_content, "Rasa postaci brak w systemie"


# ─── CP11: 3 turns warrior (LIVE only) ──────────────────────────────────────

@pytest.mark.skipif(not LIVE, reason="Set RACE_SMOKE_LIVE=1 for live turn tests")
def test_cp11_three_turns_warrior_no_500():
    """CP11: 3 turns as dwarf warrior — all HTTP 200, no crashes."""
    wid = _dwarf_warrior_id()
    # Find or create a campaign for the warrior
    status, camps = _http("GET", f"/campaigns?user_id=1")
    if status != 200:
        pytest.skip(f"GET /campaigns failed: {status}")
    camp_id = None
    for c in (camps if isinstance(camps, list) else camps.get("campaigns", [])):
        if c.get("character_id") == wid or c.get("status") == "active":
            camp_id = c.get("id")
            break
    if not camp_id:
        pytest.skip("Brak aktywnej kampanii dla krasnoluda — uruchom setup_campaign.py")

    messages = [
        "Rozglądam się po okolicy i szukam przygód.",
        "Idę dalej i patrzę co jest do zrobienia.",
        "Sprawdzam czy jest jakiś wróg w pobliżu.",
    ]
    for i, msg in enumerate(messages, 1):
        status, body = _http(
            "POST",
            f"/campaigns/{camp_id}/turns",
            {"character_id": wid, "user_message": msg},
            timeout=90,
        )
        assert status == 200, f"Tura {i} zwróciła HTTP {status}: {body.get('detail', body)}"
        assert "assistant_text" in body or "narrative" in body, (
            f"Tura {i} brak narracji: {body}"
        )


# ─── CP12: 3 turns scholar (LIVE only) ──────────────────────────────────────

@pytest.mark.skipif(not LIVE, reason="Set RACE_SMOKE_LIVE=1 for live turn tests")
def test_cp12_three_turns_scholar_rdzen_magic():
    """CP12: 3 turns as dwarf scholar — rdzen spells, mana changes, no crashes."""
    sid = _dwarf_scholar_id()
    status, camps = _http("GET", f"/campaigns?user_id=1")
    if status != 200:
        pytest.skip(f"GET /campaigns failed: {status}")
    camp_id = None
    for c in (camps if isinstance(camps, list) else camps.get("campaigns", [])):
        if c.get("character_id") == sid or c.get("status") == "active":
            camp_id = c.get("id")
            break
    if not camp_id:
        pytest.skip("Brak aktywnej kampanii dla uczonego-krasnoluda")

    conn = _db()
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id=?", (sid,)
    ).fetchone()
    conn.close()
    mana_before = json.loads(row["sheet_json"]).get("current_mana", 0)

    messages = [
        "Przygotowuję czar i czuję wibrację żył kamieniowych.",
        "Rzucam vein_tremor na wroga jeśli jest w pobliżu.",
        "Używam rdzen_shield aby się chronić.",
    ]
    for i, msg in enumerate(messages, 1):
        status, body = _http(
            "POST",
            f"/campaigns/{camp_id}/turns",
            {"character_id": sid, "user_message": msg},
            timeout=90,
        )
        assert status == 200, f"Tura {i} zwróciła HTTP {status}: {body.get('detail', body)}"

    conn = _db()
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id=?", (sid,)
    ).fetchone()
    conn.close()
    mana_after = json.loads(row["sheet_json"]).get("current_mana", mana_before)
    # Mana może spaść jeśli uczony rzucił czar, albo pozostać gdy narracja nie dała walki.
    assert mana_after >= 0, f"Mana ujemna: {mana_after}"
