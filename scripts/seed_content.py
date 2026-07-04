#!/usr/bin/env python3
"""Apply git content seeds into a DB (#1202 CZĘŚĆ A).

Wired into deploy_*.sh (after migrations, before healthcheck). Full per-table
replace from data/seeds/content/*.json, column-NAME addressed, ONE transaction
with rollback + per-table count verification. Runs on the HOST against the
bind-mounted sqlite file.

    python3 scripts/seed_content.py --dry-run [--db data/ai_gm.db] [--seeds data/seeds/content]
    python3 scripts/seed_content.py --apply   [--db data/ai_gm.db] [--seeds data/seeds/content]

Canon-only tables (npcs, game_locations): DELETE + re-insert touch only authored
rows — campaign / gameplay rows on the target are never deleted (Wariant 2).
Take a DB backup before --apply (deploy does this automatically).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_seed_lib import apply_all  # noqa: E402

DEFAULT_DB = "data/ai_gm.db"
DEFAULT_SEEDS = "data/seeds/content"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--seeds", default=DEFAULT_SEEDS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ABORT: DB not found: {args.db}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isdir(args.seeds):
        print(f"ABORT: seeds dir not found: {args.seeds}", file=sys.stderr)
        sys.exit(2)

    res = apply_all(args.db, args.seeds, dry_run=args.dry_run)
    for p in res.get("plan", []):
        drift = ""
        if p["seed_only"]:
            drift += f"  [seed-only cols skipped: {','.join(p['seed_only'])}]"
        if p["db_only"]:
            drift += f"  [db-only cols keep defaults: {','.join(p['db_only'])}]"
        canon = " (canon-only)" if p["canon_filtered"] else ""
        print(f"  {p['table']}: {p['rows']} rows, {p['common']} common cols{canon}{drift}")

    if not res["ok"]:
        for prob in res.get("problems", []):
            print(f"ABORT: {prob}", file=sys.stderr)
        sys.exit(1)

    if res.get("dry_run"):
        print("DRY-RUN OK — nothing written.")
    else:
        print("APPLY OK — all tables seeded and verified.")


if __name__ == "__main__":
    main()
