"""E13 (#428) — generic encounter pool.

Seeds a set of standard, reusable encounters into `adventure_hooks` tagged with
biome / trigger_types / level_min / level_max so the encounter engine
(`encounter_service.maybe_inject_encounter`) can draw biome- and level-matched
random encounters in any campaign. Idempotent: each encounter carries a
`__generic_encounter__` marker key so re-running never duplicates.
"""
from __future__ import annotations

import json
import sqlite3

DB_PATH = "/data/ai_gm.db"

# biome values mirror world_hexes.hex_type / game_locations.biome conventions.
GENERIC_ENCOUNTERS = [
    {
        "key": "wolves_forest",
        "title": "Wataha wilków",
        "description": "Głodne wilki wychodzą z gęstwiny, węsząc świeży trop.",
        "biomes": ["forest", "las", "wilderness"],
        "trigger_types": ["hex_enter", "n_turns"],
        "level_min": 1, "level_max": 3, "trigger_probability": 0.25,
        "enemies": [{"enemy_key": "wolf", "name": "wilk", "count": 2}],
    },
    {
        "key": "bandits_road",
        "title": "Zasadzka bandytów",
        "description": "Z zarośli przy trakcie wyłaniają się uzbrojeni rozbójnicy.",
        "biomes": ["road", "plains", "grassland", "wilderness"],
        "trigger_types": ["hex_enter"],
        "level_min": 2, "level_max": 5, "trigger_probability": 0.22,
        "enemies": [{"enemy_key": "bandit", "name": "bandyta", "count": 2}],
    },
    {
        "key": "goblins_cave",
        "title": "Gobliński patrol",
        "description": "Z mroku jaskini dobiega skrzekot — goblińska zwiadowcza banda.",
        "biomes": ["dungeon", "cave", "loch", "mountain"],
        "trigger_types": ["hex_enter", "n_turns"],
        "level_min": 2, "level_max": 6, "trigger_probability": 0.25,
        "enemies": [{"enemy_key": "goblin", "name": "goblin", "count": 3}],
    },
    {
        "key": "undead_crypt",
        "title": "Ożywieńcy z krypty",
        "description": "Spod ziemi wygrzebują się szkielety, klekocząc kośćmi.",
        "biomes": ["dungeon", "crypt", "loch", "ruins"],
        "trigger_types": ["hex_enter", "n_turns"],
        "level_min": 4, "level_max": 8, "trigger_probability": 0.2,
        "enemies": [{"enemy_key": "skeleton", "name": "szkielet", "count": 3}],
    },
    {
        "key": "ambush_city_thugs",
        "title": "Zaułkowi rzezimieszki",
        "description": "W ciemnym zaułku zachodzą cię drogę miejscy zbiry.",
        "biomes": ["city", "miasto", "town", "settlement"],
        "trigger_types": ["hex_enter"],
        "level_min": 1, "level_max": 4, "trigger_probability": 0.18,
        "enemies": [{"enemy_key": "thug", "name": "zbir", "count": 2}],
    },
    # F8 (#468) — robbery encounters (no combat, gold stolen)
    {
        "key": "robbery_road_bandits",
        "title": "Napad na trakcie",
        "description": "Uzbrojeni bandyci wyskakują zza drzew i grożą bronią — oddaj sakiewkę!",
        "biomes": ["road", "plains", "wilderness", "forest"],
        "trigger_types": ["hex_enter", "n_turns"],
        "level_min": 1, "level_max": 10, "trigger_probability": 0.12,
        "encounter_type": "robbery",
        "enemies": [],
    },
    {
        "key": "robbery_city_pickpocket",
        "title": "Kieszonkowiec na targu",
        "description": "W tłumie targowiska zręczne ręce sięgają do twojej sakiewki.",
        "biomes": ["city", "miasto", "town", "settlement"],
        "trigger_types": ["n_turns"],
        "level_min": 1, "level_max": 8, "trigger_probability": 0.10,
        "encounter_type": "robbery",
        "enemies": [],
    },
]


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed_generic_encounters() -> int:
    """Insert any missing generic encounters into adventure_hooks. Returns the
    number present after seeding (idempotent — keyed by `__generic_encounter__`)."""
    conn = _conn()
    inserted = 0
    try:
        existing = {
            row["k"]
            for row in conn.execute(
                "SELECT json_extract(draft_data, '$.__generic_encounter__') AS k "
                "FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'"
            ).fetchall()
            if row["k"]
        }
        for e in GENERIC_ENCOUNTERS:
            if e["key"] in existing:
                continue
            enc_body = {
                "label": e["title"],
                "biomes": e["biomes"],
                "trigger_types": e["trigger_types"],
                "level_min": e["level_min"],
                "level_max": e["level_max"],
                "trigger_probability": e["trigger_probability"],
                "enemies": e["enemies"],
                "source": "generic_pool",
            }
            if e.get("encounter_type"):
                enc_body["encounter_type"] = e["encounter_type"]
            draft_data = {
                "__generic_encounter__": e["key"],
                "encounter": enc_body,
            }
            conn.execute(
                """INSERT INTO adventure_hooks
                   (hook_type, title, description, significance, draft_data, status, quality_rating)
                   VALUES ('encounter', ?, ?, 'minor', ?, 'approved', 3)""",
                (e["title"], e["description"], json.dumps(draft_data, ensure_ascii=False)),
            )
            inserted += 1
        conn.commit()
        # Return the TOTAL count present after seeding (idempotent-friendly).
        return conn.execute(
            "SELECT COUNT(*) AS n FROM adventure_hooks WHERE draft_data LIKE '%\"__generic_encounter__\"%'"
        ).fetchone()["n"]
    finally:
        conn.close()
