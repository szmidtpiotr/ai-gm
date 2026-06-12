Pracujemy nad HOTFIXAMI w FAZIE U gry AI-GM. Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. notes.md → sekcja "FAZA U" → NAJNOWSZA sekcja "Hotfixy po ..." (checklista — jedyne źródło statusów).

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDEN hotfix, ani mniej, ani więcej:
1. W najnowszej sekcji "Hotfixy po ..." w notes.md znajdź pierwszą niezaznaczoną pozycję [ ] HF-N
   (kolejność = kolejność na liście; jest celowa).
2. Jeśli HF ma link do issue — przeczytaj issue ORAZ WSZYSTKIE komentarze (instrukcja naprawy
   często jest w komentarzu, nie w opisie). Jeśli HF nie ma issue — utwórz je:
   tytuł "[BUG] HF-N — <opis>", labels: bug + needs-testing, treść z wpisu w notes.md.
3. Sprawdź w kodzie, czy diagnoza z issue/notes.md zgadza się z rzeczywistością.
   Sprzeczność → STOP, opisz prostym językiem, czekaj na moją decyzję.
4. Wdróż skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
   Wyjątek — HF oznaczony "COMMIT" (fix już istnieje w drzewie roboczym): nie cofaj fixu dla RED;
   napisz test regresyjny (od razu GREEN), zacommituj istniejący fix razem z testem.
5. Deploy na DEV: rebuild `docker compose -f docker-compose.dev.yml up -d --build backend`
   (restart NIE wystarczy). Po deployu sprawdź logi backendu pod kątem błędu, którego dotyczył HF.
6. Zaktualizuj notes.md: [x] przy HF-N + numer commita. Zaproponuj commit zgodny z konwencją —
   nie pushuj bez mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co było zepsute i co naprawiono (2-3 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku (przeglądarka https://aigm-dev.studio-colorbox.com/
     albo dokładna komenda SQL/log),
   - który HF jest następny w kolejce (albo: "sekcja hotfixów pusta — wracaj do prompt.md").

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD.
- Zakres = TYLKO ten jeden hotfix. Żadnych refaktorów, ulepszeń ani innych bugów "przy okazji" —
  zauważone problemy wpisz do raportu, nie do kodu.
- Nigdy pełny `pytest tests/` — tylko testy hotfixu i powiązanego modułu.
- Commit OBOWIĄZKOWY w tej samej sesji — fix bez commita znika przy następnym rebuildzie.
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
