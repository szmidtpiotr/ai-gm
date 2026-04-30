import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

import stt as stt_module
import tts as tts_module
from config import load_config, save_config

app = FastAPI(title="voice-service", version="1.0.0")


@app.get("/voice/healthz")
def healthz() -> dict[str, object]:
    cfg = load_config()
    voices = tts_module.list_voices()
    return {
        "status": "ok",
        "tts_voice": cfg["tts_voice"],
        "stt_model": cfg["stt_model"],
        "tts_loaded": cfg["tts_voice"] in voices,
        "stt_loaded": True,
        "available_voices": voices,
    }


@app.get("/voice/tts")
def get_tts(
    text: str = Query(..., max_length=2000),
    voice: Optional[str] = None,
    speed: Optional[float] = None,
) -> Response:
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    try:
        audio = tts_module.synthesize(text, voice=voice, speed=speed)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive mapping
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/wav")


@app.get("/voice/voices")
def get_voices() -> dict[str, list[str]]:
    return {"voices": tts_module.list_voices()}


class ConfigUpdate(BaseModel):
    tts_enabled: Optional[bool] = None
    stt_enabled: Optional[bool] = None
    tts_voice: Optional[str] = None
    tts_speed: Optional[float] = None
    tts_noise_scale: Optional[float] = None
    tts_noise_w: Optional[float] = None
    stt_model: Optional[str] = None
    stt_language: Optional[str] = None
    stt_beam_size: Optional[int] = None
    vad_filter: Optional[bool] = None


@app.get("/voice/config")
def get_config() -> dict[str, object]:
    return load_config()


@app.post("/voice/config")
def post_config(update: ConfigUpdate) -> dict[str, object]:
    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    if "stt_model" in changes or "stt_language" in changes:
        stt_module.reload_model()
    return save_config(changes)


@app.websocket("/voice/stt")
async def websocket_stt(ws: WebSocket) -> None:
    await ws.accept()
    buffer = bytearray()
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_bytes(), timeout=2.0)
                buffer.extend(data)
            except asyncio.TimeoutError:
                if buffer:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, stt_module.transcribe, bytes(buffer))
                    await ws.send_json(result)
                    buffer.clear()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - websocket defensive path
        await ws.send_json({"error": str(exc)})
