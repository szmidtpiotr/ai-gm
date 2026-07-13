#!/usr/bin/env python3
"""Issue #1377 — normalizacja XP + reband vampire_master (residua #1376).

Diagnoza:
  • xp_award niespójny: goblin xp=3 (bug), drift legacy vs nowy content (skeleton 60
    vs zbieg 28 przy tym samym threat), bossy niemonotoniczne (demon_lord 1800 >
    dragon 1500 mimo niższego threat).
  • vampire_master (elite threat 102.5, sufit tieru) pada od lvl 6 — za mocny na 6-7.

Ten seed:
  1. Ustawia xp_award = round(threat × mult_tieru) dla wszystkich global/permanent.
     mult z median obecnych ratio xp/threat (weak 1.4 / std 3.4 / elite 5.3 / boss 8.2)
     → aggregate ~-2.8% (ekonomia awansów zachowana, tylko outliery wyrównane).
  2. Reband vampire_master L6-9 → L8-10.

threat = encounter_service.enemy_threat_value (hp + 2×dpr + atk + 0.5×armor).
Wartości = STARTING VALUES (Numbers Policy), strojlne w Sandboxie. Idempotentny.

Run inside dev backend container:
    docker exec -i ai-gm-dev-backend-1 python3 - < scripts/seed_xp_normalize_1377.py
"""
from __future__ import annotations

import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# mult z median ratio xp/threat per tier (patrz diagnoza) — net-neutral
XP_MULT = {"weak": 1.4, "standard": 3.4, "elite": 5.3, "boss": 8.2}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    from app.services.encounter_service import enemy_threat_value

    rows = conn.execute(
        """SELECT * FROM game_config_enemies
           WHERE world_scope='global' AND review_status='permanent' AND is_active=1"""
    ).fetchall()

    changed = 0
    for r in rows:
        d = dict(r)
        mult = XP_MULT.get(d["tier"])
        if not mult:
            continue
        new_xp = int(round(enemy_threat_value(d) * mult))
        if new_xp != (d["xp_award"] or 0):
            conn.execute(
                "UPDATE game_config_enemies SET xp_award=?, updated_at=datetime('now') WHERE key=?",
                (new_xp, d["key"]),
            )
            changed += 1

    # Reband vampire_master (sufit elit → wysokie poziomy)
    conn.execute(
        "UPDATE game_config_enemies SET min_level=8, max_level=10, updated_at=datetime('now') "
        "WHERE key='vampire_master'"
    )

    conn.commit()
    print(f"OK: xp znormalizowany na {changed} wrogach; vampire_master reband L8-10 (#1377).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
