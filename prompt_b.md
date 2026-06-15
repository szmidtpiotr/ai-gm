Pracujemy nad FAZĄ B — Balans 3 klas + Czary maga (AI-GM). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. game_mechanics.md → CZĘŚĆ AK (filary klas, liczby kanoniczne, system czarów, fazy adaptacji, decyzje D1–D3),
3. notes.md → sekcja "FAZA B" (checklista — jedyne źródło statusów),
4. rpg_spells_design_doc.md (katalog 50 czarów — źródło dla Bloku 2/3).

ZAKRES (sesja projektowa Piotra, 2026-06-14):
- Założenia tożsamości: WOJOWNIK = tank (najwięcej HP, melee, mało INT, mało skilli);
  ŁOTRZYK = zwinny zwiadowca/złodziej (DEX, NAJWIĘCEJ skilli, MNIEJ HP niż warrior,
  burst z ukrycia); MAG = słaby fizycznie (najmniej HP), nadrabia czarami
  (heal/tarcza/buff/kontrola/atak).
- Liczby kanoniczne (CZĘŚĆ AK.2): HP 10/8/6 (warrior/rogue/mag), bonus statów
  warrior STR+2/CON+1, rogue DEX+2/LCK+1, mag INT+2/WIS+1, skille rogue 9/10 > warrior 7/8.
- KOLEJNOŚĆ: Blok 1 (B1–B5) standalone — można PRZED/równolegle z FAZĄ L. Blok 2 (B6–B13)
  niezależny od L, wymaga FAZY S (✅ kompletna). Blok 3 (B14–B17) ⛔ ZABLOKOWANY do
  FAZY 5 (MP/towarzysze) + systemu reakcji — NIE zaczynaj go.
- Czary: Faza 1 = tylko single-target / self-buff / heal-self / kondycje (silnik wspiera).
  Ally-target, summony, reakcje = Faza 2 (Blok 3) — poza zakresem teraz. Czary mapują
  efekty na ISTNIEJĄCE kondycje FAZY S (poisoned/slowed/frozen/blinded/stunned/confused/
  cursed) — reużycie, NIE duplikat.
- DECYZJE NIEZAMKNIĘTE (CZĘŚĆ AK.6): D1 HP 10/8/6 — przyjęte roboczo, wdrażaj te wartości.
  D2 (B4 rogue sneak attack jako cecha vs generyczny hidden) i D3 (B17 mag CHA-czary)
  NIE są rozstrzygnięte — jeśli wypadnie B4 lub B17, STOP i zapytaj Piotra o decyzję
  zanim cokolwiek wdrożysz.
- Poza zakresem (NIE implementuj): pełny system towarzyszy/petów, ally-target/summon/reakcje
  czarów (Blok 3), leaderboard czarów, czary rytualne poza walką.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie B, ani mniej, ani więcej:
1. W notes.md → FAZA B znajdź pierwsze niezaznaczone [ ] zadanie w kolejności
   Blok 1 (B1→B2→B3→B4→B5) → Blok 2 (B6→B7→B8→B9→B10→B11→B12→B13). B11 ⛔ wymaga #595
   (wybór celu) — pomiń jeśli #595 niegotowe. Jeśli pierwsze niezaznaczone to B14–B17
   (Blok 3) — STOP: to znaczy, że Blok 1+2 domknięte, a Blok 3 wymaga FAZY 5; zapytaj Piotra.
2. Przeczytaj pełen opis w CZĘŚCI AK i sprawdź w kodzie, czy opis zgadza się z rzeczywistością
   (pliki z AK.3: characters.py, vitality_service.py, character_creation_config.py, spell_service.py,
   app.js). Jeśli sprzeczność — STOP, opisz prostym językiem, czekaj na decyzję.
3. Utwórz GitHub issue: tytuł "[TASK] BNN — <nazwa>", labels: enhancement + needs-testing,
   struktura wg szablonu z issue #18 (sekcja Numbers Policy obowiązkowa — wartości HP/skilli/
   tier/DC/mana z CZĘŚCI AK to wartości startowe). Buge tożsamości (B1–B3) mogą być labelem bug.
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymywania na pytaniach pośrednich).
   WYJĄTKI bez cyklu TDD:
   - B5 (test balansu): rozszerz test_issue475_combat_balance.py o 3 klasy — sam test jest
     deliverable, nie ma osobnego kodu produkcyjnego do TDD,
   - B13 (playtest): bez issue [TASK]; utwórz/użyj issue [SMOKE] FAZA B na raport.
5. Wykonaj sekcję "Weryfikacja". Tworzenie postaci weryfikuj w kreatorze (kreator MUSI pokazywać
   prawdziwe HP/staty/skille = to co dostaje gotowa postać). Walkę/czary maga weryfikuj w Combat
   Sandbox; flow gracza przez /game-test-player lub ręcznie na DEV.
6. Zaktualizuj notes.md ([x] + link [#NNN]) i game_mechanics.md CZĘŚĆ AK, jeśli zadanie
   zmieniło design (np. domknięcie decyzji D1–D3). Zaproponuj commit zgodny z konwencją —
   nie pushuj bez mojej zgody.
7. STOP. Raport końcowy po polsku, prostym językiem:
   - co zostało zrobione i dlaczego (2–4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku na https://aigm-dev.studio-colorbox.com/
     (co kliknąć, co powinno się pokazać),
   - co jest następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy nie dotykaj PROD.
- Mechaniki zablokowane (CLAUDE.md → Locked Game Mechanics): staty 7, formuła rzutu, skala DC,
  HP = base + CON_mod×level. Zmiana HP per klasa wynika z decyzji D1 — nie ruszaj formuły ani
  balansu wrogów #475 (warrior zostaje 10; różnicowanie przez rogue 10→8).
- Mechanika decyduje, LLM narruje (Zasady CZĘŚĆ 10). Czar: silnik liczy obrażenia/heal/manę/
  miscast, LLM tylko opisuje.
- Spójność kreator↔postać: każda liczba pokazana w kreatorze MUSI równać się tej, którą dostaje
  gotowy bohater (lekcja z #618). Nie kłam w UI.
- Czary reużywają kondycji FAZY S (game_config_conditions) — nie twórz duplikatów stanów.
- Żadnych destrukcyjnych migracji DB. Seedy zawsze created_by='seed'.
- Nigdy pełny `pytest tests/` — tylko testy zadania i powiązanych modułów (vitality, finalize,
  balance, spell, combat).
- Bump `?v=` przy zmianach shared modułów JS.
- Issue zamyka tylko Piotr, po weryfikacji wizualnej. Label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
