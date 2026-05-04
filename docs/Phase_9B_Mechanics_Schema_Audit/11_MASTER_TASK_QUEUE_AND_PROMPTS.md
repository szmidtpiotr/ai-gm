# Master: kolejka zadań + prompty (jeden plik)

<!-- MASTER_STATUS: ACTIVE -->
<!-- LAST_UPDATE: 2026-05-04 -->
<!-- NOTATKI_IMPL: uzupełniane przy każdym wdrożeniu (T01–T15 OK 2026-05-04) -->
<!-- FORMAT: szablon jak ../../skills/_UNIVERSAL_CURSOR_PROMPT_TEMPLATE.md -->

**Cel:** Jedna lista **kolejności realizacji**, odhaczanie postępu (`[ ]` → `[x]`), oraz pod spodem **każde zadanie jako PROMPT** (Cel → Kontekst → Pytania blokujące → Implementacja → Co zostało zrobione).

**Zasady pracy**

1. Realizuj **według Lp** (kolumna *Zależność* — nie zaczynaj zadania, dopóki poprzednie wymagane nie są `[x]`).
2. Po rozpoczęciu: w sekcji PROMPT ustaw `STATUS: IN_PROGRESS` → po zakończeniu `STATUS: DONE` i wypełnij **Co zostało zrobione**.
3. Ustaw `[x]` w tabeli §1 dla ukończonego wiersza.
4. Po **każdym wdrożeniu** uzupełnij **Notatki po implementacji** u danego ID (operacyjne: regresja, config, bezpieczeństwo, dług techniczny, link do PR/commit).

**Uchwały źródłowe:** [`04_decisions_log.md`](04_decisions_log.md) — **[S11b]**, **[S10e]**, **[S10d]**, **[IMPL]**, **[AUDIT]**; spec: [`07_extended_design_spec.md`](07_extended_design_spec.md) §7.

---

## 1. Kolejka realizacji (odhaczanie)

> Zaznaczaj `[x]` po ukończeniu. Kolumna **Zależność** = minimalny Lp, który musi być gotowy wcześniej (lub `—`).

| Lp | ID | Gotowe | Zadanie (skrót) | Zależność | Uchwała / blok |
|----|-----|:------:|-----------------|-----------|----------------|
| 1 | **T01** | [x] | Test: **jeden** prompt rollup (gracz+MG) vs **dwa** prompty — jakość, leak, JSON | — | **[S11b]** |
| 2 | **T02** | [x] | Migracja + model: **dwa zapisy** rollupu (`audience` / `kind` lub druga tabela) | T01 | **[S11b]** |
| 3 | **T03** | [x] | **Prompt** podsumowania gracza: **tylko** transkrypt — **bez** `gm_plan_json` w kontekście | T02 | **[S11b]** |
| 4 | **T04** | [x] | **Prompt** wersji MG: transkrypt **+** plan (`gm_plan_json`) | T02 | **[S11b]** |
| 5 | **T06** | [x] | **`gm_plan_json` W1**: `gm_plan_schema` (normalize, merge, format), PATCH, §7.1, testy | — | **[S11b]**, W2 backlog |
| 6 | **T05** | [x] | Po zapisie postaci: **generacja planu do skutku**; **blokada** pierwszej narracji bez planu | T06 | **[S11b]** |
| 7 | **T07** | [x] | API / serializacja: **gracz nie dostaje** `gm_plan_json` w GET kampanii (lista + szczegóły) | T06 | **[S11b]** |
| 8 | **T08** | [x] | Multiplayer: **cooldown** odświeżenia rollupu **per `campaign_id`** | T02 | **[S11b]** |
| 9 | **T09** | [x] | UI: stan **„wymaga odświeżenia”** po błędzie LLM rollupu | T02 | **[S11b]** |
| 10 | **T10** | [x] | **Fala [IMPL] 1:** auto / prog tur / cron `POST …/history/summary/ensure` | T02–T04 (logicznie po dual zapisie) | **[IMPL]** |
| 11 | **T11** | [x] | Zamknięcie **[AUDIT]**: synchronizacja [`06_schema_gaps.md`](06_schema_gaps.md) + wpis w `04` | — | **[AUDIT]** |
| 12 | **T12** | [x] | Tabela nagród XP **[S10e]** + minimalny odczyt w silniku / admin | — | **[S10e]** |
| 13 | **T13** | [x] | Player rulebook: lekki rozdział **XP** (blok D agendy) | T12 (opcjonalnie równolegle po szkicu tabeli) | Blok **D** |
| 14 | **T14** | [x] | **W2** (tabela `campaign_story_beats`): tylko jeśli T06–T07 niewystarczają — ADR + migracja | T06 | **[S11b]** |
| 15 | **T15** | [x] | **Nowy akt** w tym samym `campaign_id`: trigger po głównym queście → ten sam LLM co start + narracja spinająca | T05, T06 | **[S11b]** |
| 16 | **T16** | [x] | **[IMPL] fala 2:** broń / `weapon_type` ↔ atak, finesse, dwuręczność | T11 częściowo | **[IMPL]**, **[S1]** |
| 17 | **T17** | [ ] | **[IMPL] fala 3:** `effect_json` + walidacja admin | T11 | **[IMPL]**, **[S13]** |
| 18 | **T18** | [ ] | **[IMPL] fala 4:** warunki + konsumable / `item_key` | T17 | **[IMPL]**, **[S6]** |
| 19 | **T19** | [ ] | **[IMPL] fala 5:** import / snapshot / ostrzeżenia | T11 | **[IMPL]**, **[S7]** |
| 20 | **T20** | [ ] | **[IMPL] fala 6:** dywergencja (heurystyka / drugi LLM) + UI plan MG (admin) | T05–T07 | **[IMPL]**, **[S11]** |
| 21 | **T21** | [ ] | **[IMPL] fala 7:** progres cech za XP (meta + endpoint) | T12 | **[IMPL]**, **[S10]** |

