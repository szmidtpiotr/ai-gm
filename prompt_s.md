Pracujemy nad FAZĄ S — Skille i Stany (rozszerzenie mechaniki gry AI-GM). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AI (pełne opisy zadań FAZY S + Decyzje 1–2 + Zasady projektowe FAZY S),
3. skills_conditions_design_doc.md (korzeń repo — tabele źródłowe skilli i kondycji: DC, sposób testowania, efekty),
4. notes.md → sekcja "FAZA S" (checklista — jedyne źródło statusów).

ZAKRES (decyzja Piotra, 2026-06-12):
- FAZA S idzie po FAZIE U albo przeplatana z nią — jeśli w notes.md FAZA U ma niezamknięte
  zadania, NIE przejmuj się tym: pracujesz wyłącznie nad FAZĄ S wg jej własnej kolejności.
- WYJĄTEK TWARDY: Blok 3 (S8–S14) wymaga ukończonego U10 (effect schema lockdown). Jeśli
  pierwsze niezrobione zadanie jest z Bloku 3, a U10 w notes.md nie jest [x] — STOP i zapytaj
  (Blok 4 może wejść wcześniej, ale S18 wymaga S8).
- Poza zakresem (NIE implementuj, nawet jeśli design doc je opisuje): disease, broken_limb,
  crafting mechaniczny (trade_craft/alchemy tylko narracyjnie), pełne charmed/insane,
  skutki inwentarzowe pickpocket/torture.
- Margines sukcesu (S1) i staty aktorów (S2–S4) to ZATWIERDZONE zmiany zablokowanej mechaniki
  i nadpisanie decyzji z CZĘŚCI AB — zgody zapisane w CZĘŚCI AI "Decyzje projektowe".

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie S, ani mniej, ani więcej:
1. W notes.md → FAZA S znajdź pierwsze niezaznaczone [ ] zadanie zgodnie z kolejnością z sekcji
   "FAZA S — zależności i kolejność" w CZĘŚCI AI (S1→S2→S3→S4 → S5→S6→S7 → [U10] S8→S9→S10→
   S11→S12→S13→S14 → S15→S16→S17→S18→S19 → S20).
2. Przeczytaj pełny opis zadania w CZĘŚCI AI (Cel / Dla agenta / Weryfikacja) ORAZ odpowiedni
   wiersz tabeli w skills_conditions_design_doc.md i sprawdź w kodzie, czy opis zgadza się
   z rzeczywistością. Jeśli jest sprzeczność — STOP, opisz ją prostym językiem i czekaj na
   moją decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] SNN — <nazwa>", labels: enhancement + needs-testing,
   struktura treści wg szablonu z issue #18 (sekcja Numbers Policy obowiązkowa — liczby
   z design doc to wartości startowe).
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
   Wyjątek: S20 (czysty playtest /game-smoke + Sandbox sweep) — bez cyklu TDD i bez issue
   [TASK]; utwórz/użyj issue [SMOKE] FAZA S na raport.
5. Wykonaj sekcję "Weryfikacja" z opisu zadania. Kondycje i mechaniki bojowe weryfikuj
   w Combat Sandbox (admin → Narzędzia); gdzie wskazano /game-test-player — użyj go.
6. Zaktualizuj notes.md ([x] + link [#NNN] + licznik fazy) i game_mechanics.md CZĘŚĆ AI, jeśli
   zadanie zmieniło design (w szczególności: nowy typ efektu = aktualizacja tabeli typów
   w CZĘŚCI X — Zasada 4). Zaproponuj commit zgodny z konwencją projektu — nie pushuj bez
   mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zostało zrobione i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku na https://aigm-dev.studio-colorbox.com/
     (co kliknąć, co powinno się pokazać; dla kondycji: Sandbox, jaki przycisk, jaki log),
   - co jest następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD.
- Każda zmiana zgodna z Zasadami CZĘŚĆ 10 (mechanika decyduje, LLM narruje) + Zasadami
  projektowymi FAZY S z CZĘŚCI AI (prymityw raz, kondycja danymi — żadnych
  `if condition_key == ...` w silniku; nowy typ efektu aktualizuje 4 miejsca).
- Rzuty ataku w walce (nat 20/nat 1, podwójne obrażenia) NIETYKALNE — margines dotyczy
  wyłącznie testów umiejętności.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
