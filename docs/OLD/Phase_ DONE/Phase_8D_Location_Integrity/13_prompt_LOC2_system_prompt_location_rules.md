<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 13 — 8D-LOC-2: System prompt — reguły korzystania z kontekstu lokacji

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-8d-location-integrity`
> **Plik:** `docs/Phase_8D_Location_Integrity/13_prompt_LOC2_system_prompt_location_rules.md`
> **Zależność:** PROMPT 12 (8D-LOC-1) wdrożony ✔️ — blok `[LOCATION CONTEXT]` jest wstrzykiwany przez backend przed każdą turą.

---

## Cel

Rozszerzyć sekcję `## LOKALIZACJE I PRZEMIESZCZANIE` w `backend/prompts/system_prompt.txt` o reguły semantyczne, dzięki którym GM:
- używa **tylko** lokacji z `[LOCATION CONTEXT]` przy `action: move`
- tworzy nową lokację (`action: create`) wyłącznie gdy gracz odkrywa coś faktycznie nowego
- ignoruje deklaracje stanu gracza (`"jestem na plaży"`) — postać pozostaje w `current_location`
- nie przenosi gracza bez narracyjnego uzasadnienia przejścia z aktualnej lokacji
- poprawnie zachowuje się gdy backend **nie przesłał** bloku `[LOCATION CONTEXT]` (brak ustalonej lokacji w silniku)

---

## Kontekst techniczny (po REV 1)

- **Plik do modyfikacji:** `backend/prompts/system_prompt.txt` — jedyne źródło prawdy dla GM, **295 linii** przed zmianą / **326 linii** po
- **Sekcja docelowa:** `## LOKALIZACJE I PRZEMIESZCZANIE` — zaczyna się ok. **linii 148**, zawiera:
  - typy makro/sub i zasady przejść
  - `### FORMAT JSON ODPOWIEDZI` (`null`/`move`/`create`)
  - `### KOMPATYBILNOŚĆ Z ROLL CUE I COMBAT_START`
  - `### BLOKADA RUCHU` (reakcja na `[LOCATION_BLOCKED: …]`)
  - **Brak** reguł semantycznych o używaniu listy z kontekstu — to właśnie dodajemy
- **Czego NIE ruszać:**
  - Składnia `location_intent` JSON — bez zmian
  - Pozostałe sekcje promptu (walka, statystyki, roll cue, język)
  - `docker-compose.yml` prod
  - `data/ai_gm.db`
- **Ważne:** `[LOCATION CONTEXT]` **nie jest tekstem statycznym** w `system_prompt.txt` — trafia do GM jako **osobna druga wiadomość systemowa** z backendu. Przy braku `current_location_id` backend **całkowicie pomija** ten blok (log `location_context_skipped`) — GM nie widzi pustego nagłówka, po prostu go nie ma.

---

## Implementacja (REV 2)

### Krok 0 — Commit przed implementacją

```bash
git branch --show-current   # musi być: phase-8d-location-integrity
rm -rf backend/tmp_loc1_push/
git add -A && git commit -m "feat: LOC-1 location context injection do LLM"
```

### Krok 1 — Dodaj podsekcję `### UŻYWANIE KONTEKSTU LOKACJI`

W `backend/prompts/system_prompt.txt`, w sekcji `## LOKALIZACJE I PRZEMIESZCZANIE`, **przed** `### FORMAT JSON ODPOWIEDZI`:

```
### UŻYWANIE KONTEKSTU LOKACJI

Przed każdą turą backend może przesłać Ci blok [LOCATION CONTEXT] jako osobną
wiadomość systemową. Zawiera aktualną pozycję postaci i listę znanych lokacji.

Gdy OTRZYMASZ blok [LOCATION CONTEXT]:

1. action: move — używaj WYŁĄCZNIE kluczy lokacji z listy known_locations.
   Nie wymyslaj lokacji spoza tej listy. Jeśli gracz chce przejść do miejsca
   którego tam nie ma — opisz to narracyjnie ("droga jest nieznana", "musisz
   najpierw się tam dostać") i NIE emituj action: move.

2. action: create — tylko gdy gracz faktycznie odkrywa NOWE miejsce poprzez
   eksplorację lub narracyjne działanie. Nie twórz duplikatów lokacji
   które już są na liście.

3. Deklaracje stanu gracza ("jestem na plaży", "wchodzę do lasu") to INTENCJA,
   nie fakt. Postać pozostaje w current_location dopóki GM narracyjnie
   przeprowadzi ją przez przejście i wyemituje action: move.

4. Nie przenosimy postaci bez narracji przejścia. Przykład:
   NAJPIERW: "Wychodzisz z karczmy na rynek wioski, chłodne powietrze uderza
   Ci w twarz."
   DOPIERO POTEM: action: move z key rynku.

Gdy NIE OTRZYMASZ bloku [LOCATION CONTEXT] (brak ustalonej lokacji w silniku):

- Dla opening scene — możesz użyć action: create aby ustanowić pierwszą lokację.
- W pozostałych przypadkach — prowadź narrację bez emitowania location_intent
  (ustaw location_intent: null) i opisz scenę bez określania konkretnej lokacji.
```

