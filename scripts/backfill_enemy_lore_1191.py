#!/usr/bin/env python3
"""#1191 E6 — backfill game_config_enemies.lore_text via the content LLM.

Generates 2–4 sentences of Polish dark-fantasy flavour per enemy that has no
lore_text yet, and writes it back. Uses the content LLM profile (gpt-5.4, not
the gameplay model — gemma chokes on prose). Idempotent: skips enemies that
already have lore unless --force.

Run INSIDE the backend container (needs app.services + /data/ai_gm.db):
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/backfill_enemy_lore_1191.py --limit 5
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/backfill_enemy_lore_1191.py          # all
"""
import argparse
import sqlite3
import sys

DB = "/data/ai_gm.db"

SYS = (
    "Jesteś twórcą klimatu do mrocznego fantasy RPG osadzonego w Kresach. "
    "Piszesz zwięzły, sugestywny opis bestii do bestiariusza gracza. "
    "Zwróć WYŁĄCZNIE 2-4 zdania po polsku — bez nagłówków, bez statystyk, "
    "bez formatowania. Ton: groza i legenda, nie karta mechaniczna."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max enemies (0 = all)")
    ap.add_argument("--force", action="store_true", help="overwrite existing lore")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from app.services.llm_service import (
        content_llm_enabled,
        resolve_content_llm_config,
        generate_chat,
    )

    cfg = resolve_content_llm_config() if content_llm_enabled() else None
    print(f"content LLM: {cfg.get('model') if cfg else 'DEFAULT (content profile off)'}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    where = "" if args.force else "WHERE lore_text IS NULL OR lore_text = ''"
    rows = conn.execute(
        f"SELECT key, label, description FROM game_config_enemies {where} ORDER BY key"
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} enemy(ies) to process")

    ok = err = 0
    for i, r in enumerate(rows, 1):
        label = r["label"] or r["key"]
        desc = (r["description"] or "").strip()
        user = f"Bestia: {label}."
        if desc:
            user += f" Znane fakty: {desc[:200]}"
        print(f"[{i}/{len(rows)}] {r['key']} — {label}")
        if args.dry_run:
            continue
        try:
            lore = generate_chat(
                messages=[{"role": "system", "content": SYS},
                          {"role": "user", "content": user}],
                llm_config=cfg,
                call_type="bestiary_lore",
            ).strip()
            if not lore:
                raise ValueError("empty lore")
            conn.execute(
                "UPDATE game_config_enemies SET lore_text = ? WHERE key = ?",
                (lore, r["key"]),
            )
            conn.commit()
            ok += 1
            print(f"      → {lore[:90]}…")
        except Exception as e:
            err += 1
            print(f"      ERROR: {e}", file=sys.stderr)
    print(f"Done. OK={ok} errors={err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
