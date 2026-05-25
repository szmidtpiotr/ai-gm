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
    turns,
    mechanics,
    inventory,
    npcs,
    shop,
)
from app.api.dungeons import router as dungeons_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.client_logs import router as client_logs_router
from app.api.knowledge import router as knowledge_router
from app.migrations_admin import run_admin_migrations
from app.services.llm_admin_service import hydrate_runtime_from_stored_preset
from app.routers.admin import router as admin_router
from app.routers.admin_cheat import router as admin_cheat_router
from app.routers.sandbox import router as sandbox_router
from app.routers.rest_sandbox import router as rest_sandbox_router
from app.routers.admin_visual import admin_router as admin_visual_router, public_router as visual_public_router
from app.routers.settings import router as settings_router
from app.routers.debug import router as debug_router
from app.routers.test_runner import router as test_runner_router
from app.routers.locations import router as locations_router
from app.routers.session_location import router as session_location_router
from app.routers.admin_location import router as admin_location_router
from app.routers.bg_images import router as bg_images_router
from app.routers.admin_analytics import router as admin_analytics_router
from app.routers.world_review import router as world_review_router
from app.routers.ideas_workshop import router as ideas_workshop_router
from app.routers.campaign_workshop import router as campaign_workshop_router
from app.routers.smart_entry import router as smart_entry_router
from app.routers.hex_world import router as hex_world_router


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
    "UPDATE npcs SET is_ally = 1        WHERE npc_type = 'ally'        AND is_ally = 0",
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
    run_admin_migrations()
    hydrate_runtime_from_stored_preset()
    yield
    # Shutdown (nothing needed)


app = FastAPI(title="AI Game Master PL", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(mechanics.router, prefix="/api")
app.include_router(client_logs_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
# Keep non-prefixed character endpoints available for direct local calls
# (e.g. /characters/{id}/sheet), while preserving /api/* routes.
app.include_router(characters.router)
app.include_router(health_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(admin_analytics_router, prefix="/api")
app.include_router(admin_cheat_router, prefix="/api")
app.include_router(sandbox_router, prefix="/api")
app.include_router(rest_sandbox_router, prefix="/api")
app.include_router(admin_visual_router, prefix="/api")
app.include_router(visual_public_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(locations_router, prefix="/api")
app.include_router(session_location_router)
app.include_router(admin_location_router)
app.include_router(bg_images_router, prefix="/api")
app.include_router(world_review_router)
app.include_router(ideas_workshop_router)
app.include_router(campaign_workshop_router)
app.include_router(smart_entry_router)
app.include_router(hex_world_router)
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
