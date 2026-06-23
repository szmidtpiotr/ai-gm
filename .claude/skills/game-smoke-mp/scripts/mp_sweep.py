#!/usr/bin/env python3
"""Force-close an expired 'collecting' MP round without waiting the wall-clock timer.

Uses the G30 (#801) test hook svc.force_sweep(now=<injected>) inside the backend container,
then synchronously narrates this campaign's resulting 'narrating' round so the round reaches
'done' deterministically (missing players get [BRAK AKCJI]/[AUTOPILOT] per the absence ladder).

Time is injected at now+offset (default +90s, just past a 1-minute lobby timer) to keep the
blast radius tiny — only rounds already within ~that window of expiry are touched.

Usage (run from .19; shells into .61 + docker exec):
    mp_sweep.py --campaign 42 [--offset-seconds 90]

Returns JSON: {"campaign_id","swept_round_id","round_status","ok":true}
"""
import argparse
import json
import subprocess
import sys

PY_SNIPPET = r'''
import sys, json, sqlite3
sys.path.insert(0, "/app")
from datetime import datetime, timedelta, timezone
import app.services.multiplayer_round_service as svc
from app.core.db_runtime import resolve_db_path

CID = {cid}
OFFSET = {offset}
now = datetime.now(timezone.utc) + timedelta(seconds=OFFSET)
svc.force_sweep(now=now)

conn = sqlite3.connect(resolve_db_path())
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT id, status FROM campaign_rounds WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
    (CID,)).fetchone()
rid = row["id"] if row else None
status = row["status"] if row else None
conn.close()

if rid and status == "narrating":
    try:
        svc.trigger_narration(rid)
    except Exception as e:
        print(json.dumps({{"swept_round_id": rid, "round_status": "narrating",
                           "narration_error": str(e)[:200]}}))
        sys.exit(0)
    conn = sqlite3.connect(resolve_db_path()); conn.row_factory = sqlite3.Row
    r2 = conn.execute("SELECT status FROM campaign_rounds WHERE id=?", (rid,)).fetchone()
    conn.close()
    status = r2["status"] if r2 else status

print(json.dumps({{"swept_round_id": rid, "round_status": status}}))
'''


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", type=int, required=True)
    p.add_argument("--offset-seconds", type=int, default=90)
    args = p.parse_args()

    snippet = PY_SNIPPET.format(cid=args.campaign, offset=args.offset_seconds)
    cmd = [
        "ssh", "claude@192.168.1.61",
        "docker exec -i ai-gm-dev-backend-1 python3 -",
    ]
    res = subprocess.run(cmd, input=snippet, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        print(json.dumps({"error": f"sweep exec failed: {res.stderr[:300] or res.stdout[:300]}"}))
        return 2
    out = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "{}"
    try:
        data = json.loads(out)
    except Exception:
        print(json.dumps({"error": f"non-JSON sweep output: {res.stdout[:300]}"}))
        return 2
    data["campaign_id"] = args.campaign
    data["ok"] = True
    print(json.dumps(data, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
