from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import random
import re
import os

# Use Docker service name or env var
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

app = FastAPI(title="AI Game Master PL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GAME_SYSTEMS = {
    "warhammer": {
        "prompt": "Jesteś Mistrzem Gry Warhammer Fantasy Roleplay. Odpowiadasz po polsku. Klimat Starego Świata, mrok, brud, chaos, intryga. Używaj zasad d100."
    },
    "cyberpunk": {
        "prompt": "Jesteś Mistrzem Gry Cyberpunk RED. Odpowiadasz po polsku. Klimat Night City, edgerunnerzy, korporacje, slang cyberpunkowy."
    },
    "neuroshima": {
        "prompt": "Jesteś Mistrzem Gry Neuroshima. Odpowiadasz po polsku. Klimat post-apo Polski, Moloch, Hegemonia, brud i przemoc."
    },
}

class ChatReq(BaseModel):
    model: str
    messages: list[dict]
    game_system: str = "warhammer"

class DiceReq(BaseModel):
    dice: str

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "ollama": OLLAMA_BASE_URL}

@app.get("/games")
async def games():
    return [{"id": k, "name": k} for k in GAME_SYSTEMS.keys()]

@app.post("/gm/dice")
async def gm_dice(req: DiceReq):
    # Fixed regex - no double-escapes
    match = re.match(r"(\d*)?d(\d+)([+-]\d+)?", req.dice.strip(), re.I)
    if not match:
        raise HTTPException(status_code=400, detail=f"Nieprawidłowy format: '{req.dice.strip()}' (np. d20, 2d6+3, d100)")

    num = int(match.group(1) or 1)
    sides = int(match.group(2))
    mod = int(match.group(3) or 0)

    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls) + mod

    return {"dice": req.dice.strip(), "rolls": rolls, "total": total}
@app.post("/gm/chat")
async def gm_chat(req: ChatReq):
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
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")