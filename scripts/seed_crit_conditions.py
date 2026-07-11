#!/usr/bin/env python3
"""#1210 — seed 6 warunków ran krytycznych (hit-location) do game_config_conditions.

Krytyk (Nat 20) rzuca lokalizację trafienia (d6) → warunek na trafionym:
  gracz krytuje wroga  → stunned/bleeding(*)/disarmed/hobbled
  wróg krytuje gracza  → dazed/winded/arm_wound/leg_wound

(*) stunned + bleeding istnieją już w katalogu — tu dokładamy tylko brakujące 6.
Mechanika ucieczki (leg_wound -2, hobbled = blokada) czyta te warunki PO KLUCZU
w combat_service.flee_penalty_from_conditions — effect_json niesie tu głównie czas
trwania (expires: duration_rounds:N) i modyfikatory statów foldujące się w silnik (S18).

Idempotentny (ON CONFLICT). Content-as-code: git = źródło prawdy, deploy auto-stosuje.
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

CRIT_CONDITIONS = [
    # ── na WROGU (krytyk gracza) ────────────────────────────────────────────
    {
        "key": "disarmed",
        "label": "Rozbrojony",
        "description": "Broń wytrącona z dłoni — ciosy słabsze. -2 do obrażeń na 3 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "damage_bonus", "value": -2,
                 "expires": "duration_rounds:3"}
            ],
        },
        "auto_remove": "duration_rounds:3",
    },
    {
        "key": "hobbled",
        "label": "Okulawiony",
        "description": "Noga bezużyteczna — nie da się uciec. Blokuje ucieczkę na 3 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "flee_block", "expires": "duration_rounds:3"}
            ],
        },
        "auto_remove": "duration_rounds:3",
    },
    # ── na GRACZU (krytyk wroga) ─────────────────────────────────────────────
    {
        "key": "dazed",
        "label": "Oszołomiony",
        "description": "Cios w głowę zamroczył — traci następną akcję.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "skip_turn", "duration_rounds": 1}
            ],
        },
        "auto_remove": "duration_rounds:1",
    },
    {
        "key": "winded",
        "label": "Bez tchu",
        "description": "Cios w tors wybił powietrze — akcje siłowe słabsze. STR -2 na 2 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "STR", "value": -2,
                 "expires": "duration_rounds:2"}
            ],
        },
        "auto_remove": "duration_rounds:2",
    },
    {
        "key": "arm_wound",
        "label": "Rana ramienia",
        "description": "Rozcięte ramię — ręka słabnie. -1 do ataku na 3 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "static_stat_modifier", "stat": "attack_bonus", "value": -1,
                 "expires": "duration_rounds:3"}
            ],
        },
        "auto_remove": "duration_rounds:3",
    },
    {
        "key": "leg_wound",
        "label": "Rana nogi",
        "description": "Rozcięta noga — ucieczka utrudniona. -2 do rzutu na ucieczkę na 3 rundy.",
        "effect_json": {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "flee_penalty", "value": -2, "expires": "duration_rounds:3"}
            ],
        },
        "auto_remove": "duration_rounds:3",
    },
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        n = 0
        for c in CRIT_CONDITIONS:
            conn.execute(
                """
                INSERT INTO game_config_conditions
                    (key, label, effect_json, description, stackable, auto_remove, is_active)
                VALUES (?, ?, ?, ?, 0, ?, 1)
                ON CONFLICT(key) DO UPDATE SET
                    label = excluded.label,
                    effect_json = excluded.effect_json,
                    description = excluded.description,
                    auto_remove = excluded.auto_remove,
                    is_active = 1,
                    updated_at = datetime('now')
                """,
                (c["key"], c["label"], json.dumps(c["effect_json"], ensure_ascii=False),
                 c["description"], c["auto_remove"]),
            )
            n += 1
        conn.commit()
        print(f"✓ Crit-location conditions seeded: {n}")
        for c in CRIT_CONDITIONS:
            row = conn.execute(
                "SELECT key, label FROM game_config_conditions WHERE key = ?", (c["key"],)
            ).fetchone()
            if row:
                print(f"  {row[0]:12s} → {row[1]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
