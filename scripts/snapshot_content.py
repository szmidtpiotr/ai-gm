#!/usr/bin/env python3
"""Snapshot game-content tables from a DB into git seeds (#1202 CZĘŚĆ A).

Run on DEV after editing content in the admin panel; the committed JSON files
become the source of truth (commit = Piotr's approval, same model as
snapshot_world_map.py). Runs on the HOST against the bind-mounted sqlite file.

    python3 scripts/snapshot_content.py \
        [--db data-dev/ai_gm.db] [--out data/seeds/content]

Canon-only tables (npcs, game_locations) export only authored rows — campaign /
gameplay-generated rows stay out of git (Wariant 2).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_seed_lib import snapshot_all  # noqa: E402

DEFAULT_DB = "data-dev/ai_gm.db"
DEFAULT_OUT = "data/seeds/content"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ABORT: DB not found: {args.db}", file=sys.stderr)
        sys.exit(2)

    report = snapshot_all(args.db, args.out)
    total = 0
    missing = []
    for t, n in report.items():
        if n is None:
            missing.append(t)
            print(f"  {t}: MISSING on DB (skipped)")
        else:
            total += n
            print(f"  {t}: {n} rows")
    print(f"snapshot OK — {total} rows across {len(report) - len(missing)} tables -> {args.out}")
    if missing:
        print(f"WARNING: {len(missing)} tables missing on DB: {', '.join(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
