# E2E — Combat System Phase 8A / 8B (manual, przeglądarka)

**Środowisko**

| Warstwa   | URL / ścieżka              |
| --------- | -------------------------- |
| Frontend  | http://localhost:3001      |
| Backend   | http://localhost:8000      |
| Baza      | `data/ai_gm.db`            |

**Zasady:** tylko ręczne klikanie / DevTools / opcjonalnie `curl` przy podanych endpointach. Brak pytest.

**Przed startem:** backend i frontend uruchomione; znany login do aplikacji.

---

## SCENARIUSZ 1 — Nowa kampania → walka → victory → łupy

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] Otwórz http://localhost:3001 i zaloguj się.
- [ ] Utwórz **nową kampanię** i dokończ tworzenie postaci (dowolna konfiguracja dopuszczalna przez kreatora).
- [ ] W polu narracji wpisz intencję rozpoczęcia walki, np. „Atakuję bandytę” (dostosuj nazwę do wroga dostępnego w świecie / sugestii GM, jeśli „bandit” nie zadziała — ważna jest **wyraźna intencja ataku**).
- [ ] **OCZEKIWANE:** Odpowiedź GM kończy się **`[COMBAT_START:<enemy_key>]`** albo (fallback Phase 8A) ostatnia linia to **`Roll Initiative d20`** — bez samego opisu ciosu zamiast cue.
- [ ] **OCZEKIWANE:** Widoczny jest panel walki (`#combat-panel-host` w `#combat-panel-slot`) i jest **nad** kartą postaci (`#sheet-panel-body` niżej w sidebarze).
- [ ] **OCZEKIWANE:** W polu statusu walki (`#combat-debug-status`) widać linię w stylu **„Przeciwnik: `enemy_key` — nazwa HP X/Y”** dla aktywnego celu (gdy tura nie jest gracza; dokładna składnia jak w aktualnym buildzie).
- [ ] Kliknij **„Atak”** w panelu walki (tura gracza).
- [ ] **OCZEKIWANE:** W czacie pojawia się bąbelek z kartą rzutu **`__AI_GM_COMBAT_ROLL_V1__`**: d20, modyfikator STR, suma, trafienie/pudło/unik (wg wyniku), obrażenia przy trafieniu, **AC** (target).
- [ ] **OCZEKIWANE:** Po strumieniu SSE pojawia się **narracja GM po polsku** opisująca skutek ataku.
- [ ] Powtarzaj **„Atak”** (i ewentualnie tury wroga wg UI), aż **HP wroga = 0**.
- [ ] **OCZEKIWANE po śmierci wroga (ostatni wróg / victory):**
  - [ ] **a.** GM **najpierw** dostarcza narrację śmierci wroga (min. 2–3 zdania), bez natychmiastowego „skoku” samego overlayu przed tekstem.
  - [ ] **b.** **Dopiero po** narracji pojawia się flow zwycięstwa: **overlay łupów** („Łupy z pokonanych”) z listą pozycji, potem ekran końca walki z **„Kontynuuj”** (kolejność zgodna z implementacją step 7.1).
  - [ ] **c.** Lista łupów **nie jest pusta** (wróg zdefiniowany w katalogu ma `loot_pool` / dropy).
  - [ ] **d.** **„Kontynuuj”** zamyka overlay końca walki i **chowa** panel walki.
- [ ] **OCZEKIWANE:** Status COMBAT wraca do wariantu **brak aktywnej walki** / `(brak — active=false)` z ewentualną linią **„Wróg: …”** z ostatniej walki (debug).

---

## SCENARIUSZ 2 — Ucieczka z walki

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] Rozpocznij walkę jak w scenariuszu 1 (kroki do pojawienia się panelu i sensownego statusu COMBAT).
- [ ] Kliknij **„Ucieczka”** w panelu walki.
- [ ] **OCZEKIWANE:** Żądanie `POST http://localhost:8000/api/campaigns/:id/combat/flee` zwraca **HTTP 200** (DevTools → Network; `:id` = ID wybranej kampanii).
- [ ] **OCZEKIWANE:** Panel walki **znika** od razu po sukcesie.
- [ ] **OCZEKIWANE:** GM (SSE / narracja) opisuje **ucieczkę po polsku** (chaos, dystans, reakcja wrogów — sens fabularny).
- [ ] **OCZEKIWANE:** Status COMBAT = **brak aktywnej walki** (bez sensu „wciąż trwa walka”).
- [ ] **NIE OCZEKUJEMY:** overlayu **zwycięstwa** ani **popupu łupów** typu victory.

---

## SCENARIUSZ 3 — Śmierć gracza

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] Rozpocznij walkę (jak w scenariuszu 1).
- [ ] Ustaw **HP gracza na 2** (jedna z metod):
  - [ ] edycja `sheet_json` w tabeli `characters` w `data/ai_gm.db` (`UPDATE …`), **lub**
  - [ ] `PATCH`/`PUT` postaci przez API http://localhost:8000 (ścieżka zgodna z Twoim `openapi` / dokumentacją).
