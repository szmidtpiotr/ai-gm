<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 02 — Docker Compose + Nginx proxy dla voice-service

> Workflow: REV 2 gotowy — Cursor implementuje.
> **Wymaga ukończonego PROMPT 01** — katalog `voice-service/` musi istnieć.

## Cel

Integracja `voice-service` z istniejącą infrastrukturą:
1. Dodanie serwisu `voice-service` do `docker-compose.yml` (PROD) i `docker-compose.dev.yml` (DEV)
2. Konfiguracja Nginx — proxy `/voice/` oraz WebSocket `/voice/stt` na `voice-service:8300`

> **Architektura nginx:** Nginx stoi na **osobnej maszynie** `192.168.1.4` (nie na `192.168.1.61`).
> Cursor próbuje podłączyć się przez SSH i skonfigurować nginx automatycznie (Opcja A).
> Jeśli SSH się nie uda — generuje snippet do ręcznego wklejenia (Opcja B).

## Kontekst techniczny

- Sieć PROD: `ai-gm` (bridge), DEV: `ai-gm-dev`
- Nginx host: `root@192.168.1.4` (osobna VM)
- App host: `piotrszmidt@192.168.1.61`
- NIE ruszamy: reszty serwisów w compose, istniejących reguł nginx
- Branch: `phase-8g-voice-system`

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Czy `voice-service/main.py` istnieje? (`ls -la voice-service/main.py`)
2. Czy jesteś na właściwym branchu? (`git branch --show-current`)
3. Czy są niezacommitowane zmiany? (`git status`)
4. Czy SSH do nginx VM działa bez hasła? (`ssh -o BatchMode=yes root@192.168.1.4 echo OK`)
5. Jeśli SSH działa — gdzie leży config nginx dla tej domeny? (`ssh root@192.168.1.4 "find /etc/nginx -name '*.conf' | xargs grep -l aigm-prod 2>/dev/null"`)

---

# ✅ IMPLEMENTACJA REV 2 — Cursor wykonuje

## Krok 1 — Dodaj `voice-service` do `docker-compose.yml` (PROD)

Dodaj nowy serwis **przed sekcją `networks:`**:

```yaml
  voice-service:
    build:
      context: ./voice-service
    container_name: ai-gm-voice
    restart: unless-stopped
    environment:
      - VOICE_CONFIG_PATH=/app/config.json
      - VOICE_MODELS_DIR=/app/models/tts
      - VOICE_MODELS_DIR_STT=/app/models/stt
      - PIPER_BIN=/opt/piper/piper
    volumes:
      - ./voice-service/models:/app/models
      - ./voice-service/config.json:/app/config.json
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8300/voice/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    networks:
      - ai-gm
```

## Krok 2 — Dodaj `voice-service` do `docker-compose.dev.yml` (DEV)

Dodaj nowy serwis **przed sekcją `networks:`**:

```yaml
  voice-service:
    build:
      context: ./voice-service
    container_name: ai-gm-voice-dev
    restart: unless-stopped
    ports:
      - "8300:8300"
    environment:
      - VOICE_CONFIG_PATH=/app/config.json
      - VOICE_MODELS_DIR=/app/models/tts
      - VOICE_MODELS_DIR_STT=/app/models/stt
      - PIPER_BIN=/opt/piper/piper
    volumes:
      - ./voice-service/models:/app/models
      - ./voice-service/config.json:/app/config.json
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8300/voice/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    labels:
      - service=voice-dev
    networks:
      - ai-gm-dev
```

## Krok 3 — Nginx — 🆅 Opcja A: SSH automatyczny (priorytet)

**Wykonaj kroki poniżej. Jeśli którykolwiek krok się nie uda — zatrzymaj się i przejdź do Opcji B.**

### 3A-1. Sprawdź SSH i znajdź plik konfiguracji nginx

```bash
ssh -o BatchMode=yes root@192.168.1.4 echo "SSH OK"
ssh root@192.168.1.4 "grep -rl 'aigm' /etc/nginx/ 2>/dev/null"
```

Jeśli SSH zawodzi → **przejdź do Opcji B**.

### 3A-2. Dodaj bloki location i przeładuj nginx

```bash
ssh root@192.168.1.4 bash << 'ENDSSH'
NGINX_CONF_PATH="WSTAW_SCIEZKE_TUTAJ"
cp "$NGINX_CONF_PATH" "${NGINX_CONF_PATH}.bak.$(date +%Y%m%d%H%M%S)"
# Wstaw /voice/stt (przed /voice/) i /voice/ przed ostatnim }
ENDSSH
nginx -t && nginx -s reload
```

---

## Krok 3 — Nginx — 🅱️ Opcja B: Ręczny snippet (fallback)

```nginx
    location /voice/stt {
        proxy_pass http://192.168.1.61:8300/voice/stt;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /voice/ {
        proxy_pass http://192.168.1.61:8300/voice/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
```

---

## Krok 4 — Weryfikacja end-to-end

```bash
curl -sf https://aigm-dev.studio-colorbox.com/voice/healthz && echo "NGINX OK"
curl -sf "https://aigm-dev.studio-colorbox.com/voice/tts?text=Witaj+w%C4%99drowcze" --output /tmp/test.wav
ls -lh /tmp/test.wav
```

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano `voice-service` do `docker-compose.yml` (PROD) i `docker-compose.dev.yml` (DEV).
- DEV zweryfikowany lokalnie: healthz i TTS zwracają OK.
- Dodano auto-download modeli Piper w `tts.py` gdy bind-mount `voice-service/models` jest pusty.
- Nginx: finalnie użyto **Opcji A (SSH)** — klucz SSH ustawiony ręcznie przez właściciela.
  - spatchowano `/data/nginx/proxy_host/69.conf` (aigm-prod) i `/data/nginx/proxy_host/72.conf` (aigm-dev)
  - wykonano backup, `nginx -t` + `nginx -s reload` — OK
- Weryfikacja E2E:
  - `https://aigm-dev.studio-colorbox.com/voice/healthz` ✅
  - `https://aigm-dev.studio-colorbox.com/voice/tts?...` → WAV ✅
  - `https://aigm-prod.studio-colorbox.com/voice/healthz` ✅

## Notatki po implementacji *(uzupełnia Perplexity)*

**DONE — 2026-04-30**

- Nginx na projekcie działa jako **Nginx Proxy Manager** na VM `192.168.1.4` — runtime configs w `/data/nginx/proxy_host/*.conf` (nie w `/etc/nginx/sites-available/`). Ważne dla przyszłych promptów wymagających zmian nginx.
- Klucz SSH `~/.ssh/id_ed25519.pub` z hosta `192.168.1.61` dodany do `root@192.168.1.4` — kolejne automatyczne SSH działaą bez hasła. Opcja A będzie działać w przyszłych promptach.
- PROD voice-service NIE ma wystawionego portu 8300 publicznie — dostępny wyłącznie przez nginx (wewnętrzna sieć `ai-gm`). DEV ma `ports: 8300:8300` dla bezpośredniego testowania.
- voice-service zbudowany razem z głosami Piper (`darkman-medium`, `gosia-medium`) i modelem Whisper `small` w obrazie Docker. Bind-mount `voice-service/models` umożliwia podmianę modeli bez rebuildu.
- **Następny krok:** PROMPT 03 — integracja `game.js` z TTS playback i STT mic input.
