Pracujemy nad FAZĄ O — Observability + Mapa węzłów (architektura). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. docs/V2_ARCHITECTURE/22_FAZA_O_OBSERVABILITY_ARCHMAP.md (pełny spec fazy: Cel/Dla agenta/Weryfikacja per zadanie, Numbers Policy, zależności),
3. docs/V2_ARCHITECTURE/08_OBSERVABILITY_AND_MCP.md (szczegóły mechaniki observability — DDL tabel, payloady, narzędzia MCP),
4. notes.md → sekcja "FAZA O" (checklista — jedyne źródło statusów),
5. tools/archmap/INSTRUKCJA.md + README.md (jak działa mapa — pilot combat już gotowy).

ZAKRES (decyzje Piotra 2026-06-16):
- Observability i mapa węzłów to JEDNA faza, dwa tory. Łączy je heat-map mapy czytająca tabele
  game_events/llm_call_log (te same co observability) oraz serwer MCP mogący serwować mapę.
- Kolejność: FAZA O idzie PO FAZIE L (lochy). NIE blokuje FAZY 5 MP — może iść równolegle.
- Tabele game_events/llm_call_log JUŻ ISTNIEJĄ (migracja z #587) — O1 częściowo zrobione; nie
  duplikuj migracji, dodaj tylko event_logger.py + payloady. Sprawdź realny stan w kodzie.
- Sugerowana kolejność zadań: O6 → O1 → O2 → O3 → O8 → O4 → O5 → O7 → O9 (O6 daje natychmiastową
  wartość, O8 spina oba tory). Zależności w specu §Zależności — uszanuj je.
- Poza zakresem: wydzielenie archmap do osobnego repo (Piotr decyduje osobno — "repo potem");
  rotacja/leaderboard; cokolwiek spoza 10 zadań O (O1–O10).

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie O, ani mniej, ani więcej:
1. W notes.md → FAZA O znajdź pierwsze niezaznaczone [ ] zadanie zgodnie z sugerowaną kolejnością
   i zależnościami ze specu. Jeśli zależność (np. O8 wymaga O1+O2) nie jest [x] — weź wcześniejsze.
2. Przeczytaj pełny opis zadania w 22_FAZA_O (Cel / Dla agenta / Weryfikacja) i sprawdź w kodzie,
   czy opis zgadza się z rzeczywistością (szczególnie stan tabel po #587, punkt log_combat_turn:2893
   w combat_service, istniejące endpointy analytics). Sprzeczność → STOP, opisz prostym językiem,
   czekaj na moją decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] ONN — <nazwa>", labels: enhancement + needs-testing, struktura
   wg szablonu #18 (sekcja "## Files changed" OBOWIĄZKOWA — to ona zasila nakładkę mapy; Numbers
   Policy z tabeli w specu to wartości startowe).
   WYJĄTEK: O5 (test MCP) — czysty playtest, bez issue [TASK].
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich), o ile to
   zmiana backendu/frontu z testowalną logiką. Dla zadań mapy (O6/O7/O8/O9 część HTML) — wykonaj
   wg opisu; mapę weryfikuj wizualnie (otwórz architecture-map.html / http.server 4747).
   Zasady logowania observability: NIGDY nie wołaj LLM w ścieżce zapisu zdarzenia, nigdy nie blokuj
   tury (fire-and-forget dozwolone).
5. Wykonaj sekcję "Weryfikacja" z opisu zadania. Dane observability weryfikuj na DEV (rozegraj
   walkę w Combat Sandbox → sprawdź wiersze w tabelach). Mapę — wizualnie + drift_check.py.
6. Zaktualizuj notes.md ([x] + link [#NNN]) i 22_FAZA_O / heat-source.json / node-map.json, jeśli
   zadanie zmieniło design lub dodało węzły. Zaproponuj commit wg konwencji — nie pushuj bez zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zrobione i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku (panel admina / mapa w przeglądarce / co kliknąć),
   - co następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy PROD.
- Migracje nie-destrukcyjne (kolumny legacy zostają). Seedy created_by='seed'.
- Dostęp do DB tylko przez SSH+docker. Heat-map czyta DB read-only — NIGDY przez sshfs (psuje SQLite).
- Logowanie zdarzeń: czysty Python, zero LLM, zero blokowania pętli gry.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów.
- Bump `?v=` przy zmianach shared modułów JS (panel analityki).
- Issue zamykam tylko ja, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.
- Mapa: skrypty overlay uruchamiaj na hoście z gh + dostępem do repo; map-overlay.json jest
  generowany — nie edytuj ręcznie.

Zacznij od kroku 1.
