<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 03 — Frontend Game Integration (TTS playback + STT mic input)

> Workflow: REV 2 gotowy — Cursor implementuje.
> **Wymaga ukończonych PROMPT 01 i 02** — `/voice/tts`, `/voice/stt`, `/voice/config`, nginx `/voice/*` już działają.

## Cel

Integracja systemu głosowego z frontendem gry — dwa niezależne moduły:
1. **TTS playback** — po każdej odpowiedzi GM tekst jest automatycznie czytany przez voice-service
2. **STT input** — gracz może nacisnąć przycisk 🎤, powiedzieć akcję, transkrypt trafia do pola input

Oba moduły mają lokalne toggles zapisane w `localStorage`. Zero zmian w backendzie gry.

## Kontekst techniczny

- Główny runtime gry jest rozproszony między `frontend/js/app.js`, `frontend/js/ui.js`, `frontend/js/api.js`; brak `game.js`.
- Chat DOM: `#chat`, input: `<textarea id="input">`, send button: `#send-btn`.
- `window.addMessage` — główny punkt wejścia dla hook TTS.
- voice-service dostępny przez nginx pod `/voice/*` (DEV i PROD).
- NIE ruszamy: `backend/`, `data/ai_gm.db`, docker-compose, nginx.

## Odpowiedzi Cursora (REV 1)

1. Branch: `phase-8g-voice-system`. ✅
2. Zmiany z PROMPT 01/02 w repo. ✅
3. Brak `frontend/js/game.js` — integracja przez nowy `voice.js`. ✅
4. DOM: `#input`, `#send-btn`, `#chat`. ✅
5. voice-service `/voice/healthz` OK. ✅
6. nginx `/voice/` OK na DEV i PROD. ✅

---

# ✅ IMPLEMENTACJA REV 2 — Cursor wykonał

## Co zostało zrobione *(uzupełnił Cursor)*

- Zmodyfikowane pliki:
  - `frontend/index.html`
  - `frontend/styles.css`
  - `frontend/js/voice.js` (nowy)
- UI:
  - dodano przyciski `#tts-toggle` (🔊), `#stt-toggle` (🎤) i status `#voice-status` w composerze.
  - dodano style `.voice-toggle`, `.voice-toggle.is-active`, `.voice-toggle.is-recording`, `.voice-toggle:disabled`, `.voice-status`.
  - animacja pulsu (`@keyframes voice-recording-pulse`) dla stanu nagrywania.
- Hook odpowiedzi GM:
  - patch `window.addMessage` w `voice.js`: dla `role === 'assistant' || role === 'gm'` wywoływane `voiceUI.speakGMText(text)`.
- Playback TTS:
  - natywny `Audio` + `blob URL` z `GET /voice/tts?text=...`.
  - poprzednie audio zatrzymywane przez `stopPlayback()` przed nowym odtworzeniem.
- STT flow:
  - toggle 🎤 uruchamia `getUserMedia` + `MediaRecorder` (preferencja `audio/webm`) + WebSocket `/voice/stt`.
  - audio chunks wysyłane do WS; transkrypt z powrotem → `#input` + event `input` + focus.
  - opcjonalny autosend przez `LS_STT_AUTOSEND`.
- Fallbacki:
  - `/voice/healthz` offline → disable przycisków, status „Głos chwilowo niedostępny”, gra działa normalnie.
  - brak `mediaDevices`/`MediaRecorder` → STT disabled + status inline.
  - błędy TTS/WS → `console.warn`, bez crasha UI.

## Notatki po implementacji *(uzupełnia Perplexity)*

**DONE — 2026-04-30**

- Nowy moduł `frontend/js/voice.js` jest izolowany i nie modyfikuje żadnego istniejącego pliku logiki gry poza minimalnymi hookami. Odwracalny przy potrzebie — wystarczy usunąć plik i przyciski z HTML.
- Hook `window.addMessage` jest defensywny (`try/catch`, optional chaining) — błąd w TTS nie wpływa na wyświetlanie wiadomości GM.
- Brak formalnej weryfikacji manualnej w przegladarce od Cursora (Lints OK, ale testy UI nie były wykonane w raporcie) — przy pierwszym `sync do develop` + deploy DEV warto raz sprawdzić ręcznie: przyciski 🔊/🎤, TTS po odpowiedzi GM, STT → `#input`.
- Frontend serwowany z bind-mount — **nie wymaga docker rebuild**, wystarczy hard refresh (Ctrl+F5) w przeglądarce po wdrożeniu.
- **localStorage keys do debugowania w DevTools:** `voice_tts_enabled`, `voice_stt_enabled`, `voice_stt_autosend`.
- **Następny krok:** PROMPT 04 — panel admina: zakładka Głos (konfiguracja głosu, speed, preview TTS, toggle domyślny).

## Follow-up (po stabilizacji STT na frontendzie)

Po wdrożeniu i testach użytkownika potwierdzono, że STT/TTS działa end-to-end (nagrywanie, transkrypcja, autosend), ale strojenie auto-stop ciszy zależy od urządzenia i warunków akustycznych.

### Wymaganie do kolejnej iteracji (admin panel)

Do zakładki Voice w admin panelu należy dodać możliwość regulacji parametrów detekcji ciszy STT:

- `stt_silence_auto_stop_ms` — czas ciszy po którym nasłuch kończy się automatycznie (ms).
- `stt_min_voice_rms_threshold` — minimalny próg RMS traktowany jako mowa.
- `stt_noise_multiplier` — mnożnik progu względem wykrytego tła/szumu.

Zakres i walidacja:

- wartości muszą być walidowane po stronie backendu (`/voice/config`),
- frontend powinien pobierać je przy starcie (`GET /voice/config`) i stosować w `voice.js`,
- zmiany w panelu admin powinny działać bez rebuildu frontendu (reload konfiguracji + restart voice-service jeśli wymagany).
