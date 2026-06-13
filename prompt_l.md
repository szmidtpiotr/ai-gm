Pracujemy nad FAZĄ L — Lochy kafelkowe (redesign trybu lochów AI-GM). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AJ (pełne opisy zadań FAZY L + Decyzje 1–17 + tabela kolizji + Numbers Policy),
3. notes.md → sekcja "FAZA L" (checklista — jedyne źródło statusów).

ZAKRES (decyzje Piotra, 2026-06-12, sesja "Fable Lochy Projekt"):
- Jeden tryb lochów: kafelkowy. Legacy proceduralny tryb usuwamy w L9 — wcześniej go nie
  naprawiaj ani nie rozbudowuj.
- FAZA L jest niezależna od FAZ U i S z JEDNYM twardym wyjątkiem: L5 wymaga ukończonego S2
  (statbloki wrogów). Jeśli pierwsze niezrobione zadanie to L5, a S2 w notes.md nie jest [x]
  — STOP i zapytaj (możesz zaproponować wykonanie S2 albo przeskok do innego dostępnego
  zadania zgodnie z zależnościami).
- L17 wykonujemy dopiero PO L19 (kamieniu milowym). L9 dopiero gdy L1–L8 działają end-to-end.
- Nadpisania zatwierdzone (nie traktuj starych zapisów jako sprzeczności): CZĘŚĆ AA
  (nawigacja lazy, śmierć=restart) nadpisana przez CZĘŚĆ AJ; E16 #431 (restart od pokoju 1)
  nadpisane Decyzją 6 (śmierć kończy run, checkpointy); U21–U23 wchłonięte (L7/L4+L6/L5);
  H5 realizowane jako L16.
- Poza zakresem (NIE implementuj): multiplayer w lochach (tylko kształt danych positions),
  rotacja kafelków, leaderboard endless, pełny podsystem pułapek.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie L, ani mniej, ani więcej:
1. W notes.md → FAZA L znajdź pierwsze niezaznaczone [ ] zadanie zgodnie z kolejnością
   z sekcji "FAZA L — zależności i kolejność" w CZĘŚCI AJ (L1→L2→L3→L4 → L5[S2!]/L6/L7→L8
   → L9; L10 i L14→L15 można równolegle wcześniej; L11→L12→L13/L13b po L4; L18→L19; L17 po L19).
2. Przeczytaj pełny opis zadania w CZĘŚCI AJ (Cel / Dla agenta / Weryfikacja) i sprawdź
   w kodzie, czy opis zgadza się z rzeczywistością (szczególnie app.js po zmianach U28–U30).
   Jeśli jest sprzeczność — STOP, opisz ją prostym językiem i czekaj na moją decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] LNN — <nazwa>", labels: enhancement + needs-testing,
   struktura treści wg szablonu z issue #18 (sekcja Numbers Policy obowiązkowa — wartości
   z tabeli Numbers Policy FAZY L to wartości startowe).
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
   WYJĄTKI bez cyklu TDD:
   - L14–L17 (kontent/batch): wykonaj wg opisu; w L15 obowiązuje twardy STOP po pilocie
     5 obrazków — czekaj na moją akceptację jakości zanim odpalisz pełny batch,
   - L19 (czysty playtest): bez issue [TASK]; utwórz/użyj issue [SMOKE] FAZA L na raport.
5. Wykonaj sekcję "Weryfikacja" z opisu zadania. Walkę na kafelkach weryfikuj w Combat
   Sandbox; flow gracza przez /game-test-player lub ręcznie na DEV.
6. Zaktualizuj notes.md ([x] + link [#NNN]) i game_mechanics.md CZĘŚĆ AJ, jeśli zadanie
   zmieniło design. Zaproponuj commit zgodny z konwencją projektu — nie pushuj bez mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zostało zrobione i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku na https://aigm-dev.studio-colorbox.com/
     (co kliknąć, co powinno się pokazać),
   - co jest następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD. Generacja obrazków: FLUX na 192.168.1.170:8765
  (batch offline — czas generacji bez znaczenia, jakość ponad szybkość).
- Mechanika decyduje, LLM narruje (Zasady CZĘŚĆ 10). W lochu narracja hybrydowa: opis
  kafelka z DB + LLM tylko koloryzuje 1–2 zdaniami (Decyzja 3) — dlatego opisy kafelków
  muszą być porządne.
- Walka startuje deterministycznie z silnika (Decyzja 4) — żadnych tagów COMBAT_START od
  LLM w lochu.
- Żadnych destrukcyjnych migracji DB — kolumny legacy zostają, seedy dezaktywujemy
  is_active=0. Seedy zawsze created_by='seed'.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Bump `?v=` przy zmianach shared modułów JS.
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
