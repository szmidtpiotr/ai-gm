#!/usr/bin/env python3
"""Quick snapshot of campaign state for baseline + comparison."""
import json
import sys
import subprocess

def run_query(query):
    """Run SQL query via docker exec."""
    import base64
    q_b64 = base64.b64encode(query.encode()).decode()
    cmd = f"ssh claude@192.168.1.61 \"docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \\\"$(echo {q_b64} | base64 -d)\\\"\""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Query failed: {result.stderr}")
    return result.stdout.strip()

def get_snapshot(campaign_id):
    # Character HP/stats (pipe-delimited)
    char_output = run_query(f"SELECT id, name, gold_gp, sheet_json FROM characters WHERE campaign_id = {campaign_id}")
    lines = char_output.split('\n')
    char_parts = lines[0].split('|') if lines else []

    if len(char_parts) < 4:
        raise Exception(f"No character found for campaign {campaign_id}")

    char_id = int(char_parts[0])
    char_name = char_parts[1]
    char_gold = int(char_parts[2])
    sheet = json.loads(char_parts[3] or "{}")

    # Session location
    sess_output = run_query(f"SELECT current_location_id, session_flags FROM game_sessions WHERE campaign_id = {campaign_id}")
    sess_parts = sess_output.split('|')
    current_loc_id = sess_parts[0] if sess_parts[0] else None
    flags = json.loads(sess_parts[1] or "{}")

    # Location count
    loc_count = int(run_query(f"SELECT COUNT(*) FROM game_locations WHERE source_campaign_id = {campaign_id} AND is_active = 1"))

    # Turn count
    turn_count = int(run_query(f"SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = {campaign_id}"))

    # Active combat
    combat_output = run_query(f"SELECT id FROM active_combat WHERE campaign_id = {campaign_id} AND status = 'active' LIMIT 1")
    has_combat = bool(combat_output)

    result = {
        "char_id": char_id,
        "char_name": char_name,
        "char_hp": sheet.get("current_hp"),
        "char_hp_max": sheet.get("max_hp"),
        "char_gold": char_gold,
        "current_hex": flags.get("current_hex"),
        "current_location_id": current_loc_id,
        "locations_created": loc_count,
        "turns_played": turn_count,
        "active_combat": has_combat,
    }
    return result

if __name__ == "__main__":
    campaign_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1115
    snap = get_snapshot(campaign_id)
    print(json.dumps(snap, indent=2))
