#!/usr/bin/env python3
"""
Phase 7 test suite — dice roll full fix
Run: python test_phase7.py
Requires: backend running on localhost:8000, character ID 15 in campaign 5
"""

import requests
import json

BASE = "http://localhost:8000"
CAMPAIGN_ID = 5
CHARACTER_ID = 15

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
SKIP = "\033[93m⚠️  SKIP\033[0m"

results = []

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    results.append(condition)
    print(f"{status} {label}")
    if detail:
        print(f"      {detail}")

def test(label, fn):
    try:
        fn()
    except Exception as e:
        results.append(False)
        print(f"{FAIL} {label} — Exception: {e}")

print("\n=== Phase 7 — Dice Roll Full Fix ===\n")

# ── 7.1 Health check ──────────────────────────────────────────────────────
def t_health():
    r = requests.get(f"{BASE}/api/health", timeout=5)
    check("7.0 Backend alive", r.status_code == 200, r.text[:80])
test("Health", t_health)

# ── 7.2 Sheet still readable ──────────────────────────────────────────────
def t_sheet_read():
    r = requests.get(f"{BASE}/api/characters/{CHARACTER_ID}/sheet", timeout=5)
    check("7.1a GET /sheet returns 200", r.status_code == 200)
    data = r.json()
    sheet = data.get("sheet_json", {})
    check("7.1b Sheet has stats", "stats" in sheet, str(sheet.keys()))
    check("7.1c Sheet has skills", "skills" in sheet)
test("Sheet read", t_sheet_read)

# ── 7.3 Dice endpoint — simple roll (no character) ───────────────────────
def t_dice_simple():
    r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "d20"}, timeout=5)
    check("7.2a POST /gm/dice d20 returns 200", r.status_code == 200)
    data = r.json()
    check("7.2b Simple roll has 'total'", "total" in data, str(data))
    check("7.2c Total in range 1-20", 1 <= data.get("total", 0) <= 20)
test("Dice simple", t_dice_simple)

# ── 7.4 Dice endpoint — with character + roll_key (modifier wiring) ───────
def t_dice_with_modifiers():
    payload = {
        "dice": "d20",
        "character_id": CHARACTER_ID,
        "roll_key": "athletics",
        "dc": 12,
    }
    r = requests.post(f"{BASE}/api/gm/dice", json=payload, timeout=5)
    check("7.3a POST /gm/dice with character_id returns 200", r.status_code == 200)
    data = r.json()
    check("7.3b Has 'breakdown'", "breakdown" in data, str(data.get("breakdown")))
    bd = data.get("breakdown", {})
    check("7.3c breakdown.stat == STR", bd.get("stat") == "STR", f"got: {bd.get('stat')}")
    check("7.3d Has stat_modifier", "stat_modifier" in bd)
    check("7.3e Has skill_rank", "skill_rank" in bd)
    check("7.3f Has proficiency_bonus", "proficiency_bonus" in bd)
    check("7.3g Has 'success' field (DC check)", "success" in data, str(data.get("success")))
    check("7.3h success is bool", isinstance(data.get("success"), bool))
test("Dice with modifiers", t_dice_with_modifiers)

# ── 7.5 Proficiency bonus logic ───────────────────────────────────────────
def t_proficiency():
    # athletics skill_rank = 2 on Aldric → proficiency = 0
    payload = {"dice": "d20", "character_id": CHARACTER_ID, "roll_key": "athletics"}
    r = requests.post(f"{BASE}/api/gm/dice", json=payload, timeout=5)
    data = r.json()
    bd = data.get("breakdown", {})
    rank = bd.get("skill_rank", -1)
    prof = bd.get("proficiency_bonus", -1)
    check("7.4a athletics rank=2 → proficiency_bonus=0", rank == 2 and prof == 0,
          f"rank={rank}, prof={prof}")

    # melee_attack rank = 2 → also 0
    payload2 = {"dice": "d20", "character_id": CHARACTER_ID, "roll_key": "melee_attack"}
    r2 = requests.post(f"{BASE}/api/gm/dice", json=payload2, timeout=5)
    data2 = r2.json()
    bd2 = data2.get("breakdown", {})
    check("7.4b melee_attack rank=2 → proficiency_bonus=0",
          bd2.get("proficiency_bonus") == 0, str(bd2))
test("Proficiency bonus", t_proficiency)

# ── 7.6 Alias normalization ───────────────────────────────────────────────
def t_aliases():
    aliases = [
        ("attack", "STR"),
        ("str_save", "STR"),
        ("con_save", "CON"),
        ("dex_save", "DEX"),
    ]
    for alias, expected_stat in aliases:
        payload = {"dice": "d20", "character_id": CHARACTER_ID, "roll_key": alias}
        r = requests.post(f"{BASE}/api/gm/dice", json=payload, timeout=5)
        data = r.json()
        bd = data.get("breakdown", {})
        check(f"7.5 alias '{alias}' → stat {expected_stat}",
              bd.get("stat") == expected_stat,
              f"got: {bd.get('stat')}, breakdown={bd}")
test("Alias normalization", t_aliases)

# ── 7.7 /roll command via turns endpoint ─────────────────────────────────
def t_roll_command():
    payload = {
        "character_id": CHARACTER_ID,
        "text": "/roll athletics 15",
        "system": "fantasy",
    }
    r = requests.post(
        f"{BASE}/api/campaigns/{CAMPAIGN_ID}/turns",
        json=payload, timeout=30
    )
    check("7.6a /roll via turns returns 200", r.status_code == 200, r.text[:120])
    if r.status_code == 200:
        data = r.json()
        route = data.get("route", "")
        check("7.6b route is 'narrative' (not command)", route == "narrative",
              f"route={route}")
test("Roll command → narrative", t_roll_command)

# ── 7.8 /roll dice alias ──────────────────────────────────────────────────
def t_roll_dice_alias():
    payload = {
        "character_id": CHARACTER_ID,
        "text": "/roll d20",
        "system": "fantasy",
    }
    r = requests.post(
        f"{BASE}/api/campaigns/{CAMPAIGN_ID}/turns",
        json=payload, timeout=30
    )
    check("7.7 /roll d20 returns 200 (raw dice alias)", r.status_code == 200, r.text[:80])
test("Roll d20 alias", t_roll_dice_alias)

# ── 7.9 Unknown roll key graceful handling ────────────────────────────────
def t_unknown_key():
    payload = {
        "dice": "d20",
        "character_id": CHARACTER_ID,
        "roll_key": "flying_unicorn_skill",
    }
    r = requests.post(f"{BASE}/api/gm/dice", json=payload, timeout=5)
    # Should either 200 (fallback) or 422/400 (validation) — NOT 500
    check("7.8 Unknown roll_key does NOT crash (no 500)", r.status_code != 500,
          f"status={r.status_code}")
test("Unknown key graceful", t_unknown_key)

# ── Summary ───────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'='*40}")
print(f"Results: {passed}/{total} passed")
if passed == total:
    print("\033[92m🎉 All tests passed! Phase 7 complete.\033[0m")
else:
    failed = total - passed
    print(f"\033[91m{failed} test(s) failed — check output above.\033[0m")
print("="*40)
