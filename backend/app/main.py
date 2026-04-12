from datetime import datetime, timezone
import os
import random
import re

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
from app.api import turns



OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

app = FastAPI(title="AI Game Master PL")

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
app.include_router(health_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(turns.router, prefix="/campaigns", tags=["turns"])


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


class GameCreateReq(BaseModel):
    title: str
    system: str
    model: str = "gemma3:1b"


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/games")
async def games(session: Session = Depends(get_session)):
    games = session.exec(select(Game).order_by(Game.updated_at.desc())).all()
    return games


@app.post("/games")
async def create_game(req: GameCreateReq, session: Session = Depends(get_session)):
    if req.system not in GAME_SYSTEMS:
        raise HTTPException(status_code=400, detail="Nieznany system gry")

    game = Game(title=req.title, system=req.system, model=req.model)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@app.get("/games/{game_id}")
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


@app.post("/gm/dice")
async def gm_dice(req: DiceReq):
    match = re.match(r"(\d*)?d(\d+)([+-]\d+)?", req.dice.strip(), re.I)
    if not match:
        raise HTTPException(status_code=400, detail="Użyj formatu np. d20, 2d6+3, d100")

    num = int(match.group(1) or 1)
    sides = int(match.group(2))
    mod = int(match.group(3) or 0)

    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls) + mod

    return {"dice": req.dice.strip(), "rolls": rolls, "total": total}


@app.post("/gm/chat")
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