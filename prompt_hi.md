Pracujemy nad FAZĄ HI — Inspektor Bohatera (narzędzie admina dla gry AI-GM). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AL (pełne opisy zadań HI + decyzje Piotra + stan zastany backendu),
3. notes.md → sekcja "FAZA HI" (checklista — jedyne źródło statusów).

ZAKRES (decyzje Piotra, 2026-06-15):
- Cel: panel admina jak monitor kampanii, ale dla BOHATERA — podgląd+edycja arkusza
  (staty/skille/HP/mana/kondycje), ekwipunku (dodaj/usuń/załóż), zaklęć, złota, XP, questów.
- Umiejscowienie: NOWA sekcja nawigacji „Bohaterowie" + link z monitora kampanii.
- Model edycji: REUSE istniejących endpointów (cheat/xp/inventory/spells); dopisać TYLKO
  3 luki (set skill rank, set mana, add/remove condition) + czysty GET odczytu. Bez dublowania logiki.
- Bezpieczeństwo: każda mutacja → wpis do `admin_audit_log`; ostrzeżenie przy koncie
  obserwowanym (#1013); BLOKADA edycji gdy bohater ma aktywną walkę/turę (409 live_locked).
- Niezależne od FAZ S/L/MP — to intermezzo.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie HI, ani mniej, ani więcej:
1. W notes.md → FAZA HI znajdź pierwsze niezaznaczone [ ] zadanie zgodnie z kolejnością
   z CZĘŚCI AL (HI1 → HI2 → HI3 → HI4 → HI5). HI1 musi być pierwsze (frontend zależy od `/full`).
2. Przeczytaj pełny opis (Cel / Dla agenta / Weryfikacja) w CZĘŚCI AL i sprawdź w kodzie, czy
   opis zgadza się z rzeczywistością (szczególnie istniejące endpointy: `admin_cheat.py`,
   `sandbox.py:313`, `api/inventory.py`, `/admin/characters/{id}/spells/*`). Jeśli sprzeczność
   — STOP, opisz prostym językiem, czekaj na moją decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] HINN — <nazwa>", labels: enhancement + needs-testing,
   struktura wg szablonu z issue #18.
4. Wdróż skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
5. Wykonaj sekcję "Weryfikacja". UI weryfikuj przez Playwright + /game-screen; edycję realnego
   bohatera — na koncie Demo (user_id=1), NIGDY na #1013.
6. Zaktualizuj notes.md ([x] + link [#NNN] + licznik fazy) i game_mechanics.md CZĘŚĆ AL, jeśli
   zadanie zmieniło design. Zaproponuj commit zgodny z konwencją — nie pushuj bez mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zrobione i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku w https://aigm-dev.studio-colorbox.com/admin/
     (co kliknąć, co powinno się pokazać),
   - co następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD. Edycja testowa wyłącznie na bohaterach konta Demo (1).
- REUSE przed pisaniem nowego — nowy backend tylko dla 3 luk + czysty GET (HI1). Reszta to
  istniejące endpointy + frontend.
- Każda mutacja bohatera przez inspektora MUSI: pisać audyt + respektować guard live_locked.
- Backend baked into image — zmiany Pythona wymagają rebuildu `--build backend` na .61.
- Bump `?v=` w admin/index.html przy zmianie shared/section modułów.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
