#!/usr/bin/env python3
"""CB-7 (#1490) — smaczki Czarnoboru do katalogu: próchno świetlne + dziegieć.

Idempotentny INSERT OR REPLACE do game_config_items / game_config_consumables +
oznaczenie pochodni jako otwartego ognia (light_kind=open_flame). Kolumny spoza
tabeli są pomijane (fallback do defaultów schematu).

    docker cp scripts/seed_czarnobor_smaczki.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_smaczki.py
    docker exec ai-gm-dev-backend-1 python /app/seed_czarnobor_smaczki.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys


def _cols(db: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}


def _upsert(db: sqlite3.Connection, table: str, row: dict, valid: set[str]) -> None:
    row = {k: v for k, v in row.items() if k in valid}
    keys = list(row)
    placeholders = ",".join(["?"] * len(keys))
    collist = ",".join(keys)
    db.execute(
        f"INSERT OR REPLACE INTO {table} ({collist}) VALUES ({placeholders})",
        [row[k] for k in keys],
    )


PROCHNO = {
    "key": "prochno_swietlne",
    "label": "Próchno świetlne",
    "item_type": "gear",
    "description": (
        "Garść zbutwiałego czarnodrzewu, tlącego się zimnym, sinym światłem. "
        "Rozjaśnia mrok boru nie gorzej niż pochodnia, lecz — inaczej niż otwarty "
        "ogień — nie wabi tego, co w mroku czeka."
    ),
    "value_gp": 5,
    "price_gp": 5,
    "weight_kg": 0.2,
    "charges": 1,
    "rarity": 2,
    "effect_json": json.dumps(
        {"effect_category": "light_source", "light_kind": "cold", "attracts_encounters": False}
    ),
    "allowed_classes": json.dumps(["warrior", "ranger", "scholar"]),
    "armor_coverage": "torso",
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "czarnobor",
    "created_by": "seed",
    "no_trade": 0,
    "note": "Zimne światło — nie podbija szansy spotkań w nocnym marszu (w przeciwieństwie do pochodni).",
}

DZIEGIEC = {
    "key": "dziegiec_czarnodrzewny",
    "label": "Dziegieć czarnodrzewny",
    "description": (
        "Cuchnące, smoliste smarowidło pędzone z kory czarnodrzewu w Smolarni na "
        "Palach. Wtarte w skórę i sprzęt zabija ludzki zapach — leśne bestie mijają "
        "cię obojętnie, a skradanie idzie łatwiej przez cały dzień gry."
    ),
    "effect_type": "misc",
    "effect_target": "self",
    "weight_kg": 0.3,
    "charges": 1,
    "base_price": 20,
    "price_gp": 20,
    "rarity": 2,
    "approved": 1,
    "min_level": 1,
    "location_tags": "czarnobor",
    "effect_json": json.dumps(
        {"effect_category": "scent_mask", "forest_encounter_mult": 0.5, "stealth_bonus": 2, "duration_hours": 24}
    ),
    "is_active": 1,
    "note": "Buff dzienny (session_flags): -50% szansy spotkań z bestiami na hexach leśnych + bonus do skradania, 1 dzień gry.",
}

TORCH_EFFECT = json.dumps(
    {"effect_category": "light_source", "light_kind": "open_flame", "attracts_encounters": True}
)
TORCH_DESC = (
    "Pakuł nasycony smołą na drewnianym kiju. Płonie godzinę silnym, dymiącym "
    "płomieniem. W borze nocą otwarty ogień wabi to, co czai się w mroku."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    ic = _cols(db, "game_config_items")
    cc = _cols(db, "game_config_consumables")

    _upsert(db, "game_config_items", PROCHNO, ic)
    _upsert(db, "game_config_consumables", DZIEGIEC, cc)
    db.execute(
        "UPDATE game_config_items SET effect_json = ?, description = ? WHERE key = 'torch'",
        (TORCH_EFFECT, TORCH_DESC),
    )
    db.commit()

    # U11c dual-write: legacy game_config_* → unified game_items (sklepy/loot czytają
    # game_items). Bez tego walidacja handlu „brak w katalogu" i przedmiot nie do kupienia.
    sys.path.insert(0, "/app")
    try:
        from app.services import game_items_service as gis
        gis.sync_from_legacy(db, "game_config_items", "prochno_swietlne")
        gis.sync_from_legacy(db, "game_config_items", "torch")
        gis.sync_from_legacy(db, "game_config_consumables", "dziegiec_czarnodrzewny")
        db.commit()
    except Exception as e:  # noqa: BLE001
        print(f"WARN: game_items sync failed: {e}")

    ok = True
    for key in ("prochno_swietlne", "torch"):
        r = db.execute("SELECT effect_json FROM game_config_items WHERE key = ?", (key,)).fetchone()
        print(f"item {key}: {r['effect_json'] if r else '<MISSING>'}")
        ok = ok and bool(r)
    r = db.execute(
        "SELECT effect_json FROM game_config_consumables WHERE key = ?", ("dziegiec_czarnodrzewny",)
    ).fetchone()
    print(f"consumable dziegiec_czarnodrzewny: {r['effect_json'] if r else '<MISSING>'}")
    ok = ok and bool(r)
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
