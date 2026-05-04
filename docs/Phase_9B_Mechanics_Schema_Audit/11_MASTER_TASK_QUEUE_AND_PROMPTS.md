# Master: kolejka zadań + prompty (jeden plik)

<!-- MASTER_STATUS: ACTIVE -->
<!-- LAST_UPDATE: 2026-05-04 -->
<!-- T01_ROW: DONE — zamknięte na stałe; follow-up „admin per kampania” to osobna praca (T20 / UX), NIE ponowne T01 ani cofanie [x]. -->
<!-- FORMAT: szablon jak ../../skills/_UNIVERSAL_CURSOR_PROMPT_TEMPLATE.md -->

**Cel:** Jedna lista **kolejności realizacji**, odhaczanie postępu (`[ ]` → `[x]`), oraz pod spodem **każde zadanie jako PROMPT** (Cel → Kontekst → Pytania blokujące → Implementacja → Co zostało zrobione).

**Zasady pracy**

1. Realizuj **według Lp** (kolumna *Zależność* — nie zaczynaj zadania, dopóki poprzednie wymagane nie są `[x]`).
2. Po rozpoczęciu: w sekcji PROMPT ustaw `STATUS: IN_PROGRESS` → po zakończeniu `STATUS: DONE` i wypełnij **Co zostało zrobione**.
3. Ustaw `[x]` w tabeli §1 dla ukończonego wiersza.
4. **Zadania już `[x]` (np. T01, T02):** nie cofaj checkboxa przy dopisywaniu follow-upów ani kolejnych fal — nowe wymagania przenoś do innego wiersza (np. T20) lub nowego ID; **T01 jest wykonane** (kod + testy + decyzja wariantu A); ewent. przeniesienie podglądu dual do admina to **osobny** element planu, nie „dokończenie T01”.
5. Opcjonalnie: **Notatki po implementacji** (Perplexity / człowiek).

**Uchwały źródłowe:** [`04_decisions_log.md`](04_decisions_log.md) — **[S11b]**, **[S10e]**, **[S10d]**, **[IMPL]**, **[AUDIT]**; spec: [`07_extended_design_spec.md`](07_extended_design_spec.md) §7.

---

## 1. Kolejka realizacji (odhaczanie)

> Zaznaczaj `[x]` po ukończeniu. Kolumna **Zależność** = minimalny Lp, który musi być gotowy wcześniej (lub `—`).

| Lp | ID | Gotowe | Zadanie (skrót) | Zależność | Uchwała / blok |
|----|-----|:------:|-----------------|-----------|----------------|
| 1 | **T01** | [x] | Test: **jeden** prompt rollup (gracz+MG) vs **dwa** prompty — jakość, leak, JSON | — | **[S11b]** |
| 2 | **T02** | [x] | Migracja + model: **dwa zapisy** rollupu (`audience` / `kind` lub druga tabela) | T01 | **[S11b]** |
| 3 | **T03** | [ ] | **Prompt** podsumowania gracza: **tylko** transkrypt — **bez** `gm_plan_json` w kontekście | T02 | **[S11b]** |
| 4 | **T04** | [ ] | **Prompt** wersji MG: transkrypt **+** plan (`gm_plan_json`) | T02 | **[S11b]** |
| 5 | **T06** | [ ] | **`gm_plan_json` W1**: szkielet pól, merge, dokumentacja w `07` / kodzie | — | **[S11b]**, W2 backlog |
| 6 | **T05** | [ ] | Po zapisie postaci: **generacja planu do skutku**; **blokada** pierwszej narracji bez planu | T06 | **[S11b]** |
| 7 | **T07** | [ ] | API / serializacja: **gracz nie dostaje** `gm_plan_json` w GET kampanii (lista + szczegóły) | T06 | **[S11b]** |
| 8 | **T08** | [ ] | Multiplayer: **cooldown** odświeżenia rollupu **per `campaign_id`** | T02 | **[S11b]** |
| 9 | **T09** | [ ] | UI: stan **„wymaga odświeżenia”** po błędzie LLM rollupu | T02 | **[S11b]** |
| 10 | **T10** | [ ] | **Fala [IMPL] 1:** auto / prog tur / cron `POST …/history/summary/ensure` | T02–T04 (logicznie po dual zapisie) | **[IMPL]** |
| 11 | **T11** | [ ] | Zamknięcie **[AUDIT]**: synchronizacja [`06_schema_gaps.md`](06_schema_gaps.md) + wpis w `04` | — | **[AUDIT]** |
| 12 | **T12** | [ ] | Tabela nagród XP **[S10e]** + minimalny odczyt w silniku / admin | — | **[S10e]** |
| 13 | **T13** | [ ] | Player rulebook: lekki rozdział **XP** (blok D agendy) | T12 (opcjonalnie równolegle po szkicu tabeli) | Blok **D** |
| 14 | **T14** | [ ] | **W2** (tabela `campaign_story_beats`): tylko jeśli T06–T07 niewystarczają — ADR + migracja | T06 | **[S11b]** |
| 15 | **T15** | [ ] | **Nowy akt** w tym samym `campaign_id`: trigger po głównym queście → ten sam LLM co start + narracja spinająca | T05, T06 | **[S11b]** |
| 16 | **T16** | [ ] | **[IMPL] fala 2:** broń / `weapon_type` ↔ atak, finesse, dwuręczność | T11 częściowo | **[IMPL]**, **[S1]** |
| 17 | **T17** | [ ] | **[IMPL] fala 3:** `effect_json` + walidacja admin | T11 | **[IMPL]**, **[S13]** |
| 18 | **T18** | [ ] | **[IMPL] fala 4:** warunki + konsumable / `item_key` | T17 | **[IMPL]**, **[S6]** |
| 19 | **T19** | [ ] | **[IMPL] fala 5:** import / snapshot / ostrzeżenia | T11 | **[IMPL]**, **[S7]** |
| 20 | **T20** | [ ] | **[IMPL] fala 6:** dywergencja (heurystyka / drugi LLM) + UI plan MG (admin); **follow-up po T01 (T01 nadal [x]):** po usunięciu „Podgląd dual” z frontu gracza — odpowiednik w adminie per kampania (§1 *Follow-up UX*, §2 T01) | T05–T07 | **[IMPL]**, **[S11]** |
| 21 | **T21** | [ ] | **[IMPL] fala 7:** progres cech za XP (meta + endpoint) | T12 | **[IMPL]**, **[S10]** |

