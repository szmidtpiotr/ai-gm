import os
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/admin/game-mechanics", tags=["game_mechanics"])

@router.get("/content", response_class=PlainTextResponse)
async def get_game_mechanics_content():
    """
    Serve game_mechanics.md with no-cache headers.
    Always fetches fresh from disk.
    """
    try:
        # Try multiple possible locations
        possible_paths = [
            "/app/game_mechanics.md",
            os.path.join(os.getcwd(), "game_mechanics.md"),
            "/home/piotrszmidt/ai-gm/game_mechanics.md",
        ]

        mechanics_path = None
        for p in possible_paths:
            if Path(p).exists():
                mechanics_path = Path(p)
                break

        if not mechanics_path:
            return PlainTextResponse(f"# Błąd\n\nPlik nie znaleziony. Szukano w: {possible_paths}", status_code=404)

        with open(mechanics_path, "r", encoding="utf-8") as f:
            content = f.read()

        response = PlainTextResponse(content)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        return PlainTextResponse(f"# Błąd\n\n{str(e)}", status_code=500)
