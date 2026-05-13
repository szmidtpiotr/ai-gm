<!-- STATUS: DONE -->
<!-- REV: 1 | DATE: 2026-04-29 -->

# PROMPT 15 — 8D-LOC-4: Panel admina — pogląd i ręczne ustawianie `current_location_id` per kampania

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-8d-location-integrity`
> **Plik:** `docs/Phase_8D_Location_Integrity/15_prompt_LOC4_admin_panel_session_location.md`
> **Zależności:**
> - PROMPT 12 (8D-LOC-1) — `[LOCATION CONTEXT]` injection ✔️
> - PROMPT 13 (8D-LOC-2) — reguły GM w system_prompt ✔️
> - PROMPT 14 (8D-LOC-3) — backend guard w `validate_move()` ✔️

---

## Cel

Dodanie w panelu admina sekcji **Session Location** per kampania, która umożliwia:
- **Pogląd** aktualnej `current_location_id` sesji (key + label + typ makro/sub)
- **Ręczne ustawienie** lokacji startowej / resetowanie sesji do innej lokacji
- **Listę dostępnych lokacji** danej kampanii do wyboru

Bez tego debug i testowanie Phase 8D wymaga wejścia w DB przez SQLite lub logi — panel admina ma to eliminować.

---

## Kontekst techniczny

- **Pliki do modyfikacji (prawdopodobne):**
  - `frontend/panel/` — UI panelu admina (Vanilla JS + HTML)
  - `backend/app/api/` — nowy endpoint lub rozszerzenie istniejącego admin API
- **Schemat DB:**
  - `game_sessions.current_location_id` — FK do `game_locations.id`
  - `game_locations`: `id`, `key`, `label`, `location_type` (makro/sub), `approved`
  - `game_sessions`: `id TEXT`, `campaign_id`
- **Czego NIE ruszać:**
  - `docker-compose.yml` prod
  - `data/ai_gm.db`
  - Logika `validate_move()` / `_get_available_location_keys()` z LOC-3
  - `build_location_context_block()` z LOC-1
  - Inne sekcje panelu admina (walka, ekwipunek, flażki itp.)

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

Cursor odpowiada na poniższe pytania **zanim** przystąpi do implementacji:

1. Jaki jest aktualny branch? (`git branch --show-current`)
2. Czy working tree jest czysty? Jeśli nie — wykonaj commit zbiorczy LOC-1+2+3:
   ```bash
   git add -A && git commit -m "feat: LOC-1/2/3 location integrity system"
   ```
3. Jak wygląda struktura `frontend/panel/` — ile plików JS/HTML? (`ls -la frontend/panel/` lub `find frontend/panel -name "*.js" -o -name "*.html"`). Czy panel to SPA w jednym pliku czy wiele modułów?
4. Czy istnieje już jakiś endpoint API do pobierania sesji kampanii (`/api/admin/campaigns/:id/session` lub podobny)? Pokaż listę route’ów w admin API: `grep -r "@router" backend/app/api/ --include="*.py" -l`
5. Czy jest już endpoint do pobierania listy lokacji dla kampanii (`/api/admin/campaigns/:id/locations` lub `/api/locations`)? Pokaż jego sygnaturę.
6. Jak wygląda obecny widok kampanii w panelu admina — czy istnieje strona szczegółów kampanii z sekcjami (np. sesja, postacie, tury)? (`ls frontend/panel/campaign*` lub podobne)
7. Czy istnieje middleware autoryzacyjny dla admin endpointów — jak wygląda zabezpieczenie? (`grep -r "admin" backend/app/api/ --include="*.py" -l`)
8. Czy baza danych jest w dobrym stanie? (`ls -lh data/ai_gm.db`)

---

## Implementacja (REV 1 — szkic do zatwierdzenia przez Perplexity)

> ⚠️ Cursor **NIE implementuje** poniższego zanim Perplexity nie zatwierdzi po odpowiedziach blokujących.

### Krok 1 — Backend: endpoint GET `/api/admin/campaigns/{campaign_id}/session-location`

```python
# Zwraca: session_id, current_location_id, key, label, location_type
# + listę wszystkich lokacji kampanii (id, key, label, location_type, approved)
GET /api/admin/campaigns/{campaign_id}/session-location
```

### Krok 2 — Backend: endpoint PATCH `/api/admin/campaigns/{campaign_id}/session-location`

```python
# Body: { "location_id": "<id z game_locations>" } lub { "location_id": null } (reset)
# Wykonuje: UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?
# Loguje: admin_location_override z session_id, old_location_key, new_location_key
PATCH /api/admin/campaigns/{campaign_id}/session-location
```

### Krok 3 — Frontend: sekcja w panelu admina

W widoku kampanii (lub jako osobna zakładka) dodaj sekcję **Session Location**:

```
[ℹ️ Session Location]
Aktualna lokacja: Karczma "Pod Skrzyżowanymi Kordelasami" (sub) [klucz: inn_main]
ID sesji: 105

