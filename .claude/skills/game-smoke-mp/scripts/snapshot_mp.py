#!/usr/bin/env python3
"""Read-only MP state dump for checkpoint verification.

Reads run inside the backend container (live WAL) via ssh + `docker exec sqlite3 -json`,
NOT the sshfs mount — WAL commits are not reliably visible through the network mount.

Usage:
    snapshot_mp.py --campaign 42

Returns JSON with: campaign, members, latest_round, round_actions, character_campaign_state,
party_messages (last 20), kick_votes, round_summaries.
"""
import argparse
import json
import sys

from _mp_common import db_query


def safe(sql):
    try:
        return db_query(sql)
    except Exception as e:
        return {"error": str(e)[:160]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", type=int, required=True)
    args = p.parse_args()
    cid = int(args.campaign)

    out = {"campaign_id": cid}
    camp = safe(
        "SELECT id, title, mode, status, host_user_id, lobby_status, max_players, "
        "round_timer_minutes, spectator_policy, quiet_start, quiet_end, team_tz "
        f"FROM campaigns WHERE id={cid};")
    out["campaign"] = camp[0] if isinstance(camp, list) and camp else camp

    out["members"] = safe(
        "SELECT m.user_id, u.username, m.role, m.status, m.character_id, "
        "m.absence_warnings, m.autopilot_consent, m.pending_intro, m.last_seen "
        "FROM campaign_members m LEFT JOIN users u ON u.id=m.user_id "
        f"WHERE m.campaign_id={cid} ORDER BY m.id;")

    latest = safe(
        "SELECT id, round_number, status, deadline, closed_at, "
        "substr(COALESCE(narrative_json,''),1,400) AS narrative_preview, created_at "
        f"FROM campaign_rounds WHERE campaign_id={cid} ORDER BY round_number DESC LIMIT 1;")
    out["latest_round"] = latest[0] if isinstance(latest, list) and latest else None

    if out["latest_round"]:
        rid = int(out["latest_round"]["id"])
        out["round_actions"] = safe(
            "SELECT user_id, character_name, action_text, initiative_roll, "
            "submitted_at, client_action_id FROM campaign_round_actions "
            f"WHERE round_id={rid} ORDER BY initiative_roll DESC;")
    else:
        out["round_actions"] = []

    out["character_campaign_state"] = safe(
        "SELECT character_id, current_hp, max_hp, current_mana, max_mana, "
        "conditions_json, position_json, updated_at FROM character_campaign_state "
        f"WHERE campaign_id={cid};")

    out["party_messages"] = safe(
        "SELECT id, user_id, character_name, message, whisper_to, created_at "
        f"FROM party_messages WHERE campaign_id={cid} ORDER BY id DESC LIMIT 20;")

    out["kick_votes"] = safe(
        "SELECT target_user_id, voter_user_id, created_at FROM campaign_kick_votes "
        f"WHERE campaign_id={cid};")

    out["round_summaries"] = safe(
        "SELECT layer, round_from, round_to, substr(text,1,120) AS text_preview, created_at "
        f"FROM campaign_round_summaries WHERE campaign_id={cid} ORDER BY id;")

    out["ok"] = True
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