**Uwaga kolejności:** W tabeli **T06** jest przed **T05** (najpierw szkielet planu, potem blokada pierwszej narracji).

**Follow-up UX (po zamkniętym T01 → admin):** **T01 pozostaje wykonane** (`[x]` w tabeli — bez zmian). Poniżej jest wyłącznie **kolejny krok produktowy**, gdy zniknie tymczasowy UI u gracza. Przycisk **„Podgląd dual (T01)”** w modalu gracza jest **tymczasowy** (debug jakości rollupu). Gdy zostanie **usunięty z frontu gry**, ta sama możliwość ma być **przeniesiona do panelu administratora** — **per kampania** (`campaign_id`): odczyt tych samych wyników co dziś w podglądzie (tekst dla gracza, notatka MG, heurystyka wycieku planu, błąd parsowania JSON; opcjonalnie ponowne wywołanie `POST …/dual-summary-preview` lub ekwiwalent tylko dla ról admin). Gracz nie widzi tego widoku. Szczegóły: §2 T01 — *Plan wdrożenia (po usunięciu z UI gracza)* — ten blok **nie** anuluje ani nie „odświeża” zamknięcia T01.

---

## 2. PROMPTY — T01

<!-- STATUS_T01: DONE -->

### T01 — Test: jeden prompt (gracz + MG) vs dwa prompty

**Stan zadania:** **DONE (trwale)** — zakres T01 (wariant A, moduł `history_summary_dual_prompt`, testy, tymczasowy podgląd w UI) jest **zamknięty**; dalsze prace opisane w *Plan wdrożenia (po usunięciu z UI gracza)* to **inna pozycja w planie** (np. T20), **nie** ponowne otwarcie T01.

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
- **Frontend (bez konsoli):** w modalu **„Podsumowanie kampanii”** (tylko **właściciel** kampanii) jest przycisk **„Podgląd dual (T01)”** — wywołuje `POST /api/campaigns/{id}/dual-summary-preview` (router `campaigns.py`, żeby uniknąć 404 na starych obrazach bez `campaign_history`) i pokazuje w oknie: tekst dla gracza, notatkę MG, heurystykę wycieku, ewent. błąd parsowania JSON. **Nie zapisuje** w `campaign_ai_summaries`.
- **Live 3× LLM:** wykonaj przez UI jak wyżej; wynik możesz dopisać w **Notatki** poniżej.

**Rekomendacja (po kodzie, przed pełnym live):** przyjmij **wariant A** w T02/T03 z parsowaniem JSON + logowaniem heurystyki; wariant B tylko jeśli podgląd z UI pokaże powtarzalne halucynacje.

**Notatki po implementacji**

-

**Plan wdrożenia (po usunięciu z UI gracza)** — *nie jest częścią „dokończenia T01”; T01 jest już **DONE**.*

