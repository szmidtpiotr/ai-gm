"""Seed L14 — dungeon tile category 'krypta' + 20 tile definitions.

Run inside dev backend container:
  docker exec ai-gm-dev-backend-1 python3 /app/scripts/seed_l14_krypta.py

Idempotent: skips records that already exist (by key/label).
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/ai_gm.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


# ── Category ──────────────────────────────────────────────────────────────────

CATEGORY = {
    "key": "krypta",
    "label": "Krypta",
    "description": "Kamienne katakumby pełne sarkofagów, kości i mrocznej magii nieumarłych.",
    "style_modifier": (
        "stone catacombs interior, sarcophagi and tombs, bones and skulls scattered on floor, "
        "candles and torches, crumbling stone walls, dark and foreboding atmosphere, "
        "ancient crypt aesthetic, dusty and decayed"
    ),
    "system_prompt": (
        "Opisujesz pomieszczenie w starożytnej krypcie/katakumbach. "
        "Koncentruj się na detalach: sarkofagi, kości, kamienne posadzki, świece, pochodnie, "
        "pajęczyny, pył, mrok. Opis po polsku, 2-3 zdania klimatyczne. "
        "Używaj zmysłowych szczegółów — co gracz czuje, słyszy, widzi."
    ),
    "sort_order": 10,
    "is_active": 1,
}

# ── New riddles (crypt-themed) ─────────────────────────────────────────────────

NEW_RIDDLES = [
    {
        "key": "riddle_grave",
        "text": (
            "Mam imię wyryte w kamieniu, lecz nie odpowiem gdy mnie wołasz. "
            "Śpię spokojnie, choć oczy mam otwarte na wieczność. Czym jestem?"
        ),
        "answer": "nagrobek",
        "answer_alts": json.dumps(["grób", "płyta nagrobna", "kamień nagrobny"]),
        "hints": json.dumps(["Stoi nad ziemią", "Upamiętnia kogoś, kto odszedł"]),
        "difficulty": 2,
        "theme": "death",
    },
    {
        "key": "riddle_tomb",
        "text": (
            "Zamykam komnaty bez kluczy, pochłaniam światło bez oczu. "
            "Towarzyszę umarłym od wieków, a żywi drżą gdy mnie dotykają. Czym jestem?"
        ),
        "answer": "mrok",
        "answer_alts": json.dumps(["ciemność", "cień", "mrok krypty"]),
        "hints": json.dumps(["Nie ma formy", "Znika gdy pojawia się ogień"]),
        "difficulty": 2,
        "theme": "death",
    },
]

# ── 20 Tile definitions ────────────────────────────────────────────────────────
# doors_json: list of cardinal directions ['N','S','E','W']
# enemies_json: list of {enemy_key, count}
# items_json: list of {type} or {item_key}
# riddle_key: FK to game_config_riddles or None
# is_boss_tile: 0 or 1

TILES = [
    # ── 2-door tiles (6) ──────────────────────────────────────────────────────
    {
        "label": "Korytarz Kości",
        "doors_json": ["N", "S"],
        "enemies_json": [{"enemy_key": "skeleton", "count": 2}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "stone catacombs corridor top-down view, scattered bones and skulls on stone floor, "
            "two wall torches casting orange glow, ancient crumbling stonework, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Cela Umarłego",
        "doors_json": ["E", "W"],
        "enemies_json": [{"enemy_key": "zombie", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "small crypt cell top-down view, single stone sarcophagus in center, "
            "torn burial wrappings on floor, single candle stub, damp stone walls, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Kaplica Cienia",
        "doors_json": ["N", "E"],
        "enemies_json": [],
        "items_json": [],
        "riddle_key": "riddle_shadow",
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "ancient crypt chapel top-down view, stone altar with dark shadow patterns, "
            "melted black candles, faded wall paintings of shadowy figures, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Komora Zagadki",
        "doors_json": ["S", "W"],
        "enemies_json": [],
        "items_json": [],
        "riddle_key": "riddle_bones",
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt chamber top-down view, central stone pedestal with inscribed riddle tablet, "
            "bone arrangements forming patterns on floor, faded runes on walls, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Izba Spoczynku",
        "doors_json": ["N", "S"],
        "enemies_json": [],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "peaceful crypt antechamber top-down view, stone benches along walls, "
            "fresh candles burning, clean swept floor, old tapestries, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Nisza z Trumną",
        "doors_json": ["N", "W"],
        "enemies_json": [{"enemy_key": "ghost", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt niche top-down view, ornate wooden coffin with tarnished silver handles, "
            "wilted funeral flowers, dusty cobwebs, greenish ghostly mist wisps, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    # ── 3-door tiles (8) ──────────────────────────────────────────────────────
    {
        "label": "Sala Szkieletów",
        "doors_json": ["N", "S", "E"],
        "enemies_json": [{"enemy_key": "skeleton", "count": 2}, {"enemy_key": "zombie", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "large crypt hall top-down view, multiple standing skeleton remains in niches, "
            "bone-strewn floor, large stone pillars, cracked stone slabs, chains on walls, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Komnata Zgnilizny",
        "doors_json": ["N", "S", "W"],
        "enemies_json": [{"enemy_key": "zombie", "count": 1}, {"enemy_key": "ghoul", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "putrid crypt chamber top-down view, cracked sarcophagi with lids ajar, "
            "dark stains on floor, broken burial urns, fetid water pooling in corners, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Skrzyżowanie Widm",
        "doors_json": ["N", "E", "W"],
        "enemies_json": [{"enemy_key": "ghost", "count": 1}, {"enemy_key": "wraith", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt crossroads top-down view, spectral blue mist swirling on stone floor, "
            "ancient iron lanterns with ghostly flame, faded spirit trail markings, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Galeria Posągów",
        "doors_json": ["S", "E", "W"],
        "enemies_json": [],
        "items_json": [{"type": "chest"}],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt gallery top-down view, stone statues of robed figures lining walls, "
            "ornate treasure chest on stone pedestal in center, dusty pedestals, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Komnata Śmierci",
        "doors_json": ["N", "S", "E"],
        "enemies_json": [{"enemy_key": "skeleton", "count": 1}],
        "items_json": [],
        "riddle_key": "riddle_death",
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt death chamber top-down view, large stone altar with carved skull motifs, "
            "hourglass and scales of judgment, black candles in iron holders, inscribed floor, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Sala Ofiar",
        "doors_json": ["N", "S", "W"],
        "enemies_json": [{"enemy_key": "ghoul", "count": 2}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "sacrifice hall top-down view, dark stained altar stone, discarded bones and offerings, "
            "ritual circles drawn on floor, iron shackles on walls, guttered black candles, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Skarbiec Krypty",
        "doors_json": ["N", "E", "W"],
        "enemies_json": [],
        "items_json": [{"type": "chest"}],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "crypt treasure vault top-down view, iron-bound chest on raised stone platform, "
            "old coins scattered on floor, tarnished silver candlesticks, cobweb-draped shelves, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Komora Ciszy",
        "doors_json": ["S", "E", "W"],
        "enemies_json": [],
        "items_json": [],
        "riddle_key": "riddle_silence",
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "silent crypt chamber top-down view, perfectly smooth stone floor with central inscription, "
            "sealed alcoves with carved faces, oppressive stillness, single flame in carved stone bowl, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    # ── 4-door tiles (4) ──────────────────────────────────────────────────────
    {
        "label": "Główna Sala Krypty",
        "doors_json": ["N", "S", "E", "W"],
        "enemies_json": [{"enemy_key": "wraith", "count": 1}, {"enemy_key": "skeleton", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "grand crypt main hall top-down view, vaulted ceiling glimpsed, four stone archways, "
            "central raised dais with ancient sarcophagus, wraith-shadow stains on floor, pillar shadows, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Wielka Komnata",
        "doors_json": ["N", "S", "E", "W"],
        "enemies_json": [{"enemy_key": "undead_champion", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "vast crypt chamber top-down view, central stone throne on raised platform, "
            "ancient weapons rack, battle-worn banners hanging, bone-dust scattered floor, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Sanktuarium Mroku",
        "doors_json": ["N", "S", "E", "W"],
        "enemies_json": [{"enemy_key": "wraith", "count": 1}],
        "items_json": [{"type": "chest"}],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "dark sanctuary top-down view, shadowy altar with sealed iron chest, "
            "dark crystal obelisk in corner, silver-inlaid floor patterns, drifting shadow wisps, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Kaplica Przeklętych",
        "doors_json": ["N", "S", "E", "W"],
        "enemies_json": [],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 0,
        "image_gen_prompt": (
            "cursed crypt chapel top-down view, broken stone pews, cracked stained glass fragments, "
            "overgrown with dark vines, toppled candelabra, eerie calm, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    # ── Boss tiles (2) ────────────────────────────────────────────────────────
    {
        "label": "Tron Lisza",
        "doors_json": ["N", "S", "E", "W"],
        "enemies_json": [{"enemy_key": "lich", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 1,
        "image_gen_prompt": (
            "lich throne room top-down view, massive obsidian throne on elevated platform, "
            "arcane rune circles on floor, floating spell tomes, dark energy crystals at corners, "
            "ancient phylactery on altar, dramatic dark lighting, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
    {
        "label": "Komnata Mistrza Wampirów",
        "doors_json": ["N", "S", "W"],
        "enemies_json": [{"enemy_key": "vampire_master", "count": 1}],
        "items_json": [],
        "riddle_key": None,
        "is_boss_tile": 1,
        "image_gen_prompt": (
            "vampire master lair top-down view, ornate stone coffin with crimson velvet lining, "
            "blood-red candles in silver holders, gothic iron furniture, bat-wing carved reliefs, "
            "wine-dark stains on ancient stone floor, "
            "Gloomhaven board game art style, flat 2D painted illustration, no walls no doors"
        ),
    },
]


def seed(conn: sqlite3.Connection) -> None:
    # ── 1. Category ───────────────────────────────────────────────────────────
    existing = conn.execute(
        "SELECT key FROM dungeon_tile_categories WHERE key = ?", (CATEGORY["key"],)
    ).fetchone()
    if existing:
        print(f"[SKIP] Category '{CATEGORY['key']}' already exists")
    else:
        conn.execute(
            """INSERT INTO dungeon_tile_categories
               (key, label, description, style_modifier, system_prompt, sort_order, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                CATEGORY["key"],
                CATEGORY["label"],
                CATEGORY["description"],
                CATEGORY["style_modifier"],
                CATEGORY["system_prompt"],
                CATEGORY["sort_order"],
                CATEGORY["is_active"],
            ),
        )
        print(f"[OK] Category '{CATEGORY['key']}' created")

    # ── 2. New riddles ────────────────────────────────────────────────────────
    for riddle in NEW_RIDDLES:
        existing = conn.execute(
            "SELECT key FROM game_config_riddles WHERE key = ?", (riddle["key"],)
        ).fetchone()
        if existing:
            print(f"[SKIP] Riddle '{riddle['key']}' already exists")
        else:
            conn.execute(
                """INSERT INTO game_config_riddles
                   (key, text, answer, answer_alts, hints, difficulty, theme, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    riddle["key"],
                    riddle["text"],
                    riddle["answer"],
                    riddle["answer_alts"],
                    riddle["hints"],
                    riddle["difficulty"],
                    riddle["theme"],
                ),
            )
            print(f"[OK] Riddle '{riddle['key']}' created")

    # ── 3. Tiles ──────────────────────────────────────────────────────────────
    inserted = 0
    skipped = 0
    for tile in TILES:
        existing = conn.execute(
            "SELECT id FROM dungeon_tiles WHERE category_key = ? AND label = ?",
            (CATEGORY["key"], tile["label"]),
        ).fetchone()
        if existing:
            print(f"[SKIP] Tile '{tile['label']}' already exists")
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO dungeon_tiles
               (category_key, label, image_gen_prompt, doors_json, enemies_json,
                items_json, riddle_key, is_boss_tile, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                CATEGORY["key"],
                tile["label"],
                tile["image_gen_prompt"],
                json.dumps(tile["doors_json"]),
                json.dumps(tile["enemies_json"]),
                json.dumps(tile["items_json"]),
                tile["riddle_key"],
                tile["is_boss_tile"],
            ),
        )
        print(f"[OK] Tile '{tile['label']}' (doors={tile['doors_json']}, boss={tile['is_boss_tile']})")
        inserted += 1

    conn.commit()
    print(f"\nDone: {inserted} tiles inserted, {skipped} skipped.")


if __name__ == "__main__":
    with _conn() as conn:
        seed(conn)
