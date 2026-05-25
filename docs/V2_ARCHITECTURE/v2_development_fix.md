# V2 Development — Lista Napraw

Źródło bugów: `PHASE_11_TEST_CAMPAIGNS/01_COMBAT_SIMULATION.md` (sesja testowa 2026-05-25, 29 tur).

**Zasady tego pliku:**
- Nowe zadania dodajemy **na dole sekcji TO DO**
- Ukończone zadania **przenosimy na dół pliku** do sekcji DONE
- W każdym zadaniu: **Co zrobić / Co ustalono / Czego się spodziewać** — prostym językiem, bez żargonu
- Po każdym ukończonym zadaniu dopisz **Jak przetestować** — konkretne kroki weryfikacji (co otworzyć, kliknąć, wywołać, co powinno się zmienić)
- Dla każdego zadania zawsze zakładaj **issue na GitHub** z labelami `enhancement` + `needs-testing`; link wklej w sekcji DONE

---

## TO DO

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

### BUG-03 — NPC nie są zapamiętywani ✅ (2026-05-25)

**Co zrobiono:**  
Nowa tabela `campaign_known_npcs` (FK do `npcs`, z polami `notes`, `relation_status`, `first_met_location`, `first_met_turn`) i serwis `npc_memory_service.py` z funkcjami `record_npc_met` / `update_npc_relation` / `get_recent_known_npcs`. Hook w `create_turn_log` parsuje pola `npc_met` i `npc_update` z odpowiedzi MG i zapisuje do bazy. `context_injector` dołącza ostatnich 10 spotkanych NPC do system promptu każdej kolejnej tury (sekcja "ZNANI NPC" z notatkami i statusem relacji). Nowa zakładka "👥 Znani NPC" w monitorze kampanii (admin panel v2) z tabelą wszystkich poznanych postaci. Nowy admin endpoint `GET /api/admin/campaigns/{id}/known-npcs`.

**Czego się spodziewać:**  
Po pierwszej rozmowie z Martą MG zapisuje ją do listy. W kolejnych turach MG widzi "ZNANI NPC: - Marta (karczmarka)..." w prompcie i konsekwentnie odgrywa postać. Gdy gracz pomaga lub obraża NPC, MG emituje `npc_update` i status relacji zmienia się na friendly/hostile. Admin może podejrzeć całą listę w panelu kampanii.

**Pliki:** `backend/app/migrations_admin.py`, `backend/app/services/npc_memory_service.py` (nowy), `backend/app/services/context_injector.py`, `backend/app/api/turns.py`, `backend/app/routers/admin.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_bug03_npc_memory.py` (nowy), `frontend/admin_panel_v2/sections/campaigns.js`, `frontend/admin_panel_v2/sections/campaigns_hub.js`

**Jak przetestować:**
1. Wejdź na https://aigm-dev.studio-colorbox.com/ jako gracz, zagraj turę gdzie MG przedstawia nową postać (np. karczmarza).
2. W panelu admina otwórz kampanię → zakładka "👥 Znani NPC" — sprawdź że postać się pojawiła z rolą i statusem `neutral`.
3. Zagraj turę gdzie pomagasz NPC (np. "pomagam mu"). Sprawdź czy status zmienił się na `friendly`.
4. Zagraj kolejną turę — upewnij się że MG nadal spójnie odgrywa tę postać (imię, rola) w narracji.
5. `docker exec ai-gm-dev-backend-1 pytest backend/tests/test_bug03_npc_memory.py -v` — wszystkie testy zielone.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/123

---

### BUG-04 — Plan MG (Akt / Scena / Cel) zawsze pusty ✅ (2026-05-25)

