<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-29 -->

# PROMPT 1 — Globalna konfiguracja LLM: migracja DB + backend + Admin Panel UI + cleanup frontendu

> Workflow: Cursor odpowiada na pytania blokujące (NIE implementuje) → Perplexity generuje REV 2 → Cursor implementuje.

---

## Cel

Zob. `00_brief.md` — faza 8G. Skrót:
- Nowa tabela `global_llm_settings` w SQLite (singleton)
- Backend ładuje config z DB przy starcie (trwałość po restarcie kontenera)
- Admin Panel → Technical: formularz edycji LLM + test połączenia
- Frontend gracza: usunięcie per-user LLM settings UI
- `user_llm_settings` tabela i serwis backendowy: **NIE ruszamy**

---

## Kontekst techniczny

**Kluczowe pliki:**
- `backend/app/services/llm_service.py` — `_runtime_config`, `get_effective_config()`, `set_runtime_config()`
- `backend/app/services/user_llm_settings.py` — per-user fallback (nie ruszamy logiki)
- `backend/app/services/ollama_service.py` — legacy? do audytu
- `backend/app/main.py` — startup/lifespan
- `backend/app/migrations_admin.py` — wzorzec migracji
- `backend/app/routers/` — admin routery
- `frontend/panel/` — Admin Panel (Technical section)
- `frontend/` — UI gracza (usunięcie LLM settings)

**Hierarchia config po zmianach (finalna):**
```
1. per-user user_llm_settings (DB) — jeśli row istnieje
2. global_llm_settings (DB)        — NOWE
3. _runtime_config in-memory       — fallback
4. env vars                        — LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_API_KEY
5. hardcoded defaults              — ollama / http://localhost:11434 / gemma4:e4b
```

**NIE ruszamy:**
```
docker-compose.yml / docker-compose.dev.yml
data/ai_gm.db
backend/prompts/system_prompt.txt
backend/app/core/llm_config.py
backend/app/services/user_llm_settings.py  (tylko logika; UI gracza usuwamy)
```

**API kontrakty (wiążące):**
```
GET  /api/admin/settings/llm
  response: { ok: true, data: { provider, base_url, model, api_key_set: bool } }

POST /api/admin/settings/llm
  request:  { provider, base_url, model, api_key: str|null }
  response: { ok: true }
  errors:   400, 401

POST /api/admin/settings/llm/test
  response: { ok: true, data: { reachable: bool, provider, base_url, model, error: str|null } }
```

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

Cursor: odpowiedz na każde pytanie, **NIE implementuj**.

1. **Branch:** `git branch --show-current` — czy jesteś na `develop`?

2. **Git status:** `git status` — czy są niezacommitowane zmiany? Wymień.

3. **DB health:** `ls -lh data/ai_gm.db` — rozmiar i data modyfikacji.

4. **Tabela global_llm_settings:** `sqlite3 data/ai_gm.db ".tables"` — czy `global_llm_settings` już istnieje?

5. **Wzorzec migracji:** Czy migracje są inline w `migrations_admin.py` czy jako osobne pliki `.sql` w `backend/sql/`? Podaj przykład jednej migracji.

6. **Istniejące endpointy LLM:** `grep -r "settings/llm" backend/ --include="*.py" -n` — jakie endpointy LLM settings już istnieją i w jakich plikach?

7. **Ollama service usage:** `grep -r "ollama_service" backend/ --include="*.py" -l` — które pliki go importują? Czy jest aktywnie używany czy legacy?

8. **Frontend gracza — LLM UI:** `grep -r "llm\|base_url\|api_key" frontend/ --include="*.js" --include="*.html" -l` — jakie pliki (NIE panel) mają LLM settings? Podaj listę.

9. **Admin Panel Technical — struktura:** Jak wygląda sekcja Technical w Admin Panelu? Pokaż fragment HTML/JS odpowiedzialny za zakładki (np. Health, Backup). Chcę wiedzieć gdzie dodać nową sekcję LLM.

10. **Admin auth pattern:** Jak działa autoryzacja adminów w istniejących routerach? Czy jest dekorator/dependency `require_admin` lub podobny?

---

## Implementacja (szkic REV 1 — Cursor NIE wykonuje)

> To jest szkic do zatwierdzenia. Po odpowiedziach Cursora Perplexity wygeneruje REV 2.

### Krok 1 — Migracja DB
Nowa tabela `global_llm_settings` (singleton id=1) zgodnie z wzorcem projektu.

### Krok 2 — `global_llm_settings.py`
Nowy serwis: `load_from_db()`, `save_to_db(provider, base_url, model, api_key)`.

### Krok 3 — `llm_service.py`
- `get_effective_config()` — poziom 2: odczyt z `global_llm_settings`
- `main.py` lifespan: wywołanie load + `set_runtime_config()`

### Krok 4 — Router admin
Nowe endpointy GET/POST `/api/admin/settings/llm` i POST `.../test`.

### Krok 5 — Admin Panel UI
Formularz w sekcji Technical (wzorowany na istniejących zakładkach).

### Krok 6 — Cleanup frontend gracza
Usunięcie per-user LLM settings UI.

### Krok 7 — `ollama_service.py`
Na podstawie odpowiedzi z pyt. 7: podpiąć lub oznaczyć jako dead code.

### Krok 8 — Testy
```python
def test_get_global_llm_settings_returns_masked(admin_client)
def test_post_global_llm_settings_saves_to_db(admin_client)
def test_post_global_llm_settings_updates_runtime_config(admin_client)
def test_post_global_llm_settings_api_key_null_preserves_existing(admin_client)
def test_llm_test_endpoint_returns_reachable_or_error(admin_client)
```

---

## Odpowiedzi Cursora (REV 1)

*(Wklej tutaj odpowiedzi Cursora na pytania blokujące)*

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji REV 2)*

*(Cursor uzupełnia po implementacji)*

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełnia po raporcie Cursora)*
