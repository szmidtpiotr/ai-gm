<!-- STATUS: DRAFT -->
<!-- PHASE: 8I | DATE_START: - | DATE_END: - -->

# Phase 8I — Custom Voice Training (Piper TTS) · Brief

> Cel: nagranie własnego głosu i wytrenowanie dedykowanego modelu Piper TTS dla GM.
> Wynik: plik `*.onnx` + `*.onnx.json` gotowy do wrzucenia do `voice-service/models/tts/`
> bez rebuildu Dockera — przez istniejący bind-mount.

---

## 1. Cel fazy

Dodanie dedykowanego głosu GM — nagranego przez właściciela projektu — do systemu TTS
(wdrożonego w Phase 8G). Głos pojawi się w dropdownie panelu admina i będzie dostępny
przez `GET /voice/voices` bez żadnych zmian w backendzie.

**Definicja ukończenia (DoD):**
- [ ] nagrane klipy WAV spełniają wymagania Piper (mono, 22050 Hz, 16-bit)
- [ ] skompilowany model `custom-gm.onnx` + `custom-gm.onnx.json`
- [ ] model wrzucony do `voice-service/models/tts/`
- [ ] `GET /voice/voices` zwraca nowy głos
- [ ] test TTS w panelu admina — słyszalny efekt
- [ ] model dodany do `docker-compose.yml` (volume) — persystencja po restart

---

## 2. Zakres

| # | Komponent | Opis | Priorytet |
|---|---|---|-|
| 1 | Nagrania | Zebranie klipów WAV własnego głosu | 🔴 Must |
| 2 | Dataset prep | Konwersja do LJSpeech, transkrypcja przez Whisper | 🔴 Must |
| 3 | Finetune | Douczenie `darkman-medium` lub `pl_PL-gosia-medium` na własnym głosie | 🔴 Must |
| 4 | Eksport | Konwersja checkpointa do `.onnx` + `.onnx.json` | 🔴 Must |
| 5 | Deploy | Wrzucenie modelu do `voice-service/models/tts/` przez bind-mount | 🔴 Must |
| 6 | Model od zera | Trening full od zera (wymaga 1-2h nagrań, GPU dni) | 🟢 Nice to have |

**Out of scope:**
- Zmiany w kodzie `voice-service` (backend już obsługuje dowolne modele Piper)
- Streaming TTS (Phase 12)
- Multi-speaker models

---

## 3. Zależności

| Zależność | Status | Gdzie |
|---|---|---|
| `voice-service` backend + TTS/STT | ✅ DONE | Phase 8G PROMPT 01 |
| Bind-mount `voice-service/models/tts/` | ✅ DONE | `docker-compose.yml` |
| Dropdown głosów w admin panelu | ✅ DONE | Phase 8G PROMPT 04 |
| GPU do treningu (NVIDIA, CUDA) | ⏳ Zewnętrzny | lokalny PC lub Colab/RunPod |

---

## 4. Wymagania nagrań

### Format obligatoryjny
- WAV, **mono**, **22 050 Hz**, **Signed 16-bit PCM**
- Długość klipu: **5–15 sekund** (dłuższe Piper odrzuca)
- Brak tła, szumów, muzyki
- Jedno zdanie = jeden plik

### Ilość nagrań

| Cieżka | Ilość klipów | Łączny czas | Jakość efektu |
|---|---|---|---|
| Finetune (szybka) | 50–200 | ~5–20 min | Twój akcent + bazowy głos |
| Finetune (dobra) | 200–500 | ~20–50 min | Bliski klonowi |
| Model od zera | 1000+ | 1–2h | Pełny klon |

**Rekomendacja na start:** finetune `darkman-medium` na ~100 klipach (~10 min nagrań).

---

## 5. Architektura — pipeline treningu

```
[Nagrania WAV]
       ↓
[piper-recording-studio] lub [Audacity]
       ↓ WAV 22050Hz mono 16-bit
[Audio-to-Voice-Dataset] — Whisper transkrybuje + tnie na klipy
       ↓ format LJSpeech
       metadata.csv + wavs/
[TextyMcSpeechy / piper-train]
       ↓ finetune darkman-medium
       checkpoint .ckpt
       ↓ export
[piper --export-onnx]
       ↓
custom-gm.onnx + custom-gm.onnx.json
       ↓ scp / cp
voice-service/models/tts/
       ↓ restart voice-service
GET /voice/voices → ["darkman-medium", "gosia-medium", "custom-gm"]
```

