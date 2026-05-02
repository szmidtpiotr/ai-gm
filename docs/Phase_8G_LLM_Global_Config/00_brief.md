<!-- STATUS: ACTIVE -->
<!-- PHASE: 8G | DATE_START: 2026-04-29 | DATE_END: - -->

# Phase 8G — Global LLM Config · Brief

---

## 1. Cel fazy

Ujednolicenie konfiguracji LLM w jednym globalnym miejscu — Admin Panel → Technical → LLM Settings.

**Problem:** `_runtime_config` w `llm_service.py` jest in-memory i resetuje się po każdym restarcie kontenera. Gracz może dziś (niepotrzebnie) ustawiać per-user LLM endpoint w UI. Brak jednego trwałego, widocznego miejsca do zarządzania połączeniem LLM dla całego systemu.

**Wartość:** Admin może zmienić endpoint/model bez restartu ani SSH. Config przeżywa restart kontenera. Zero rozproszenia.

**Definicja ukończenia (DoD):**
- [ ] Nowa tabela `global_llm_settings` istnieje w DB i przeżywa rebuild kontenera
- [ ] Po restarcie backendu `_runtime_config` jest automatycznie załadowany z DB
- [ ] Admin Panel → Technical → zakładka/sekcja „LLM" umożliwia edycję provider/base_url/model/api_key
- [ ] Przycisk „Test połączenia" w Admin Panelu zwraca status reach/not-reach
- [ ] UI per-user LLM settings usunięte z frontendu gracza
- [ ] Testy backendowe przechodzą (`pytest -q`)
- [ ] Healthcheck DEV OK (`curl .../api/healthz`)
- [ ] Funkcja przetestowana manualnie w przeglądarce (DEV)

---

## 2. Zakres — co wchodzi w fazę

| # | Komponent | Opis | Priorytet |
|---|---|---|---|
| 1 | Migracja DB | Nowa tabela `global_llm_settings` (singleton id=1) | 🔴 Must |
| 2 | `llm_service.py` | Funkcje load/save global config z DB; nowy poziom w hierarchii `get_effective_config()` | 🔴 Must |
| 3 | `main.py` startup | Ładowanie globalnego configu z DB przy starcie aplikacji | 🔴 Must |
| 4 | API endpointy admin | GET/POST `/api/admin/settings/llm` + POST `/api/admin/settings/llm/test` | 🔴 Must |
| 5 | Admin Panel UI | Formularz edycji LLM settings + przycisk Test w sekcji Technical | 🔴 Must |
| 6 | Frontend gracza | Usunięcie/ukrycie UI per-user LLM settings | 🔴 Must |
| 7 | `ollama_service.py` audit | Sprawdzić czy jest jeszcze używany; jeśli tak — podpiąć pod `llm_service` lub usunąć jako legacy | 🟡 Should |
| 8 | Testy | Testy nowych endpointów i logiki ładowania z DB | 🔴 Must |

**Czego NIE ma w tej fazie (Out of scope):**
- Per-user LLM overrides w UI (tabela `user_llm_settings` zostaje w DB, ale bez UI — future use)
- Parametry generowania (temperature, top_k itp.) — to `llm_config.py`, osobna rzecz
- Streaming LLM — Phase 12+
- Multi-provider selection per-campaign

---

## 3. Zależności

| Zależność | Status | Gdzie zaimplementowane |
|---|---|---|
| `llm_service.py` z OllamaDriver/OpenAIDriver | ✅ DONE | `backend/app/services/llm_service.py` |
| `user_llm_settings` tabela i serwis | ✅ DONE | `backend/app/services/user_llm_settings.py` |
| Admin Panel struktura (Technical tab) | ✅ DONE | `frontend/panel/` |
| `migrations_admin.py` wzorzec migracji | ✅ DONE | `backend/app/migrations_admin.py` |

---

## 4. Ustalone reguły biznesowe / design decisions

### Reguły ogólne
- Tabela `user_llm_settings` **NIE jest usuwana** — zostaje na przyszłość (future multi-user support)
- `llm_config.py` (temperature, top_k, top_p itp.) **NIE jest ruszany** — to osobna warstwa
- `ollama_service.py` — do audytu: jeśli nadal używany, należy go podpiąć pod `get_effective_config()`; jeśli legacy (nikt nie wywołuje) — można zostawić lub usunąć

### Hierarchia priorytetów configu (ostateczna)

| Poziom | Źródło | Uwagi |
|---|---|---|
| 1 | Per-user `user_llm_settings` (DB) | Jeśli row istnieje dla user_id |
| 2 | **`global_llm_settings` (DB)** | ← NOWE — trwały globalny config |
| 3 | `_runtime_config` in-memory | Kompatybilność wsteczna, ładowany z DB przy starcie |
| 4 | Env vars (`LLM_BASE_URL`, `LLM_MODEL` itp.) | Fallback dla docker-compose |
| 5 | Hardcoded defaults | `ollama` / `http://localhost:11434` / `gemma4:e4b` |

### Reguły specyficzne dla fazy

| Reguła | Wartość / decyzja | Uzasadnienie |
|---|---|---|
| `global_llm_settings` ma zawsze dokładnie 1 wiersz | `id=1`, INSERT OR IGNORE przy migracji | Singleton — nie ma sensu wiele globalnych configów |
| api_key nigdy nie wraca do klienta w plaintext | Pole zwracane jako `""` + `api_key_set: bool` | Bezpieczeństwo — spójnie z `user_llm_settings` |
| Po zapisie w Admin Panelu runtime_config aktualizuje się natychmiast | `set_runtime_config()` wywoływany po upsert | Brak potrzeby restartu kontenera |
| Przycisk Test sprawdza aktualny globalny config (nie per-user) | `llm_service.get_health()` bez override | Test połączenia = test konfiguracji systemowej |

