# V2 Development — Lista Napraw

Źródło bugów: `PHASE_11_TEST_CAMPAIGNS/01_COMBAT_SIMULATION.md` (sesja testowa 2026-05-25, 29 tur).

**Zasady tego pliku:**
- Nowe zadania dodajemy **na dole sekcji TO DO**
- Ukończone zadania **przenosimy na dół pliku** do sekcji DONE
- W każdym zadaniu: **Co zrobić / Co ustalono / Czego się spodziewać** — prostym językiem, bez żargonu

---

## TO DO

### BUG-03 — NPC nie są zapamiętywani 🔴

**Co zrobić:**  
Zrobić listę "spotkanych NPC" per kampania. Dziś po dziesiątkach rozmów z karczmarką Martą system wciąż pokazuje "brak znanych NPC". MG może o niej "zapomnieć" w następnej turze.

**Co ustalono:**  
- Nowa tabela `campaign_known_npcs` z FK do istniejącej tabeli `npcs` (żeby korzystać z `description`, `personality`, `inventory` które już są).
- Dodatkowe pola: `first_met_location`, `first_met_turn`, `notes` (krótka notatka MG), `relation_status` ('friendly' / 'neutral' / 'hostile').
- MG emituje `NPC_MET: {name, role, location, notes}` przy pierwszym spotkaniu, opcjonalnie `NPC_UPDATE: {name, relation_status, notes}` dla zmian.
- Do system promptu wstrzykiwanych **ostatnich 10 spotkanych NPC** z notatkami i statusem relacji.

**Czego się spodziewać:**  
MG będzie konsekwentnie odgrywał poznane postacie — pamięta ich imiona, role, ostatnie spotkanie. Gracz w panelu zobaczy listę poznanych ludzi.

---

### BUG-01 — Przedmioty się duplikują przy oddaniu NPC 🟡

**Co zrobić:**  
Naprawić sytuację gdy gracz oddaje rzecz NPC-owi — dziś rzecz zostaje u gracza i jeszcze pojawia się druga kopia. Backend musi rzeczywiście usuwać przedmiot z plecaka kiedy MG opisuje oddanie.

**Co ustalono:**  
Robota mechaniczna — MG dostanie nowy sygnał "usuń rzecz", backend go obsłuży. Plus fallback na słowa "oddaję / kładę / przekazuję" w tekście.

**Czego się spodziewać:**  
Kiedy oddasz księgę NPC-owi, ta księga znika z twojego plecaka. Bez duplikatów.

---

### BUG-04 — Plan MG (Akt / Scena / Cel) zawsze pusty 🟡

**Co zrobić:**  
Pola "Akt", "Scena", "Cel sceny" w panelu kampanii są puste przez całą grę. MG ma plan, ale nie zapisuje go do bazy. Trzeba dodać aktualizację.

**Co ustalono:**  
*Do omówienia* — jak często MG ma aktualizować plan? Co turę? Tylko przy zmianie sceny? Czy sam decyduje?

**Czego się spodziewać:**  
W panelu kampanii widać aktualny akt fabuły, w jakiej scenie jesteśmy i jaki jest jej cel. Gracz może też widzieć cel sceny w swoim UI (jako podpowiedź "co teraz?").

---

### BUG-05 — Nudne opisy porażek rzutów 🟢

**Co zrobić:**  
Kiedy gracz nie zda rzutu, MG dziś daje generyczny opis typu "tajemnica pozostaje ukryta" — fabuła stoi. Trzeba zmusić MG żeby przy porażce wprowadzał konkretną konsekwencję (hałas, strata czasu, zmęczenie, niechciana uwaga).

**Co ustalono:**  
Robota mechaniczna — dopiszemy regułę do system promptu, lista 5 typów konsekwencji już jest gotowa.

**Czego się spodziewać:**  
Porażka rzutu pcha fabułę do przodu w niewygodny sposób — np. nieudane skradanie ściąga strażnika, nieudana perswazja kosztuje pół godziny czasu.

---

### BUG-06 — XP rośnie za wolno 🟢