[Dropdown: wybierz nową lokację]
  ► Rynek Główny (makro) [village_square]
  ► Karczma (sub) [inn_main]  ← aktualna
  ► Brama Miejska (makro) [city_gate]
  ...
[Ustaw lokację]   [Reset (null)]
```

- Dropdown pokazuje lokacje posortowane: najpierw `approved=1`, potem reszta (oznaczone)
- Po "Ustaw" — PATCH do backendu + odświeżenie widoku z nowym stanem
- Po "Reset" — PATCH z `location_id: null` + informacja że sesja będzie fail-open
- Brak lokacji w sesji: komunikat `⚠️ Brak aktualnej lokacji (fail-open: guard nie blokuje)`

### Krok 4 — Brak migracji DB

Nie dodajemy nowych kolumn ani tabel — używamy istniejących `game_sessions.current_location_id` i `game_locations`.

### Krok 5 — Testy

```python
def test_get_session_location_returns_current(client, campaign_with_session):
    """GET session-location zwraca aktualną lokację sesji + listę dostępnych."""
    ...

def test_patch_session_location_updates_db(client, campaign_with_session):
    """PATCH session-location zmienia current_location_id w game_sessions."""
    ...

def test_patch_session_location_null_resets(client, campaign_with_session):
    """PATCH z location_id=null ustawia current_location_id=NULL."""
    ...
```

### Krok 6 — Weryfikacja manualna na DEV

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# GET
curl -sf http://localhost:8100/api/admin/campaigns/1065/session-location | jq .

# PATCH — zmień lokację
curl -X PATCH http://localhost:8100/api/admin/campaigns/1065/session-location \
  -H "Content-Type: application/json" \
  -d '{"location_id": "<id_lokacji>"}'

# Sprawdź w DB
sqlite3 data/ai_gm.db \
  "SELECT gs.id, gs.current_location_id, gl.key, gl.label \
   FROM game_sessions gs \
   LEFT JOIN game_locations gl ON gl.id = gs.current_location_id \
   WHERE gs.campaign_id = '1065';"

# Logi
docker logs ai-gm-dev-backend-1 --tail=20 | grep admin_location_override
```

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8d-location-integrity`.
2. **Working tree:** **nie czysty** (LOC 1–3, testy, zmiany poboczne). Zbiorczego commitu z kroku dokumentu nie wykonywałem automatycznie.
3. **Struktura UI:** Nie ma `frontend/panel/` — panel to **`frontend/admin_panel/`** (`index.html`, `sections/*.js`, `shared/`). Moduły ES, sekcje wg sidebara.
4. **Endpoint „sesja kampanii”:** Osobnego `GET /api/admin/campaigns/:id/session` brak. Istnieje **`/api/session/{session_id}/location`** ( **`session_id`** ). LOC‑4 dopina **`/api/admin/campaigns/{campaign_id}/session-location`**.
5. **Lista lokacji:** **`GET /api/locations`** oraz admin w **`admin_location`**. Bez `campaign_id` w `game_locations` lista w panelu = **pełny aktywny katalog** z sortowaniem (approved najpierw).
6. **Widok kampanii:** W **`accounts.js`** tabela kampanii użytkownika; LOC‑4 jako **przycisk + modal** przy danym wierszu kampanii.
7. **Auth:** **`require_admin_token`** + `Bearer` + `verify_admin_token` (jak pozostałe `/api/admin/...`).
8. **`data/ai_gm.db`:** Istnieje (~2.6 MB).

**Bloker:** brak.

---

## Co zostało zrobione *(uzupełnia Cursor)*

- **Backend** (wcześniej): `GET`/`PATCH` `/api/admin/campaigns/{campaign_id}/session-location` w `admin_location.py` — payload: `session_id`, `current_location_id`, `current`, `locations` (katalog aktywnych lokacji).
- **Frontend:** `frontend/admin_panel/sections/accounts.js` — przycisk **„📍 Session location”** przy każdej kampanii (Accounts → szczegóły użytkownika → Campaigns); modal z dropdownem, **Set location**, **Reset (null)**; cache-bust importów `?v=19`.
- **Testy:** `test_phase8d_api_http.py` — klasa `TestLoc4AdminCampaignSessionLocation`: `404` dla nieistniejącej kampanii na `GET` i `PATCH`.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