**Uwaga kolejności:** W tabeli **T06** jest przed **T05** (najpierw szkielet planu, potem blokada pierwszej narracji).

### Backlog — poza numeracją T01–T21 (żeby nie umknęło)

| ID | Opis |
|----|------|
| **B01** | **DONE (2026-05-04):** panel admin ma formularz do zmiany globalnej wartości **`game_config_meta.summary_rollup_cooldown_turns`** (`/api/settings/summary`, sekcja Config). |
| **B02** | **DONE (2026-05-04):** „Podgląd dual (T01)” **zostaje**, ale jest sterowany ustawieniem **`dual_summary_preview_mode`** (`owner` / `owner_admin` / `off`). Nadal **nie zapisuje** do DB; to ścieżka QA, osobna od produkcyjnego rollupu T02. |

---

## 2. PROMPTY — T01

<!-- STATUS_T01: DONE -->

### T01 — Test: jeden prompt (gracz + MG) vs dwa prompty

**Cel:** Na podstawie realnego lub mock LLM ustalić, czy **wariant A** (jeden call, dwa pola JSON) jest **wystarczający** — jeśli tak, wdrożyć tylko A (**mniej ścieżek = mniej pomyłek**, **[S11b]**).

**Kontekst techniczny:** [`backend/app/services/history_summary_service.py`](../../backend/app/services/history_summary_service.py); [`backend/prompts/history_summary_prompt.txt`](../../backend/prompts/history_summary_prompt.txt); [`backend/app/history_summary_prompt_loader.py`](../../backend/app/history_summary_prompt_loader.py).

**Nowy moduł (wariant A):** [`backend/app/services/history_summary_dual_prompt.py`](../../backend/app/services/history_summary_dual_prompt.py)

**⛔ Pytania blokujące przed testem**

1. Czy środowisko ma działający LLM lub mock zwracający stały JSON?
2. Czy transkrypt testowy jest **anonimowy** i krótki (10–20 tur)?

**Implementacja (kroki)**

1. Przygotuj wariant **A**: jeden prompt zwracający `{"player_summary","gm_notes"}` — `gm_notes` może używać planu; **player_summary** tylko z transkryptu.
2. Uruchom min. **3×** wariant A; zapisz halucynacje w `player_summary`.
3. Opcjonalnie porównaj z wariantem **B** (dwa calla).
4. Wniosek zapisz w **Co zostało zrobione** + rekomendacja A lub B.

**Co zostało zrobione**

- **`history_summary_dual_prompt.py`:** `DUAL_SINGLE_SYSTEM_PROMPT`, `build_dual_single_messages`, `parse_dual_json_response` (JSON + opcjonalna obudowa markdown code fence), `leaked_plan_tokens_in_player_summary` (heurystyka wycieku planu do `player_summary`).
- **`tests/test_history_summary_t01_dual_prompt.py`:** unittest — uruchom: `cd backend && PYTHONPATH=. python3 -m unittest tests.test_history_summary_t01_dual_prompt -v`.
- **Frontend (bez konsoli):** w modalu **„Podsumowanie kampanii”** przycisk **„Podgląd dual (T01)”** jest widoczny zgodnie z globalnym ustawieniem **`dual_summary_preview_mode`** z `/api/settings/summary`: `owner` = właściciel kampanii; `owner_admin` = właściciel z rolą global admin; `off` = ukryty. Endpoint: `POST /api/campaigns/{id}/dual-summary-preview` (router `campaigns.py`, żeby uniknąć 404 na starych obrazach bez `campaign_history`). **Nie zapisuje** w `campaign_ai_summaries`.
- **Czy to zostaje / czy zniknie:** **Tak — nadal ma sens.** To nie jest duplikat docelowego rollupu (T02): w grze chodzi o zapisane podsumowania z `POST …/history/summary` (`audience=player|gm`). Podgląd dual to **osobne** wywołanie: jeden prompt, **brak zapisu** w `campaign_ai_summaries` — do QA / porównania jakości. Po **B02** dostęp jest po prostu **konfigurowalny** z panelu admin, zamiast twardo zaszyty.
- **Live 3× LLM:** wykonaj przez UI jak wyżej; wynik możesz dopisać w **Notatki** poniżej.

**Rekomendacja (po kodzie, przed pełnym live):** przyjmij **wariant A** w T02/T03 z parsowaniem JSON + logowaniem heurystyki; wariant B tylko jeśli podgląd z UI pokaże powtarzalne halucynacje.

**Notatki po implementacji**

- Seria **live 3× LLM** z UI (podgląd dual): wyniki halucynacji / stabilność JSON można dopisać tutaj lub w osobnym logu QA po ręcznym przebiegu.
- **Podgląd dual** nie zastępuje produkcyjnego rollupu — do porównania wariantu A; rollout T02/T03 jest w osobnych endpointach z zapisem.

---

## 3. PROMPTY — T02

<!-- STATUS_T02: DONE -->

### T02 — Dwa rekordy rollupu (gracz vs MG) w DB

**Cel:** Rozdzielić zapis podsumowania zgodnie z **[S11b]** (dwa rekordy lub `audience` / `kind` w `campaign_ai_summaries`).