**Co zrobić:**  
Gracz po 29 turach gry (las, ruiny, misja, rozmowy z NPC) dostał tylko 9 XP. Dziś XP daje się głównie za odpoczynek. Brakuje XP za walkę i za akcje fabularne.

**Co ustalono:**  
*Do omówienia* — konkretne wartości XP (5? 10? 25?) za różne eventy. Czy walka też ma dawać XP (dziś **nie daje wcale**)?

**Czego się spodziewać:**  
Gracz widzi że gra nagradza go za eksplorację, rozmowy z nowymi ludźmi, zdobywanie ważnych przedmiotów, kończenie misji. Awanse poziomu pojawiają się w sensownych odstępach.

---

### BUG-08 — Nowy łotr startuje z pustym plecakiem 🟢

**Co zrobić:**  
Łotr poziomu 1 zaczyna grę bez **niczego** — bez broni, bez prowiantu, bez światła. Powód: w bazie nie ma archetypu "łotr", tylko "wojownik" i "uczony".

**Co ustalono:**  
*Do omówienia* — co dokładnie ma dostać łotr na start? (sztylet, wytrychy, 5 złota, pochodnia?)

**Czego się spodziewać:**  
Nowy łotr startuje z sensownym zestawem startowym, tak jak wojownik i uczony. Nie wchodzi do groźnych ruin gołymi rękami.

---

## DONE

### BUG-02 — Zegar gry stoi w miejscu ✅ (2026-05-25)

**Co zrobiono:**  
`clock_service` dostał wsparcie dla minut (`session_flags.ingame_minutes`, 0–59) bez utraty kompatybilności z istniejącymi wywołaniami opartymi o godziny. Nowy serwis `clock_config_service` trzyma konfigurację w `game_config_meta` (defaults: narrative=15min, combat=5min, travel=60min). Funkcja `create_turn_log` w `turns.py` po każdym zapisie tury wywołuje `advance_clock` z wartością zależną od `route`. MG może nadpisać w górę dla narracji przez nowe pole `time_advance_minutes` w odpowiedzi JSON (0–480 min). Nowe admin endpoints `GET/PATCH /api/admin/clock-config`. Frontend odświeża zegar w nagłówku po każdej turze. Display: `"Dzień 3, 14:23 Popołudnie"` (przedtem: `"14:00"`).

**Czego się spodziewać:**  
Zegar gry idzie do przodu po każdej turze narracyjnej (domyślnie +15 min) i walki (+5 min). Gracz widzi popołudnie po kilkunastu turach, wieczór po wielu rozmowach. MG przy długich akcjach (rozmowa, czytanie księgi) może podbić wartość. Admin tunuje defaulty bez deploya przez `/api/admin/clock-config`. UI admin panelu jako follow-up.

**Pliki:** `backend/app/services/clock_service.py`, `backend/app/services/clock_config_service.py` (nowy), `backend/app/api/turns.py`, `backend/app/routers/admin.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_bug02_clock_minutes.py` (nowy), `frontend/front/js/app.js`, `frontend/front/index.html`

---

### BUG-07 — Techniczny błąd widoczny w narracji ✅ (2026-05-25)

**Co zrobiono:**  
Funkcja `_inject_location_blocked` w `backend/app/api/turns.py` przestała doklejać techniczny tag `[LOCATION_BLOCKED:...]` do narracji. Zostaje tylko `location_intent = null` (żeby błędna lokacja się nie zapisała) oraz server-side log. Usunięta sekcja "BLOKADA RUCHU" w `system_prompt.txt` (była martwym kodem — post-hook wykonywał się PO generacji, więc MG nigdy nie widział tagu w tej samej turze).

**Czego się spodziewać:**  
Gracz nigdy nie zobaczy `[LOCATION_BLOCKED:...]` w narracji. Jeśli MG opisze ruch do nieistniejącej lokacji, panel po prostu nie zmieni current_location — bez technicznego komunikatu.

**Pliki:** `backend/app/api/turns.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_phase8d_location_hook.py`
