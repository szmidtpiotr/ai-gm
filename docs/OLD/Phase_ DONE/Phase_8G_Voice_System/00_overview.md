# Phase 8G — Voice System (TTS/STT)

> Status 2026-04-30: PROMPT 01-04 wdrożone, w tym zakładka "Głos" w admin panelu.

## Cel fazy

Wdrożenie systemu głosowego do gry RPG AI-GM:
- **TTS (Text-to-Speech):** odpowiedzi GM czytane głosem przez Piper TTS (self-hosted)
- **STT (Speech-to-Text):** gracz mówi do mikrofonu → Whisper transkrybuje → tekst idzie do gry jako normalna wiadomość
- **Panel admina:** zakładka `Głos` w istniejącym `/panel/` do konfiguracji głosu GM, modelu Whisper, parametrów

## Architektura

```
[Frontend JS — frontend/js/voice.js + frontend/js/ui.js]
  ├─ GM odpowiedź → GET /voice/tts?text=...  → Piper TTS → audio/wav → Audio/WebAudio playback
  └─ MediaRecorder mic → WebSocket /voice/stt  → Whisper → {text} → input + auto-send

[Frontend JS — admin_panel/sections/voice.js]
  └─ GET/POST /voice/config  → settings: model, głos, speed, noise, enabled + progi auto-stop STT

[voice-service — nowy kontener Docker]
  ├─ FastAPI na porcie 8300
  ├─ /voice/tts  — Piper TTS
  ├─ /voice/stt  — faster-whisper
  ├─ /voice/config GET/POST — konfiguracja runtime
  └─ /voice/healthz
```

## Pliki których dotyczy faza

**Nowe pliki:**
- `voice-service/` — nowy serwis (Dockerfile, main.py, tts.py, stt.py, config.py, config.json)
- `frontend/js/voice.js` — główna logika TTS/STT po stronie gry
- `frontend/admin_panel/sections/voice.js` — nowa sekcja panelu admina
- `frontend/nginx.conf` — proxy `/voice/` → voice-service:8300

**Modyfikowane pliki:**
- `docker-compose.yml` + `docker-compose.dev.yml` — kontener `voice-service`
- `frontend/index.html` — UI przycisków voice + podpięcie `voice.js`
- `frontend/styles.css` — style TTS/STT + debug overlay
- `frontend/js/ui.js` — hooki bąbelków GM i statusów
- `frontend/admin_panel/index.html` — dodanie zakładki nav
- `voice-service/main.py`, `voice-service/config.py`, `voice-service/config.json` — config API i parametry STT auto-stop

**NIE ruszamy:**
- `data/ai_gm.db` — żadnych migracji
- `backend/app/` — bez zmian funkcjonalnych Voice w gameplay loop
- `backend/prompts/system_prompt.txt` — bez zmian
- Docker volumes z danymi gry

## Kolejność promptów

| # | Plik | Zakres |
|---|---|---|
| 01 | `01_prompt_voice_service_backend.md` | Kontener voice-service: FastAPI + Piper TTS + Whisper STT |
| 02 | `02_prompt_nginx_docker.md` | docker-compose + nginx proxy dla voice-service |
| 03 | `03_prompt_frontend_game_integration.md` | `frontend/js/voice.js` + UI voice, WebSocket STT, TTS playback |
| 04 | `04_prompt_admin_panel_voice.md` | Panel admina — zakładka Głos, konfiguracja, test głosu |
| 05 | `05_prompt_tests.md` | Testy integracyjne voice-service |

## Zależności między promptami

```
01 (voice-service backend)
  └─ 02 (docker + nginx)  ← wymaga działającego serwisu
      └─ 03 (frontend voice.js + ui.js)    ← wymaga endpointów
       └─ 04 (admin panel) ← wymaga /voice/config endpoint
            └─ 05 (testy)
```

## Konfiguracja modeli (domyślna)

- STT: `faster-whisper`, model `small`, język `pl`, int8
- TTS: `piper`, głos `pl_PL-darkman-medium`
- Głosy do wyboru w panelu: `pl_PL-darkman-medium`, `pl_PL-bass-high` (+ zależnie od wolumenu także `pl_PL-gosia-medium`)
- Parametry TTS: `length_scale` (speed: 0.5–2.0), `noise_scale` (ekspresja), `noise_w`
- Parametry STT auto-stop (admin): `stt_silence_auto_stop_ms`, `stt_min_voice_rms_threshold`, `stt_noise_multiplier`

## Zasoby VM (po rozszerzeniu)

Rekomendowane dla tego kontenera: **4 vCPU, 6 GB RAM**
- Whisper small (int8): ~1 GB RAM
- Piper + model PL: ~512 MB RAM
- FastAPI overhead: ~256 MB
- Bufor: ~4 GB
