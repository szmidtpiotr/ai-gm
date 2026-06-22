from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import random

# env.test / .env w katalogu repozytorium (obok backend/) — AI_TEST_MODE=1 itd. bez ręcznego export
from app.bootstrap_env import load_repo_env

load_repo_env()
import re
import sqlite3
import time
import uuid
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.logging import bind_context, configure_logging, get_logger, reset_request_context
import app.core.metrics  # noqa: F401 — registers domain Prometheus metrics at startup (G31 #811)
from app.db import get_session, init_db
from app.models import Game, Message
from app.services.dice import build_gm_dice_breakdown, parse_character_sheet
from app.services.llm_service import generate_chat
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT

from app.api import (
    auth,
    campaign_helpme,
    campaign_history,
    campaign_memory,
    campaigns,
    characters,
    combat,
    commands,
    friends,
    turns,
    mechanics,
    inventory,
    npcs,
    shop,
)
from app.api.dungeons import router as dungeons_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.version import router as version_router
from app.api.client_logs import router as client_logs_router
from app.api.knowledge import router as knowledge_router
from app.api.multiplayer import router as multiplayer_router
from app.api.party_chat import router as party_chat_router
from app.migrations_admin import run_admin_migrations
from app.services.llm_admin_service import hydrate_runtime_from_stored_preset
from app.routers.admin import router as admin_router
from app.routers.rules_content import router as rules_content_router
from app.routers.admin_cheat import router as admin_cheat_router
from app.routers.sandbox import router as sandbox_router
from app.routers.rest_sandbox import router as rest_sandbox_router
from app.routers.admin_visual import admin_router as admin_visual_router, public_router as visual_public_router
from app.routers.admin_ui_texts import admin_router as admin_ui_texts_router, public_router as ui_texts_public_router
from app.routers.settings import router as settings_router
from app.routers.debug import router as debug_router
from app.routers.test_runner import router as test_runner_router
from app.routers.locations import router as locations_router
from app.routers.session_location import router as session_location_router
from app.routers.admin_location import router as admin_location_router
from app.routers.bg_images import router as bg_images_router
from app.routers.dungeon_tiles import router as dungeon_tiles_router
from app.routers.admin_analytics import router as admin_analytics_router
from app.routers.world_review import router as world_review_router
from app.routers.admin_spectate import router as admin_spectate_router
from app.routers.smart_entry import router as smart_entry_router
from app.routers.adventure_forge import router as adventure_forge_router, public_router as campaign_templates_router
from app.routers.hex_world import router as hex_world_router
from app.routers.hidden_traits import router as hidden_traits_router
from app.routers.voice_proxy import public_router as voice_public_router
from app.routers.voice_proxy import admin_router as voice_admin_router
from app.routers.admin_images import router as admin_images_router
from app.routers.bug_report import router as bug_report_router
from app.routers.world_state_history import router as world_state_history_router
from app.routers.push_notifications import router as push_notifications_router
from app.routers.notify_prefs import router as notify_prefs_router
from app.routers.seen_mechanics import router as seen_mechanics_router
from app.routers.game_mechanics import router as game_mechanics_router
from app.routers.db_lint import router as db_lint_router
from app.routers.admin_dice_config import admin_router as dice_config_admin_router, public_router as dice_config_public_router


# Keep DB path consistent with API routers using raw sqlite connections.
DB_PATH = "/data/ai_gm.db"
logger = get_logger("ai_gm")


GAME_SYSTEMS = {
    "fantasy": {
        "prompt": SYSTEM_PROMPT_TEXT,
    },
    "warhammer": {
        "prompt": (
            "Jesteś Mistrzem Gry Warhammer Fantasy Roleplay. "
            "Odpowiadasz po polsku. Klimat Starego Świata, mrok, brud, chaos, "
            "intryga. Używaj zasad d100. "
            "NIGDY nie podawaj graczowi ponumerowanych opcji. NIGDY nie kończ pytaniem Co robisz?"
        )
    },
    "cyberpunk": {
        "prompt": (
            "Jesteś Mistrzem Gry Cyberpunk RED. "
            "Odpowiadasz po polsku. Klimat Night City, edgerunnerzy, "
            "korporacje, slang cyberpunkowy. "
            "NIGDY nie podawaj graczowi ponumerowanych opcji. NIGDY nie kończ pytaniem Co robisz?"
        )
    },
    "neuroshima": {
        "prompt": (
            "Jesteś Mistrzem Gry Neuroshima. "
            "Odpowiadasz po polsku. Klimat post-apo Polski, Moloch, "
            "Hegemonia, brud i przemoc. "
            "NIGDY nie podawaj graczowi ponumerowanych opcji. NIGDY nie kończ pytaniem Co robisz?"
        )
    },
}


