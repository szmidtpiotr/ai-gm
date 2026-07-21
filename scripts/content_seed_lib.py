#!/usr/bin/env python3
"""Content-as-code library — single source of truth for git-seeded game content.

#1202 CZĘŚĆ A. Extends the world_map_seed.json model (docs/world/, snapshot +
seed scripts, commit = Piotr's approval) to the 27 content tables from #1201.

Imported by:
  * scripts/snapshot_content.py  — DB  -> data/seeds/content/*.json  (run on DEV)
  * scripts/seed_content.py      — JSON -> DB  (run in deploy_*.sh, before healthcheck)
  * scripts/sync_content_dev_to_prod.py — emergency DEV->PROD sync (#1201)
  * backend/tests/test_issue1202_content_seed.py — round-trip + canon-filter safety

Stdlib only (sqlite3, json, os) so it runs on a bare host and inside the PROD
container alike — same constraint as the #1201 sync script.

Design invariants
-----------------
* Column-NAME addressed everywhere (never positional) — immune to schema drift.
* snapshot and apply share ONE canon filter per table, so campaign / gameplay
  rows are never read out to git nor deleted on the target (Wariant 2, #1202).
* apply runs in ONE transaction: any error rolls the whole thing back, the DB is
  never left half-applied. Per-table row counts verified before commit.
"""

import json
import os
import sqlite3

# ── Canonical table list (THE single source; sync imports this) ───────────────
# 26 tabel (#1201 minus legacy npc_locations, skasowane w #1524). Excluded by design: users / characters / campaigns
# (player data), world_hexes (own seed-flow), game_config_meta (env-specific),
# admin_tokens / audit.
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

# ── Wariant 2 (#1202): canon-only tables ──────────────────────────────────────
# npcs and game_locations also hold rows generated at play time. The gameplay
# generator (world_service) stamps review_status='pending_review'; campaign
# locations additionally carry source_campaign_id. The filter below is applied
# to BOTH the snapshot SELECT and the pre-insert DELETE, so any campaign /
# gameplay row on the target is neither exported to git nor deleted on apply.
# #1382/#941 — test-suite pollution (test_*, __test_*, dup_test_*, issue1105_* …) is
# not canon. Klucze z prefiksem numeru issue (`issue1105_gospoda_szlaku_990001105`)
# przeciekły do git mimo filtra na `test_` — stąd wzorzec GLOB 'issue[0-9]*' (#1480).
# Trzymaj ten zestaw wzorców zgodny z JUNK_PREDICATE w scripts/cleanup_test_locations.py.
def _not_junk(col):
    return (
        f"{col} NOT LIKE 'test\\_%' ESCAPE '\\' "
        f"AND {col} NOT LIKE '\\_\\_test%' ESCAPE '\\' "
        f"AND {col} NOT LIKE '%\\_test\\_%' ESCAPE '\\' "
        f"AND {col} NOT GLOB 'issue[0-9]*'"
    )


CANON_FILTERS = {
    # Filtr działa na snapshot SELECT ORAZ na pre-insert DELETE, więc śmieć nigdy nie
    # trafia do gita, a wiersze śmieciowe na targecie nie są ruszane (sprzątanie to
    # osobne zadanie: scripts/cleanup_test_locations.py).
    "game_locations": (
        "source_campaign_id IS NULL "
        "AND (review_status IS NULL OR review_status != 'pending_review') "
        "AND " + _not_junk("key")
    ),
    "npcs": "(review_status IS NULL OR review_status != 'pending_review')",
    # Przypisania wskazują na lokację kluczem — bez filtra do gita trafiał
    # np. location_npc_assignments → test_inn_u31 (#1480).
    "location_npc_assignments": _not_junk("location_key"),
    "location_enemy_assignments": _not_junk("location_key"),
}


def table_columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _order_by(conn, table):
    """Deterministic row order (stable diffs + round-trip identity)."""
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    pk = [r[1] for r in sorted((r for r in info if r[5]), key=lambda r: r[5])]
    cols = pk or ([info[0][1]] if info else [])
    return ", ".join(cols) if cols else "rowid"


def _where(table):
    f = CANON_FILTERS.get(table)
    return f" WHERE {f}" if f else ""


def seed_path(out_dir, table):
    return os.path.join(out_dir, f"{table}.json")


# ── Snapshot: DB -> JSON ──────────────────────────────────────────────────────
def snapshot_all(db_path, out_dir, tables=None):
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    report = {}
    try:
        for t in tables or CONTENT_TABLES:
            cols = table_columns(conn, t)
            if not cols:
                report[t] = None  # table missing — recorded, not fatal
                continue
            collist = ", ".join(cols)
            rows = conn.execute(
                f"SELECT {collist} FROM {t}{_where(t)} ORDER BY {_order_by(conn, t)}"
            ).fetchall()
            data = [{c: r[c] for c in cols} for r in rows]
            with open(seed_path(out_dir, t), "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)
                fh.write("\n")
            report[t] = len(data)
    finally:
        conn.close()
    return report


# ── Apply: JSON -> DB (one transaction) ───────────────────────────────────────
def apply_all(db_path, in_dir, dry_run=False, tables=None):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    plan = []
    problems = []
    for t in tables or CONTENT_TABLES:
        path = seed_path(in_dir, t)
        if not os.path.exists(path):
            problems.append(f"{t}: seed file missing ({path})")
            continue
        db_cols = table_columns(conn, t)
        if not db_cols:
            problems.append(f"{t}: table missing on target DB")
            continue
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        seed_cols = list(rows[0].keys()) if rows else db_cols
        common = [c for c in db_cols if c in seed_cols]
        if not common:
            problems.append(f"{t}: zero common columns")
            continue
        plan.append(
            {
                "table": t,
                "rows": rows,
                "common": common,
                "seed_only": [c for c in seed_cols if c not in db_cols],
                "db_only": [c for c in db_cols if c not in seed_cols],
            }
        )
    if problems:
        return {"ok": False, "problems": problems, "plan": []}

    summary = []
    for p in plan:
        summary.append(
            {
                "table": p["table"],
                "rows": len(p["rows"]),
                "common": len(p["common"]),
                "seed_only": p["seed_only"],
                "db_only": p["db_only"],
                "canon_filtered": p["table"] in CANON_FILTERS,
            }
        )
    if dry_run:
        return {"ok": True, "dry_run": True, "plan": summary}

    try:
        conn.execute("BEGIN")
        for p in plan:
            t, common = p["table"], p["common"]
            conn.execute(f"DELETE FROM {t}{_where(t)}")
            if p["rows"]:
                collist = ", ".join(common)
                ph = ", ".join("?" for _ in common)
                conn.executemany(
                    f"INSERT INTO {t} ({collist}) VALUES ({ph})",
                    [tuple(r.get(c) for c in common) for r in p["rows"]],
                )
        # Verify canon-scoped counts before committing anything.
        for p in plan:
            t = p["table"]
            n_db = conn.execute(f"SELECT count(*) FROM {t}{_where(t)}").fetchone()[0]
            if n_db != len(p["rows"]):
                raise RuntimeError(
                    f"count mismatch {t}: seed={len(p['rows'])} db(canon)={n_db}"
                )
        conn.commit()
        return {"ok": True, "dry_run": False, "plan": summary}
    except Exception as e:  # noqa: BLE001 — rollback + surface
        conn.rollback()
        return {"ok": False, "problems": [f"ROLLED BACK: {e}"], "plan": summary}
    finally:
        conn.close()
