#!/usr/bin/env python3
"""
AI-GM Backend Test Suite
Testuje wszystkie endpointy API na http://localhost:8000
Uruchom: python3 test_backend.py
"""

import json
import sys
import requests

BASE = "http://localhost:8000"
PASS = "\033[92m\u2713\033[0m"
FAIL = "\033[91m\u2717\033[0m"

results = {"pass": 0, "fail": 0}

def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS} {name}")
        results["pass"] += 1
    else:
        print(f"  {FAIL} {name}  [{detail}]")
        results["fail"] += 1

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

campaign_id = None
character_id = None
turn_id = None

# ======================================================
section("1. HEALTH & INFO")
# ======================================================

r = requests.get(f"{BASE}/")
check("GET /  -> status ok", r.status_code == 200 and r.json().get("status") == "ok")

r = requests.get(f"{BASE}/api/health")
check("GET /api/health -> ok", r.status_code == 200)

r = requests.get(f"{BASE}/api/models")
check("GET /api/models -> lista modeli", r.status_code == 200 and isinstance(r.json(), (list, dict)))

# ======================================================
section("2. CAMPAIGNS")
# ======================================================

r = requests.get(f"{BASE}/api/campaigns")
check("GET /api/campaigns -> lista", r.status_code == 200 and isinstance(r.json(), list))

r = requests.post(f"{BASE}/api/campaigns", json={"title": "Test Campaign", "system_id": "fantasy"})
check("POST /api/campaigns -> 201 created", r.status_code in (200, 201))
if r.status_code in (200, 201):
    campaign_id = r.json().get("id")
    check("  campaign_id w odpowiedzi", campaign_id is not None)

if campaign_id:
    r = requests.get(f"{BASE}/api/campaigns/{campaign_id}")
    check(f"GET /api/campaigns/{campaign_id} -> dane kampanii", r.status_code == 200)

    r = requests.patch(f"{BASE}/api/campaigns/{campaign_id}", json={"title": "Updated Campaign"})
    check(f"PATCH /api/campaigns/{campaign_id} -> zmiana tytulu", r.status_code == 200)

    r = requests.post(f"{BASE}/api/campaigns", json={"title": "", "system_id": "fantasy"})
    check("POST /api/campaigns pusty title -> blad walidacji", r.status_code in (400, 422))

    r = requests.post(f"{BASE}/api/campaigns", json={"title": "X", "system_id": "nieznany"})
    check("POST /api/campaigns nieznany system -> blad", r.status_code in (400, 422))

# ======================================================
section("3. CHARACTERS")
# ======================================================

if campaign_id:
    r = requests.get(f"{BASE}/api/campaigns/{campaign_id}/characters")
    check("GET /api/campaigns/{id}/characters -> lista", r.status_code == 200)

    r = requests.post(f"{BASE}/api/characters", json={
        "campaign_id": campaign_id,
        "name": "Aldric Test",
        "system_id": "fantasy",
        "archetype": "warrior"
    })
    check("POST /api/characters -> nowa postac", r.status_code in (200, 201))
    if r.status_code in (200, 201):
        character_id = r.json().get("id")
        check("  character_id w odpowiedzi", character_id is not None)

if character_id:
    r = requests.get(f"{BASE}/api/characters/{character_id}")
    check(f"GET /api/characters/{character_id} -> dane postaci", r.status_code == 200)

    r = requests.get(f"{BASE}/api/characters/{character_id}/sheet")
    check(f"GET /api/characters/{character_id}/sheet -> sheet_json", r.status_code == 200)
    if r.status_code == 200:
        sheet = r.json().get("sheet_json", {})
        check("  sheet_json zawiera stats", "stats" in sheet)
        check("  sheet_json zawiera current_hp", "current_hp" in sheet)
        check("  sheet_json zawiera skills", "skills" in sheet)

    r = requests.patch(f"{BASE}/api/characters/{character_id}/sheet",
        json={"sheet_json": {"current_hp": 5}})
    check("PATCH /characters/{id}/sheet current_hp=5", r.status_code == 200)
    if r.status_code == 200:
        check("  current_hp zapisany jako 5",
            r.json().get("sheet_json", {}).get("current_hp") == 5)

    r = requests.patch(f"{BASE}/api/characters/{character_id}/sheet",
        json={"sheet_json": {"current_hp": 0}})
    check("PATCH sheet current_hp=0 (martwy)", r.status_code == 200)

    r = requests.patch(f"{BASE}/api/characters/{character_id}",
        json={"name": "Aldric Renamed"})
    check("PATCH /api/characters/{id} -> zmiana nazwy", r.status_code == 200)

    r = requests.get(f"{BASE}/api/characters/99999/sheet")
    check("GET nieistniejaca postac -> 404", r.status_code == 404)

# ======================================================
section("4. DICE ROLLS")
# ======================================================

