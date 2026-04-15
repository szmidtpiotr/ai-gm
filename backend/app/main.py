from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import random
import re
import sqlite3

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api import campaigns, characters, commands, turns
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.db import get_session, init_db
from app.models import Game, Message


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

# Extract the file path from DATABASE_URL so both init_db() and raw migrations use the same file
_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/ai_gm.db")
if _DATABASE_URL.startswith("sqlite:///"):
    DB_PATH = _DATABASE_URL[len("sqlite:///"):]
else:
    DB_PATH = "/data/ai_gm.db"


GAME_SYSTEMS = {
    "fantasy": {
        "prompt": (
            "Jesteś Mistrzem Gry prostego systemu fantasy. "
            "Odpowiadasz po polsku. Prowadź przygodę w klimacie mrocznego, "
            "brudnego fantasy. Reaguj na działania gracza, zachowuj spójność świata, "
            "opisuj konsekwencje działań i czasem dawaj 2-3 sensowne opcje."
        )
    },
    "warhammer": {
        "prompt": (
            "Jesteś Mistrzem Gry Warhammer Fantasy Roleplay. "
            "Odpowiadasz po polsku. Klimat Starego Świata, mrok, brud, chaos, "
            "intryga. Używaj zasad d100."
        )
    },
    "cyberpunk": {
        "prompt": (
            "Jesteś Mistrzem Gry Cyberpunk RED. "
            "Odpowiadasz po polsku. Klimat Night City, edgerunnerzy, "
            "korporacje, slang cyberpunkowy."
        )
    },
    "neuroshima": {
        "prompt": (
            "Jesteś Mistrzem Gry Neuroshima. "
            "Odpowiadasz po polsku. Klimat post-apo Polski, Moloch, "
            "Hegemonia, brud i przemoc."
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
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    init_db()
    run_raw_migrations()
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

app.include_router(commands.router, prefix="/api")
app.include_router(turns.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
# Keep non-prefixed character endpoints available for direct local calls
# (e.g. /characters/{id}/sheet), while preserving /api/* routes.
app.include_router(characters.router)
app.include_router(health_router, prefix="/api")
app.include_router(models_router, prefix="/api")


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
        skill_to_stat = {
            "athletics": "STR",
            "melee_attack": "STR",
            "stealth": "DEX",
            "reflex_save": "DEX",
            "ranged_attack": "DEX",
            "fortitude_save": "CON",
            "arcana": "INT",
            "lore": "INT",
            "investigation": "INT",
            "arcane_save": "INT",
            "spell_attack": "INT",
            "awareness": "WIS",
            "survival": "WIS",
            "medicine": "WIS",
            "willpower_save": "WIS",
            "persuasion": "CHA",
            "intimidation": "CHA",
        }
        aliases = {
            "str_save": "fortitude_save",
            "dex_save": "reflex_save",
            "int_save": "arcane_save",
            "wis_save": "willpower_save",
            "cha_save": "persuasion",
            "con_save": "fortitude_save",
            "attack": "melee_attack",
        }
        normalized_key = req.roll_key.strip().lower().replace("-", "_")
        normalized_key = normalized_key.replace(" ", "_")
        normalized_key = aliases.get(normalized_key, normalized_key)

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (req.character_id,),
        ).fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Character not found")

        try:
            sheet = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
        except Exception:
            sheet = {}

        stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
        skills = sheet.get("skills") if isinstance(sheet.get("skills"), dict) else {}

        stat_name = skill_to_stat.get(normalized_key)
        stat_value = 10
        if stat_name:
            stat_value = int(
                stats.get(
                    stat_name,
                    stats.get(stat_name.lower(), 10),
                )
            )
        stat_modifier = (stat_value - 10) // 2
        skill_rank = int(skills.get(normalized_key, 0))
        proficiency_bonus = 2 if skill_rank >= 3 else 0
        computed_modifier = stat_modifier + skill_rank + proficiency_bonus + base_mod
        d20_roll = rolls[0]
        total = d20_roll + computed_modifier

        return {
            "dice": req.dice.strip(),
            "rolls": rolls,
            "roll": d20_roll,
            "modifier": computed_modifier,
            "total": total,
            "dc": req.dc,
            "success": (total >= req.dc) if req.dc is not None else None,
            "breakdown": {
                "roll_key": normalized_key,
                "stat": stat_name,
                "stat_value": stat_value,
                "stat_modifier": stat_modifier,
                "skill_rank": skill_rank,
                "proficiency_bonus": proficiency_bonus,
                "base_modifier": base_mod,
            },
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
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": req.model,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if req.game_id:
            game = session.get(Game, req.game_id)
            if game:
                last_user_msg = req.messages[-1]["content"] if req.messages else ""
                if last_user_msg:
                    session.add(Message(game_id=req.game_id, role="user", content=last_user_msg))

                assistant_content = data.get("message", {}).get("content", "")
                if assistant_content:
                    session.add(Message(game_id=req.game_id, role="assistant", content=assistant_content))

                game.updated_at = datetime.now(timezone.utc)
                session.commit()

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")