---

## 5. Architektura — pliki do stworzenia / modyfikacji

### Nowe pliki
```
backend/app/services/global_llm_settings.py   ← load/save global config z/do DB
```

### Modyfikowane pliki
```
backend/app/services/llm_service.py           ← get_effective_config() nowy poziom 2; import global_llm_settings
backend/app/main.py                           ← startup: load_global_config_from_db()
backend/app/routers/[admin_router].py         ← nowe endpoints GET/POST /api/admin/settings/llm
frontend/panel/[technical section]            ← nowa sekcja LLM Settings z formularzem
frontend/[player UI]                          ← usunięcie per-user LLM settings UI
```

### Do audytu
```
backend/app/services/ollama_service.py        ← sprawdzić użycie, ewentualnie podpiąć/usunąć
```

### ⛔ NIE ruszamy
```
docker-compose.yml / docker-compose.dev.yml   ← konfiguracja środowisk
data/ai_gm.db                                 ← produkcyjna baza
backend/prompts/system_prompt.txt             ← nie dotyczy tej fazy
backend/app/core/llm_config.py                ← parametry temperature itp. — osobna warstwa
backend/app/services/user_llm_settings.py     ← logika zostaje, tylko UI gracza usuwamy
```

---

## 6. API — kontrakty endpointów

```
GET  /api/admin/settings/llm
  auth:     admin session
  response: {
    ok: true,
    data: {
      provider: str,       // "ollama" | "openai"
      base_url: str,
      model: str,
      api_key_set: bool    // NIGDY nie zwracamy api_key w plaintext
    }
  }

POST /api/admin/settings/llm
  auth:     admin session
  request:  {
    provider: str,
    base_url: str,
    model: str,
    api_key: str | null    // null = nie zmieniaj istniejącego klucza
  }
  response: { ok: true }
  errors:   400 — brak wymaganych pól | 401 — brak auth

POST /api/admin/settings/llm/test
  auth:     admin session
  response: {
    ok: true,
    data: {
      reachable: bool,
      provider: str,
      base_url: str,
      model: str,
      error: str | null    // jeśli reachable=false
    }
  }
```

---

## 7. UI / UX — opis ekranów

### Admin Panel → Technical → LLM Settings

```
⚙️ LLM Settings
─────────────────────────────────────────────
Provider:   [ollama ▼]
Base URL:   [http://host.docker.internal:11434    ]
Model:      [gemma4:e4b                           ]
API Key:    [••••••••••••••  (set)                ]  ← placeholder jeśli api_key_set=true

            [💾 Zapisz]   [🔌 Test połączenia]

Status:  ● Reachable  /  ● Not reachable — [Errno 111] Connection refused
─────────────────────────────────────────────
```

### Frontend gracza — usunąć
Usunąć wszelkie pola/formularze gdzie gracz może wpisać LLM base_url / model / api_key.
Sekcja może zniknąć całkowicie lub jeśli istnieje w kontekście konta — schować za feature flag.

---

## 8. Testy — lista wymaganych

```python
def test_get_global_llm_settings_returns_masked(admin_client)
def test_post_global_llm_settings_saves_to_db(admin_client)
def test_post_global_llm_settings_updates_runtime_config(admin_client)
def test_post_global_llm_settings_api_key_null_preserves_existing(admin_client)
def test_llm_test_endpoint_returns_reachable_or_error(admin_client)
def test_startup_loads_global_config_from_db()   # jeśli testowalny
```

---

## 9. Weryfikacja manualna (DEV)

```bash
# Rebuild DEV
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans

# Health
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# GET global LLM settings
curl -s -b "..." http://localhost:8100/api/admin/settings/llm | jq .

# POST nowy config
curl -s -X POST http://localhost:8100/api/admin/settings/llm \
  -H "Content-Type: application/json" \
  -b "..." \
  -d '{"provider":"ollama","base_url":"http://host.docker.internal:11434","model":"gemma4:e4b","api_key":null}' | jq .

# Test połączenia
curl -s -X POST http://localhost:8100/api/admin/settings/llm/test -b "..." | jq .

# Testy
docker compose -f docker-compose.dev.yml exec -T backend \
  python3 -m pytest tests/test_phase_8g_llm_global_config.py -v

# Sprawdź Admin Panel w przeglądarce
# https://aigm-dev.studio-colorbox.com/panel/ → Technical → LLM Settings
```

---

## Podsumowanie wdrożenia *(uzupełnia Cursor po zakończeniu fazy)*

### Co zostało zaimplementowane
- [ ] Migracja DB (`global_llm_settings`)
- [ ] `global_llm_settings.py` serwis
- [ ] `llm_service.py` — nowy poziom hierarchii + startup load
- [ ] API endpointy admin
- [ ] Admin Panel UI — LLM Settings sekcja
- [ ] Frontend gracza — usunięcie per-user LLM UI
- [ ] `ollama_service.py` audit
- [ ] Testy

### Co NIE zostało zaimplementowane (jeśli dotyczy)
-

### Odchylenia od Briefu
-

### Wyniki testów
```
[wklej output pytest]
```

### Wyniki weryfikacji manualnej
```
[wklej output curl / opis testu w przeglądarce]
```

### Hash commitów
```bash
# [branch] → [hash] — "[opis commita]"
```

---

## Analiza po fazie *(uzupełnia Perplexity po raporcie Cursora)*

### Ocena implementacji
-

### Decyzje do przeniesienia do następnej fazy
-

### STATUS: ACTIVE — `DATE_END: -`