- [ ] Pozwól **wrógowi** wykonać turę (przycisk / flow **enemy turn** z UI) i odbierz obrażenia, albo wykonaj akcje aż **HP gracza spadnie do 0** (wg silnika).
- [ ] **OCZEKIWANE:** Overlay **„Zostałeś pokonany…”** z przyciskiem **„Kontynuuj”**.
- [ ] **OCZEKIWANE:** W UI pojawia się **propozycja rzutu** **`death_save`** (np. popup akcji / przycisk kontekstowy zależnie od wersji frontu).
- [ ] **NIE OCZEKUJEMY:** overlayu **zwycięstwa** ani **listy łupów** victory.

---

## SCENARIUSZ 4 — Tury w panelu (`#combat-engine-turns`)

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] W **aktywnej** walce wykonaj co najmniej **dwa ataki** (np. dwa ataki gracza z przynajmniej jedną turą wroga pomiędzy, jeśli kolejność tego wymaga).
- [ ] **OCZEKIWANE:** Sekcja **`#combat-engine-turns`** jest widoczna i zawiera wiersze:
  - [ ] **Atak gracza:** nagłówek z **⚔️**, linia szczegółów: rzut vs AC → **trafienie/pudło**, **obrażenia**.
  - [ ] **Atak wroga:** nagłówek z **🗡️** (ATAK WROGA), rzut vs **AC gracza** → trafienie/pudło, obrażenia.
  - [ ] **Śmierć:** wiersz z **💀**, gdy w logu silnika pojawiło się zdarzenie śmierci (wróg lub inny opisany przypadek).
- [ ] **OCZEKIWANE:** `GET http://localhost:8000/api/campaigns/:id/combat/turns` → **200** oraz JSON z listą `turns` (DevTools lub `curl` z nagłówkiem auth, jeśli wymagany).

---

## SCENARIUSZ 5 — Karta rzutu walki (`__AI_GM_COMBAT_ROLL_V1__`)

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] Po **każdym ataku gracza** z panelu sprawdź **prawy** bąbelek (użytkownik) w czacie.
- [ ] **OCZEKIWANE pola karty** (player attack):
  - [ ] Nagłówek typu **„ATAK (STR)”** (lub równoważny label z panelu).
  - [ ] **Surowy d20**, **mod STR**, **suma (total)**.
  - [ ] **AC przeciwnika** (vs AC …).
  - [ ] **Werdykt** czytelny jako trafienie / pudło / unik (fatalne pudło przy nat 1) — dopasuj do faktycznego tekstu UI.
  - [ ] **Obrażenia** przy trafieniu.
  - [ ] **Stopka „Wróg pokonany”** (lub równoważna), gdy to ostatnie uderzenie zabijające (`enemy_dead`).
- [ ] (Opcjonalnie, wiele prób) Sprawdź **nat 20** na ataku gracza → zachowanie zgodne z silnikiem (auto-trafienie; w narracji / logach może być **krytyczne trafienie** — opisz w polu „Failed”, jeśli rozjechało się z dokumentacją).
- [ ] (Opcjonalnie, wiele prób) Sprawdź **nat 1** → **fatalne pudło / utrata tempa** (tekst zgodny z kartą + narracja).

---

## SCENARIUSZ 6 — Panel walki nad kartą postaci (DOM + CSS)

**Status:** [ ] Passed  [ ] Failed  **Data testu:** ___________

- [ ] Otwórz **sidebar** z kartą postaci (arkusz).
- [ ] Rozpocznij walkę tak, by panel walki był widoczny.
- [ ] **OCZEKIWANE (DOM):** W DevTools → Elements, w `#sheet-panel` węzeł **`#combat-panel-slot`** występuje **przed** `#sheet-panel-body` (panel walki wyżej w drzewie).
- [ ] **OCZEKIWANE (CSS):** element `#sheet-panel` (klasa `.sheet-panel`) ma **`display: flex`** oraz **`flex-direction: column`** w trybie z otwartym arkuszem (np. `.play-area.sheet-open .sheet-panel`).
- [ ] **OCZEKIWANE:** `#combat-panel-slot` ma **`flex: 0 0 auto`** (slot nie „rozjeżdża” layoutu).
- [ ] **OCZEKIWANE:** W `combat.css` reguła dla `#combat-panel-slot` zawiera **`margin: 0 0 12px`** (odstęp pod panelem walki nad kartą).

---

## Notatki z sesji (opcjonalnie)

| Scenariusz | Tester | Uwagi / link do screena |
| ---------- | ------ | ----------------------- |
| 1          |        |                         |
| 2          |        |                         |
| 3          |        |                         |
| 4          |        |                         |
| 5          |        |                         |
| 6          |        |                         |
