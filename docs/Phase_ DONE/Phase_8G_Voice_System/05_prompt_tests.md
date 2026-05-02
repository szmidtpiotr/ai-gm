<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-29 -->

# PROMPT 05 — Testy integracyjne Voice System

> Workflow: Cursor odpowiada na pytania blokujące (NIE implementuje). Potem Perplexity generuje REV 2.

## Cel

Napisanie testów integracyjnych dla `voice-service` weryfikujących poprawność wszystkich endpointów.
Testy uruchamiane przez SSH na `.61`, analogicznie do testów backendu.

## Zakres testów

### Testy API (pytest)

```
voice-service/tests/
├── test_health.py       # GET /voice/healthz — status 200, pola ok
├── test_tts.py          # GET /voice/tts?text=... — audio/wav, usunięcie [ROLL:...]
├── test_stt.py          # WebSocket /voice/stt — audio .wav → tekst
├── test_config.py       # GET + POST /voice/config — zapis/odczyt
└── test_voices.py       # GET /voice/voices — lista modeli
```

### Przypadki testowe TTS
- Tekst polski — zwraca WAV (bytes > 0)
- Tekst z `[ROLL: Zręczność vs 15]` — fragment usunięty przed syntezą
- Pusty tekst — zwraca 400
- Tekst > 2000 znaków — zwraca 400
- Parametr `speed=0.7` — zwraca WAV (inna długość niż speed=1.0)
- Nieznany `voice=xyz` — zwraca 400

### Przypadki testowe STT
- Przesyłanie pliku `test_audio_pl.wav` — zwraca `{text: non-empty}`
- Pusty bufor — zwraca `{text: ""}`
- Zamknięcie WebSocket przed wynikiem — brak crashów

### Przypadki testowe Config
- GET /voice/config — wszystkie pola obecne
- POST `/voice/config` z `{tts_speed: 1.5}` — zmiana zapisana
- POST `/voice/config` z nieprawidłową wartością `{tts_speed: 99}` — zwraca 422
- POST `/voice/config` zmiana głosu na `pl_PL-gosia-medium` — config zaktualizowany

## Plik audio testowy

```python
# W fixtures: wygeneruj syntetyczny plik WAV (1 sekunda ciszy lub tone)
# lub użyj małego nagrania sample dłączonego do repo w voice-service/tests/fixtures/
```

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Czy jesteś na właściwym branchu? (`git branch --show-current`)
2. Czy voice-service działa? (`curl http://localhost:8300/voice/healthz`)
3. Czy pytest jest dostępny w kontenerze voice-service? (`docker exec voice-service pytest --version`)
4. Czy istnieje już katalog `voice-service/tests/`? (`ls -la voice-service/tests/`)
5. Jak uruchamiane są testy backendu? (`cat Makefile` lub `ls scripts/`) — żeby zachować spójność

## Odpowiedzi Cursora (REV 1)

*(Cursor wpisuje tutaj odpowiedzi na pytania blokujące)*

## Co zostało zrobione *(uzupełnia Cursor)*

*(Po implementacji REV 2)*

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Po raporcie Cursora)*
