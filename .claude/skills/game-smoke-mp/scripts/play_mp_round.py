#!/usr/bin/env python3
"""Play one multiplayer round end-to-end.

For each active (non-spectator) member: POST /campaigns/{id}/round/submit with a unique
client_action_id. Then poll /round/status until 'done' (or timeout), and fetch
/round/narration per player token (private notes/roll_facts are user-scoped).

Usage:
    play_mp_round.py --campaign 42 --members-json '<members array>' \
        --actions '["Idę na północ szukać śladów", "Osłaniam drużynę"]' \
        [--absent 1055] [--withdraw 1056] [--wait 150] [--narration-only]

- --absent USER_ID   : that member does NOT submit (test sweep / autopilot). Repeatable.
- --withdraw USER_ID : that member submits then immediately withdraws (G24). Repeatable.
- --narration-only   : skip submit; just poll+fetch (use after mp_sweep.py).
- --actions          : JSON list mapped to active members in order; cycles if shorter.

Returns JSON:
  {"campaign_id","round_status","submitted":[user_ids],"withdrawn":[user_ids],
   "absent":[user_ids],"narration_done":bool,
   "narration_by_player":{user_id:{narrative,player_note,roll_facts}}, "ok":true}
"""
import argparse
import json
import sys
import time
import uuid

from _mp_common import api_post, api_get, api_delete, db_query

DEFAULT_ACTIONS = [
    "Rozglądam się po okolicy i ruszam naprzód, szukając śladów.",
    "Osłaniam drużynę i wypatruję zagrożeń.",
    "Skradam się przodem, sprawdzając pułapki.",
    "Trzymam straż z tyłu, gotów reagować.",
]


def char_name(character_id):
    if character_id is None:
        return None
    rows = db_query(f"SELECT name FROM characters WHERE id={int(character_id)};")
    return rows[0]["name"] if rows else f"Hero{character_id}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", type=int, required=True)
    p.add_argument("--members-json", required=True)
    p.add_argument("--actions", default="")
    p.add_argument("--absent", type=int, action="append", default=[])
    p.add_argument("--withdraw", type=int, action="append", default=[])
    p.add_argument("--wait", type=int, default=150)
    p.add_argument("--narration-only", action="store_true")
    args = p.parse_args()

    members = json.loads(args.members_json)
    players = [m for m in members if m.get("role") != "spectator"]
    actions = json.loads(args.actions) if args.actions else DEFAULT_ACTIONS

    cid = args.campaign
    submitted, withdrawn, absent, blocked = [], [], [], []

    if not args.narration_only:
        for i, m in enumerate(players):
            uid = m["user_id"]
            if uid in args.absent:
                absent.append(uid)
                continue
            text = actions[i % len(actions)]
            cname = char_name(m.get("hero_id"))
            st, b = api_post(f"/api/campaigns/{cid}/round/submit", {
                "action_text": text,
                "character_id": m.get("hero_id"),
                "character_name": cname,
                "client_action_id": str(uuid.uuid4()),
            }, user_id=uid, timeout=30)
            if st != 200:
                print(json.dumps({"error": f"submit user {uid} failed {st}: {b}"}))
                return 2
            # The endpoint returns HTTP 200 even on a logical refusal (e.g. round_closed):
            # the body carries an `error` field. Surface it instead of counting a phantom submit.
            if b.get("error"):
                blocked.append({"user_id": uid, "error": b["error"],
                                "detail": b.get("detail"), "round_status": b.get("status")})
                continue
            submitted.append(uid)
            if uid in args.withdraw:
                stw, bw = api_delete(f"/api/campaigns/{cid}/round/action", user_id=uid, timeout=20)
                if stw == 200:
                    withdrawn.append(uid)
                    submitted.remove(uid)

    # Poll status until done or timeout.
    poll_uid = players[0]["user_id"]
    deadline = time.time() + args.wait
    status_body = {}
    done = False
    # A round that took no submissions (everyone blocked/absent) and isn't being swept
    # has nothing new to narrate — any 'done' we'd see is the stale prior round.
    if not args.narration_only and not submitted:
        print(json.dumps({
            "campaign_id": cid, "round_status": {}, "submitted": submitted,
            "withdrawn": withdrawn, "absent": absent, "blocked": blocked,
            "narration_done": False, "narration_by_player": {},
            "note": "no actions accepted this round (see blocked) — round did not open",
            "ok": True,
        }, ensure_ascii=False, default=str))
        return 0
    while time.time() < deadline:
        st, status_body = api_get(f"/api/campaigns/{cid}/round/status", user_id=poll_uid, timeout=20)
        if st == 200 and status_body.get("status") == "done":
            done = True
            break
        time.sleep(3)

    narration_by_player = {}
    if done:
        for m in players:
            uid = m["user_id"]
            st, nb = api_get(f"/api/campaigns/{cid}/round/narration", user_id=uid, timeout=30)
            if st == 200:
                narration_by_player[str(uid)] = {
                    "narrative": (nb.get("narrative") or "")[:600],
                    "player_note": nb.get("player_note") or nb.get("player_notes"),
                    "roll_facts": nb.get("roll_facts"),
                }

    print(json.dumps({
        "campaign_id": cid,
        "round_status": status_body,
        "submitted": submitted,
        "withdrawn": withdrawn,
        "absent": absent,
        "blocked": blocked,
        "narration_done": done,
        "narration_by_player": narration_by_player,
        "ok": True,
    }, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
