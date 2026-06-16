#!/usr/bin/env python3
"""
Drift guard (generic): compare the files a map claims to cover (node-map.json)
against the files that actually exist in the configured scope. Tells you when the
map skeleton has gone stale so you can ask an agent to add/remove nodes.

Project-agnostic: reads `scope_globs` and the path->node map from node-map.json.
Repo root is auto-detected by walking up to the nearest `.git`.

node-map.json must contain:
    { "scope_globs": ["src/services/*.py", ...], "paths": { "rel/path": "node-id", ... } }

It does NOT edit the map. It only reports:
  - NEW   files in scope with no node  -> map is missing them
  - GONE  paths in node-map.json with no file  -> node points at a deleted file

Usage:
    python3 drift_check.py                 # human report, exit 0
    python3 drift_check.py --ci            # exit 1 on any drift (cron/CI alert)
    python3 drift_check.py --node-map P    # explicit node-map.json path
"""
import json, sys, argparse
from pathlib import Path

def find_repo_root(start):
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return p.parents[2] if len(p.parents) >= 3 else p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--node-map", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    node_map_path = Path(args.node_map) if args.node_map else (here / "node-map.json")
    if not node_map_path.exists():
        # also try alongside an overlay/ dir next to the engine
        alt = here.parent / "overlay" / "node-map.json"
        node_map_path = alt if alt.exists() else node_map_path
    if not node_map_path.exists():
        sys.exit(f"node-map.json not found (looked at {node_map_path})")

    cfg = json.loads(node_map_path.read_text())
    globs = cfg.get("scope_globs", [])
    mapped = set(cfg.get("paths", {}).keys())
    if not globs:
        print("No scope_globs in node-map.json — add them to enable drift checking.")
        return 0

    repo = find_repo_root(node_map_path)
    on_disk = set()
    for g in globs:
        for p in repo.glob(g):
            if p.is_file():
                on_disk.add(str(p.relative_to(repo)))

    new = sorted(on_disk - mapped)
    gone = sorted(p for p in mapped if not (repo / p).exists())

    if not new and not gone:
        print(f"OK — map skeleton matches the scope on disk ({repo}).")
        return 0

    if new:
        print(f"\nNEW ({len(new)}) — files in scope with no node on the map:")
        for p in new: print(f"  + {p}")
        print('  -> tell an agent: "update the map — new files"')
    if gone:
        print(f"\nGONE ({len(gone)}) — node paths whose file no longer exists:")
        for p in gone: print(f"  - {p}")
        print('  -> tell an agent: "update the map — removed files"')
    print()
    return 1 if args.ci else 0

if __name__ == "__main__":
    sys.exit(main())
