Pracujemy nad FAZĄ LB — Balans lochów: rozdział onboarding vs głębszy. Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AJ → sekcja "FAZA LB — Balans lochów" (decyzje LB-1..LB-5, dane symulacji Monte Carlo, Numbers Policy),
3. notes.md → sekcja "## FAZA LB" (checklista — jedyne źródło statusów).

KONTEKST / KLUCZOWE ODKRYCIE (sesja projektowa 2026-06-17, po /llm-council + sim):
- Starter-loch `krypta_probna` (5 walk + Lisz 40 PŻ, absolutna skala) jest matematycznie
  NIEukańczalny solo lvl1 (clear ≈0%, nawet lvl7 ≈3%). Zabójca = compounding 5 sekwencyjnych
  walk + action economy multi-enemy + brak leczenia między walkami + boss 40 PŻ — NIE poziom.
- Rozwiązanie: rozdzielić na DWA uczciwe lochy (onboarding + głębszy) + ogólna mechanika
  odpoczynku na wyczyszczonym kaflu (heal% + ładunki flagowane lochem).
- #733 (ease-in) i #734 (mid-fight heal) zostały REKLASYFIKOWANE do głębszego lochu (LB4) —
  NIE dotyczą onboardingu. Onboarding ma działać bez nich.

ZAKRES (decyzje LB-1..LB-5 z CZĘŚCI AJ):
- LB1 (✅ zrobione, backend 4504fff + frontend #735): odpoczynek na cleared kaflu — kafel
  staje się "bezpieczny" po pokonaniu wrogów → akcja rest na węźle (NIE nowy kafel, nie rusza
  budowy ścieżki/grafu). Flaga `game_dungeons.rest_heal_pct`/`rest_charges`: onboarding
  100%/unlimited, reszta 20%/ładunki.
- LB2: soft-init — bohater ZAWSZE pierwszy w turn_order w PIERWSZEJ walce runu lochu
  (combat_index==0). Neutralizuje śmierć-na-inicjatywie z testu L18. Dungeon-scoped, mała
  zmiana inicjatywy w combat_service. NIE rusza absolutnej skali D1–D5.
- LB3: re-spec `krypta_probna` = ONBOARDING (config/seed): tile_count=3, 2 komnaty walki
  (1 wróg/komnata, najsłabszy z puli), boss ~18 PŻ, min_level=1, rest_heal_pct=100,
  rest_charges=0 (unlimited). Cel clear ~78-85% solo lvl1.
- LB4: nowy głębszy loch `katakumby_mroku` (config/seed): obecna treść 5 walk + Lisz 40 PŻ,
  absolutna skala D1, min_level=3, rest_heal_pct=20/ładunki. Przenieś tam #733/#732/#734.
- LB5: (przyszłość MP, osobny ticket) — skaluj LICZBĘ wrogów rozmiarem drużyny, siłę zostaw
  tierem. NIE teraz — jeśli plan trafi na LB5, STOP i zgłoś jako poza zakresem tej sesji.
- LB6: walidacja końcowa — Playwright przejazd onboarding solo lvl1 (cel clear ~80%).

Poza zakresem (NIE implementuj): skalowanie liczby wrogów wg drużyny (LB5/MP), zmiana
absolutnej skali D1–D5, leaderboard endless, nowe podsystemy walki.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie LB, ani mniej, ani więcej:
1. W notes.md → ## FAZA LB znajdź pierwsze niezaznaczone [ ] zadanie w kolejności LB2→LB3→
   LB4→LB6 (LB1 zrobione; LB5 poza zakresem — pomiń/STOP jeśli wypadnie).
2. Przeczytaj pełny opis w CZĘŚCI AJ → FAZA LB (decyzja LB-N + Numbers Policy) i sprawdź w
   kodzie, czy opis zgadza się z rzeczywistością. Jeśli jest sprzeczność spec↔kod — STOP,
   opisz ją prostym językiem i czekaj na decyzję Piotra.
3. Utwórz/zaktualizuj GitHub issue: tytuł "[TASK] LBNN — <nazwa>", labels: enhancement +
   needs-testing, struktura treści wg szablonu z issue #18 (sekcja Numbers Policy obowiązkowa —
   wartości z FAZY LB to wartości startowe). LB2=#736, LB3=#737, LB4=#738 — użyj istniejących.
4. Wdróż:
   - LB2 — skillem /tdd w trybie auto (niezmiennik inicjatywy: bohater pierwszy w 1. walce
     runu; TDD na logice, NIE na balansie).
   - LB3 / LB4 — re-spec/seed (config). Bez pełnego cyklu TDD jeśli to czysta zmiana danych;
     dodaj test niezmiennika gdzie sensowne (tile_count, min_level, rest_heal_pct). Seedy
     zawsze created_by='seed', nigdy destrukcyjnych migracji (legacy dezaktywuj is_active=0).
   - LB6 — czysty playtest: użyj /playwright-test-report (onboarding solo Wojownik lvl1),
     bez issue [TASK]; cel clear ~80%; raport do notes.md.
5. Wykonaj sekcję "Weryfikacja": pytest TYLKO testów zadania w kontenerze
   ai-gm-dev-backend-1 (nigdy pełny pytest tests/). Walkę/balans na kafelkach weryfikuj w
   Combat Sandbox (żywy silnik) — symulator to hipoteza, nie prawda. Zmiana backendu walki
   wymaga --build backendu na DEV.
6. Zaktualizuj notes.md ([x] + link [#NNN]) i game_mechanics.md CZĘŚĆ AJ tylko jeśli zadanie
   zmieniło design lub wykryto rozjazd spec↔gra. Zaproponuj commit zgodny z konwencją
   (commit jako sudo -u piotrszmidt na .61) — NIE pushuj bez zgody Piotra.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zrobiono i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku na https://aigm-dev.studio-colorbox.com/,
   - co następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD. Commit jako sudo -u piotrszmidt; --build na zmiany
  backendu; pytest w kontenerze ai-gm-dev-backend-1.
- Mechanika decyduje, LLM narruje. Walka startuje deterministycznie z silnika (żadnych tagów
  COMBAT_START od LLM w lochu).
- NIE łamać absolutnej skali D1–D5 (bez rubber-bandingu). Balans (HP bossa, #komnat, szanse)
  strojony przez sim+Sandbox, NIE przez asercje jednostkowe; TDD tylko na niezmiennikach
  (rest-on-cleared + flaga heal%, soft-init, cap encountera).
- Żadnych destrukcyjnych migracji DB — kolumny legacy zostają, seedy dezaktywujemy
  is_active=0. Seedy zawsze created_by='seed'.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Bump `?v=` przy zmianach shared modułów JS.
- Issue zamyka tylko Piotr, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
