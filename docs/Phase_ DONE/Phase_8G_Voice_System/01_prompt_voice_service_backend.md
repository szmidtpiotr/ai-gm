<!-- STATUS: IN_PROGRESS -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 01 — Voice Service Backend (Piper TTS + Whisper STT)

> Workflow: REV 2 gotowy — Cursor implementuje.

## Cel

Stworzenie nowego, izolowanego mirkoserwisu `voice-service` jako osobnego kontenera Docker.
Serwis obsługuje:
1. **TTS** — konwersja tekstu na mowę przez Piper TTS (model polski)
2. **STT** — transkrypcja audio na tekst przez faster-whisper (model small, język pl)
3. **Config API** — odczyt i zapis konfiguracji runtime (głos, model, parametry)

Serwis jest **całkowicie niezależny** od backendu gry — zero zmian w `backend/app/`.

## Kontekst techniczny

- Repo: `szmidtpiotr/ai-gm`, host: `piotrszmidt@192.168.1.61`
- Branch: `phase-8g-voice-system`
- Stack: Docker Compose, FastAPI/Python
- Nowy katalog: `voice-service/` w root repo
- Nowy port: `8300` (wolny, potwierdzono)
- Przestrzeń dyskowa: ~62 GB wolne z 80 GB — modele (~1.5 GB) bez problemu
- NIE ruszamy: `backend/`, `data/ai_gm.db`, `docker-compose.yml`, `docker-compose.dev.yml`

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Czy katalog `voice-service/` już istnieje? (`ls -la voice-service/`)
2. Czy port 8300 jest wolny? (`ss -tlnp | grep 8300`)
3. Czy jesteś na właściwym branchu? (`git branch --show-current`)
4. Czy są niezacommitowane zmiany? (`git status`)
5. Czy Python 3.11 jest dostępny na hoście? (`python3.11 --version`)
6. Ile wolnej przestrzeni dyskowej? (`df -h /home/piotrszmidt/ai-gm`)
7. Czy `piper-tts` jest dostępne przez pip? (`pip show piper-tts`)

## Odpowiedzi Cursora (REV 1)

1. **`voice-service/`** — NIE istnieje. ✅ Tworzymy od zera.
2. **Port 8300** — wolny. ✅
3. **Branch** — `phase-8g-voice-system`. ✅
4. **Niezacommitowane zmiany** — brak. ✅
5. **Python 3.11 na hoście** — NIE dostępny. ⚠️ Nie ma znaczenia — wszystko budujemy w Dockerze (`python:3.11-slim`).
6. **Przestrzeń dyskowa** — ~62 GB wolne. ✅
7. **`piper-tts` przez pip** — NIE zainstalowane. ⚠️ Instalujemy w Dockerfile. Piper nie ma oficjalnego pipa — używamy binarki lub `piper-tts` z PyPI (patrz REV 2).

---

# ✅ IMPLEMENTACJA REV 2 — Cursor wykonuje

> Wszystkie blokery wyjaśnione. Python 3.11 tylko w kontenerze (nie na hoście — bez znaczenia).
> `piper-tts` instalujemy jako pakiet PyPI (`piper-tts>=1.2.0`) lub przez binarki — patrz Dockerfile poniżej.

## Krok 1 — Utwórz strukturę katalogów

```bash
mkdir -p voice-service/models/tts
mkdir -p voice-service/models/stt
mkdir -p voice-service/tests
touch voice-service/models/.gitkeep
```

Dodaj do `.gitignore`:
```
voice-service/models/tts/*.onnx
voice-service/models/tts/*.onnx.json
voice-service/models/stt/
```

## Krok 2 — `voice-service/requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9
websockets==12.0
faster-whisper==1.0.3
piper-tts==1.2.0
numpy==1.26.4
soundfile==0.12.1
```

> **Uwaga:** Jeśli `piper-tts` z PyPI nie istnieje lub jest niezgodny, użyj podejścia z binarką:
> W Dockerfile pobierz binarke `piper` z GitHub releases i wrzuc do `/usr/local/bin/piper`.
> Szczegóły w sekcji Dockerfile poniżej.

## Krok 3 — `voice-service/config.json`

```json
{
  "tts_enabled": true,
  "stt_enabled": true,
  "tts_voice": "pl_PL-darkman-medium",
  "tts_speed": 1.0,
  "tts_noise_scale": 0.667,
  "tts_noise_w": 0.8,
  "stt_model": "small",
  "stt_language": "pl",
  "stt_beam_size": 5,
  "vad_filter": true
}
```

## Krok 4 — `voice-service/config.py`

```python
import json, os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.getenv("VOICE_CONFIG_PATH", "/app/config.json"))

