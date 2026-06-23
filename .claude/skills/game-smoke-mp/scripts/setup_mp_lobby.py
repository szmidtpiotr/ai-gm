#!/usr/bin/env python3
"""Create an MP lobby, invite + accept all members, optionally a spectator, and start.

Host = first user (tester_mp1). Timer defaults to 1 minute so force-sweep is cheap to
trigger. Idempotent-ish: if a lobby with the given title already exists for the host it is
reused (and re-started if still 'open').

Usage:
    setup_mp_lobby.py --count 3 [--spectator] [--title "#MP-smoke"] [--timer 1]

Pipe the users JSON from setup_mp_users.py via --users-json, or let this script call it.

Returns JSON:
  {"campaign_id", "host_user_id", "title", "lobby_status",
   "members": [{"username","user_id","hero_id","role","accepted"}],
   "round1_status", "ok": true}
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from _mp_common import api_post, api_get, db_query

HERE = Path(__file__).resolve().parent


def load_users(count, spectator, users_json):
    if users_json:
        return json.loads(users_json)["users"]
    cmd = [sys.executable, str(HERE / "setup_mp_users.py"), "--count", str(count)]
    if spectator:
        cmd.append("--spectator")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"setup_mp_users failed: {res.stdout}{res.stderr}")
    return json.loads(res.stdout)["users"]


def find_existing_lobby(host_id, title):
    safe = title.replace("'", "''")
    rows = db_query(
        f"SELECT id, lobby_status FROM campaigns WHERE title='{safe}' "
        f"AND host_user_id={int(host_id)} AND mode='multiplayer' ORDER BY id DESC LIMIT 1;"
    )
    return (rows[0]["id"], rows[0]["lobby_status"]) if rows else (None, None)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=2, choices=[2, 3, 4])
    p.add_argument("--spectator", action="store_true")
    p.add_argument("--title", default="#MP-smoke")
    p.add_argument("--timer", type=int, default=1, help="round_timer_minutes (default 1)")
    p.add_argument("--users-json", default="")
    args = p.parse_args()

    users = load_users(args.count, args.spectator, args.users_json)
    players = [u for u in users if u["role"] != "spectator"]
    spectators = [u for u in users if u["role"] == "spectator"]
    host = players[0]

    cid, lobby_status = find_existing_lobby(host["user_id"], args.title)
    created = False
    if cid is None:
        status, body = api_post("/api/multiplayer/campaigns", {
            "title": args.title,
            "system_id": "fantasy",
            "round_timer_minutes": args.timer,
            "max_players": max(args.count, 2),
        }, user_id=host["user_id"], timeout=30)
        if status != 200:
            print(json.dumps({"error": f"create lobby failed {status}: {body}"}))
            return 2
        cid = body["campaign_id"]
        lobby_status = "open"
        created = True

    members_out = [{"username": host["username"], "user_id": host["user_id"],
                    "hero_id": host["hero_id"], "role": "owner", "accepted": True}]

    if lobby_status == "open":
        # The host is auto-added as an accepted owner but with NO character_id. Select the
        # host's hero too (accept sets character_id + creates the per-campaign battle state).
        if host.get("hero_id"):
            api_post(f"/api/multiplayer/campaigns/{cid}/accept",
                     {"character_id": host["hero_id"]}, user_id=host["user_id"], timeout=20)

        # Invite + accept everyone else.
        for u in players[1:] + spectators:
            st, b = api_post(f"/api/multiplayer/campaigns/{cid}/invite/username",
                             {"username": u["username"]}, user_id=host["user_id"], timeout=20)
            if st not in (200, 409):
                print(json.dumps({"error": f"invite {u['username']} failed {st}: {b}"}))
                return 2
            accept_body = ({"as_spectator": True} if u["role"] == "spectator"
                           else {"character_id": u["hero_id"]})
            st, b = api_post(f"/api/multiplayer/campaigns/{cid}/accept", accept_body,
                             user_id=u["user_id"], timeout=20)
            accepted = st == 200
            if not accepted:
                print(json.dumps({"error": f"accept {u['username']} failed {st}: {b}"}))
                return 2
            members_out.append({"username": u["username"], "user_id": u["user_id"],
                                "hero_id": u["hero_id"], "role": u["role"], "accepted": True})

        # Start the game (host only).
        st, b = api_post(f"/api/multiplayer/campaigns/{cid}/start", user_id=host["user_id"], timeout=30)
        if st != 200:
            print(json.dumps({"error": f"start failed {st}: {b}"}))
            return 2
        lobby_status = "started"
    else:
        # Already started — rebuild member list from DB.
        rows = db_query(
            "SELECT m.user_id, m.role, m.character_id, u.username "
            "FROM campaign_members m JOIN users u ON u.id=m.user_id "
            f"WHERE m.campaign_id={int(cid)} AND m.status='accepted';"
        )
        members_out = [{"username": r["username"], "user_id": r["user_id"],
                        "hero_id": r["character_id"], "role": r["role"], "accepted": True}
                       for r in rows]

    # Round-1 status as seen by host.
    st, status_body = api_get(f"/api/campaigns/{cid}/round/status", user_id=host["user_id"], timeout=20)

    print(json.dumps({
        "campaign_id": cid,
        "host_user_id": host["user_id"],
        "title": args.title,
        "lobby_status": lobby_status,
        "created": created,
        "members": members_out,
        "round1_status": status_body if st == 200 else {"http": st, "body": status_body},
        "frontend_url": "https://aigm-dev.studio-colorbox.com/",
        "admin_url": "https://aigm-dev.studio-colorbox.com/admin/#campaigns",
        "ok": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