### Krok 2 — Czego NIE zmieniać

- Składni JSON w `### FORMAT JSON ODPOWIEDZI` — **bez zmian**
- Sekcji `### BLOKADA RUCHU` — **bez zmian**
- Sekcji `### KOMPATYBILNOŚĆ Z ROLL CUE I COMBAT_START` — **bez zmian**

### Krok 3 — Weryfikacja manualna na DEV

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build backend
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
# Test 1: gracz deklaruje ruch do miejsca spoza known_locations
# Oczekiwane: GM narracyjnie, location_intent: null
# Test 2: kampania bez current_location_id
# Oczekiwane: GM bez action: move/create
docker logs ai-gm-dev-backend-1 --tail=30 | grep -E "location_context|location_intent"
```

### Krok 4 — Brak testów jednostkowych

Zmiany w `system_prompt.txt` nie wymagają testów jednostkowych.

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8d-location-integrity`
2. **Working tree:** nie czysty — zmiany z LOC-1 + nowy `test_loc1_location_context_block.py` + `backend/tmp_loc1_push/` (do usunięcia).
3. **Sekcja `## LOKALIZACJE I PRZEMIESZCZANIE`:** od ok. linii 148; zawiera typy makro/sub, format JSON, kompatybilność z roll cue/combat_start, blokadę ruchu `[LOCATION_BLOCKED]`. **Brak** reguł semantycznych o używaniu listy z kontekstu.
4. **`[LOCATION CONTEXT]` w pliku:** nie występuje — blok trafia wyłącznie jako druga wiadomość systemowa z backendu (LOC-1).
5. **Długość pliku:** 295 linii przed / 326 po.
6. **LOC-1 status:** wdrożony, działa — brak blokera pod LOC-2.

**Uwaga Cursora:** przy braku `current_location_id` backend **całkowicie pomija blok** — reguła powinna mówić "gdy nie otrzymasz bloku", nie "gdy blok jest pusty". Poprawione w REV 2.

---

## Co zostało zrobione *(Cursor)*

- W `backend/prompts/system_prompt.txt` dodano podsekcję **`### UŻYWANIE KONTEKSTU LOKACJI`** przed `### FORMAT JSON ODPOWIEDZI` z kompletnym zestawem reguł: `move` tylko z `known_locations`, `create` tylko przy realnym odkryciu, deklaracje gracza vs `current_location`, narracja przejścia przed `move`, zachowanie gdy backend **nie wysłał** bloku.
- Poprawka językowa w przykładzie: „uderza Ci w twarz” (biernik).
- Usunięto `backend/tmp_loc1_push/`.
- Plik: **326 linii** (było 295).
- **Commit** — do wykonania osobno przez właściciela (Cursor nie wykonał kroku 0).

**Rebuild DEV wymagany:** `docker compose -f docker-compose.dev.yml up -d --build backend`

---

## Notatki po implementacji *(Perplexity)*

- **Brak commitów z LOC-1 i LOC-2** — Cursor nie wykonał kroku 0. Przed przekazaniem PROMPT 14 (LOC-3) do implementacji **należy scommitować working tree**: `git add -A && git commit -m "feat: LOC-1 context injection + LOC-2 system prompt rules"`. Jeden commit obejmujący oba zadania jest w porządku — lub dwa osobne jeśli chcesz czyściejszą historię (LOC-1 osobno, LOC-2 osobno).
- **Rebuild DEV** przed testowaniem LOC-2: `system_prompt.txt` jest kopiowany do obrazu przy `COPY` — bez rebuild Cursor/GM serwuje starą wersję promptu.
- **System prompt 326 linii** — przyrost o 31 linii to rozsądny zakres. Warto monitorować czy dodanie nowej podsekcji nie wchodzi w kolizję z `### BLOKADA RUCHU` (która obsługuje `[LOCATION_BLOCKED]` — osobny mechanizm backendowy, niezależny od `[LOCATION CONTEXT]`).
- **Uwaga dla LOC-3 (PROMPT 14):** guard backendu musi być spójny z Opcją A (graf sąsiedztwa) z LOC-1 — walidacja `target_key` przy `action: move` powinna sprawdzać ten sam zbiór lokacji co `known_locations` z bloku kontekstu. Szkic REV 1 w PROMPT 14 używa `campaign_id` i `location_key` — oba błędne (brak `campaign_id` w `game_locations`, kolumna to `key`). Perplexity poprawi przed REV 2.
