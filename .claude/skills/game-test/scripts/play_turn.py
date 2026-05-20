#!/usr/bin/env python3
"""POST a single player turn to the DEV backend and return a structured result.

Usage:
    play_turn.py --campaign <id> --character <id> --message "wracam do karczmy" [--narr-chars 250]

Pre-flight: snapshots last turn id + current_location_id + max location id.
Post-flight: same, then diffs.

JSON on stdout:
{
  "turn_id": int,
  "turn_number": int,
  "route": "narrative"|"skill_test"|...,
  "narrative": "...",  # first N chars, with LOCATION_BLOCKED stripped
  "location_blocked_tags": ["target_key_not_in_session_graph", ...],
  "location_intent": {...} | null,
  "new_locations": [{id, key, label, parent_key, biome, ai_generated}, ...],
  "session_location_change": {"from": {...} | null, "to": {...} | null},
  "error": null | "...",
  "http_status": 200,
  "elapsed_seconds": 12.4
}
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DB_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")
API_BASE = "http://192.168.1.61:8100"
LOCATION_BLOCKED_RE = re.compile(r"\s*\[LOCATION_BLOCKED:\s*([^\]]+)\]")


def fetch_one(db, sql, params=()):
    r = db.execute(sql, params).fetchone()
    return dict(r) if r else None


def fetch_loc(db, loc_id):
    if loc_id is None:
        return None
    return fetch_one(
        db,
        "SELECT id, key, label, parent_key FROM game_locations WHERE id=?",
        (loc_id,),
    )


def snapshot_min(campaign_id: int) -> dict:
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    last_turn = fetch_one(
        db,
        "SELECT id FROM campaign_turns WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    )
    session = fetch_one(
        db,
        "SELECT id, current_location_id FROM game_sessions WHERE campaign_id=? "
        "ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    )
    max_loc = fetch_one(db, "SELECT COALESCE(MAX(id), 0) AS max_id FROM game_locations")
    cur_loc = fetch_loc(db, session["current_location_id"] if session else None)
    return {
        "last_turn_id": last_turn["id"] if last_turn else 0,
        "session_id": session["id"] if session else None,
        "current_location_id": session["current_location_id"] if session else None,
        "current_location": cur_loc,
        "max_loc_id": max_loc["max_id"],
    }


def post_turn(campaign_id: int, character_id: int, message: str, timeout: int):
    payload = json.dumps({"character_id": character_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/api/campaigns/{campaign_id}/turns",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body, time.time() - t0, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), time.time() - t0, str(e)
    except Exception as e:
        return None, "", time.time() - t0, str(e)


def parse_response_prose(prose: str):
    """Backend returns prose as a JSON string with narrative + location_intent.

    Strip LOCATION_BLOCKED tags from narrative and surface them separately.
    """
    narrative = ""
    location_intent = None
    blocked_tags = []
    try:
        raw = prose.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, dict):
            narrative = data.get("narrative") or ""
            location_intent = data.get("location_intent")
    except Exception:
        narrative = prose

    for m in LOCATION_BLOCKED_RE.finditer(narrative):
        blocked_tags.append(m.group(1).strip())
    narrative = LOCATION_BLOCKED_RE.sub("", narrative).strip()
    return narrative, location_intent, blocked_tags


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", type=int, required=True)
    p.add_argument("--character", type=int, required=True)
    p.add_argument("--message", type=str, required=True)
    p.add_argument("--narr-chars", type=int, default=250)
    p.add_argument("--timeout", type=int, default=90)
    args = p.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_PATH}"}))
        return 2

    before = snapshot_min(args.campaign)
    status, body, elapsed, err = post_turn(args.campaign, args.character, args.message, args.timeout)

    result = {
        "http_status": status,
        "elapsed_seconds": round(elapsed, 2),
        "error": err,
        "turn_id": None,
        "turn_number": None,
        "route": None,
        "narrative": "",
        "location_blocked_tags": [],
        "location_intent": None,
        "new_locations": [],
        "session_location_change": {"from": before["current_location"], "to": None},
    }

    if status != 200 or err:
        try:
            err_data = json.loads(body) if body else {}
            result["error"] = result["error"] or err_data.get("detail") or body[:300]
        except Exception:
            result["error"] = result["error"] or body[:300]
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0

    try:
        resp = json.loads(body)
    except Exception:
        result["error"] = "non-JSON response"
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0

    result["turn_id"] = resp.get("id")
    result["turn_number"] = resp.get("turn_number")
    result["route"] = resp.get("route")

    narrative, intent, blocked = parse_response_prose(resp.get("prose") or "")
    if args.narr_chars > 0 and len(narrative) > args.narr_chars:
        narrative = narrative[: args.narr_chars] + "…"
    result["narrative"] = narrative
    result["location_intent"] = intent
    result["location_blocked_tags"] = blocked

    # Brief retry: the session UPDATE can land microseconds after the HTTP response
    # returns. Poll up to ~1.5s for the location pointer to either change or stabilize.
    after = snapshot_min(args.campaign)
    if (
        after["current_location_id"] == before["current_location_id"]
        and result["location_intent"]
        and isinstance(result["location_intent"], dict)
        and result["location_intent"].get("action") in ("move", "create")
    ):
        for _ in range(6):
            time.sleep(0.25)
            after = snapshot_min(args.campaign)
            if after["current_location_id"] != before["current_location_id"]:
                break

    result["session_location_change"]["to"] = after["current_location"]
    if (
        before["current_location_id"] == after["current_location_id"]
        and before["current_location"] == after["current_location"]
    ):
        result["session_location_change"] = {"unchanged": True, "at": after["current_location"]}

    if after["max_loc_id"] > before["max_loc_id"]:
        db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT id, key, label, parent_id, parent_key, biome, location_subtype, "
            "ai_generated, source_campaign_id, is_active FROM game_locations "
            "WHERE id > ? ORDER BY id ASC",
            (before["max_loc_id"],),
        ).fetchall()
        result["new_locations"] = [dict(r) for r in rows]

    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