DEFAULTS = {
    "tts_enabled": True,
    "stt_enabled": True,
    "tts_voice": "pl_PL-darkman-medium",
    "tts_speed": 1.0,
    "tts_noise_scale": 0.667,
    "tts_noise_w": 0.8,
    "stt_model": "small",
    "stt_language": "pl",
    "stt_beam_size": 5,
    "vad_filter": True,
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return {**DEFAULTS, **data}
    return DEFAULTS.copy()

def save_config(updates: dict) -> dict:
    cfg = load_config()
    cfg.update(updates)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    return cfg
```

## Krok 5 — `voice-service/tts.py`

```python
import subprocess, tempfile, re, os
from pathlib import Path
from config import load_config

MODELS_DIR = Path(os.getenv("VOICE_MODELS_DIR", "/app/models/tts"))
PIPER_BIN = os.getenv("PIPER_BIN", "piper")

def _clean_text(text: str) -> str:
    """Usuń [ROLL: ...] i ogranicz długość."""
    text = re.sub(r'\[ROLL:[^\]]*\]', '', text).strip()
    return text[:2000]

def synthesize(text: str, voice: str = None, speed: float = None) -> bytes:
    cfg = load_config()
    voice = voice or cfg["tts_voice"]
    speed = speed or cfg["tts_speed"]
    noise_scale = cfg["tts_noise_scale"]
    noise_w = cfg["tts_noise_w"]

    text = _clean_text(text)
    if not text:
        raise ValueError("Empty text after cleanup")

    model_path = MODELS_DIR / f"{voice}.onnx"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_f:
        out_path = out_f.name

    try:
        cmd = [
            PIPER_BIN,
            "--model", str(model_path),
            "--output_file", out_path,
            "--length_scale", str(1.0 / speed),  # piper używa length_scale
            "--noise_scale", str(noise_scale),
            "--noise_w", str(noise_w),
        ]
        result = subprocess.run(
            cmd, input=text.encode("utf-8"),
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper error: {result.stderr.decode()}")
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)

def list_voices() -> list[str]:
    return [p.stem for p in MODELS_DIR.glob("*.onnx")]
```

## Krok 6 — `voice-service/stt.py`

```python
import io, os
from pathlib import Path
from faster_whisper import WhisperModel
from config import load_config

MODELS_DIR = Path(os.getenv("VOICE_MODELS_DIR_STT", "/app/models/stt"))
_model_cache: dict = {}

def get_model(model_name: str = None) -> WhisperModel:
    cfg = load_config()
    name = model_name or cfg["stt_model"]
    if name not in _model_cache:
        _model_cache[name] = WhisperModel(
            name,
            device="cpu",
            compute_type="int8",
            download_root=str(MODELS_DIR),
        )
    return _model_cache[name]

def transcribe(audio_bytes: bytes) -> dict:
    cfg = load_config()
    model = get_model(cfg["stt_model"])
    audio_io = io.BytesIO(audio_bytes)
    segments, info = model.transcribe(
        audio_io,
        language=cfg["stt_language"] if cfg["stt_language"] != "auto" else None,
        beam_size=cfg["stt_beam_size"],
        vad_filter=cfg["vad_filter"],
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {"text": text, "language": info.language, "confidence": round(info.language_probability, 3)}

def reload_model():
    """Wyładuj cache modeli (wywołaj po zmianie konfiguracji)."""
    _model_cache.clear()
```

## Krok 7 — `voice-service/main.py`

```python
import asyncio
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import tts as tts_module
import stt as stt_module
from config import load_config, save_config

app = FastAPI(title="voice-service", version="1.0.0")

# --- Health ---

@app.get("/voice/healthz")
def healthz():
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

# --- TTS ---

@app.get("/voice/tts")
def get_tts(
    text: str = Query(..., max_length=2000),
    voice: Optional[str] = None,
    speed: Optional[float] = None,
):
    if not text.strip():
        raise HTTPException(400, "Empty text")
    try:
        audio = tts_module.synthesize(text, voice=voice, speed=speed)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    return Response(content=audio, media_type="audio/wav")

# --- Voices ---

@app.get("/voice/voices")
def get_voices():
    return {"voices": tts_module.list_voices()}

# --- Config ---

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
def get_config():
    return load_config()

@app.post("/voice/config")
def post_config(update: ConfigUpdate):
    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    if "stt_model" in changes or "stt_language" in changes:
        stt_module.reload_model()
    return save_config(changes)

# --- STT WebSocket ---

@app.websocket("/voice/stt")
async def websocket_stt(ws: WebSocket):
    await ws.accept()
    buffer = bytearray()
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_bytes(), timeout=2.0)
                buffer.extend(data)
            except asyncio.TimeoutError:
                if buffer:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, stt_module.transcribe, bytes(buffer)
                    )
                    await ws.send_json(result)
                    buffer.clear()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_json({"error": str(e)})
