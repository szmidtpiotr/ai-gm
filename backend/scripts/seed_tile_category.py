"""Generic dungeon tile-category seeder (Option B — content as data).

One code path for EVERY category (krypta, jaskinie, goblin_tunnels, ...). The
mechanics live in the engine and never change; a category is pure DATA fed as a
JSON file. Replaces the per-category bespoke scripts (seed_l14_krypta.py,
seed_l17_jaskinie.py).

JSON shape (see data/seeds/tile_categories/*.json):
  {
    "category": { "key", "label", "description", "style_modifier",
                  "system_prompt", "sort_order", "is_active" },
    "riddles":  [ { "key","text","answer","answer_alts","hints","difficulty","theme" }, ... ],
    "tiles":    [ { "label","doors","enemies","items","riddle_key","is_boss","image_gen_prompt" }, ... ]
  }
  - doors:   list of cardinals, e.g. ["N","S"]
  - enemies: list of { "enemy_key", "count" }
  - items:   list of { "type": "chest" } (or {"item_key": ...})
  - answer_alts / hints: list (serialized to JSON for the DB)

Idempotent: skips category / riddles / tiles that already exist (by key / label).
Re-running after appending NEW tiles to the JSON inserts only the new ones — this
is how you grow a category (e.g. +50 tiles) without touching existing rows.

Run inside dev backend container (docker cp the script + JSON first if not baked):
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_tile_category.py /app/scripts/jaskinie.json
"""

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def seed(conn: sqlite3.Connection, data: dict) -> None:
    cat = data["category"]
    riddles = data.get("riddles", [])
    tiles = data["tiles"]

    # ── 1. Category ───────────────────────────────────────────────────────────
    existing = conn.execute(
        "SELECT key FROM dungeon_tile_categories WHERE key = ?", (cat["key"],)
    ).fetchone()
    if existing:
        # Category row exists — refresh its prompt fields (base_prompt/style_modifier/
        # system_prompt) so editing the JSON and re-seeding propagates. Tiles still
        # skip-if-exists below (content is append-only).
        conn.execute(
            """UPDATE dungeon_tile_categories
               SET label = ?, description = ?, style_modifier = ?, system_prompt = ?,
                   sort_order = ?, base_prompt = ?
               WHERE key = ?""",
            (
                cat["label"], cat.get("description", ""), cat["style_modifier"],
                cat["system_prompt"], cat.get("sort_order", 100),
                cat.get("base_prompt"), cat["key"],
            ),
        )
        print(f"[OK] Category '{cat['key']}' updated (prompts refreshed)")
    else:
        conn.execute(
            """INSERT INTO dungeon_tile_categories
               (key, label, description, style_modifier, system_prompt, sort_order, is_active, base_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cat["key"], cat["label"], cat.get("description", ""),
                cat["style_modifier"], cat["system_prompt"],
                cat.get("sort_order", 100), cat.get("is_active", 1),
                cat.get("base_prompt"),
            ),
        )
        print(f"[OK] Category '{cat['key']}' created")

    # ── 2. Riddles ────────────────────────────────────────────────────────────
    for r in riddles:
        existing = conn.execute(
            "SELECT key FROM game_config_riddles WHERE key = ?", (r["key"],)
        ).fetchone()
        if existing:
            print(f"[SKIP] Riddle '{r['key']}' already exists")
            continue
        conn.execute(
            """INSERT INTO game_config_riddles
               (key, text, answer, answer_alts, hints, difficulty, theme, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                r["key"], r["text"], r["answer"],
                json.dumps(r.get("answer_alts", []), ensure_ascii=False),
                json.dumps(r.get("hints", []), ensure_ascii=False),
                r.get("difficulty", 2), r.get("theme", "general"),
            ),
        )
        print(f"[OK] Riddle '{r['key']}' created")

    # ── 3. Tiles ──────────────────────────────────────────────────────────────
    inserted = skipped = 0
    for t in tiles:
        existing = conn.execute(
            "SELECT id FROM dungeon_tiles WHERE category_key = ? AND label = ?",
            (cat["key"], t["label"]),
        ).fetchone()
        if existing:
            print(f"[SKIP] Tile '{t['label']}' already exists")
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO dungeon_tiles
               (category_key, label, image_gen_prompt, doors_json, enemies_json,
                items_json, riddle_key, is_boss_tile, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                cat["key"], t["label"], t["image_gen_prompt"],
                json.dumps(t["doors"]),
                json.dumps(t.get("enemies", [])),
                json.dumps(t.get("items", [])),
                t.get("riddle_key"),
                1 if t.get("is_boss") else 0,
            ),
        )
        print(f"[OK] Tile '{t['label']}' (doors={t['doors']}, boss={1 if t.get('is_boss') else 0})")
        inserted += 1

    conn.commit()
    print(f"\nDone [{cat['key']}]: {inserted} tiles inserted, {skipped} skipped.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generic dungeon tile-category seeder")
    ap.add_argument("json_path", help="Path to category JSON file")
    args = ap.parse_args()

    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    with _conn() as conn:
        seed(conn, data)


if __name__ == "__main__":
    main()
