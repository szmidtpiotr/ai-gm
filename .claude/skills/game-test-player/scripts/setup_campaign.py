#!/usr/bin/env python3
"""Setup a test campaign for issue verification on Demo account (user_id=1).

Usage:
    setup_campaign.py --issue 378 --archetype warrior

- Finds or creates campaign "#378" for user_id=1
- Assigns [TEST] Wojownik/Uczony/Łotrzyk based on archetype
- Sends __AI_GM_OPEN if campaign has no turns yet
- Leaves everything intact (never deletes)

Returns JSON:
{
  "campaign_id": int,
  "character_id": int,
  "archetype": str,
  "hero_name": str,
  "existed": bool,
  "turns_before": int,
  "opening_narrative": str|null,
  "frontend_url": str,
  "admin_url": str,
  "ok": true
}
"""
import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

DB_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")
API_BASE = "http://192.168.1.61:8100"
USER_ID = 1

HERO_NAMES = {
    "warrior": "[TEST] Wojownik",
    "scholar": "[TEST] Uczony",
    "rogue":   "[TEST] Łotrzyk",
}


def api_post(path: str, payload: dict, timeout: int = 90) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode(errors="replace"))
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--archetype", choices=["warrior", "scholar", "rogue"], default="warrior")
    args = p.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_PATH}"}))
        return 2

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    title = f"#{args.issue}"

    # Find hero from pool
    hero_name = HERO_NAMES[args.archetype]
    hero = db.execute(
        "SELECT id FROM characters WHERE user_id=? AND name=? LIMIT 1",
        (USER_ID, hero_name),
    ).fetchone()
    if not hero:
        print(json.dumps({
            "error": f"Hero '{hero_name}' not found. Run setup_hero_pool.py first.",
        }))
        return 2
    character_id = hero["id"]

    result: dict = {
        "character_id": character_id,
        "archetype": args.archetype,
        "hero_name": hero_name,
    }

    # Find or create campaign
    camp = db.execute(
        "SELECT id FROM campaigns WHERE title=? AND owner_user_id=? LIMIT 1",
        (title, USER_ID),
    ).fetchone()

    if camp:
        campaign_id = camp["id"]
        result["campaign_id"] = campaign_id
        result["existed"] = True
        print(f"[reuse] campaign '{title}' → id {campaign_id}", file=sys.stderr)
    else:
        status, body = api_post("/api/campaigns", {
            "title": title,
            "system_id": "fantasy",
            "model_id": "default",
            "owner_user_id": USER_ID,
            "language": "pl",
            "mode": "solo",
            "status": "active",
        }, timeout=30)
        if status != 200:
            print(json.dumps({"error": f"Campaign create failed {status}: {body}"}))
            return 2
        campaign_id = body["id"]
        result["campaign_id"] = campaign_id
        result["existed"] = False
        print(f"[created] campaign '{title}' → id {campaign_id}", file=sys.stderr)

    # Assign hero to campaign
    status, body = api_post(f"/api/characters/{character_id}/assign-campaign", {
        "campaign_id": campaign_id,
        "user_id": USER_ID,
    }, timeout=30)
    if status != 200:
        print(json.dumps({"error": f"Assign hero failed {status}: {body}"}))
        return 2
    print(f"[assigned] {hero_name} (id {character_id}) → campaign {campaign_id}", file=sys.stderr)

    # Re-open DB (might have been modified by API calls above)
    db.close()
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    # Check existing turns
    turns_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM campaign_turns WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()
    turns_before = turns_row["cnt"]
    result["turns_before"] = turns_before

    if turns_before == 0:
        # Send opening scene
        print("[opening] sending __AI_GM_OPEN…", file=sys.stderr)
        status, body = api_post(f"/api/campaigns/{campaign_id}/turns", {
            "character_id": character_id,
            "text": "__AI_GM_OPEN",
        }, timeout=120)
        if status != 200:
            print(json.dumps({"error": f"Open turn failed {status}: {body}"}))
            return 2

        prose = body.get("prose") or ""
        try:
            data = json.loads(prose)
            narrative = data.get("narrative", prose) if isinstance(data, dict) else prose
        except Exception:
            narrative = prose
        opening = narrative[:500] + ("…" if len(narrative) > 500 else "")
        result["opening_narrative"] = opening
        print(f"[opening] got {len(narrative)} chars", file=sys.stderr)
    else:
        result["opening_narrative"] = None
        print(f"[skip opening] campaign has {turns_before} turns already", file=sys.stderr)

    result["ok"] = True
    result["frontend_url"] = "https://aigm-dev.studio-colorbox.com/"
    result["admin_url"] = "https://aigm-dev.studio-colorbox.com/admin/#campaigns"
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
