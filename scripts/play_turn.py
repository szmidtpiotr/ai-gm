#!/usr/bin/env python3
"""Submit a player turn or drive a combat round to the game."""
import requests
import json
import sys
import random

BASE_URL = "http://192.168.1.61:8100"

def play_turn(campaign_id, character_id, message):
    """POST narrative turn, return result."""
    url = f"{BASE_URL}/api/campaigns/{campaign_id}/turns"
    body = {"character_id": character_id, "text": message}
    try:
        resp = requests.post(url, json=body, timeout=100)
        resp.raise_for_status()
        result = resp.json()
        prose = (result.get("prose") or "")[:300]
        return {
            "turn_id": result.get("turn_id"),
            "turn_number": result.get("turn_number"),
            "route": result.get("route"),
            "prose_start": prose,
            "result": result.get("result"),
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_combat_state(campaign_id):
    resp = requests.get(f"{BASE_URL}/api/campaigns/{campaign_id}/combat", timeout=10)
    data = resp.json()
    if data.get("active"):
        return data["combat"]
    return None


def resolve_player_attack(campaign_id, roll=None, raw_d20=None):
    """Player attacks — uses rolled result or rolls randomly."""
    if raw_d20 is None:
        raw_d20 = random.randint(1, 20)
    if roll is None:
        # Warrior STR +3, melee_attack rank 1 → +4 total
        roll = raw_d20 + 4
    body = {"roll_result": roll, "raw_d20": raw_d20, "attacker": "player"}
    resp = requests.post(
        f"{BASE_URL}/api/campaigns/{campaign_id}/combat/resolve-attack",
        json=body, timeout=20
    )
    if resp.status_code == 400:
        return {"error": resp.json().get("detail"), "skipped": True}
    resp.raise_for_status()
    result = resp.json()
    result["raw_d20"] = raw_d20
    result["roll"] = roll
    return result


def resolve_enemy_turn(campaign_id):
    """Trigger enemy attack."""
    resp = requests.post(
        f"{BASE_URL}/api/campaigns/{campaign_id}/combat/enemy-turn",
        timeout=20
    )
    if resp.status_code == 400:
        return {"error": resp.json().get("detail"), "skipped": True}
    resp.raise_for_status()
    return resp.json()


def advance_combat_turn(campaign_id):
    """Advance combat to next actor."""
    combat = get_combat_state(campaign_id)
    if not combat:
        return "ended"
    current = combat.get("current_turn", "")
    if current == "player":
        return resolve_player_attack(campaign_id)
    else:
        return resolve_enemy_turn(campaign_id)


def drive_combat_to_end(campaign_id, max_rounds=15):
    """Drive full combat loop until ended. Returns summary."""
    print(f"  [combat] Starting combat driver for campaign {campaign_id}")
    rounds_done = 0
    log = []

    for _ in range(max_rounds * 4):  # max_rounds * 2 actors per round
        combat = get_combat_state(campaign_id)
        if not combat or combat.get("status") != "active":
            print(f"  [combat] Ended after {rounds_done} rounds")
            break

        current = combat.get("current_turn", "")
        rnd = combat.get("round", 1)
        if rnd > rounds_done:
            rounds_done = rnd

        if current == "player":
            res = resolve_player_attack(campaign_id)
            log_line = f"  Round {rnd} PLAYER: d20={res.get('raw_d20')} total={res.get('roll')} hit={res.get('hit')} dmg={res.get('damage')} enemy_hp={res.get('target_hp_remaining')}"
            print(log_line)
            log.append(log_line)
            if res.get("skipped"):
                print(f"    SKIP: {res.get('error')}")
                break
        else:
            res = resolve_enemy_turn(campaign_id)
            log_line = f"  Round {rnd} ENEMY: hit={res.get('hit')} dmg={res.get('damage')} player_hp={res.get('player_hp_remaining')}"
            print(log_line)
            log.append(log_line)
            if res.get("skipped"):
                print(f"    SKIP: {res.get('error')}")
                break

    final = get_combat_state(campaign_id)
    ended = not final or final.get("status") != "active"
    return {"ended": ended, "rounds": rounds_done, "log": log, "final_state": final}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: play_turn.py <campaign_id> <character_id> <message>")
        print("    OR play_turn.py combat <campaign_id>")
        sys.exit(1)

    if sys.argv[1] == "combat":
        campaign_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1115
        result = drive_combat_to_end(campaign_id)
        print(json.dumps(result, indent=2))
    else:
        campaign_id = int(sys.argv[1])
        character_id = int(sys.argv[2])
        message = sys.argv[3]
        result = play_turn(campaign_id, character_id, message)
        print(json.dumps(result, indent=2))