```

## Krok 8 — `voice-service/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps dla piper binary + audio
RUN apt-get update && apt-get install -y \
    wget curl ca-certificates \
    libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Pobierz piper binary (amd64 linux)
RUN wget -q https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
    -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /tmp \
    && mv /tmp/piper/piper /usr/local/bin/piper \
    && chmod +x /usr/local/bin/piper \
    && rm -rf /tmp/piper*

# Python deps (bez piper-tts PyPI — używamy binarki)
COPY requirements.txt .
RUN pip install --no-cache-dir faster-whisper==1.0.3 fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 python-multipart==0.0.9 \
    websockets==12.0 numpy==1.26.4 soundfile==0.12.1

# Pobierz model Whisper small przy buildzie
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/app/models/stt')"

# Pobierz głosy Piper PL przy buildzie
RUN mkdir -p /app/models/tts && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx \
        -O /app/models/tts/pl_PL-darkman-medium.onnx && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx.json \
        -O /app/models/tts/pl_PL-darkman-medium.onnx.json && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx \
        -O /app/models/tts/pl_PL-gosia-medium.onnx && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx.json \
        -O /app/models/tts/pl_PL-gosia-medium.onnx.json

COPY . .

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300", "--workers", "2"]
```

> **Uwaga do buildu:** Model Whisper i głosy Piper są pobierane podczas `docker build` (~1.5 GB).
> Build może trwać 5–10 minut przy pierwszym uruchomieniu. Docelowo można wrzucić do volume Docker.

## Krok 9 — Weryfikacja po implementacji

Po zbudowaniu kontenera (przed PROMPT 02 — nginx/docker-compose) przetestuj lokalnie:

```bash
# Zbuduj i uruchom testowo
cd voice-service
docker build -t voice-service-test .
docker run --rm -p 8300:8300 voice-service-test &

# Sprawdź health
curl http://localhost:8300/voice/healthz

# Test TTS — zapisz WAV
curl "http://localhost:8300/voice/tts?text=Witaj+wędrowcze" --output /tmp/test.wav
ls -lh /tmp/test.wav  # powinien być > 0 bytes

# Test voices
curl http://localhost:8300/voice/voices

# Test config
curl http://localhost:8300/voice/config

# Zatrzymaj kontener
docker stop $(docker ps -q --filter ancestor=voice-service-test)
```

Jeśli wszystkie komendy zwracają poprawną odpowiedź — przejdź do PROMPT 02.

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Utworzono nowy katalog `voice-service/` z plikami:
  - `main.py` (FastAPI: `/voice/healthz`, `/voice/tts`, `/voice/voices`, `/voice/config`, WebSocket `/voice/stt`)
  - `config.py` + `config.json`
  - `tts.py` (Piper)
  - `stt.py` (faster-whisper)
  - `Dockerfile`, `requirements.txt`, `tests/.gitkeep`, `models/.gitkeep`
- Dodano wpisy do `.gitignore` dla modeli runtime:
  - `voice-service/models/tts/*.onnx`
  - `voice-service/models/tts/*.onnx.json`
  - `voice-service/models/stt/`
- Build obrazu `voice-service-test` zakończony powodzeniem.
- Smoke testy zakończone powodzeniem:
  - `GET /voice/healthz` -> `status: ok`
  - `GET /voice/voices` -> zwraca głosy PL
  - `GET /voice/config` -> zwraca config domyślny
  - `GET /voice/tts?text=...` -> zwraca poprawny WAV (`audio/wav`)
- Naprawiono błędy runtime wykryte podczas testów:
  - dodano `requests` (wymagane przez `faster-whisper` przy preload modelu),
  - dodano `libespeak-ng1`,
  - poprawiono instalację binarki Piper wraz z bibliotekami współdzielonymi (`/opt/piper`, `LD_LIBRARY_PATH`).

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Po raporcie Cursora)*
