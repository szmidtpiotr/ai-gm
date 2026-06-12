Pracujemy nad FAZĄ U — planem naprawczym gry AI-GM. Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AH (pełne opisy zadań FAZY U + zasada "mechanika decyduje, LLM narruje"),
3. notes.md → sekcja "FAZA U" (checklista — jedyne źródło statusów).

ZAKRES (decyzja Piotra, 2026-06-12):
- Pracujemy WYŁĄCZNIE nad trybami Nowa Kampania i Gotowa Kampania.
- Lochy kafelkowe POZA zakresem: pomijaj cały Blok 6 (U21–U23) i loch-fragmenty innych zadań.
- Wszystkie stare issues na GitHubie zostały zamknięte — startujemy z czystym trackerem.
  Nie wznawiaj starych issues; twórz nowe.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie U, ani mniej, ani więcej:
1. W notes.md → FAZA U znajdź pierwsze niezaznaczone [ ] zadanie zgodnie z kolejnością z sekcji
   "FAZA U — zależności i kolejność" w CZĘŚCI AH (U1→U2→U3→U4→U5–U9→U9b→U28–U32→U32b→U10–U14→Blok 5→Blok 7→U27).
   Blok 6 pomijasz.
2. Przeczytaj pełny opis zadania w CZĘŚCI AH (Cel / Dla agenta / Weryfikacja) i sprawdź w kodzie,
   czy opis zgadza się z rzeczywistością. Jeśli jest sprzeczność — STOP, opisz ją prostym językiem
   i czekaj na moją decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] UNN — <nazwa>", labels: enhancement + needs-testing,
   struktura treści wg szablonu z issue #18.
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
   Wyjątki: U1 (czysta dokumentacja) oraz U4/U9b/U32b (czyste playtesty /game-smoke) — bez cyklu TDD
   i bez nowego issue [TASK]; raporty jako komentarze do #512/#513, pełny raport końcowy normalnie.
5. Wykonaj sekcję "Weryfikacja" z opisu zadania. Gdzie wskazano /game-test-player-screenshot — użyj go.
6. Zaktualizuj notes.md ([x] + link [#NNN] + licznik fazy) i game_mechanics.md jeśli zadanie
   zmieniło design. Zaproponuj commit zgodny z konwencją projektu — nie pushuj bez mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zostało zrobione i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku w przeglądarce na https://aigm-dev.studio-colorbox.com/
     (co kliknąć, co powinno się pokazać),
   - co jest następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD.
- Każda zmiana zgodna z Zasadami 1–5 z game_mechanics.md CZĘŚĆ 10 (mechanika decyduje, LLM narruje).
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.