**Kontekst techniczny:** migracje w [`backend/app/main.py`](../../backend/app/main.py) / [`migrations_admin.py`](../../backend/app/migrations_admin.py); API [`campaign_history`](../../backend/app/api/campaign_history.py) (jeśli tam zapis).

**⛔ Pytania blokujące**

1. Czy migracja jest akceptowalna na dev (reset DB OK)?
2. Czy istniejące wiersze `campaign_ai_summaries` dostaną domyślne `audience=player`?

**Implementacja**

1. Dodaj kolumnę (np. `audience TEXT NOT NULL DEFAULT 'player'`) lub drugą tabelę — **jedna** spójna decyzja w ADR w PR.
2. Zaktualizuj INSERT/SELECT przy zapisie i odczycie ostatniego podsumowania per audience.
3. Testy jednostkowe migracji / round-trip.

**Co zostało zrobione**

- **Decyzja:** jedna tabela + kolumna `audience` (`player` | `gm`), domyślnie `player` dla istniejących wierszy (migracja `_ensure_campaign_ai_summaries_audience` + `RAW_MIGRATIONS` w `main.py`).
- **Zapis:** `persist_summary(..., audience=…)`; endpointy `POST/GET …/history/summary` i `…/ensure` przyjmują query `audience` (pattern `player|gm`), domyślnie `player`.
- **Narracja:** `fetch_latest_saved_summary_for_narrative` — najpierw ostatni `gm`, w przeciwnym razie `player` (kompatybilność z samym stosem `player`).
- **`/mem`:** corpus tylko z wierszy `audience=player` (żeby nie mieszać treści MG-only).
- **Testy:** `backend/tests/test_history_summary_t02_audience.py`.

**Notatki po implementacji**

- Migracja `audience` jest **idempotentna** na starych DB; istniejące wiersze dostają domyślnie `player`.
- Przy **imporcie** snapshotów konfiguracji / dumpów z innego środowiska sprawdzać spójność `audience` w `campaign_ai_summaries`, żeby nie „podmienić” stosu gracza wierszem MG.

---

## 4. PROMPTY — T03

<!-- STATUS_T03: DONE -->

### T03 — Prompt rollupu **gracza**: wyłącznie transkrypt

**Cel:** W promptcie generującym tekst dla gracza **nie** wklejać `gm_plan_json`; twarda instrukcja: tylko fakty z transkryptu (**[S11b]**).

**Kontekst:** plik promptu + `history_summary_service`.

**⛔ Pytania blokujące**

1. Czy T02 już rozdziela ścieżki zapisu?

**Implementacja**

1. Osobna funkcja lub flaga `audience=player` wołająca LLM **tylko** z `format_transcript(...)`.
2. Reguły w system prompt (PL/EN wg kampanii).
3. Test: plan zawiera sekretny NPC nieobecny w czacie → **nie** może pojawić się w `player_summary`.

**Co zostało zrobione**

- **Ścieżka runtime:** `generate_campaign_summary(..., audience=...)` w [`history_summary_service.py`](../../backend/app/services/history_summary_service.py); dla `audience=player` do system promptu dopinana jest jawna reguła „tylko fakty z transkryptu”, bez użycia `gm_plan_json`.
- **API:** [`campaign_history.py`](../../backend/app/api/campaign_history.py) przekazuje `audience` do generatora; ścieżka `player` jest więc formalnie oddzielona od przyszłej ścieżki `gm`.
- **Admin / persist:** [`admin_campaigns.py`](../../backend/app/services/admin_campaigns.py) jawnie zapisuje regenerowany summary jako `audience=player`, żeby nie mieszać go z MG-only backlogiem T04.
- **Test regresyjny:** [`backend/tests/test_history_summary_t03_player_only.py`](../../backend/tests/test_history_summary_t03_player_only.py) sprawdza, że sekret z `gm_plan_json` nie trafia do promptu gracza oraz że `gm` nie dostaje przez przypadek player-only instrukcji.
- **Weryfikacja:** lokalnie i na `.61` zielone: `tests.test_history_summary_t01_dual_prompt`, `tests.test_history_summary_t02_audience`, `tests.test_history_summary_t03_player_only`.

**Notatki po implementacji**

- **Regresja:** każda zmiana w gałęzi `audience=player` w `generate_campaign_summary` → uruchomić `tests/test_history_summary_t03_player_only.py`.
- **`/mem`** celowo czyta tylko rollup **player** — zmiana tego zachowania wymaga uzgodnienia z T02 (mieszanie treści MG-only z pamięcią gracza).

---

## 5. PROMPTY — T04

<!-- STATUS_T04: DONE -->

### T04 — Prompt rollupu **MG**: transkrypt + plan

**Cel:** Drugi call (lub druga gałąź w wariancie A z T01) z dostępem do `gm_plan_json` + transkryptu.

**Implementacja**

1. Zbuduj blok planu wspólnie z narracją: `format_gm_plan_block` w [`gm_plan_schema.py`](../../backend/app/services/gm_plan_schema.py) (używane w `game_engine` i rollupie MG).
2. Zapis pod `audience=gm` (lub równoważnie).
3. Upewnij się, że endpoint dla gracza **nigdy** nie zwraca tego pola.

**Co zostało zrobione**

