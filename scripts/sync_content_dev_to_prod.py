#!/usr/bin/env python3
"""Schema-drift-safe game-content sync: DEV snapshot -> PROD database.

Runs INSIDE the PROD backend container (python3 + sqlite3 stdlib only):

    docker exec ai-gm-backend-1 python3 /tmp/sync_content_dev_to_prod.py \
        /tmp/dev_snapshot.db [--dry-run]

Why this exists (#1201, post-incident 2026-07-04): the old sync piped
`sqlite3 .mode insert` output (positional VALUES) into the PROD db. Two fatal
flaws: (1) DEV and PROD schemas drift (different column counts AND different
column ORDER for same-named columns), so positional inserts either fail or —
worse — silently write values into the wrong columns; (2) the sqlite3 CLI does
not stop on statement errors, so the DELETEs committed even when every INSERT
failed, wiping PROD content tables.

This script instead:
  * ATTACHes the DEV snapshot and copies each table via
    INSERT INTO main.t (<common cols>) SELECT <common cols> FROM dev.t
    — column-NAME-addressed, so order and extra columns never matter;
  * reports drift (columns present on only one side) instead of tripping on it;
  * wraps the WHOLE sync in one transaction — any error rolls back everything,
    PROD is never left half-synced;
  * verifies row counts per table before committing.

Tables NOT synced (by design): users/characters/campaigns (player data),
world_hexes (PROD owns its bigger map), game_config_meta (env-specific),
admin_tokens/audit. Same exclusion list as the /prod-update skill.
"""

import os
import sqlite3
import sys

PROD_DB = "/data/ai_gm.db"

# Single source of truth for the table list = content_seed_lib (#1202). Import it
# if copied alongside this script; otherwise fall back to an embedded copy so this
# emergency tool always runs standalone. A backend test asserts the lists match.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from content_seed_lib import CONTENT_TABLES  # noqa: F401
except ImportError:
    CONTENT_TABLES = [
        "game_config_stats",
        "game_config_skills",
        "game_config_dc",
        "game_config_conditions",
        "game_config_xp_rewards",
        "game_config_xp_awards",
        "game_config_archetypes",
        "game_config_weapons",
        "game_config_spells",
        "game_config_items",
        "game_config_consumables",
        "game_config_loot_tables",
        "game_config_enemies",
        "game_config_loot_entries",
        "game_config_visual",
        "game_config_affixes",
        "game_config_hidden_traits",
        "game_config_riddles",
        "game_config_services",
        "game_config_skill_risk_categories",
        "game_dungeons",
        "campaign_templates",
        "npcs",
        "game_locations",
        "location_enemy_assignments",
        "location_npc_assignments",
    ]


def cols(conn, schema, table):
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return [r[1] for r in rows]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    dev_snapshot = sys.argv[1]
    dry_run = "--dry-run" in sys.argv[2:]

    conn = sqlite3.connect(PROD_DB)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(f"ATTACH DATABASE '{dev_snapshot}' AS dev")

    plan = []
    problems = []
    for t in CONTENT_TABLES:
        dev_cols = cols(conn, "dev", t)
        prod_cols = cols(conn, "main", t)
        if not dev_cols:
            problems.append(f"{t}: missing in DEV snapshot")
            continue
        if not prod_cols:
            problems.append(f"{t}: missing on PROD (deploy/migrations not run?)")
            continue
        common = [c for c in dev_cols if c in prod_cols]
        if not common:
            problems.append(f"{t}: zero common columns")
            continue
        plan.append(
            {
                "table": t,
                "common": common,
                "dev_only": [c for c in dev_cols if c not in prod_cols],
                "prod_only": [c for c in prod_cols if c not in dev_cols],
            }
        )

    if problems:
        for p in problems:
            print(f"ABORT: {p}")
        sys.exit(1)

    print(f"{'DRY-RUN' if dry_run else 'SYNC'} — {len(plan)} tables")
    for p in plan:
        drift = ""
        if p["dev_only"]:
            drift += f"  [DEV-only cols skipped: {','.join(p['dev_only'])}]"
        if p["prod_only"]:
            drift += f"  [PROD-only cols keep defaults: {','.join(p['prod_only'])}]"
        n = conn.execute(f"SELECT count(*) FROM dev.{p['table']}").fetchone()[0]
        print(f"  {p['table']}: {n} rows, {len(p['common'])} common cols{drift}")

    if dry_run:
        print("DRY-RUN OK — nothing written.")
        return

    try:
        conn.execute("BEGIN")
        for p in plan:
            t, collist = p["table"], ", ".join(p["common"])
            conn.execute(f"DELETE FROM main.{t}")
            conn.execute(
                f"INSERT INTO main.{t} ({collist}) SELECT {collist} FROM dev.{t}"
            )
        # Verify counts before committing anything.
        for p in plan:
            t = p["table"]
            nd = conn.execute(f"SELECT count(*) FROM dev.{t}").fetchone()[0]
            np_ = conn.execute(f"SELECT count(*) FROM main.{t}").fetchone()[0]
            if nd != np_:
                raise RuntimeError(f"count mismatch {t}: dev={nd} prod={np_}")
        conn.commit()
        print("COMMIT OK — all tables synced and verified.")
    except Exception as e:
        conn.rollback()
        print(f"ROLLED BACK — nothing changed on PROD. Reason: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
