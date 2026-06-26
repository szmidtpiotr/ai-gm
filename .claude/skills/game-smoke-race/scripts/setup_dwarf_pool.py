#!/usr/bin/env python3
"""Ensure [TEST] Krasnolud hero pool exists for user_id=1 (Demo account).
Creates missing dwarf heroes via API. Safe to re-run (idempotent).

Returns JSON:
  {"warrior_id": int, "scholar_id": int, "ok": true}
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

DWARF_HEROES = [
    {"name": "[TEST] Krasnolud Wojownik", "archetype": "warrior", "key": "warrior"},
    {"name": "[TEST] Krasnolud Uczony",   "archetype": "scholar", "key": "scholar"},
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

    for hero in DWARF_HEROES:
        row = db.execute(
            "SELECT id FROM characters WHERE user_id=? AND name=? LIMIT 1",
            (USER_ID, hero["name"]),
        ).fetchone()

        if row:
            result[hero["key"] + "_id"] = row["id"]
            print(f"[reuse] {hero['name']} id={row['id']}", file=sys.stderr)
            continue

        status, body = api_post(
            "/characters",
            {
                "user_id": USER_ID,
                "name": hero["name"],
                "race": "dwarf",
                "language": "pl",
                "system_id": "fantasy",
                "sheet_json": {"archetype": hero["archetype"]},
            },
        )
        if status not in (200, 201) or "id" not in body:
            print(json.dumps({"error": f"Failed to create {hero['name']}: HTTP {status} {body}"}))
            return 1

        result[hero["key"] + "_id"] = body["id"]
        print(f"[created] {hero['name']} id={body['id']}", file=sys.stderr)

    db.close()
    result["ok"] = True
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