- **Ścieżka runtime:** `generate_campaign_summary(..., audience="gm")` buduje prompt MG-only w [`history_summary_service.py`](../../backend/app/services/history_summary_service.py) z osobnym `GM_SUMMARY_SYSTEM_APPEND`.
- **Kontekst planu:** do wersji MG dokładany jest blok `[PLAN_MG]...[/PLAN_MG]` oparty o sformatowane `gm_plan_json` (roadmapa, cele sceny, haki, ordinal), plus `[TRANSKRYPT]`.
- **Persist / API:** istniejące endpointy `campaign_history.py` zapisują i odczytują `audience=gm` bez zmian kontraktu T02; T03 (`player`) pozostało odseparowane.
- **Testy:** nowy plik [`backend/tests/test_history_summary_t04_gm_context.py`](../../backend/tests/test_history_summary_t04_gm_context.py) sprawdza, że prompt MG dostaje plan i nie używa player-only reguł.
- **Weryfikacja:** lokalnie i na `.61` zielone: `tests.test_history_summary_t01_dual_prompt`, `tests.test_history_summary_t02_audience`, `tests.test_history_summary_t03_player_only`, `tests.test_history_summary_t04_gm_context`.

**Notatki po implementacji**

- Prompt MG jest **cięższy** niż player (transkrypt + `[PLAN_MG]`): przy bardzo długich kampaniach warto monitorować limity kontekstu LLM i ewentualnie skrócić `max_turns` po stronie wywołania.
- Separacja T03/T04 utrzymuje zgodność z **[S11b]** — nie doklejać planu do ścieżki player „dla wygody”.

---

## 6. PROMPTY — T06

<!-- STATUS_T06: DONE -->

### T06 — `gm_plan_json` **W1**: szkielet, merge, dokumentacja

**Cel:** MVP planu w jednym JSON na kampanii; **W2** tylko jeśli nie starczy (**[S11b]**).

**Implementacja**

1. Ustal `schema_version` + pola: np. `arcs`, `active_arc_id`, `scene_goals`, sekcja prywatna pod przyszłe beaty.
2. Funkcja **merge** (płytki lub głęboki merge pod kluczami — dokumentacja).
3. Opisz w `07_extended_design_spec.md` §7 lub komentarzu w kodzie.

**Co zostało zrobione**

- Moduł [`backend/app/services/gm_plan_schema.py`](../../backend/app/services/gm_plan_schema.py): `schema_version = 2`, `normalize_gm_plan`, `merge_gm_plan_patch` (m.in. legacy flat PATCH → aktywny łuk), `format_gm_plan_block`.
- API: [`campaigns.py`](../../backend/app/api/campaigns.py) — `PATCH /gm-plan` używa merge zamiast `{**a,**b}`; `advance-scene` dopisuje log pod aktywnym łukiem.
- Narracja / rollup: [`game_engine.py`](../../backend/app/services/game_engine.py), [`history_summary_service.py`](../../backend/app/services/history_summary_service.py) — jeden formatter z `gm_plan_schema`.
- Dokumentacja: [`07_extended_design_spec.md`](07_extended_design_spec.md) §7.1.
- Testy: [`backend/tests/test_gm_plan_schema.py`](../../backend/tests/test_gm_plan_schema.py), zaktualizowany [`test_history_summary_t04_gm_context.py`](../../backend/tests/test_history_summary_t04_gm_context.py).

**Notatki po implementacji**