- **Trigger:** usunięcie przycisku „Podgląd dual (T01)” z modala **„Podsumowanie kampanii”** po stronie gracza (właściciel kampanii).
- **Wymaganie:** zamiast całkowicie chować narzędzie — **widok w panelu administratora** powiązany z **konkretną kampanią**: prezentacja tych samych danych co obecny podgląd (treść `player_summary` / `gm_notes`, heurystyka wycieku, komunikat parsowania), z dostępem wyłącznie dla ról admin (nie dla zwykłego gracza).
- **Powiązanie z kolejką:** implementacja UI najpewniej w **tej samej fali co rozbudowa admina pod rollup / plan MG** (logicznie obok **T20** — UI edycji planu; ewent. osobna zakładka/sekcja „Debug rollup” przy kampanii). Nie blokuje **T10** (automat `ensure`), ale **nie** odkładaj w nieskończoność: bez tego zespół traci widoczność jakości dual promptu po czyszczeniu frontu.

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

-

---

## 4. PROMPTY — T03

<!-- STATUS_T03: PENDING -->

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

-

**Notatki po implementacji**

-

---

## 5. PROMPTY — T04

<!-- STATUS_T04: PENDING -->

### T04 — Prompt rollupu **MG**: transkrypt + plan

**Cel:** Drugi call (lub druga gałąź w wariancie A z T01) z dostępem do `gm_plan_json` + transkryptu.

**Implementacja**

1. Zbuduj blok planu jak w `game_engine` (`_format_gm_plan_block`).
2. Zapis pod `audience=gm` (lub równoważnie).
3. Upewnij się, że endpoint dla gracza **nigdy** nie zwraca tego pola.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 6. PROMPTY — T06

<!-- STATUS_T06: PENDING -->

### T06 — `gm_plan_json` **W1**: szkielet, merge, dokumentacja

**Cel:** MVP planu w jednym JSON na kampanii; **W2** tylko jeśli nie starczy (**[S11b]**).

**Implementacja**

1. Ustal `schema_version` + pola: np. `arcs`, `active_arc_id`, `scene_goals`, sekcja prywatna pod przyszłe beaty.
2. Funkcja **merge** (płytki lub głęboki merge pod kluczami — dokumentacja).
3. Opisz w `07_extended_design_spec.md` §7 lub komentarzu w kodzie.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 7. PROMPTY — T05

<!-- STATUS_T05: PENDING -->

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

-

**Notatki po implementacji**

-

---

## 8. PROMPTY — T07

<!-- STATUS_T07: PENDING -->

### T07 — API: `gm_plan_json` niewidoczne dla gracza

**Cel:** Listy i GET kampanii dla roli gracza **nie** zwracają planu; tylko owner/admin/debug (**[S11b]**).

**Implementacja**

1. Przejrzyj [`campaigns.py`](../../backend/app/api/campaigns.py) i serializację w listach.
2. Test API: klient gracza nie widzi klucza `gm_plan_json`.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 9. PROMPTY — T08

<!-- STATUS_T08: PENDING -->

### T08 — Cooldown odświeżenia rollupu **per kampania**

**Cel:** W MP każdy może wymusić odświeżenie, ale nie częściej niż co **N** rund (np. 20) **dla całej kampanii**, **[S11b]**.

**Implementacja**

1. Kolumna `campaigns.last_summary_turn` lub licznik w meta.
2. Walidacja w `POST …/history/summary` (lub ensure).
3. Konfiguracja N w `game_config_meta` lub stała na start.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 10. PROMPTY — T09

<!-- STATUS_T09: PENDING -->

### T09 — UI: „wymaga odświeżenia” po błędzie rollupu

**Cel:** Gdy LLM rollup się wywali — czytelny stan + ewent. ostatnia dobra wersja (**[S11b]**).

**Kontekst:** [`frontend/js/app.js`](../../frontend/js/app.js) (modal podsumowania), endpointy summary.

**Implementacja**

1. Mapowanie kodów błędów z API na komunikat.
2. Opcjonalnie flaga `summary_stale` w odpowiedzi kampanii.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 11. PROMPTY — T10

<!-- STATUS_T10: PENDING -->

### T10 — Automatyzacja `history/summary/ensure` (**[IMPL]** fala 1)

**Cel:** Skrót fabuły nie jest przestarzały w nieskończoność — cron lub co N tur narracyjnych.

**Implementacja**

1. Worker / wywołanie po turze gdy `turn_number % N == 0`.
2. Konfiguracja N; nie łamać cooldownu T08.
3. Logi i metryki błędów.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 12. PROMPTY — T11

<!-- STATUS_T11: PENDING -->

### T11 — Zamknięcie **[AUDIT]** (`06_schema_gaps` + `04`)

**Cel:** Wiersze w [`06_schema_gaps.md`](06_schema_gaps.md) zgodne z kodem i migracjami; wpis domknięcia w [`04_decisions_log.md`](04_decisions_log.md) przy **[AUDIT]**.

**Implementacja**

