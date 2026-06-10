#!/usr/bin/env python3
"""Ensure [TEST] hero pool exists for user_id=1 (Demo account).
Creates missing heroes. Safe to re-run (idempotent).

Returns JSON:
  {"warrior_id": int, "scholar_id": int, "rogue_id": int, "ok": true}
"""
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

DB_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")
API_BASE = "http://192.168.1.61:8100"
USER_ID = 1

HEROES = [
    {"name": "[TEST] Wojownik", "archetype": "warrior", "key": "warrior"},
    {"name": "[TEST] Uczony",   "archetype": "scholar", "key": "scholar"},
    {"name": "[TEST] Łotrzyk",  "archetype": "rogue",   "key": "rogue"},
]


def api_post(path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode(errors="replace"))
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_PATH}"}))
        return 2

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    result: dict = {}

    for hero in HEROES:
        row = db.execute(
            "SELECT id FROM characters WHERE user_id=? AND name=? LIMIT 1",
            (USER_ID, hero["name"]),
        ).fetchone()

        if row:
            result[hero["key"] + "_id"] = row["id"]
            result[hero["key"] + "_created"] = False
        else:
            status, body = api_post("/api/characters", {
                "user_id": USER_ID,
                "name": hero["name"],
                "system_id": "fantasy",
                "sheet_json": {"archetype": hero["archetype"]},
            })
            if status != 200:
                print(json.dumps({"error": f"Create '{hero['name']}' failed {status}: {body}"}))
                return 2
            result[hero["key"] + "_id"] = body["id"]
            result[hero["key"] + "_created"] = True
            print(f"[created] {hero['name']} → id {body['id']}", file=sys.stderr)

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
