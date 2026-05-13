# Phase 8G — Voice System · Brief

> Zamkniecie fazy 8G (voice-service + integracja frontend + admin panel Voice).

---

## Workflow Perplexity + Cursor

Pelny opis: [`00_WORKFLOW_PERPLEXITY_CURSOR.md`](../00_WORKFLOW_PERPLEXITY_CURSOR.md)

Skrot:
1. Perplexity tworzy brief + prompty REV 1.
2. Cursor odpowiada na pytania blokujace.
3. Perplexity publikuje REV 2.
4. Cursor implementuje, testuje i deployuje.
5. Po zamknieciu fazy brief zawiera raport koncowy.

---

<!-- STATUS: DONE -->
<!-- PHASE: 8G | DATE_START: 2026-04-30 | DATE_END: 2026-04-30 -->

## 1. Cel fazy

Dostarczyc kompletny system glosowy dla gry AI-GM:
- TTS (Piper) dla odpowiedzi GM,
- STT (faster-whisper) dla inputu gracza,
- integracja przez nginx + docker compose (DEV/PROD),
- panel admina do konfiguracji Voice.

**Definicja ukonczenia (DoD):**
- [x] voice-service dziala i expose: `/voice/healthz`, `/voice/tts`, `/voice/stt`, `/voice/config`, `/voice/voices`
- [x] frontend ma dzialajace TTS + STT (nagrywanie, transkrypcja, autosend)
- [x] admin panel ma sekcje "Glos" z zapisem config
- [x] healthcheck DEV OK
- [x] test manualny wykonany (uzytkownik potwierdzil dzialanie TTS/STT; pozostalo dalsze strojenie auto-stop pod urzadzenie)

## 2. Zakres

| # | Komponent | Opis | Priorytet |
|---|---|---|---|
| 1 | `voice-service` | mikroserwis FastAPI dla TTS/STT + config API | 🔴 Must |
| 2 | Frontend gry | UI toggles glosu, playback TTS, nagrywanie STT, debug status | 🔴 Must |
| 3 | Infra DEV/PROD | docker-compose + nginx `/voice/*` proxy + deploy | 🔴 Must |
| 4 | Admin panel Voice | nowa zakladka do konfiguracji TTS/STT i testu glosu | 🟡 Should |
| 5 | Dodatkowe glosy | dodanie `pl_PL-bass-high` | 🟢 Nice to have |

**Out of scope:**
- trenowanie nowych modeli glosowych (osobna faza 8I),
- zmiany silnika gry poza integracja voice hooks.

## 3. Zaleznosci

| Zaleznosc | Status | Gdzie |
|---|---|---|
| Voice endpoints backend | ✅ | `voice-service/main.py` |
| Nginx proxy `/voice/*` | ✅ | host `192.168.1.4`, conf NPM |
| Frontend hook wiadomości GM | ✅ | `frontend/js/voice.js`, `frontend/js/ui.js` |
| Admin panel lazy sections | ✅ | `frontend/admin_panel/index.html`, `sections/voice.js` |

## 4. Reguly biznesowe

- TTS i STT maja globalne flagi (admin) oraz lokalne zachowanie UI.
- Frontend ma dzialac defensywnie: brak glosu nie moze wywalic chatu.
- STT wysyla transkrypt do input i moze auto-send.
- Parametry auto-stop ciszy STT sa konfigurowalne przez `/voice/config`.

## 5. Architektura

### Nowe pliki
```
voice-service/main.py
voice-service/config.py
voice-service/tts.py
voice-service/stt.py
voice-service/config.json
voice-service/requirements.txt
voice-service/Dockerfile
frontend/js/voice.js
frontend/admin_panel/sections/voice.js
```

### Modyfikowane pliki
```
docker-compose.yml
docker-compose.dev.yml
frontend/index.html
frontend/nginx.conf
frontend/styles.css
frontend/js/ui.js
frontend/admin_panel/index.html
frontend/admin_panel/layout.css
voice-service/config.json
voice-service/config.py
voice-service/main.py
voice-service/Dockerfile
```

