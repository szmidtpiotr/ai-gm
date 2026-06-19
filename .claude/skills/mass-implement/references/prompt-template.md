<!--
  mass-implement v2 — built-in child-prompt template.
  The orchestrator fills the {PLACEHOLDERS} from .claude/mass-implement.json + the
  inline ZAKRES block, then prepends the per-task control header. This is the shared
  ~80% skeleton; the ~20% that varies per faza/list lives in {ZAKRES}.
  Placeholders: {ID} {SPEC_FILES} {PIPELINE} {GITHUB} {BRANCH} {ZAKRES}
-->
Pracujemy w trybie automatycznym nad JEDNYM zadaniem: **{ID}**.

Najpierw przeczytaj (zasady i kontekst): {SPEC_FILES}.
Trzymaj się ich bezwzględnie (środowisko, mechaniki zablokowane, zasady commitów).

## KROKI — dokładnie jedno zadanie

1. **Wczytaj pełny opis zadania {ID}** ze źródła wskazanego w ZAKRES poniżej
   (issue GitHub `{GITHUB}` wraz z komentarzami, lub sekcja w specu).
   Komentarz właściciela jest NADRZĘDNY nad treścią opisu (wybór A/B, „to nadal
   nie działa", „działa/zatwierdzone"). Przeczytaj cały wątek.

2. **ZWERYFIKUJ CZY JUŻ ZAIMPLEMENTOWANE** (opis mógł się zdezaktualizować, ktoś
   mógł już naprawić — checklist `[ ]` bywa nieaktualny). Sprawdź realny stan kodu/DB/UI
   pod kątem sekcji „Acceptance":
   - Jeśli JUŻ SPEŁNIONE: zaznacz `[x]` w checkliście, dodaj komentarz do issue
     („Zweryfikowano — już zaimplementowane: <co/gdzie>"), **NIE wdrażaj ponownie**,
     zakończ markerem `MASS_STATUS: DONE-ALREADY`.

3. **Sprawdź sprzeczność opisu z kodem.** Jest → **STOP**, opisz prostym językiem,
   marker `MASS_STATUS: GATE — sprzeczność opis↔kod`. Nie wdrażaj fikcji.

4. **Wdróż** zgodnie z pipeline projektu: {PIPELINE}.
   Pierwszy krok pipeline (np. /tdd) w trybie auto — bez pytań pośrednich.
   Stosuj wyjątki TDD wskazane w ZAKRES (kontent/batch/playtest, jeśli są).

5. **Wykonaj „Acceptance"** z opisu zadania (test / sandbox / ręcznie na środowisku).

6. **Zaktualizuj:** checklistę (`[x]` + link `[#NNN]`), spec jeśli zmienił się design,
   issue (komentarz „fix + SHA + co zmienione", label `needs-testing`, **NIE zamykaj** —
   zamyka właściciel po weryfikacji wizualnej).

7. **Commit** na `{BRANCH}` wg konwencji projektu (ref issue). **NIE rób `git push`** —
   właściciel przejrzy i wypchnie sam. NIGDY main/PROD.

## ZAKRES (decyzje + specyfika tego zadania)
{ZAKRES}

## ZASADY ŻELAZNE
- Tylko środowisko wskazane w zasadach; nigdy PROD/main.
- Nie zmieniaj zablokowanej mechaniki bez decyzji właściciela.
- Żadnych destrukcyjnych migracji (legacy zostaje; seedy nieaktywne; created_by='seed').
- Jedno zadanie na sesję. Nie zamykaj issue.

## MARKER — ostatnia linia outputu, dokładnie jeden:
- `MASS_STATUS: DONE`          — wdrożone, testy zielone, lista zaktualizowana
- `MASS_STATUS: DONE-ALREADY`  — było już zaimplementowane, tylko odhaczone
- `MASS_STATUS: GATE — <powód po polsku>`   — decyzja właściciela / sprzeczność / niegotowa zależność
- `MASS_STATUS: ERROR — <powód po polsku>`  — błąd uniemożliwiający wdrożenie