**Co zrobiono:**  
Trójwarstwowy system aktualizacji planu MG. **`gm_note`** (opcjonalne, co turę) — krótka notatka narracyjna trafia do rolling buffera 30 wpisów w `engine_private.gm_note_buffer`. **`scene_advance: true`** — inkrementuje `current_scene_ordinal` aktywnego łuku. **`gm_plan_update`** — merguje zmiany roadmapy, dodaje/usuwa cele sceny, aktualizuje `last_plan_updated_turn`. Trigger: `scene_advance` lub konfigurowalny próg (default 25 tur) — gdy przekroczony, `context_injector` wstrzykuje do system promptu blok "AKTUALIZACJA PLANU MG — WYMAGANA" i MG zwraca `gm_plan_update` w tym samym response (zero dodatkowych LLM callów). Nowa zakładka "⚙ Ustawienia" w panelu Kampanie z edytowalnymi wartościami dla progu planu i zegara (oba z opisem). Przy okazji: `npc_met` w system_prompt.txt zmieniony z OPCJONALNE na OBOWIĄZKOWE — LLM czytał "optional" dosłownie.

**Czego się spodziewać:**  
Po co 25 turach MG dostaje prośbę o update i aktualizuje roadmapę, cele i stan sceny. Admin widzi w panelu aktualną notatkę MG i licznik sceny. W ⚙ Ustawieniach można zmienić próg.

**Pliki:** `backend/app/services/plan_config_service.py` (nowy), `backend/app/services/context_injector.py`, `backend/app/services/turn_pipeline.py`, `backend/app/api/turns.py`, `backend/app/routers/admin.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_bug04_gm_plan_update.py` (nowy), `frontend/admin_panel_v2/sections/campaigns_hub.js`, `frontend/admin_panel_v2/sections/campaigns_settings.js` (nowy)

**Jak przetestować:**
1. W panelu admina → Kampanie → ⚙ Ustawienia — sprawdź że widać pola "Plan MG" i "Zegar gry" z wartościami.
2. Zmień próg na 5 tur, zapisz. Zagraj 5 tur narracyjnych — MG powinien zwrócić `gm_plan_update` w JSON.
3. Otwórz kampanię → Plan GM — sprawdź że roadmap ma nową notatkę `[T5] ...`.
4. Zagraj turę gdzie MG powie że scena się skończyła (`scene_advance: true`) — sprawdź w DB że `current_scene_ordinal` wzrósł.
5. `docker exec ai-gm-dev-backend-1 pytest tests/test_bug04_gm_plan_update.py -v` — 9 passed.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/125

---

### BUG-01 — Przedmioty się duplikują przy oddaniu NPC ✅ (2026-05-25)

**Co zrobiono:**  
Nowe pole `remove_item` w odpowiedzi JSON MG. Kiedy narracja opisuje oddanie, zostawienie lub utratę przedmiotu — MG wstawia `{"label": "Stara Księga"}` (lub array dla kilku). Hook w `create_turn_log` parsuje to pole i usuwa pasujący wiersz z `character_inventory` (DELETE przy qty=1, dekrementacja przy qty>1). Dopasowanie po labelu jest case-insensitive (LOWER). Nowa sekcja "ODDAWANIE I TRACENIE PRZEDMIOTÓW" w system_prompt.txt z zasadami i przykładami.

**Czego się spodziewać:**  
Kiedy oddasz księgę NPC-owi, ta księga znika z twojego plecaka. Bez duplikatów.

**Pliki:** `backend/app/api/turns.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_bug01_remove_item.py` (nowy)

**Jak przetestować:**
1. Zagraj turę gdzie zdobywasz przedmiot (np. "biorę księgę") — sprawdź że jest w plecaku.
2. Zagraj turę "daję księgę Marcie" — MG powinien wyemitować `remove_item` w JSON.
3. Sprawdź że księga **zniknęła** z plecaka w UI gracza. Brak duplikatów.
4. Przetestuj stos: wejdź w posiadanie 3 fiolek, oddaj jedną — powinny zostać 2.
5. `docker exec ai-gm-dev-backend-1 pytest tests/test_bug01_remove_item.py -v` — 8 passed.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/124

---

### BUG-02 — Zegar gry stoi w miejscu ✅ (2026-05-25)