### NIE ruszamy
```
backend/app/ (poza niezbednym API health wykorzystanym juz istniejaco)
data/ai_gm.db
```

## 6. API kontrakty

```http
GET /voice/healthz
response: {
  "status": "ok",
  "tts_loaded": true|false,
  "stt_loaded": true|false,
  "tts_voice": "...",
  "stt_model": "...",
  "available_voices": [...]
}
```

```http
GET /voice/tts?text=...&voice=...&speed=...
response: audio/wav
```

```http
WS /voice/stt
request: audio chunks (bytes) + "__end__"
response: {"text": "...", "language": "...", "confidence": ...} | {"error": "..."}
```

```http
GET /voice/config
POST /voice/config
request fields (subset):
{
  "tts_enabled": bool,
  "stt_enabled": bool,
  "tts_voice": str,
  "tts_speed": float,
  "tts_noise_scale": float,
  "tts_noise_w": float,
  "stt_model": str,
  "stt_language": str,
  "stt_beam_size": int,
  "stt_silence_auto_stop_ms": int,
  "stt_min_voice_rms_threshold": float,
  "stt_noise_multiplier": float
}
```

## 7. UI/UX

- Sidebar: przyciski TTS/MIC.
- Input chat: przycisk mikrofonu (start/stop nasluchu).
- Bubble GM: ikona glosu i status czytania.
- Overlay debug: status TTS/STT (`Czytam`, `Nagrywanie`, `Transkrypcja gotowa`, itd.).
- Admin panel `/panel/`: sekcja "Glos" do strojenia runtime.

## 8. Testy wymagane

```bash
# smoke DEV voice API
curl -sf http://127.0.0.1:8300/voice/healthz
curl -sf "http://127.0.0.1:8300/voice/tts?text=Test" -o /tmp/tts.wav
curl -sf http://127.0.0.1:8300/voice/voices
```

```bash
# smoke przez dev domain
curl -sf https://aigm-dev.studio-colorbox.com/voice/healthz
```

## 9. Weryfikacja manualna (DEV)

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
curl -sf http://localhost:8300/voice/healthz && echo "VOICE OK"
```

Manual:
1. Wejdz na `https://aigm-dev.studio-colorbox.com/`.
2. Wlacz TTS -> GM odpowiedz jest czytana.
3. Wlacz MIC -> transkrypcja trafia do input i auto-send dziala.
4. Wejdz na `/panel/` -> sekcja "Glos" widoczna i zapis config dziala.

## 10. Podsumowanie wdrozenia (Cursor)

- Co zrobiono:
  - wdrozone voice-service (TTS/STT/config),
  - podpiete compose + nginx proxy,
  - zintegrowane UI voice w grze,
  - dodana sekcja admin panel Voice,
  - dodany model `pl_PL-bass-high`.
- Co nie weszlo:
  - brak finalnej automatycznej kalibracji progow ciszy per urządzenie (wymaga dalszego tuningu runtime).
- Odchylenia:
  - konieczne byly iteracyjne hotfixy STT autoplay/websocket/EOF i cache-busting frontend.
- Wyniki testow:
  - smoke endpointow voice OK,
  - manualne testy usera: TTS i STT dzialaja.
- Commity (kluczowe):
  - `06600bf` admin Voice panel + config API
  - `de2139d` model `pl_PL-bass-high`
  - `f0f5155` fix odtwarzania TTS (unmute/volume)

## 11. Analiza po fazie (Perplexity)

- Zgodnosc z briefem: wysoka (core scope dostarczony).
- Ryzyka:
  - czułość auto-stop STT zależna od urzadzenia i odszumiania systemowego.
- Kolejne kroki:
  - dopiac runtime pobieranie progow ciszy do `frontend/js/voice.js` z `/voice/config` przy init,
  - dodac preset/profil "mobile noisy room",
  - po stabilizacji przeniesc folder do `docs/!Phase DONE/`.