class ChatReq(BaseModel):
    model: str
    messages: list[dict]
    game_system: str = "fantasy"
    game_id: int | None = None


class DiceReq(BaseModel):
    dice: str
    character_id: int | None = None
    roll_key: str | None = None
    dc: int | None = None


class GameCreateReq(BaseModel):
    title: str
    system: str
    model: str = "gemma3:1b"


RAW_MIGRATIONS = [
    "ALTER TABLE characters ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE campaign_turns ADD COLUMN character_id INTEGER",
    "ALTER TABLE characters ADD COLUMN sheet_json TEXT",
    "ALTER TABLE campaigns ADD COLUMN death_reason TEXT",
    "ALTER TABLE campaigns ADD COLUMN ended_at TEXT",
    "ALTER TABLE campaigns ADD COLUMN epitaph TEXT",
    "ALTER TABLE campaigns ADD COLUMN gm_plan_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE campaigns ADD COLUMN last_rollup_narrative_turn_count INTEGER",
    """
    CREATE TABLE IF NOT EXISTS character_xp_grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER NOT NULL,
        campaign_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'mg_manual',
        granted_by_user_id INTEGER NOT NULL,
        meta_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_character_xp_grants_character
    ON character_xp_grants(character_id, created_at DESC)
    """,
    # U25 (#575): affix pity timers — counters survive restart.
    # scope='boss_drop' (per character) | 'reroll:<inventory_id>' (per item).
    """
    CREATE TABLE IF NOT EXISTS affix_pity (
        character_id INTEGER NOT NULL,
        scope TEXT NOT NULL,
        counter INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (character_id, scope)
    )
    """,
    # U25 (#575): flag set when a boss tier enemy dies, read by post-combat loot
    # claim so the affix pity timer knows the kill was a boss.
    "ALTER TABLE active_combat ADD COLUMN boss_defeated INTEGER NOT NULL DEFAULT 0",
    """
    CREATE TABLE IF NOT EXISTS campaign_ai_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        model_used TEXT,
        included_turn_count INTEGER,
        audience TEXT NOT NULL DEFAULT 'player',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_xp_rewards (
        key TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        label TEXT NOT NULL,
        description TEXT,
        xp_amount INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        locked_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Trim trigger_keywords for skills that were too-broadly matching narrative
    # text and spawning phantom skill tests (audit follow-up to issue #20).
    # 'kowalstwo': weapon nouns (miecz/ostrze/zbroja/metal/jakość) matched any
    # mention of a sword, not actual blacksmithing intent. Keep only craft-
    # intent verbs and the role noun "kowal".
    "UPDATE game_config_skills SET trigger_keywords = 'kowal kuje kuję naprawiam oceniam' WHERE key = 'kowalstwo' AND trigger_keywords LIKE '%miecz%'",
    # 'initiative': meta-combat mechanic — rolled inside start_combat, never
    # as a standalone check. Its keywords (szybko/refleks/pierwszy) were also
    # generic enough to match unrelated narration. Clear entirely; the code-
    # level _COMBAT_CLASS_SKILLS guard backs this up.
    "UPDATE game_config_skills SET trigger_keywords = '' WHERE key = 'initiative'",
    # 2026-06-18 #763: 'deception' keyword 'udaję' false-matched the common Polish
    # movement idiom "udaję się [do/na ...]" (= "I head to ..."), spawning a phantom
    # Oszustwo (Deception) test on every travel declaration and trapping the player
    # in the current scene. Drop the bare 'udaję'; keep explicit lie/bluff/impersonate
    # verbs (active deception only). Idempotent — fires only while old value present.
    "UPDATE game_config_skills SET trigger_keywords = 'blefuję oszukuję oszukać ściemniam kłamię podszywam' "
        "WHERE key = 'deception' AND trigger_keywords LIKE '%udaję%'",
    # 2026-06-18 #763: 'stealth' had EMPTY trigger_keywords, so genuine sneaking never
    # fired a Stealth test via the keyword pre-scan (and worse, ambiguous declarations
    # fell to deception). Seed active-sneak verbs. Passive observation ("obserwuję",
    # "z cienia") intentionally NOT included — that stays no-roll, handled by narrator.
    "UPDATE game_config_skills SET trigger_keywords = 'skradam zakradam podkradam przemykam ukradkiem chyłkiem' "
        "WHERE key = 'stealth' AND (trigger_keywords IS NULL OR trigger_keywords = '')",
    # 2026-05-18 W4: rename fear conditions to spec terminology and collapse
    # 4 stages (fear_shaken/fear_frightened/terror/break) to 3 (frightened/
    # panicked/break) per [D2]. Idempotent — re-runs are no-ops once data is
    # already in the new state.
    "UPDATE character_conditions SET condition_type = 'frightened' "
        "WHERE condition_type IN ('fear_shaken', 'fear_frightened')",
    "UPDATE character_conditions SET condition_type = 'panicked' "
        "WHERE condition_type = 'terror'",
    # Add the missing 'break' registry row (referenced by code but never seeded).
    "INSERT OR IGNORE INTO game_config_conditions (key, label, effect_json, description) VALUES ("
        "'break', 'Złamany', "
        "'{\"forced_action\":\"flee\",\"duration\":\"encounter\"}', "
        "'Pęknięcie psychiczne. Bohater musi próbować ucieczki każdej rundy aż do końca starcia.'"
    ")",
    # 2026-05-19 Stage 2A follow-up: visual settings table + time-of-day overlay seeds.
    """CREATE TABLE IF NOT EXISTS game_config_visual (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('time_of_day.enabled', 'true')",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('time_of_day.mode', '\"frame\"')",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('time_of_day.intensity', '60')",
    """INSERT OR IGNORE INTO game_config_visual (key, value) VALUES (
        'time_of_day.rano',
        '{"color":"#ffd97a","accent":"#f7e7a3","label":"Rano"}'
    )""",
    """INSERT OR IGNORE INTO game_config_visual (key, value) VALUES (
        'time_of_day.popoludnie',
        '{"color":"#c9a54a","accent":"#d4b65e","label":"Popołudnie"}'
    )""",
    """INSERT OR IGNORE INTO game_config_visual (key, value) VALUES (
        'time_of_day.wieczor',
        '{"color":"#c95c2e","accent":"#e07555","label":"Wieczór"}'
    )""",
    """INSERT OR IGNORE INTO game_config_visual (key, value) VALUES (
        'time_of_day.noc',
        '{"color":"#5a6d99","accent":"#7a8cb8","label":"Noc"}'
    )""",
    # 2026-05-25 — multi-role NPCs. `is_shop` already exists; add `is_quest_giver`
    # and `is_ally` to mirror the same boolean-capability pattern, then backfill
    # from the legacy single-value `npc_type` so existing rows keep their role.
    # `npc_type` stays as the "primary" role (auto-derived on PATCH) for the
    # ~30 callers in services/* that still SELECT it.
    "ALTER TABLE npcs ADD COLUMN is_quest_giver INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE npcs ADD COLUMN is_ally INTEGER NOT NULL DEFAULT 0",
    "UPDATE npcs SET is_shop = 1        WHERE npc_type = 'merchant'    AND is_shop = 0",
    "UPDATE npcs SET is_quest_giver = 1 WHERE npc_type = 'quest_giver' AND is_quest_giver = 0",
    # U20 (#572): crafter flag — onboarding card on first encounter with a crafter NPC
    "ALTER TABLE npcs ADD COLUMN is_crafter INTEGER NOT NULL DEFAULT 0",
    "UPDATE npcs SET is_crafter = 1 WHERE is_crafter = 0 AND ("
    "LOWER(key) LIKE '%kowal%' OR LOWER(key) LIKE '%blacksmith%' OR LOWER(key) LIKE '%smith%' "
    "OR LOWER(key) LIKE '%platner%' OR LOWER(key) LIKE '%rzemie%' OR LOWER(key) LIKE '%craft%' "
    "OR LOWER(label) LIKE '%kowal%' OR LOWER(label) LIKE '%płatnerz%' OR LOWER(label) LIKE '%platnerz%' "
    "OR LOWER(label) LIKE '%rzemie%' OR LOWER(label) LIKE '%blacksmith%' OR LOWER(label) LIKE '%crafter%')",
    "UPDATE npcs SET is_ally = 1        WHERE npc_type = 'ally'        AND is_ally = 0",

    "ALTER TABLE game_config_weapons     ADD COLUMN rarity INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_items       ADD COLUMN rarity INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_consumables ADD COLUMN rarity INTEGER NOT NULL DEFAULT 1",

    "ALTER TABLE users ADD COLUMN game_mode_flags TEXT DEFAULT NULL",

    # Image gen config seeds — stored in game_config_visual for admin-editability
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('image_gen.url', '\"http://192.168.1.170:8765\"')",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('image_gen.steps', '4')",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('image_gen.refine_steps', '8')",
    "INSERT OR IGNORE INTO game_config_visual (key, value) VALUES ('image_gen.checkpoint', '\"\"')",

    # B1/B2 (#347/#348) — World State columns on game_sessions + snapshots table.
    # ALTER TABLE is idempotent via the try/except OperationalError in run_raw_migrations.
    "ALTER TABLE game_sessions ADD COLUMN scene_enemies TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE game_sessions ADD COLUMN scene_npcs TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE game_sessions ADD COLUMN scene_cleared INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_sessions ADD COLUMN active_quests TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE game_sessions ADD COLUMN player_conditions TEXT NOT NULL DEFAULT '[]'",
    """CREATE TABLE IF NOT EXISTS world_state_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        turn_number INTEGER NOT NULL DEFAULT 0,
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        snapshot_source TEXT NOT NULL DEFAULT 'auto',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE INDEX IF NOT EXISTS idx_world_state_snapshots_campaign
    ON world_state_snapshots(campaign_id, turn_number DESC)""",
    # C2: terrain passability for hex movement
    "ALTER TABLE hex_type_config ADD COLUMN is_passable INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE hex_type_config ADD COLUMN required_item TEXT",
    "UPDATE hex_type_config SET is_passable = 0 WHERE hex_type IN ('lake', 'ocean', 'sea')",
    # C7: XP skill costs aligned to game_mechanics.md (new=100, 1→2=75, 2→3=150)
    "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES ('xp_skill_rank_costs', '{\"1\":100,\"2\":75,\"3\":150}')",
    # C7: skill rank ceiling = 3 for all skills
    "UPDATE game_config_skills SET rank_ceiling = 3",
    # C8: stat XP costs per game_mechanics.md (new_value→cost); current 8-10=50, 11-13=100, 14-16=200, 17-18=400
    "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES ('xp_stat_point_costs', '{\"9\":50,\"10\":50,\"11\":50,\"12\":100,\"13\":100,\"14\":100,\"15\":200,\"16\":200,\"17\":200,\"18\":400,\"19\":400}')",
    # C8: stat ceiling = 19 (19+ = Niedostępne per game_mechanics.md)
    "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES ('xp_stat_value_ceiling', '19')",
    # E23 — seen_mechanics per-user tracking
    """
    CREATE TABLE IF NOT EXISTS seen_mechanics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        mechanic_key TEXT NOT NULL,
        seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(user_id, mechanic_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_seen_mechanics_user ON seen_mechanics(user_id)",
    # E28 — tutorial campaign flag
    "ALTER TABLE campaigns ADD COLUMN is_tutorial INTEGER NOT NULL DEFAULT 0",
    # F7 (#467) / S4 (#492) — durability_base on weapon config (per-weapon override over
    # rarity-based DEFAULT_DURABILITY in durability_service.py; NULL = use rarity default).
    # durability_max / durability_current on inventory rows track wear state at runtime.
    "ALTER TABLE game_config_weapons ADD COLUMN durability_base INTEGER",
    "ALTER TABLE character_inventory ADD COLUMN durability_max INTEGER",
    "ALTER TABLE character_inventory ADD COLUMN durability_current INTEGER",
    # F2 (#462) / U16 (#564) — per-inventory affix list (JSON array of affix keys).
    # Created in test schemas only; never migrated onto the live DB. U16 surfaces the
    # affix forge UI to players, so apply/reroll/upgrade need this column to persist.
    "ALTER TABLE character_inventory ADD COLUMN affixes_json TEXT",
    # S11 (#NNN) — hex world builder: missing columns added after initial schema creation
    "ALTER TABLE world_hexes ADD COLUMN parent_hex_id INTEGER REFERENCES world_hexes(id)",
    "ALTER TABLE world_hexes ADD COLUMN map_level INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE hex_type_config ADD COLUMN spawn_weight INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE hex_type_config ADD COLUMN has_submap INTEGER NOT NULL DEFAULT 0",
    # game_locations hex placement columns (world builder overlay)
    "ALTER TABLE game_locations ADD COLUMN world_hex_q INTEGER",
    "ALTER TABLE game_locations ADD COLUMN world_hex_r INTEGER",
    # S11 — seed spawn_weight for natural terrain (0 = hand-placed, not generated)
    "UPDATE hex_type_config SET spawn_weight = 30 WHERE hex_type = 'plains'",
    "UPDATE hex_type_config SET spawn_weight = 28 WHERE hex_type = 'forest'",
    "UPDATE hex_type_config SET spawn_weight = 18 WHERE hex_type = 'hills'",
    "UPDATE hex_type_config SET spawn_weight = 12 WHERE hex_type = 'mountains'",
    "UPDATE hex_type_config SET spawn_weight =  7 WHERE hex_type = 'swamp'",
    "UPDATE hex_type_config SET spawn_weight =  3 WHERE hex_type = 'ruins'",
    "UPDATE hex_type_config SET spawn_weight =  2 WHERE hex_type = 'cave'",
    # U28 — Placement engine: terrain_tags + placement na game_locations, location_spawn_chance na hex_type_config
    "ALTER TABLE game_locations ADD COLUMN terrain_tags TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE game_locations ADD COLUMN placement TEXT NOT NULL DEFAULT 'floating'",
    "ALTER TABLE hex_type_config ADD COLUMN location_spawn_chance REAL NOT NULL DEFAULT 0.15",
    # U28 — backfill placement='placed' dla lokacji już linkowanych przez world_hexes
    "UPDATE game_locations SET placement='placed'"
    " WHERE key IN (SELECT location_key FROM world_hexes WHERE location_key IS NOT NULL AND is_active=1)",
    # U28 — location_spawn_chance per hex_type (wartości startowe — kalibracja po U32b)
    "UPDATE hex_type_config SET location_spawn_chance=1.0 WHERE hex_type IN ('town','castle')",
    "UPDATE hex_type_config SET location_spawn_chance=0.8 WHERE hex_type='dungeon'",
    "UPDATE hex_type_config SET location_spawn_chance=0.6 WHERE hex_type='ruins'",
    "UPDATE hex_type_config SET location_spawn_chance=0.4 WHERE hex_type='road'",
    "UPDATE hex_type_config SET location_spawn_chance=0.3 WHERE hex_type='cave'",
    "UPDATE hex_type_config SET location_spawn_chance=0.15 WHERE hex_type IN ('plains','forest')",
    "UPDATE hex_type_config SET location_spawn_chance=0.1 WHERE hex_type IN ('hills','swamp')",
    "UPDATE hex_type_config SET location_spawn_chance=0.05 WHERE hex_type='mountains'",
    "UPDATE hex_type_config SET location_spawn_chance=0.0"
    " WHERE hex_type IN ('water','river','coast','desert','tundra','volcanic')",
    # #567: generic fallback enemy must not show the literal placeholder "Wróg".
    "UPDATE game_config_enemies SET label='Napastnik'"
    " WHERE key='enemy' AND lower(label) IN ('wróg','wrog','enemy','przeciwnik')",
    # #573: backfill the unified game_items FK on existing inventory rows (game_items.key
    # shares the legacy key namespace after the U11a backfill). Idempotent.
    "UPDATE character_inventory SET game_item_key = COALESCE(weapon_key, item_key, consumable_key)"
    " WHERE game_item_key IS NULL"
    " AND COALESCE(weapon_key, item_key, consumable_key) IN (SELECT key FROM game_items)",
    # #668: kolumna is_tester istniała na PROD, ale brak jej na DEV (auth miał fallback) —
    # przez to gating FAB raportu bugów był zawsze false i ikona znikała. Parytet DEV↔PROD.
    "ALTER TABLE users ADD COLUMN is_tester INTEGER NOT NULL DEFAULT 0",
    # #757: narracyjne pending itemy żyją w game_config_items (nie game_items), więc lista
    # plecaka nie rozwiązywała nazwy. Backfill zdenormalizowanej ci.label dla istniejących
    # wierszy (np. id 485 #99791) z katalogu game_config_items. Idempotentny.
    "UPDATE character_inventory SET label = ("
    "  SELECT label FROM game_config_items WHERE key = character_inventory.item_key)"
    " WHERE (label IS NULL OR TRIM(label) = '')"
    " AND item_key LIKE 'narrative_item_%'"
    " AND item_key IN (SELECT key FROM game_config_items)",
    # G1 (#785) — Multiplayer round tables + missing columns on campaigns/campaign_members.
    # campaign_rounds: tracks one collecting→narrating→done round per MP campaign.
    # campaign_round_actions: one row per player per round (UNIQUE round_id, user_id).
    """CREATE TABLE IF NOT EXISTS campaign_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'collecting',
        deadline TEXT,
        closed_at TEXT,
        narrative_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
    )""",
    """CREATE TABLE IF NOT EXISTS campaign_round_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL,
        campaign_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        character_id INTEGER,
        character_name TEXT NOT NULL,
        action_text TEXT NOT NULL,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(round_id, user_id),
        FOREIGN KEY (round_id) REFERENCES campaign_rounds(id)
    )""",
    # Indexes for sweep query performance
    "CREATE INDEX IF NOT EXISTS idx_campaign_rounds_status ON campaign_rounds(status, deadline)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_round_actions_round ON campaign_round_actions(round_id, user_id)",
    # Multiplayer columns on campaigns (already present for multiplayer.py to work)
    "ALTER TABLE campaigns ADD COLUMN round_timer_minutes INTEGER NOT NULL DEFAULT 1440",
    "ALTER TABLE campaigns ADD COLUMN round_timer_hours INTEGER NOT NULL DEFAULT 24",
    "ALTER TABLE campaigns ADD COLUMN max_players INTEGER NOT NULL DEFAULT 4",
    "ALTER TABLE campaigns ADD COLUMN host_user_id INTEGER",
    "ALTER TABLE campaigns ADD COLUMN lobby_status TEXT NOT NULL DEFAULT 'open'",
    "ALTER TABLE campaigns ADD COLUMN host_note TEXT",
    "ALTER TABLE campaigns ADD COLUMN template_id INTEGER",
    # Multiplayer columns on campaign_members
    "ALTER TABLE campaign_members ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted'",
    "ALTER TABLE campaign_members ADD COLUMN character_id INTEGER",
    # G5 (#789) — initiative_roll per action for conflict resolution ordering
    "ALTER TABLE campaign_round_actions ADD COLUMN initiative_roll INTEGER NOT NULL DEFAULT 0",
    # G19 (#800) — Spectators: policy on campaigns
    "ALTER TABLE campaigns ADD COLUMN spectator_policy TEXT NOT NULL DEFAULT 'none'",
    # G30 (#801) — client_action_id for request-level idempotency
    "ALTER TABLE campaign_round_actions ADD COLUMN client_action_id TEXT",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_round_action_client_id ON campaign_round_actions(client_action_id) WHERE client_action_id IS NOT NULL",
    # G27 (#808) — team quiet window (silence hours + IANA timezone)
    "ALTER TABLE campaigns ADD COLUMN quiet_start TEXT",
    "ALTER TABLE campaigns ADD COLUMN quiet_end TEXT",
    "ALTER TABLE campaigns ADD COLUMN team_tz TEXT",
]


def run_raw_migrations():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    logger.info("migration_db_path", db_path=DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for sql in RAW_MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
            logger.info("migration_applied", sql=sql)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg or "no such table" in msg:
                logger.info("migration_skipped", sql=sql, reason=str(e))
            else:
                logger.error("migration_error", sql=sql, error_message=str(e))
    conn.close()


def run_app_sql_migrations():
    """Apply optional SQL files from app/db/migrations/ (e.g. active_combat)."""
    mig_dir = Path(__file__).resolve().parent / "db" / "migrations"
    if not mig_dir.is_dir():
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        for path in sorted(mig_dir.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error("migration_sql_file_error", error_message=str(e))
        conn.rollback()
    finally:
        conn.close()


def _backfill_terrain_tags():
    """U28 — Uzupełnia terrain_tags na lokacjach bez tagów na podstawie biome/location_subtype/map_icon."""
    import json as _json

    SUBTYPE_TAGS = {
        "town": ["town", "plains"],
        "city": ["town", "plains"],
        "village": ["town", "plains"],
        "castle": ["castle", "hills"],
        "fort": ["castle", "hills"],
        "dungeon": ["dungeon", "cave", "ruins"],
        "ruins": ["ruins", "plains", "hills"],
        "cave": ["cave", "mountains", "hills"],
        "temple": ["ruins", "plains"],
        "camp": ["plains", "forest"],
        "tavern": ["town", "plains"],
    }
    ICON_TAGS = {
        "town": ["town", "plains"],
        "castle": ["castle", "hills"],
        "dungeon": ["dungeon", "cave"],
        "ruins": ["ruins", "plains"],
        "cave": ["cave", "mountains"],
    }
    BIOME_EXTRA = {
        "forest": "forest",
        "mountains": "mountains",
        "swamp": "swamp",
        "desert": "desert",
        "tundra": "tundra",
    }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT key, location_subtype, biome, map_icon FROM game_locations"
            " WHERE terrain_tags='[]' OR terrain_tags IS NULL"
        ).fetchall()
        for row in rows:
            subtype = (row["location_subtype"] or "").lower()
            biome = (row["biome"] or "").lower()
            icon = (row["map_icon"] or "").lower()

            tags = SUBTYPE_TAGS.get(subtype) or ICON_TAGS.get(icon)
            if not tags:
                tags = ["plains"]  # fallback

            extra = BIOME_EXTRA.get(biome)
            if extra and extra not in tags:
                tags = tags + [extra]

            conn.execute(
                "UPDATE game_locations SET terrain_tags=? WHERE key=?",
                (_json.dumps(tags), row["key"]),
            )
        conn.commit()
        logger.info("u28_terrain_tags_backfill", updated=len(rows))
    except Exception as exc:
        logger.warning("u28_terrain_tags_backfill_error", error=str(exc))
        conn.rollback()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging()
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    init_db()
    run_raw_migrations()
    run_app_sql_migrations()
    if os.getenv("AIGM_E2E_LITE") != "1":
        run_admin_migrations()
        hydrate_runtime_from_stored_preset()
        # E13 (#428) — ensure the generic encounter pool exists (idempotent).
        try:
            from app.services.encounter_seed_service import seed_generic_encounters
            seed_generic_encounters()
        except Exception:
            pass
        # U28 — backfill terrain_tags for locations that have none yet (idempotent).
        try:
            _backfill_terrain_tags()
        except Exception:
            pass
    # G1 (#785) + G9 (#793) — background sweep every 30s: expired narrative rounds + combat turns.
    async def _mp_sweep_loop() -> None:
        import asyncio as _asyncio
        while True:
            try:
                from app.services.multiplayer_round_service import (
                    sweep_expired_rounds,
                    sweep_expired_combat_turns,
                )
                await _asyncio.to_thread(sweep_expired_rounds)
                await _asyncio.to_thread(sweep_expired_combat_turns)
            except Exception as _e:
                logger.warning("mp_sweep_error", error=str(_e)[:200])
            await _asyncio.sleep(30)

    import asyncio as _asyncio
    _sweep_task = _asyncio.create_task(_mp_sweep_loop())

    yield

    # Shutdown
    _sweep_task.cancel()
    try:
        await _sweep_task
    except _asyncio.CancelledError:
        pass


app = FastAPI(title="AI Game Master PL", lifespan=lifespan)


def _get_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "https://aigm-dev.studio-colorbox.com,https://aigm.studio-colorbox.com")
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    reset_request_context(request_id=request_id)
    bind_context(route=request.url.path, method=request.method)
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request_complete",
            status_code=status_code,
            elapsed_ms=elapsed_ms,
        )

app.include_router(commands.router, prefix="/api")
app.include_router(dungeons_router, prefix="/api")
app.include_router(turns.router, prefix="/api")
app.include_router(campaign_history.router, prefix="/api")
app.include_router(campaign_memory.router, prefix="/api")
app.include_router(campaign_helpme.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(combat.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(npcs.router, prefix="/api")
app.include_router(shop.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(friends.router, prefix="/api")
app.include_router(mechanics.router, prefix="/api")
app.include_router(client_logs_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
# Keep non-prefixed character endpoints available for direct local calls
# (e.g. /characters/{id}/sheet), while preserving /api/* routes.
app.include_router(characters.router)
app.include_router(health_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(rules_content_router)  # already prefixed with /api internally
app.include_router(admin_analytics_router, prefix="/api")
app.include_router(admin_cheat_router, prefix="/api")
app.include_router(sandbox_router, prefix="/api")
app.include_router(rest_sandbox_router, prefix="/api")
app.include_router(admin_visual_router, prefix="/api")
app.include_router(visual_public_router, prefix="/api")
app.include_router(dice_config_admin_router, prefix="/api")
app.include_router(dice_config_public_router, prefix="/api")
app.include_router(admin_ui_texts_router, prefix="/api")
app.include_router(ui_texts_public_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(locations_router, prefix="/api")
app.include_router(session_location_router)
app.include_router(admin_location_router)
app.include_router(bg_images_router, prefix="/api")
app.include_router(dungeon_tiles_router, prefix="/api")
app.include_router(world_review_router)
app.include_router(admin_spectate_router)
app.include_router(smart_entry_router)
app.include_router(adventure_forge_router)
app.include_router(campaign_templates_router, prefix="/api")
app.include_router(hex_world_router)
app.include_router(hidden_traits_router, prefix="/api")
app.include_router(voice_public_router)
app.include_router(voice_admin_router)
app.include_router(admin_images_router)
app.include_router(bug_report_router, prefix="/api")
app.include_router(world_state_history_router, prefix="/api")
app.include_router(push_notifications_router, prefix="/api")
app.include_router(notify_prefs_router, prefix="/api")
app.include_router(seen_mechanics_router, prefix="/api")
app.include_router(multiplayer_router, prefix="/api")
app.include_router(party_chat_router, prefix="/api")
app.include_router(game_mechanics_router)
app.include_router(db_lint_router)
if os.getenv("AI_TEST_MODE") == "1":
    app.include_router(debug_router, prefix="/api")
    app.include_router(test_runner_router, prefix="/api")


Instrumentator().instrument(app).expose(app)

@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/api/games")
async def games(session: Session = Depends(get_session)):
    games = session.exec(select(Game).order_by(Game.updated_at.desc())).all()
    return games


@app.post("/api/games")
async def create_game(req: GameCreateReq, session: Session = Depends(get_session)):
    if req.system not in GAME_SYSTEMS:
        raise HTTPException(status_code=400, detail="Nieznany system gry")

    game = Game(title=req.title, system=req.system, model=req.model)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@app.get("/api/games/{game_id}")
async def get_game(game_id: int, session: Session = Depends(get_session)):
    game = session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    messages = session.exec(
        select(Message).where(Message.game_id == game_id).order_by(Message.created_at.asc())
    ).all()

    return {
        "game": game,
        "messages": messages,
    }


@app.post("/api/gm/dice")
@app.post("/gm/dice")
async def gm_dice(req: DiceReq):
    match = re.match(r"(\d*)?d(\d+)([+-]\d+)?", req.dice.strip(), re.I)
    if not match:
        raise HTTPException(status_code=400, detail="Użyj formatu np. d20, 2d6+3, d100")

    num = int(match.group(1) or 1)
    sides = int(match.group(2))
    base_mod = int(match.group(3) or 0)

    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls) + base_mod

    if req.character_id and req.roll_key and num == 1 and sides == 20:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (req.character_id,),
        ).fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Character not found")

        d20_roll = rolls[0]
        sheet = parse_character_sheet(row["sheet_json"])
        breakdown = build_gm_dice_breakdown(sheet, req.roll_key, d20_roll)
        if breakdown is None:
            raise HTTPException(status_code=404, detail="Unknown roll_key")

        final_total = breakdown["final_total"] + base_mod
        outcome = None
        if req.dc is not None:
            roll_type = str(breakdown.get("skill") or req.roll_key or "gm_dice")
            outcome = "hit" if final_total >= req.dc and "attack" in roll_type else None
            if outcome is None:
                outcome = "success" if final_total >= req.dc else "fail"
        logger.info(
            "dice_roll",
            roll_type=str(breakdown.get("skill") or req.roll_key or "gm_dice"),
            result=final_total,
            dc=req.dc,
            outcome=outcome,
            source="gm_dice",
        )

        return {
            "dice": req.dice.strip(),
            "rolls": rolls,
            "roll": d20_roll,
            "modifier": (final_total - d20_roll),
            "total": d20_roll,
            "dc": req.dc,
            "success": (final_total >= req.dc) if req.dc is not None else None,
            "breakdown": breakdown,
        }

    logger.info(
        "dice_roll",
        roll_type=req.roll_key or req.dice.strip(),
        result=total,
        dc=req.dc,
        outcome=("success" if req.dc is not None and total >= req.dc else "fail" if req.dc is not None else None),
        source="gm_dice",
    )
    return {"dice": req.dice.strip(), "rolls": rolls, "total": total}


@app.post("/api/gm/chat")
async def gm_chat(req: ChatReq, session: Session = Depends(get_session)):
    if req.game_system not in GAME_SYSTEMS:
        raise HTTPException(status_code=400, detail="Nieznany system gry")

    messages = [
        {"role": "system", "content": GAME_SYSTEMS[req.game_system]["prompt"]}
    ] + req.messages

    try:
        assistant_content = generate_chat(messages=messages, model=req.model)
        data = {"message": {"content": assistant_content}}

        if req.game_id:
            game = session.get(Game, req.game_id)
            if game:
                last_user_msg = req.messages[-1]["content"] if req.messages else ""
                if last_user_msg:
                    session.add(Message(game_id=req.game_id, role="user", content=last_user_msg))

                if assistant_content:
                    session.add(Message(game_id=req.game_id, role="assistant", content=assistant_content))

                game.updated_at = datetime.now(timezone.utc)
                session.commit()

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