### Nowe pliki (poza repo)
```
voice-service/models/tts/custom-gm.onnx
voice-service/models/tts/custom-gm.onnx.json
```
> Modele są w `.gitignore` — nie trafiają do repo, są persystowane przez bind-mount.

### NIE ruszamy
```
backend/
data/ai_gm.db
docker-compose.yml (poza ewentualnym dopisaniem volume jeśli brakuje)
voice-service/main.py, tts.py, stt.py
```

---

## 6. Narzędzia

| Narzędzie | Do czego | Link |
|---|---|---|
| **piper-recording-studio** | Web UI do nagrywania klipów | github.com/rhasspy/piper-recording-studio |
| **TextyMcSpeechy** | Docker: nagrywanie + trening + eksport all-in-one | github.com/domesticatedviking/TextyMcSpeechy |
| **Audio-to-Voice-Dataset** | Transkrypcja Whisper + cięcie na LJSpeech | github.com/thorstenMueller/Audio-to-Voice-Dataset |
| **piper (official)** | Eksport checkpointa do `.onnx` | github.com/rhasspy/piper |
| **Google Colab / RunPod** | GPU jeśli brak lokalnego | colab.research.google.com |

---

## 7. Wymagania sprzętowe

| Etap | CPU | GPU | RAM |
|---|---|---|---|
| Nagrywanie | dowolny | — | — |
| Dataset prep (Whisper) | dowolny | opcjonalnie | 4 GB |
| Finetune | wolny (wielogodzinny) | NVIDIA CUDA (min. 6 GB VRAM) | 8 GB |
| Eksport ONNX | dowolny | — | 4 GB |

> Jeśli brak GPU: Google Colab T4 (darmowy) lub RunPod (~$0.20/h) wystarczy do finetuning.

---

## 8. Plan promptów (Cursor nie potrzebny w tej fazie)

Phase 8I jest głównie operacyjna — nie wymaga zmian w kodzie. Kroki wykonuje właściciel projektu:

| Krok | Działanie | Narzędzie |
|---|---|---|
| 8I-1 | Instalacja piper-recording-studio, nagranie klipów | piper-recording-studio |
| 8I-2 | Konwersja do LJSpeech (transkrypcja Whisper) | Audio-to-Voice-Dataset |
| 8I-3 | Finetune modelu | TextyMcSpeechy lub piper-train |
| 8I-4 | Eksport `.onnx` | piper --export-onnx |
| 8I-5 | Deploy do `voice-service/models/tts/` + weryfikacja | scp / cp + curl |

Jeśli wystąpią błędy konfiguracyjne w `voice-service` — wtedy angaząujemy Cursora.

---

## 9. Weryfikacja końcowa

```bash
# Skopiuj model
cp custom-gm.onnx custom-gm.onnx.json /home/piotrszmidt/ai-gm/voice-service/models/tts/

# Restart voice-service (nie rebuild!)
docker compose -f docker-compose.dev.yml restart voice-service
sleep 10

# Sprawdź lista głosów
curl -sf https://aigm-dev.studio-colorbox.com/voice/voices | python3 -m json.tool

# Test TTS nowym głosem
curl -sf "https://aigm-dev.studio-colorbox.com/voice/tts?text=Witaj+w%C4%99drowcze&voice=custom-gm" --output /tmp/custom-gm-test.wav
ls -lh /tmp/custom-gm-test.wav
```

> Jeśli `custom-gm` pojawia się w liście i WAV > 0 bytes — faza ukończona.

---

## 10. Podsumowanie wdrożenia

*(uzupełnia właściciel po zakończeniu)*

- Wybrana Şcieżka: finetune / od zera
- Ilość nagrań:
- Bazowy model:
- Czas treningu:
- Jakość subiektywna:
- Narzędzia użyte:

## 11. Analiza po fazie (Perplexity)

*(Po zakończeniu fazy)*
