#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.effect_json_migration import normalize_flat_effect_to_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill missing game_config_items.effect_json rows using legacy effect_* columns.",
    )
    parser.add_argument(
        "--db",
        default="/data/ai_gm.db",
        help="Path to the SQLite database (default: /data/ai_gm.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates back to the database instead of only showing the proposed changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log every row processed (default: only summary and conversion notes).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        conn = sqlite3.connect(args.db)
    except sqlite3.Error as exc:
        sys.exit(f"Failed to open database {args.db}: {exc}")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT key, effect_type, effect_dice, effect_bonus, effect_target, effect_json
            FROM game_config_items
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        sys.exit(f"Failed to query game_config_items: {exc}")

    total = len(rows)
    existing = 0
    converted = 0
    skipped = 0

    for row in rows:
        key = str(row["key"])
        current_json = row["effect_json"]
        if current_json and str(current_json).strip():
            existing += 1
            continue
        normalized = normalize_flat_effect_to_json(
            row["effect_type"],
            row["effect_dice"],
            row["effect_bonus"],
            row["effect_target"],
        )
        if not normalized:
            skipped += 1
            if args.verbose:
                print(f"Skipped {key}: cannot infer effect_json from {row['effect_type']!r}")
            continue
        converted += 1
        print(f"{'APPLY' if args.apply else 'DRY'}: {key} -> {normalized}")
        if args.apply:
            conn.execute(
                """
                UPDATE game_config_items
                SET effect_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE key = ?
                """,
                (normalized, key),
            )
    if args.apply:
        conn.commit()
    print(
        f"Processed {total} rows: {converted} filled, {existing} already set, {skipped} skipped "
        f"(use --verbose for detail)."
    )


if __name__ == "__main__":
    main()