1. Dla każdego wiersza: `PRAGMA table_info` / grep → aktualizacja statusu.
2. Jeśli wszystko zamknięte: jedno zdanie w `04` z datą i wersją schematu.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 13. PROMPTY — T12

<!-- STATUS_T12: PENDING -->

### T12 — Tabela nagród XP **[S10e]**

**Cel:** Konfiguracja typu „słaby wróg → X XP”, „quest główny → Y XP” w DB; silnik czyta liczby, LLM nie jest źródłem prawdy.

**Implementacja**

1. Tabela `game_config_xp_rewards` (lub JSON w `game_config_meta` — wybór w PR z uzasadnieniem).
2. Minimalny panel admin / seed.
3. Powiązanie z `xp_award` / grantami bez duplikacji logiki.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 14. PROMPTY — T13

<!-- STATUS_T13: PENDING -->

### T13 — Player rulebook — rozdział XP (blok D)

**Cel:** Lekki rozdział zgodny z **[S10b]**/**[S10c]**/**[S10d]** — bez obiecywania UI, którego nie ma.

**Implementacja**

1. Nowy plik lub sekcja w [`player_rulebook/`](player_rulebook/).
2. Zgodność z „tylko MG przyznaje XP fabularnie” / technicznie owner.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 15. PROMPTY — T14

<!-- STATUS_T14: PENDING -->

### T14 — **W2** `campaign_story_beats` (tylko gdy W1 nie starczy)

**Cel:** ADR + migracja **tylko** jeśli T06/T07 są niewystarczające (rozmiar, złożoność, locking).

**⛔ Blokada:** Nie zaczynaj, dopóki nie ma **pisemnej** decyzji w PR / `04` „W1 insufficient because …”.

**Implementacja**

1. ADR w `docs/`.
2. Tabela + API wewnętrzne + podpięcie do promptu MG.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 16. PROMPTY — T15

<!-- STATUS_T15: PENDING -->

### T15 — **Nowy akt** w tej samej kampanii (bez nowego `campaigns`)

**Cel:** Warunek końca głównego questa → regeneracja planu (jak przy starcie) + narracja łącząca; **ciągłe** `campaign_turns` i numery tur (**[S11b]**).

**Implementacja**

1. Wykrycie „quest główny closed” (stan DB lub parser narzędzie LLM — uzgodnić w PR).
2. Wywołanie tego samego generatora planu co T05.
3. Test: brak nowego `campaign_id`.

**Co zostało zrobione**

-

**Notatki po implementacji**

-

---

## 17. PROMPTY — T16–T21 ([IMPL] fale 2–7 — skrót)

Poniżej: **jedno zdanie celu** + odesłanie do **[IMPL]**; pełne prompty można wydzielić do osobnych plików w kolejnej iteracji.

| ID | STATUS | Cel (jedno zdanie) | Główne pliki (orientacyjnie) |
|----|--------|-------------------|------------------------------|
| T16 | PENDING | Mapowanie `weapon_type` ↔ rodzaj ataku + finesse / dwuręczność | `combat_service.py`, `dice.py`, `game_config_weapons` |
| T17 | PENDING | `effect_json` v0 + walidacja przy zapisie admina | `admin`, `items`, `conditions` |
| T18 | PENDING | Konsumable / `item_key` / migracja loot | `loot_service`, migracje |
| T19 | PENDING | Import: dokumentacja ryzyk + `catalog_snapshot` jako kanon | `admin_config_transfer.py`, docs |
| T20 | PENDING | Dywergencja **[S11]** + UI edycji planu (admin); **follow-up po zamkniętym T01:** po czyszczeniu podglądu dual z frontu — debug rollupu per kampania w adminie | `game_engine`, admin |
| T21 | PENDING | Koszty statów za XP + endpoint spend | `game_config_meta`, `characters` API |

**Co zostało zrobione (T16–T21 — zbiorczo lub per ID)**

-

---

## 18. Historia zmian tego pliku

| Data | Zmiana |
|------|--------|
| 2026-05-03 | Utworzenie master kolejki T01–T21 + prompty; jeden plik źródłowy. |
| 2026-05-03 | **T01 DONE** (kod + testy unittest); live 3× LLM — do uzupełnienia ręcznie. |
| 2026-05-04 | **T02 DONE** — kolumna `audience`, API query, narracja gm→player, testy. |
| 2026-05-04 | Follow-up T01: po usunięciu podglądu dual z UI gracza — widok odpowiednika w adminie per kampania (§1 *Follow-up UX*, §2 T01, rozszerzenie opisu **T20**). |
| 2026-05-04 | Utrwalenie: **T01 = DONE** na stałe; follow-up admin wyłącznie jako osobna praca (reguła § *Zasady pracy* pkt 4; komentarz HTML; doprecyzowanie §1 *Follow-up UX* i §2 *Plan wdrożenia*). |
