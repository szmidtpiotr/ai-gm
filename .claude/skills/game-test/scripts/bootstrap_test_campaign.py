#!/usr/bin/env python3
"""One-time bootstrap: create the [TEST] Tester campaign + character via API.

Safe to re-run: skips creation if they already exist.
Prints one JSON line on stdout.
"""
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

DB_LOCAL_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")
API_BASE = "http://192.168.1.61:8100"


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
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    if not DB_LOCAL_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_LOCAL_PATH}"}))
        return 2

    db = sqlite3.connect(f"file:{DB_LOCAL_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    user = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if not user:
        print(json.dumps({"error": "No users in DB. Create a user account first."}))
        return 2
    user_id = user["id"]

    # Check existing
    camp = db.execute(
        "SELECT id FROM campaigns WHERE title LIKE '[TEST]%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    char = None
    if camp:
        char = db.execute(
            "SELECT id FROM characters WHERE campaign_id=? AND name LIKE '[TEST]%' LIMIT 1",
            (camp["id"],),
        ).fetchone()

    result = {"user_id": user_id}

    if not camp:
        status, body = api_post("/api/campaigns", {
            "title": "[TEST] Tester",
            "system_id": "fantasy",
            "model_id": "default",
            "owner_user_id": user_id,
            "language": "pl",
            "mode": "solo",
            "status": "active",
        })
        if status != 200:
            print(json.dumps({"error": f"Campaign create failed {status}: {body}"}))
            return 2
        result["campaign_id"] = body["id"]
        result["campaign_created"] = True
    else:
        result["campaign_id"] = camp["id"]
        result["campaign_created"] = False

    if not char:
        status, body = api_post("/api/characters", {
            "user_id": user_id,
            "name": "[TEST] Tester",
            "system_id": "fantasy",
            "sheet_json": {"archetype": "warrior"},
        })
        if status != 200:
            print(json.dumps({"error": f"Character create failed {status}: {body}"}))
            return 2
        result["character_id"] = body["id"]
        result["character_created"] = True

        # Assign to campaign
        status, body = api_post(f"/api/characters/{result['character_id']}/assign-campaign", {
            "campaign_id": result["campaign_id"],
            "user_id": user_id,
        })
        if status != 200:
            print(json.dumps({"error": f"Assign failed {status}: {body}"}))
            return 2
        result["assigned"] = True
    else:
        result["character_id"] = char["id"]
        result["character_created"] = False

    result["ok"] = True
    result["next"] = "Run reset_test_campaign.py to verify bootstrap, then /game-test is ready."
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
