<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 04 — Panel Admina — Zakładka Głos

> Workflow: REV 2 gotowy — Cursor implementuje.
> **Wymaga ukończonych PROMPT 01–03** — `/voice/config`, `/voice/voices`, `/voice/healthz` już działają.

## Cel

Dodanie nowej zakładki **"Głos"** do panelu admina (`/panel/`):
- Status voice-service (health)
- Włączniki globalne TTS i STT
- Konfiguracja głosu Piper (dropdown głosów, speed, ekspresja)
- Konfiguracja modelu Whisper STT
- **Parametry auto-stop ciszy STT** (nowe — wynikające z PROMPT 03)
- Test TTS inline (play preview)

## Kontekst techniczny — faktyczna architektura panelu

Admin panel działa przez **lazy-loaded ES modules**:
- Nawigacja: `<button data-section="...">` w `<nav class="sidebar-nav">` w `index.html`
- Każda sekcja: `<div class="section-panel" data-section="...">` + plik `frontend/admin_panel/sections/NAME.js`
- Inicjalizacja: `maybeInitNAME(section)` w `index.html`, dynamiczny `import()` przy pierwszym kliknięciu
- Styl kodu: ES module z eksportem `async function init(container)`, helpers `el()`, `adminFetch()`, `showToast()` ze `shared/`
- Istniejące sekcje: `accounts`, `config`, `game_design`, `npcs`, `technical`, `test_runner`, `ui_settings`
- **NIE ma `admin_panel/js/`** — sekcje siedzą w `admin_panel/sections/`

## Zależności z PROMPT 03

W `frontend/js/voice.js` zaimplementowane:
- `localStorage` keys: `voice_tts_enabled`, `voice_stt_enabled`, `voice_stt_autosend`
- `window.voiceUI.speakGMText()` — odczyt przez `GET /voice/tts?text=...`
- STT przez WebSocket `/voice/stt`
- Fallback: healthz offline → disable przycisków

Admin panel kontroluje te same parametry globalnie przez `POST /voice/config`.

---

## Co zostało zrobione *(uzupełnił Cursor)*

- Dodano nową sekcję admin panelu: `frontend/admin_panel/sections/voice.js`.
- Dodano nawigację i panel sekcji `voice` w `frontend/admin_panel/index.html` + lazy init `maybeInitVoice`.
- Sekcja Głos zawiera:
  - status `voice-service` (`/voice/healthz`) + odświeżanie i polling,
  - globalne toggles TTS/STT (`POST /voice/config`),
  - konfigurację TTS (voice, speed, noise_scale, noise_w),
  - test TTS inline (`GET /voice/tts?...` + playback),
  - konfigurację STT (model, language, beam_size),
  - konfigurację auto-stop ciszy STT (`stt_silence_auto_stop_ms`, `stt_min_voice_rms_threshold`, `stt_noise_multiplier`).
- **Parametry z Sekcji 6 wymagały zmian backendu voice-service**:
  - `voice-service/config.py` — nowe wartości domyślne,
  - `voice-service/config.json` — nowe pola,
  - `voice-service/main.py` (`ConfigUpdate`) — akceptacja nowych pól + walidacja zakresów.
- Deploy DEV: commit `06600bf` na `develop`, rebuild voice-service + frontend wykonany na `.61`.
- `/voice/config` zwraca nowe pola ✅, voice-service `healthy` ✅.

## Notatki po implementacji *(uzupełnia Perplexity)*

**DONE — 2026-04-30**

- Commit `06600bf` na `develop` — zawiera zmiany z PROMPT 04. Uwaga: zmiany z PROMPT 01–03 są **niezacommitowane** (wymienione w `git status` na początku sesji) — przed merge do `main` należy się upewnić, że cała Phase 8G jest w jednym sprzyjnym stanie.
- Parametry auto-stop ciszy (`stt_silence_auto_stop_ms`, `stt_min_voice_rms_threshold`, `stt_noise_multiplier`) są teraz zapisywane przez `POST /voice/config` i walidowane w backendzie. Frontend `voice.js` powinien je pobierać przez `GET /voice/config` przy `init()` i stosować lokalnie — jeśli jeszcze tego nie robi, to zadanie do PROMPT 05 lub poprawki.
- Rebuild `voice-service` był wymagany i został wykonany. Frontend admin panelu nie wymaga rebuildu (lazy import przez bind-mount).
- **Przed wdrożeniem na PROD** należy:
  1. Zrobić pełny `sync do develop` dla PROMPT 01–03 (niezacommitowane zmiany).
  2. Uruchomić `./scripts/promote_and_deploy_prod.sh` dla całej Phase 8G.
  3. Sprawdzić ręcznie TTS/STT w przegladarce na DEV przed release.
- **Następny krok:** `sync do develop` — commit wszystkich zmian Phase 8G (PROMPT 01–03 niezacommitowane) + ewentualny PROMPT 05 jeśli potrzebna integracja parametrów ciszy w `voice.js`.
