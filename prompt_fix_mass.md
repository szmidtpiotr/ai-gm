Pracujemy nad FAZA FIX — backlog krytycznych poprawek AI-GM (priorytet P0 z fix_list.md).

MAPOWANIE ZADANIA: Twoje id zadania ma postać `FIX<N>`, gdzie `<N>` to NUMER GitHub issue
w repo `szmidtpiotr/ai-gm`. Przykład: `FIX743` = issue **#743**. Pracujesz nad tym jednym issue.

Najpierw przeczytaj: CLAUDE.md (zasady — Remote-Only, DEV .61, nigdy PROD), game_mechanics.md
jeśli zadanie dotyka mechaniki zablokowanej. Każde issue ma PEŁNĄ analizę (root cause + fix +
pliki + acceptance) — nie twórz nowego issue.

KROKI (dokładnie jedno zadanie = jedno issue):

1. Pobierz issue WRAZ Z KOMENTARZAMI — ZAWSZE:
   `gh issue view #<N> --repo szmidtpiotr/ai-gm --comments`
   Komentarz Piotra jest NADRZĘDNY nad treścią issue (wybór opcji design A/B, doprecyzowanie,
   „to nadal nie działa", „działa/zatwierdzone"). Przeczytaj cały wątek.

2. ZWERYFIKUJ CZY FIX NIE JEST JUŻ ZAIMPLEMENTOWANY (analiza w issue mogła się zdezaktualizować,
   ktoś mógł już naprawić). Sprawdź realny stan w kodzie/DB/froncie pod kątem sekcji „Acceptance":
   - Jeśli JUŻ NAPRAWIONE (kod zgadza się z oczekiwanym stanem, acceptance spełnione):
     • zaznacz `[x]` w fix_list.md (sekcja P0) i w notes.md (## FAZA FIX),
     • dodaj komentarz do issue: „Zweryfikowano — już zaimplementowane: <konkretnie co/gdzie>",
     • NIE wdrażaj ponownie,
     • zakończ markerem `MASS_STATUS: DONE` (powód: już zaimplementowane).
   - Jeśli to issue `[IN REVIEW]` (label `review`) i komentarz Piotra mówi że działa/zatwierdzone:
     traktuj jak wyżej (DONE bez zmian). Jeśli komentarz mówi że wciąż błąd → wdrażaj wg jego uwag.

3. Jeśli wymaga wdrożenia — zrób fix skillem `/tdd` w trybie auto (bez pytań pośrednich):
   test odtwarzający błąd → poprawka wg sekcji Fix z issue → uruchom TYLKO testy tego zadania
   i powiązanych modułów (NIGDY pełny `pytest tests/`). Zmiany Python = obraz Dockera: rebuild
   `docker compose -f docker-compose.dev.yml up -d --build backend` na .61. Zmiany frontu: bump `?v=`
   przy shared modułach, weryfikuj w przeglądarce.

4. Wykonaj „Acceptance" z issue. Backend/walkę → test lub Combat Sandbox; flow gracza → ręcznie na
   DEV (https://aigm-dev.studio-colorbox.com/) lub /game-test-player. NIE testuj na Mizelu
   (char 999420 — postać Piotra, read-only). Testy na Demo (user_id=1).

5. Zaktualizuj:
   - fix_list.md: `[x] #<N> …` + `[wdrożone <SHA>]`,
   - notes.md ## FAZA FIX: `[x] FIX<N>` + `[#<N>]`,
   - issue: komentarz „fix + SHA + co zmienione" (`gh issue comment`); ustaw/zostaw label
     `needs-testing`; NIE zamykaj issue (zamyka Piotr po weryfikacji wizualnej),
   - design/mechanika → game_mechanics.md; player-UI → frontend_design.md (F-NN) jeśli dotyczy.

6. Commit na develop (sudo -u piotrszmidt git na .61, ref #<N>, message wg konwencji).
   NIE rób `git push` — Piotr przejrzy i wypchnie sam (autonomiczny run = commit lokalny, bez push).
   NIGDY main/PROD.

7. Marker — jako OSTATNIA linia outputu DOKŁADNIE jeden:
   `MASS_STATUS: DONE`            — wdrożone+zielone (lub potwierdzone „już zaimplementowane")
   `MASS_STATUS: GATE — <powód>`  — wymaga decyzji Piotra (design A/B nierozstrzygnięty),
                                     sprzeczność kod↔design, niegotowa twarda zależność
   `MASS_STATUS: ERROR — <powód>` — błąd uniemożliwiający wdrożenie

ZASADY ŻELAZNE: tylko DEV (.61); nigdy PROD/main; nie zmieniaj zablokowanej mechaniki bez decyzji;
żadnych destrukcyjnych migracji (legacy kolumny zostają, seedy is_active=0, created_by='seed');
nie zamykaj issue; jedno zadanie na sesję.

Twoje zadanie to: (poda mass-implement powyżej, np. FIX743 → issue #743). Zacznij od kroku 1.