r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "d20"})
check("POST /api/gm/dice d20 -> total 1-20", r.status_code == 200 and 1 <= r.json().get("total", 0) <= 20)

r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "2d6"})
check("POST /api/gm/dice 2d6 -> total 2-12", r.status_code == 200 and 2 <= r.json().get("total", 0) <= 12)

r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "d20+3"})
check("POST /api/gm/dice d20+3 -> total 4-23", r.status_code == 200 and 4 <= r.json().get("total", 0) <= 23)

r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "d100"})
check("POST /api/gm/dice d100 -> total 1-100", r.status_code == 200 and 1 <= r.json().get("total", 0) <= 100)

r = requests.post(f"{BASE}/api/gm/dice", json={"dice": "zlyformat"})
check("POST /api/gm/dice niepoprawny format -> 400", r.status_code == 400)

if character_id:
    r = requests.post(f"{BASE}/api/gm/dice", json={
        "dice": "d20", "character_id": character_id,
        "roll_key": "athletics", "dc": 15
    })
    check("POST dice + character_id + roll_key athletics + dc", r.status_code == 200)
    if r.status_code == 200:
        d = r.json()
        check("  odpowiedz zawiera breakdown", "breakdown" in d)
        check("  odpowiedz zawiera success (bool)", "success" in d)
        check("  breakdown.stat_modifier istnieje", "stat_modifier" in d.get("breakdown", {}))

    r = requests.post(f"{BASE}/api/gm/dice", json={
        "dice": "d20", "character_id": character_id,
        "roll_key": "melee_attack", "dc": 10
    })
    check("POST dice melee_attack (STR)", r.status_code == 200)

    r = requests.post(f"{BASE}/api/gm/dice", json={
        "dice": "d20", "character_id": character_id,
        "roll_key": "intimidation", "dc": 12
    })
    check("POST dice intimidation (CHA)", r.status_code == 200)

    r = requests.post(f"{BASE}/api/gm/dice", json={
        "dice": "d20", "character_id": character_id,
        "roll_key": "attack", "dc": 14
    })
    check("POST dice alias 'attack' -> melee_attack", r.status_code == 200)

    r = requests.post(f"{BASE}/api/gm/dice", json={
        "dice": "d20", "character_id": 99999, "roll_key": "athletics"
    })
    check("POST dice nieistniejacy character -> 404", r.status_code == 404)

# ======================================================
section("5. TURNS (narracja kampanii)")
# ======================================================

if campaign_id:
    r = requests.get(f"{BASE}/api/campaigns/{campaign_id}/turns")
    check("GET /api/campaigns/{id}/turns -> lista", r.status_code == 200)

    r = requests.post(f"{BASE}/api/campaigns/{campaign_id}/turns", json={
        "player_input": "Wchodzę do tawerny i rozglądam się.",
        "character_id": character_id
    }, timeout=120)
    check("POST /api/campaigns/{id}/turns -> nowa tura (AI call!)",
        r.status_code in (200, 201))
    if r.status_code in (200, 201):
        turn_id = r.json().get("id")
        check("  turn_id w odpowiedzi", turn_id is not None)
        gm_response = r.json().get("gm_response", "")
        check("  gm_response nie jest pusty", len(gm_response) > 0)

if turn_id and campaign_id:
    r = requests.get(f"{BASE}/api/campaigns/{campaign_id}/turns/{turn_id}")
    check(f"GET /api/campaigns/{campaign_id}/turns/{turn_id} -> szczegoly", r.status_code == 200)

# ======================================================
section("6. LEGACY: GAMES API")
# ======================================================

r = requests.get(f"{BASE}/api/games")
check("GET /api/games -> lista (legacy)", r.status_code == 200)

r = requests.post(f"{BASE}/api/games", json={"title": "LegacyGame", "system": "fantasy"})
check("POST /api/games -> nowa gra (legacy)", r.status_code in (200, 201))
legacy_id = r.json().get("id") if r.status_code in (200, 201) else None

if legacy_id:
    r = requests.get(f"{BASE}/api/games/{legacy_id}")
    check(f"GET /api/games/{legacy_id} -> gra + wiadomosci", r.status_code == 200)

r = requests.post(f"{BASE}/api/games", json={"title": "X", "system": "nieznany"})
check("POST /api/games nieznany system -> 400", r.status_code == 400)

# ======================================================
section("PODSUMOWANIE")
# ======================================================
total = results["pass"] + results["fail"]
print(f"\n  Testy: {total}  |  OK: {results['pass']}  |  FAIL: {results['fail']}\n")
if results["fail"] == 0:
    print("  WSZYSTKIE TESTY PRZESZLY!")
else:
    print(f"  UWAGA: {results['fail']} testow NIE przeszlo.")
sys.exit(0 if results["fail"] == 0 else 1)