**Co zrobiono:**  
`clock_service` dostał wsparcie dla minut (`session_flags.ingame_minutes`, 0–59) bez utraty kompatybilności z istniejącymi wywołaniami opartymi o godziny. Nowy serwis `clock_config_service` trzyma konfigurację w `game_config_meta` (defaults: narrative=15min, combat=5min, travel=60min). Funkcja `create_turn_log` w `turns.py` po każdym zapisie tury wywołuje `advance_clock` z wartością zależną od `route`. MG może nadpisać w górę dla narracji przez nowe pole `time_advance_minutes` w odpowiedzi JSON (0–480 min). Nowe admin endpoints `GET/PATCH /api/admin/clock-config`. Frontend odświeża zegar w nagłówku po każdej turze. Display: `"Dzień 3, 14:23 Popołudnie"` (przedtem: `"14:00"`).

**Czego się spodziewać:**  
Zegar gry idzie do przodu po każdej turze narracyjnej (domyślnie +15 min) i walki (+5 min). Gracz widzi popołudnie po kilkunastu turach, wieczór po wielu rozmowach. MG przy długich akcjach (rozmowa, czytanie księgi) może podbić wartość. Admin tunuje defaulty bez deploya przez `/api/admin/clock-config`. UI admin panelu jako follow-up.

**Pliki:** `backend/app/services/clock_service.py`, `backend/app/services/clock_config_service.py` (nowy), `backend/app/api/turns.py`, `backend/app/routers/admin.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_bug02_clock_minutes.py` (nowy), `frontend/front/js/app.js`, `frontend/front/index.html`

**Jak przetestować:**
1. Wejdź na https://aigm-dev.studio-colorbox.com/, sprawdź czy zegar w nagłówku pokazuje czas z minutami (np. `"Dzień 1, 08:00 Rano"`).
2. Zagraj turę narracyjną — zegar powinien przeskoczyć o +15 min. Zagraj kilka tur i obserwuj czy czas rośnie.
3. Zagraj turę walki — zegar powinien przeskoczyć o +5 min.
4. Sprawdź `GET /api/admin/clock-config` — powinien zwrócić `{narrative_min: 15, combat_min: 5, travel_min: 60}`.
5. `docker exec ai-gm-dev-backend-1 pytest backend/tests/test_bug02_clock_minutes.py -v` — wszystkie testy zielone.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/122

---

### BUG-07 — Techniczny błąd widoczny w narracji ✅ (2026-05-25)

**Co zrobiono:**  
Funkcja `_inject_location_blocked` w `backend/app/api/turns.py` przestała doklejać techniczny tag `[LOCATION_BLOCKED:...]` do narracji. Zostaje tylko `location_intent = null` (żeby błędna lokacja się nie zapisała) oraz server-side log. Usunięta sekcja "BLOKADA RUCHU" w `system_prompt.txt` (była martwym kodem — post-hook wykonywał się PO generacji, więc MG nigdy nie widział tagu w tej samej turze).

**Czego się spodziewać:**  
Gracz nigdy nie zobaczy `[LOCATION_BLOCKED:...]` w narracji. Jeśli MG opisze ruch do nieistniejącej lokacji, panel po prostu nie zmieni current_location — bez technicznego komunikatu.

**Pliki:** `backend/app/api/turns.py`, `backend/prompts/system_prompt.txt`, `backend/tests/test_phase8d_location_hook.py`

**Jak przetestować:**
1. Wejdź na https://aigm-dev.studio-colorbox.com/ i zagraj turę gdzie próbujesz wejść do nieistniejącej lokacji (np. "idę do smoczej jamy" gdy takiej nie ma w DB).
2. Sprawdź że narracja MG **nie zawiera** tekstu `[LOCATION_BLOCKED` ani żadnych technicznych tagów.
3. W panelu admina potwierdź że `current_location` kampanii się nie zmieniła (zostaje stara lokacja).
4. `docker exec ai-gm-dev-backend-1 pytest backend/tests/test_phase8d_location_hook.py -v`

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/121
