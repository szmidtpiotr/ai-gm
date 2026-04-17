from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import random
import re
import sqlite3
import json
import time
import uuid
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session, init_db
from app.models import Game, Message
from app.services.dice import build_gm_dice_breakdown, parse_character_sheet
from app.services.llm_service import generate_chat
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT

from app.api import auth, campaign_history, campaign_memory, campaigns, characters, commands, turns, mechanics
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.migrations_admin import run_admin_migrations
from app.routers.admin import router as admin_router
from app.routers.settings import router as settings_router


# Keep DB path consistent with API routers using raw sqlite connections.
DB_PATH = "/data/ai_gm.db"
logger = logging.getLogger("ai_gm")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": "backend",
            "env": os.getenv("ENV", "dev"),
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_structured_logging():
    root = logging.getLogger()
    if getattr(root, "_ai_gm_structured_logging", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root._ai_gm_structured_logging = True


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
    """
    CREATE TABLE IF NOT EXISTS campaign_ai_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        model_used TEXT,
        included_turn_count INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]


def run_raw_migrations():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    print(f"[migration] db path: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for sql in RAW_MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
            print(f"[migration] applied: {sql}")
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg or "no such table" in msg:
                print(f"[migration] skipped ({e}): {sql}")
            else:
                print(f"[migration] ERROR ({e}): {sql}")
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_structured_logging()
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    init_db()
    run_raw_migrations()
    run_admin_migrations()
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
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "route": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "elapsed_ms": elapsed_ms,
                }
            },
        )

app.include_router(commands.router, prefix="/api")
app.include_router(turns.router, prefix="/api")
app.include_router(campaign_history.router, prefix="/api")
app.include_router(campaign_memory.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(mechanics.router, prefix="/api")
# Keep non-prefixed character endpoints available for direct local calls
# (e.g. /characters/{id}/sheet), while preserving /api/* routes.
app.include_router(characters.router)
app.include_router(health_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(settings_router)


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
