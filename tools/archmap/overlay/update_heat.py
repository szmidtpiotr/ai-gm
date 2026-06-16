#!/usr/bin/env python3
"""
Write the 'heat' registry of map-overlay.json from real runtime data.

Reads heat-source.json (event/call type -> node id), runs aggregate COUNT/AVG
queries over the DB via ssh+docker+sqlite3, and writes per-node {calls, errors,
p95_ms} into map-overlay.json. The 'heat' chip in the map then colours each node
by traffic (thicker border = more calls, red border = has errors).

NOW: works against combat_turns (exists today) -> proves the wiring.
PHASE 11: flip the _phase11 sources on in heat-source.json once game_events and
llm_call_log exist. No code change needed.

Usage:
    python3 update_heat.py            # query DEV DB over ssh, write overlay
    python3 update_heat.py --dry-run
    python3 update_heat.py --local /path/to/ai_gm.db   # query a local copy

Safety: read-only SELECTs. NEVER opens the SQLite file over an sshfs mount
(corruption risk) — always goes through ssh + docker exec on the DB host.
"""
import json, subprocess, sys, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "heat-source.json"
OUT = HERE / "map-overlay.json"

def run_sql(cfg, sql, local):
    if local:
        cmd = ["sqlite3", local, sql]
    else:
        db = cfg["db"]
        inner = f'sqlite3 -readonly {db["db_path"]} "{sql}"'
        cmd = ["ssh", db["ssh_host"], "docker", "exec", db["container"], "sh", "-c", inner]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(f"[skip] {sql[:60]}... -> {res.stderr.strip()}\n")
        return []
    rows = []
    for line in res.stdout.strip().splitlines():
        if line:
            rows.append(line.split("|"))
    return rows

def table_exists(cfg, table, local):
    rows = run_sql(cfg, f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';", local)
    return bool(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local", help="path to a local sqlite copy (testing)")
    args = ap.parse_args()

    cfg = json.loads(SRC.read_text())
    heat = {}   # node -> {calls, errors, p95_ms}

    for src in cfg["sources"]:
        if src.get("_phase11") and not table_exists(cfg, src["table"], args.local):
            continue
        if not table_exists(cfg, src["table"], args.local):
            continue
        tcol, tbl = src["type_col"], src["table"]
        win = src.get("window_days", 30)
        errp = src.get("error_predicate", "0")
        lat = src.get("latency_col")
        sql = (f"SELECT {tcol}, COUNT(*), SUM(CASE WHEN {errp} THEN 1 ELSE 0 END)"
               + (f", AVG({lat})" if lat else "")
               + f" FROM {tbl} WHERE created_at >= datetime('now','-{win} days')"
               f" GROUP BY {tcol};")
        for row in run_sql(cfg, sql, args.local):
            etype = row[0]
            calls = int(row[1] or 0); errs = int(row[2] or 0)
            p95 = int(float(row[3])) if lat and len(row) > 3 and row[3] else 0
            node = src["map"].get(etype) or src["map"].get("*")
            if not node:
                continue
            h = heat.setdefault(node, {"calls": 0, "errors": 0, "p95_ms": 0})
            h["calls"] += calls; h["errors"] += errs
            h["p95_ms"] = max(h["p95_ms"], p95)

    overlay = {}
    if OUT.exists():
        try: overlay = json.loads(OUT.read_text())
        except Exception: pass
    overlay.setdefault("bugs", {}); overlay.setdefault("fixes", {})
    overlay["heat"] = heat
    overlay["heat_generated_at"] = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%MZ"], capture_output=True, text=True).stdout.strip()

    print(f"heat nodes: {len(heat)} · " + ", ".join(f"{k}={v['calls']}" for k, v in heat.items()))
    if args.dry_run:
        print(json.dumps(heat, indent=2, ensure_ascii=False))
    else:
        OUT.write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote heat into {OUT}")

if __name__ == "__main__":
    main()
