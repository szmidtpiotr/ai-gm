#!/usr/bin/env python3
"""Ensure N dedicated multiplayer test users exist, each owning one hero.

MP membership is keyed on campaign_members.user_id and the hero chosen on accept must
belong to that user — so unlike solo smoke (one Demo account) we need DISTINCT accounts.

Creates (idempotent):
  tester_mp1 (warrior), tester_mp2 (scholar), tester_mp3 (rogue), tester_mp4 (warrior)
each with password 'mp_tester_2026' and one [TEST-MP] hero.

Usage:
    setup_mp_users.py --count 3 [--spectator]

Returns JSON:
  {"users": [{"username","user_id","hero_id","archetype","role"}], "ok": true}
  (with --spectator, the last entry has role='spectator' and hero_id=null)
"""
import argparse
import json
import sys

from _mp_common import api_post, admin_token, find_user_id, find_hero_id

PASSWORD = "mp_tester_2026"
ARCHES = ["warrior", "scholar", "rogue", "warrior"]
HERO_NAME = {"warrior": "[TEST-MP] Wojownik", "scholar": "[TEST-MP] Uczony", "rogue": "[TEST-MP] Łotrzyk"}


def ensure_user(token, username, display_name):
    uid = find_user_id(username)
    if uid:
        return uid, False
    status, body = api_post("/api/admin/accounts/create", {
        "username": username,
        "password": PASSWORD,
        "display_name": display_name,
        "is_admin": 0,
    }, token=token, timeout=20)
    if status == 200 and body.get("id"):
        return body["id"], True
    if status == 409:  # race / pre-existing
        uid = find_user_id(username)
        if uid:
            return uid, False
    raise RuntimeError(f"create user {username} failed {status}: {body}")


def ensure_hero(user_id, archetype):
    name = HERO_NAME[archetype]
    hid = find_hero_id(user_id, name)
    if hid:
        return hid, False
    status, body = api_post("/api/characters", {
        "user_id": user_id,
        "name": name,
        "system_id": "fantasy",
        "sheet_json": {"archetype": archetype},
    }, timeout=30)
    if status == 200 and body.get("id"):
        return body["id"], True
    raise RuntimeError(f"create hero for user {user_id} failed {status}: {body}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=2, choices=[2, 3, 4])
    p.add_argument("--spectator", action="store_true",
                   help="add one extra user as a spectator (no hero)")
    args = p.parse_args()

    token = admin_token()
    if not token:
        print(json.dumps({"error": "admin dev-login failed (demo/demo)"}))
        return 2

    out = []
    try:
        for i in range(args.count):
            uname = f"tester_mp{i + 1}"
            arch = ARCHES[i]
            uid, _ = ensure_user(token, uname, f"MP Tester {i + 1}")
            hid, _ = ensure_hero(uid, arch)
            out.append({"username": uname, "user_id": uid, "hero_id": hid,
                        "archetype": arch, "role": "owner" if i == 0 else "player"})
        if args.spectator:
            uname = "tester_mp_spec"
            uid, _ = ensure_user(token, uname, "MP Spectator")
            out.append({"username": uname, "user_id": uid, "hero_id": None,
                        "archetype": None, "role": "spectator"})
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}))
        return 2

    print(json.dumps({"users": out, "password": PASSWORD, "ok": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