- PATCH **legacy** (płaskie klucze) jest mapowany na **aktywny łuk** — zachowanie opisane w §7.1 specyfikacji; przy refaktorze merge nie łamać testów `test_gm_plan_schema`.
- **W2** (`campaign_story_beats` itd.) — **T14 (2026-05-04):** decyzja **odroczenia** — W1 wystarcza MVP; szczegóły [`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md). W2 — po nowym ADR, jeśli W1 przestanie wystarczać.

---

## 7. PROMPTY — T05

<!-- STATUS_T05: DONE -->

### T05 — Generacja planu po postaci **do skutku** przed pierwszą narracją

**Cel:** Pierwsza wiadomość MG w czacie **dopiero** po sukcesie zapisu planu (retry / kolejka), **[S11b]**.

**Kontekst:** [`backend/app/api/characters.py`](../../backend/app/api/characters.py) (zapis postaci); [`turns.py`](../../backend/app/api/turns.py) / `game_engine` — pierwsza narracja.

**⛔ Pytania blokujące**

1. Czy T06 dostarczył minimalny kształt JSON planu?

**Implementacja**

1. Hook po `POST` zapisu postaci (lub końcowy krok kreatora): wywołanie generatora planu LLM.
2. Pętla / limit retry; przy fiasku — komunikat użytkownikowi, **brak** pustej narracji.
3. Test integracyjny: nowa postać → plan niepusty → dopiero pierwsza narracja.

**Co zostało zrobione**

- [`gm_plan_schema.gm_plan_is_ready`](../../backend/app/services/gm_plan_schema.py) — minimalna treść planu przed narracją LLM.
- [`gm_plan_generation_service`](../../backend/app/services/gm_plan_generation_service.py) — LLM JSON → W1, max 3 próby, zapis do `campaigns.gm_plan_json`; `retry_initial_gm_plan_for_campaign` dla ponowienia.
- [`characters.create_character`](../../backend/app/api/characters.py) — najpierw generacja planu, potem opening scene + pierwsza tura tylko gdy `gm_plan_ready`; w odpowiedzi `gm_plan_ready` / `gm_plan_error`.
- [`turns`](../../backend/app/api/turns.py) — przed `run_narrative_turn` / stream: `409` gdy brak planu i **0** tur narracyjnych (legacy kampanie z turami bez zmian).
- [`POST /api/campaigns/{id}/gm-plan/generate-initial`](../../backend/app/api/campaigns.py) — owner: ponowienie generacji planu.
- Testy: [`test_t05_gm_plan_generation.py`](../../backend/tests/test_t05_gm_plan_generation.py), rozszerzony [`test_gm_plan_schema.py`](../../backend/tests/test_gm_plan_schema.py).

**Notatki po implementacji**

- **Legacy:** kampanie, które już mają tury narracyjne, nie dostają twardego bloku „brak planu” na pierwszej kolejnej turze (blokada dotyczy głównie **0 tur** narracyjnych).
- **Recovery:** owner może użyć `POST …/gm-plan/generate-initial`, gdy plan nie powstał przy tworzeniu postaci (LLM timeout / błąd).
- Po zmianach w warunku „gotowy plan” → regresja: `test_t05_gm_plan_generation`, `gm_plan_is_ready`.

---

## 8. PROMPTY — T07

<!-- STATUS_T07: DONE -->

### T07 — API: `gm_plan_json` niewidoczne dla gracza

**Cel:** Listy i GET kampanii dla roli gracza **nie** zwracają planu; tylko owner/admin/debug (**[S11b]**).

**Implementacja**

1. Przejrzyj [`campaigns.py`](../../backend/app/api/campaigns.py) i serializację w listach.
2. Test API: klient gracza nie widzi klucza `gm_plan_json`.

**Co zostało zrobione**

- **`GET /api/campaigns/{id}`:** query `user_id` (opcjonalny) — bez niego lub dla nieuprawnionego widza klucz `gm_plan_json` jest **usuwany** z JSON. Uprawnieni: właściciel kampanii, `users.is_admin=1`, rola `gm`/`admin` w `campaign_members`.
- **`GET /api/campaigns` (lista):** bez zmian — SELECT już nie zawiera `gm_plan_json`.
- **`POST /campaigns`:** odpowiedź filtrowana tym samym helperem (dla zwykłego tworzenia właściciel = `owner_user_id` — plan nadal widoczny).
- **Frontend:** [`config.js`](../../frontend/js/config.js) — `window.apiCampaignGetUrl(id)` z `?user_id=` gdy jest `playerUserId`; użyte przy preflight przed tworzeniem postaci ([`actions.js`](../../frontend/js/actions.js)).
- **Testy:** [`backend/tests/test_phase9b_t07_campaign_gm_plan_visibility.py`](../../backend/tests/test_phase9b_t07_campaign_gm_plan_visibility.py).

**Notatki po implementacji**

- Query **`user_id`** określa „widza” dla GET szczegółów — to nie zastępuje pełnego modelu auth sesji; przy przyszłym JWT/API keys warto spiąć z jednym źródłem tożsamości.
- **Frontend:** właściciel musi wywoływać GET z `?user_id=` (np. `apiCampaignGetUrl`), inaczej plan nie wraca — celowe dla bezpieczeństwa T07.

---

## 9. PROMPTY — T08

<!-- STATUS_T08: DONE -->

### T08 — Cooldown odświeżenia rollupu **per kampania**

**Cel:** W MP każdy może wymusić odświeżenie, ale nie częściej niż co **N** rund (np. 20) **dla całej kampanii**, **[S11b]**.

**Implementacja**

1. Kolumna `campaigns.last_summary_turn` lub licznik w meta.
2. Walidacja w `POST …/history/summary` (lub ensure).
3. Konfiguracja N w `game_config_meta` lub stała na start.

**Co zostało zrobione**

- **Migracja:** `campaigns.last_rollup_narrative_turn_count` — kotwica = liczba tur narracyjnych (`COUNT(*)` z `campaign_turns` dla `route='narrative'`) po ostatnim udanym rollupie LLM (**wspólna** dla całej kampanii, bez rozdziału player/gm).
- **Konfiguracja:** klucz `game_config_meta.summary_rollup_cooldown_turns` (domyślnie **20** przy braku wpisu); zakres 1–500.
- **`POST /campaigns/{id}/history/summary`:** przed LLM sprawdzenie cooldownu — przy blokadzie **429** z polami `cooldown_turns`, `turns_until_allowed`, `narrative_turn_count`, `last_rollup_narrative_turn_count`.
- **`POST …/history/summary/ensure`:** jeśli wg `stale_after_turns` trzeba by odświeżyć, ale cooldown blokuje — zwracany jest **ostatni zapisany** skrót z `refreshed: false`, `cooldown_active: true`, `turns_until_summary_rollup_allowed`.
- **Po każdym udanym wywołaniu** `generate_campaign_summary` (łącznie puste podsumowanie / `persist=false`) wywoływane jest „dotknięcie” kotwicy; **admin** `regenerate_campaign_summary_admin` też aktualizuje kotwicę po zapisie.
- **Testy:** [`backend/tests/test_phase9b_t08_rollup_cooldown.py`](../../backend/tests/test_phase9b_t08_rollup_cooldown.py).

**Notatki po implementacji**

- Zmiana wartości **N**: panel admin **Config** → `/api/settings/summary` → pole `summary_rollup_cooldown_turns`; zapis do `game_config_meta`.
- **`ensure`** przy blokadzie cooldownu zwraca ostatni skrót + `cooldown_active` — obsługa w modalu historii (**T09**); **429** na `POST …/history/summary` mapowany + fallback GET ostatniego skrótu.
- Kotwica jest **wspólna** dla player/gm — jedna kampania = jeden licznik odstępu między kosztownymi rollupami LLM.

---

## 10. PROMPTY — T09

<!-- STATUS_T09: DONE -->

### T09 — UI: „wymaga odświeżenia” po błędzie rollupu

**Cel:** Gdy LLM rollup się wywali — czytelny stan + ewent. ostatnia dobra wersja (**[S11b]**).

**Kontekst:** [`frontend/js/app.js`](../../frontend/js/app.js) (modal podsumowania), endpointy summary.

**Implementacja**

1. Mapowanie kodów błędów z API na komunikat.
2. Opcjonalnie flaga `summary_stale` w odpowiedzi kampanii.

**Co zostało zrobione**

- **[`frontend/index.html`](../../frontend/index.html):** baner `#history-summary-banner` (stan / ostrzeżenie / błąd) nad treścią skrótu.
- **[`frontend/js/app.js`](../../frontend/js/app.js):** `_parseHistorySummaryDetail`, `formatHistorySummaryApiError` (502, 429 + obiekt `detail` z T08, 403, 404, 5xx, walidacja FastAPI); `fetchLatestSavedHistorySummary` — fallback `GET …/history/summary?audience=player`.
- **`loadHistorySummaryModalContent`:** przy błędzie **POST** ensure lub **POST** odświeżenia — komunikat PL + **ostatni zapisany skrót** z GET, jeśli istnieje; osobna ścieżka dla **`cooldown_active`** z ensure (T08) — baner z `turns_until_summary_rollup_allowed`; obsługa `warning` z API; catch sieciowy z tym samym fallbackiem GET.

**Notatki po implementacji**

- Flagi **`summary_stale` w GET kampanii** nie dodawano — wystarczy UI oparte na odpowiedziach endpointów historii + fallback GET (mniej zmian w API).
- Po wdrożeniu frontu: twardy refresh / bust cache, jeśli statyczne `app.js` są serwowane z CDN lub cache przeglądarki.

---

## 11. PROMPTY — T10

<!-- STATUS_T10: DONE -->

### T10 — Automatyzacja `history/summary/ensure` (**[IMPL]** fala 1)

**Cel:** Skrót fabuły nie jest przestarzały w nieskończoność — cron lub co N tur narracyjnych.

**Implementacja**

1. Worker / wywołanie po turze gdy `turn_number % N == 0`.
2. Konfiguracja N; nie łamać cooldownu T08.
3. Logi i metryki błędów.

**Co zostało zrobione**

- **`game_config_meta.summary_auto_ensure_every_n_narrative_turns`:** domyślnie `20` (migracja seed `INSERT OR IGNORE`), `0` = wyłączone; odczyt `get_summary_auto_ensure_every_n_narrative_turns` w `history_summary_service.py`.
- **Po każdym zapisie** wiersza `campaign_turns` z `route='narrative'` (`create_turn_log` w `turns.py`): jeśli `COUNT(narrative) % N == 0` i `N > 0`, wątek daemon wywołuje `run_ensure_campaign_history_summary` dla **właściciela** kampanii (`summary_ensure_automation.py`). Logika jak `POST …/ensure` — **cooldown T08** bez zmian (`run_ensure` zwraca cache / `cooldown_active`).
- **Router** `ensure` → `summary_ensure_service.run_ensure_campaign_history_summary` (wspólna ścieżka z automatyzacją).
- **Logi:** zdarzenie `summary_auto_ensure_result` (`ok`, `refreshed`, `cooldown_active`, błędy).

**Notatki po implementacji**

- Trigger po **commit** tury narracyjnej (nie osobny cron OS).
- Regulacja **N** jak cooldown T08 (`game_config_meta`); panel UI: `/api/settings/summary` (wdrożone w **B01**).

---

## 12. PROMPTY — T11

<!-- STATUS_T11: DONE -->

### T11 — Zamknięcie **[AUDIT]** (`06_schema_gaps` + `04`)

**Cel:** Wiersze w [`06_schema_gaps.md`](06_schema_gaps.md) zgodne z kodem i migracjami; wpis domknięcia w [`04_decisions_log.md`](04_decisions_log.md) przy **[AUDIT]**.

**Implementacja**

1. Dla każdego wiersza: `PRAGMA table_info` / grep → aktualizacja statusu.
2. Jeśli wszystko zamknięte: jedno zdanie w `04` z datą i wersją schematu.

**Co zostało zrobione**

- **[`06_schema_gaps.md`](06_schema_gaps.md):** ponowna tabela z kolumną **T11** — stan każdego obszaru vs `migrations_admin.py` + grep `backend/` (2026-05-04); nierozwiązane rzeczy oznaczone **Otwarte** z odnośnikiem do **T12** / **T16–T19** (nie zakładamy „braku luk” przy braku kodu).
- **[`04_decisions_log.md`](04_decisions_log.md):** sekcja **[AUDIT]** — **status closed**, data zamknięcia procesu, odnośnik do `config_version` (meta) i łańcucha migracji.

**Notatki po implementacji**

- Pełne „wyzerowanie” luk w DB **nie** jest warunkiem zamknięcia AUDIT — warunek to **jawna synchronizacja dokumentów** z repozytorium (uzgodnienie z § **[AUDIT]** w `04`).

---

## 13. PROMPTY — T12

<!-- STATUS_T12: DONE -->

### T12 — Tabela nagród XP **[S10e]**

**Cel:** Konfiguracja typu „słaby wróg → X XP”, „quest główny → Y XP” w DB; silnik czyta liczby, LLM nie jest źródłem prawdy.

**Implementacja**

1. Tabela `game_config_xp_rewards` (lub JSON w `game_config_meta` — wybór w PR z uzasadnieniem).
2. Minimalny panel admin / seed.
3. Powiązanie z `xp_award` / grantami bez duplikacji logiki.

**Co zostało zrobione**

- **Tabela `game_config_xp_rewards`** (migracja + seed wartości środkowe **[S10b]**): kategorie `enemy_tier`, `quest`, `mg_grant`; indeks po `category`.
- **Walka:** przy śmierci wroga priorytet `game_config_enemies.xp_award` > 0; w przeciwnym razie XP z wiersza `enemy_tier_{tier}` (pole `tier` zapisane w snapshotcie walki); meta grantu: `xp_source`, `enemy_tier`.
- **Grant MG:** `POST …/xp/grant-mg` — opcjonalne `reward_key` (kwota z tabeli); `GET …/characters/{id}/xp/reward-catalog` dla ownera (filtr `categories`).
- **Admin:** `GET /admin/xp-rewards`, `PATCH /admin/xp-rewards/{key}`; wpis w **catalog snapshot** import/export.
- **Testy:** [`backend/tests/test_phase9b_t12_xp_rewards.py`](../../backend/tests/test_phase9b_t12_xp_rewards.py).

**Notatki po implementacji**

- Quest-y nadal bez automatycznego silnika — wiersze `quest_*` są gotowe pod przyszłe wywołania; MG może użyć `reward_key` przy grantach ręcznych.

---

## 14. PROMPTY — T13

<!-- STATUS_T13: DONE -->

### T13 — Player rulebook — rozdział XP (blok D)

**Cel:** Lekki rozdział zgodny z **[S10b]**/**[S10c]**/**[S10d]** — bez obiecywania UI, którego nie ma.

**Implementacja**

1. Nowy plik lub sekcja w [`player_rulebook/`](player_rulebook/).
2. Zgodność z „tylko MG przyznaje XP fabularnie” / technicznie owner.

**Co zostało zrobione**

- Nowy plik [`player_rulebook/xp_pool_and_rewards.md`](player_rulebook/xp_pool_and_rewards.md): pula bez LVL, źródła XP (walka / konfiguracja / grant MG), odcinek vs tydzień (**[S10c]**), widełki orientacyjne bez nazw SQL, **LLM nie jest źródłem liczb** (**[S10d]**), fabularnie MG / technicznie właściciel kampanii.
- [`00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md): wiersz **4b** w spisie + odnośnik w zasadzie redakcyjnej §8.

**Notatki po implementacji**

- Nie opisano konkretnych przycisków ani ekranów — tylko zasady zgodne z uchwałami.

---

## 15. PROMPTY — T14

<!-- STATUS_T14: DONE -->

### T14 — **W2** `campaign_story_beats` (tylko gdy W1 nie starczy)

**Cel:** ADR + migracja **tylko** jeśli T06/T07 są niewystarczające (rozmiar, złożoność, locking).

**⛔ Blokada:** Nie zaczynaj, dopóki nie ma **pisemnej** decyzji w PR / `04` „W1 insufficient because …”.

**Implementacja**

1. ADR w `docs/`.
2. Tabela + API wewnętrzne + podpięcie do promptu MG.

**Co zostało zrobione**

- **Decyzja pisemna:** [`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md) — **W1 uznane za wystarczające** na MVP; **W2 nie migrowane** w tej iteracji; kryteria ponownej oceny w ADR.
- **[`04_decisions_log.md`](04_decisions_log.md):** doprecyzowanie **T14** pod sekcją **[S11b]** (W1 vs W2) + link do ADR.
- **[`06_schema_gaps.md`](06_schema_gaps.md):** osobny wiersz „W2 — świadomie odłożone”.

**Notatki po implementacji**

- Gdy pojawi się uzasadnienie z ADR (rozmiar JSON, locking beatów, silnik questów), **nowy** ticket: migracja `campaign_story_beats` + API — poza zamknięciem T14 w tej formie.

---

## 16. PROMPTY — T15

<!-- STATUS_T15: DONE -->

### T15 — **Nowy akt** w tej samej kampanii (bez nowego `campaigns`)

**Cel:** Warunek końca głównego questa → regeneracja planu (jak przy starcie) + narracja łącząca; **ciągłe** `campaign_turns` i numery tur (**[S11b]**).

**Implementacja**

1. Wykrycie „quest główny closed” (stan DB lub parser narzędzie LLM — uzgodnić w PR).
2. Wywołanie tego samego generatora planu co T05.
3. Test: brak nowego `campaign_id`.

**Co zostało zrobione**

- **Główny quest:** domyślny klucz `main_quest`; nadpisanie: `gm_plan_json.engine_private.main_quest_key` (owner może ustawić przez PATCH `…/gm-plan`). Wykrycie: `main_quest_just_completed(old_sheet, new_sheet, main_key)` — klucz pojawia się w `quests_completed` i wcześniej go tam nie było.
- **Pipeline:** [`new_act_service.py`](../../backend/app/services/new_act_service.py) — dwa wywołania LLM: (1) płaski JSON nowego łuku (jak T05) + **merge** W1: zamyka bieżący łuk (`status: closed`), dodaje `act_N` (`next_act_seq` w `engine_private`), ustawia `active_arc_id`; (2) krótka **narracja spinająca** dla gracza.
- **Nowa tura:** `INSERT` do `campaign_turns` (`route=narrative`, kolejny `turn_number`) — `user_text` znacznik `[Nowy akt]`, `assistant_text` = narracja łącząca (ciągła historia, bez nowego `campaign_id`).
- **Wyzwalacze:** `PATCH /characters/{id}/sheet` po zapisie merge oraz admin cheat `quest complete` (po `commit`); przy sukcesie cheat zwraca `result.new_act` (skrót pola pipeline).
- **Testy:** [`test_phase9b_t15_new_act.py`](../../backend/tests/test_phase9b_t15_new_act.py) (mock LLM + temp SQLite).

**Notatki po implementacji**

- Regeneracja planu to **osobny prompt** „nowy akt” (kontekst: poprzedni blok planu + skrót transkryptu), ale **ten sam kształt JSON** co [`generate_initial_gm_plan_with_retries`](../../backend/app/services/gm_plan_generation_service.py) (`arc_payload_from_flat_llm`).
- Brak gotowego `gm_plan_json` → pipeline zwraca błąd (`gm_plan_not_ready`); kampania `ended` → pomijane.
- **Restart backendu:** zalecany po wdrożeniu (nowy moduł importowany przy pierwszym triggerze).

---

## 17. PROMPTY — T16–T21 ([IMPL] fale 2–7 — skrót)

Poniżej: **jedno zdanie celu** + odesłanie do **[IMPL]**; pełne prompty można wydzielić do osobnych plików w kolejnej iteracji.

| ID | STATUS | Cel (jedno zdanie) | Główne pliki (orientacyjnie) |
|----|--------|-------------------|------------------------------|
| T16 | DONE | Mapowanie `weapon_type` ↔ rodzaj ataku + finesse / dwuręczność | `combat_service.py`, `dice.py`, `game_config_weapons` |
| T17 | PENDING | `effect_json` v0 + walidacja przy zapisie admina | `admin`, `items`, `conditions` |
| T18 | PENDING | Konsumable / `item_key` / migracja loot | `loot_service`, migracje |
| T19 | PENDING | Import: dokumentacja ryzyk + `catalog_snapshot` jako kanon | `admin_config_transfer.py`, docs |
| T20 | PENDING | Dywergencja **[S11]** + UI edycji planu (admin) | `game_engine`, admin |
| T21 | PENDING | Koszty statów za XP + endpoint spend | `game_config_meta`, `characters` API |

**Co zostało zrobione (T16–T21 — zbiorczo lub per ID)**

- **T16:** dodany wspólny runtime [`weapon_rules.py`](../../backend/app/services/weapon_rules.py) — wybór testu ataku z `weapon_type` (`melee_attack` / `ranged_attack` / `spell_attack`), finesse = wybór lepszego **STR/DEX** dla ataku i obrażeń przy broni zwinnej, `two_handed` = modyfikator ataku przez skill `two_handed` (fallback alias `great_weapon`; MVP: **+1** z treningiem / **-2** bez).
- **T16:** [`combat_service.py`](../../backend/app/services/combat_service.py) liczy `attack_roll` po stronie backendu na podstawie aktualnie wyposażonej broni; frontend panelu walki przestał zakładać stałe `STR`.
- **T16:** `/roll` dla testów ataku w [`turns.py`](../../backend/app/api/turns.py) jest weapon-aware — backend bierze bieżącą broń postaci zamiast ślepo ufać aliasowi wpisanemu przez klienta.
- **T16:** seed / default config dostał skill `two_handed`; testy: [`test_phase9b_t16_weapon_rules.py`](../../backend/tests/test_phase9b_t16_weapon_rules.py) + regresja [`test_phase8_combat.py`](../../backend/tests/test_phase8_combat.py).

**Notatki po implementacji**

- T16 **nie** dodaje jeszcze kolumn **[S12]** (`targeting`, `aoe_radius_m`, `magic_school`) ani pełnego sprawdzania zasięgu — to osobny follow-up schematu / taktyki.
- MVP dla `two_handed` celowo daje prosty efekt **na atak**, nie mnoży jednocześnie premii do obrażeń; liczby można później zbalansować bez zmiany kontraktu `weapon_rules.py`.
- **Restart backendu i frontendu wymagany** po wdrożeniu (backend combat + `/roll`, frontend panel walki).

---

## 18. Historia zmian tego pliku

| Data | Zmiana |
|------|--------|
| 2026-05-03 | Utworzenie master kolejki T01–T21 + prompty; jeden plik źródłowy. |
| 2026-05-03 | **T01 DONE** (kod + testy unittest); live 3× LLM — do uzupełnienia ręcznie. |
| 2026-05-04 | **T02 DONE** — kolumna `audience`, API query, narracja gm→player, testy. |
| 2026-05-04 | **T03 DONE** — player summary tylko z transkryptu, `audience` w generatorze, test regresyjny, restart backendu. |
| 2026-05-04 | **T04 DONE** — GM summary dostaje `gm_plan_json` + transkrypt, osobny test, restart backendu. |
| 2026-05-04 | **T15 DONE** — `new_act_service`: trigger po ukończeniu głównego questa, merge nowego łuku W1, tura narracji spinającej; test `test_phase9b_t15_new_act`. |
| 2026-05-04 | **T16 DONE** — `weapon_rules`: `weapon_type` → test ataku, finesse, `two_handed`; backend combat liczy `attack_roll`, `/roll` ataku stał się weapon-aware; test `test_phase9b_t16_weapon_rules` + regresja combat. |
| 2026-05-04 | Backlog **B01** (admin: edycja `summary_rollup_cooldown_turns`); doprecyzowanie przy T01: „Podgląd dual” zostaje jako QA, nie zamiennik rollupu produkcyjnego. |
| 2026-05-04 | Reguła pracy § Zasady pt. 4: **Notatki po implementacji** po każdym wdrożeniu; uzupełnione notatki dla **T01–T08**; placeholdery dla T09+. |
| 2026-05-04 | **B01/B02 DONE** — `/api/settings/summary` + panel admin (cooldown rollupu, tryb dostępu do dual preview: `owner` / `owner_admin` / `off`); frontend i backend respektują tryb podglądu dual. |
| 2026-05-04 | **T09 DONE** — modal historii: baner + mapowanie błędów + fallback ostatniego skrótu + cooldown z ensure (T08). |
