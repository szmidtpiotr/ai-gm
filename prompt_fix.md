Pracujemy nad FIX LIST — backlog wdrożeń bugów i feature AI-GM. Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska — Remote-Only, DEV .61, nigdy PROD),
2. fix_list.md (checklista — JEDYNE źródło statusów; sekcje A→G, kolejność = priorytet),
3. game_mechanics.md jeśli zadanie dotyka mechaniki zablokowanej (stats/combat/DC/archetypy).

KONTEKST: Każde zadanie to ISTNIEJĄCY GitHub issue z PEŁNĄ analizą (root cause + propozycja fix +
lista plików + Acceptance). Nie twórz nowego issue — czytasz gotowy i wdrażasz.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie, ani mniej ani więcej:

1. W fix_list.md znajdź PIERWSZE niezaznaczone `- [ ]` zadanie, idąc od sekcji A do G (góra→dół).
   - POMIŃ zadania feature (sekcja F i „Feature backlog" w G) — te wdraża się TYLKO gdy Piotr
     wskaże numer ręcznie. Jeśli pierwsze niezaznaczone to feature → przeskocz do następnego buga.
   - Sprawdź `(dep: #MMM)`: jeśli prereq nie jest jeszcze `[x]` → POMIŃ to zadanie, weź następne.
     Jeśli wszystkie pozostałe są zablokowane przez niezrobione dep → STOP i napisz co odblokować.

2. Pobierz issue: `gh issue view #NNN --repo szmidtpiotr/ai-gm`. Przeczytaj Root cause, Fix,
   Files, Acceptance. SPRAWDŹ w kodzie, czy analiza zgadza się z aktualnym stanem (pliki/linie
   mogły się przesunąć). Jeśli issue ma `(design)` / sekcję „decyzja A/B" i Piotr nie wybrał
   opcji — STOP, streść opcje prostym językiem i czekaj na decyzję.

3. Wdróż fix skillem `/tdd` w trybie auto (bez zatrzymywania na pytaniach pośrednich):
   - napisz test (pytest dla backendu i/lub Playwright wg natury buga) odtwarzający błąd,
   - zaimplementuj poprawkę wg sekcji Fix z issue,
   - uruchom TYLKO testy tego zadania i powiązanych modułów (NIGDY pełny `pytest tests/`).
   WYJĄTKI bez pełnego cyklu TDD:
   - zmiany czysto promptowe (system_prompt.txt) / danych (seed, migracja) — wdroż wg opisu,
     dodaj test regresyjny gdzie sensowny (np. parser, dedup, regex),
   - zmiany czysto frontendowe (render/strip/UI) — weryfikuj w przeglądarce + Playwright spec.

4. Wykonaj sekcję „Acceptance" z issue. Backend/walkę weryfikuj testem lub w Combat Sandbox;
   flow gracza przez `/game-test-player` lub ręcznie na DEV (https://aigm-dev.studio-colorbox.com/).
   NIE testuj na bohaterze Mizel (char 999420 — postać Piotra, read-only). Testy na Demo (user 1).

5. Zaktualizuj:
   - fix_list.md: zaznacz `- [x] #NNN …` + dopisz `[wdrożone <SHA>]`,
   - GitHub issue: komentarz „fix + SHA + co zmienione" (`gh issue comment`); ustaw label
     `needs-testing` (zostaje do weryfikacji wizualnej Piotra); NIE zamykaj issue — zamyka Piotr,
   - jeśli zmiana dotyka designu mechaniki → game_mechanics.md; player-UI → frontend_design.md (F-NN).

6. Commit + push wg konwencji projektu (develop, ref #NNN, sudo -u piotrszmidt git na .61).
   Bump `?v=` przy zmianach shared modułów JS. NIGDY nie pushuj na main/PROD.

7. STOP. Raport końcowy po polsku, prostym językiem:
   - co naprawione i dlaczego (2-4 zdania bez żargonu),
   - „Jak możesz to sam sprawdzić" — krok po kroku na DEV (co kliknąć, co ma się pokazać),
   - co jest następne niezaznaczone w fix_list.md.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy PROD (.62/.63, main).
- Mechanika decyduje, LLM narruje. Nie zmieniaj zablokowanej mechaniki bez zgody (CLAUDE.md).
- Żadnych destrukcyjnych migracji — kolumny legacy zostają, seedy is_active=0, created_by='seed'.
- Backend Python = obraz Dockera: po zmianie rebuild `docker compose -f docker-compose.dev.yml up -d --build backend`.
- Issue zamyka tylko Piotr po weryfikacji wizualnej; `needs-testing` zostaje do tego momentu.
- Jedno zadanie na sesję. Po STOP nie bierz kolejnego.

Zacznij od kroku 1.
