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

*(wszystkie bugi ze ścieżki testowej 2026-05-25 ukończone)*

---

## DONE

### BUG-09 — Walka toczy się trybem narracyjnym zamiast silnika walki ✅ (2026-05-25)

**Co zrobiono:**  
`context_injector.py` dostał nową metodę `_build_available_enemies_block()`, która przy każdej turze narracyjnej odpytuje bazę o aktywne klucze wrogów (`game_config_enemies WHERE is_active=1`) i wstrzykuje je do kontekstu LLM jako blok `=== DOSTĘPNE KLUCZE WROGÓW ===`. Wcześniej system_prompt.txt miał zahardkodowanych 10 kluczy (brak `giant_rat`, `rat`, `cave_spider`, `bat` itd.) — LLM nie wiedział jak zainicjować walkę z olbrzymim szczurem i narrował ją zamiast emitować `[COMBAT_START:giant_rat]`. Teraz LLM zawsze widzi pełną listę ~70 kluczy z bazy. Przy okazji: zegar (`clock`) jest teraz dołączany do payloadu `[DONE]` na końcu streamu — frontend aktualizuje header natychmiast bez osobnego `GET /clock`.

**Czego się spodziewać:**  
Gdy gracz spotka szczura / pająka / wilka / innego wroga z bazy, MG emituje `[COMBAT_START:odpowiedni_klucz]` i silnik walki się uruchamia. Zegar w headerze aktualizuje się w tej samej chwili co odbiór końca tury (nie z lekkim opóźnieniem).

**Pliki:** `backend/app/services/context_injector.py`, `backend/prompts/system_prompt.txt`, `backend/app/api/turns.py`, `frontend/front/js/app.js`

**Jak przetestować:**
1. Zagraj turę narracyjną gdzie MG wpycha walkę z wrogiem z bazy (np. "wchodzę do piwnicy pełnej szczurów") — powinno pojawić się okienko walki, nie sama narracja.
2. Sprawdź że po turze zegar w headerze aktualizuje się natychmiast (nie po chwili).
3. Sprawdź logi backendu: `docker logs ai-gm-dev-backend-1 --tail=50` — brak błędów `available_enemies_block_failed`.
4. W logach LLM call sprawdź że kontekst zawiera blok `DOSTĘPNE KLUCZE WROGÓW` z kluczem `giant_rat`, `cave_spider`, `bat` itp.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/129

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

---

### BUG-05 — Konsekwencje porażek rzutów ✅ (2026-05-25)

**Co zrobiono:**  
Nowa OBOWIĄZKOWA sekcja "KONSEKWENCJE PORAŻEK RZUTÓW" w `system_prompt.txt`. MG nie może już pisać "nie udało się" bez konkretu — musi wybrać konsekwencję z 6 kategorii: **Hałas** (uwaga), **Strata czasu** (`time_advance_minutes`), **Zmęczenie/rana** (HP/kondycja), **Niechciana uwaga** (NPC), **Strata zasobu** (`remove_item`), **Zranienie 3rd party** (towarzysz/NPC obrywa zamiast gracza). Sekcja zawiera 3 przykłady (skradanie, lockpicking, perswazja). Im wyższe DC, tym poważniejsza konsekwencja.

**Czego się spodziewać:**  
Porażka rzutu pcha fabułę do przodu w niewygodny sposób — nieudane skradanie ściąga strażnika, nieudany lockpicking kosztuje wytrych i pół godziny, nieudana perswazja zamyka możliwość handlu na ten dzień.

**Pliki:** `backend/prompts/system_prompt.txt`

**Jak przetestować:**
1. Zagraj 5 tur z świadomymi porażkami (akcje na słabym staty).
2. Sprawdź że każda porażka ma konkretną konsekwencję (nie tylko "nie udało się").
3. W przynajmniej 3 z 5 porażek powinny pojawić się różne kategorie konsekwencji.
4. Konsekwencje typu "strata czasu" powinny mieć w JSON `time_advance_minutes`; "strata zasobu" — `remove_item`.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/126

---

### BUG-06 — XP rośnie za wolno ✅ (2026-05-25)

**Co zrobiono:**  
Cały system XP (XS1-XS15) był **już zaimplementowany** w Stage 2D — problem był taki że MG nie znał tagów. Nowa sekcja "NAGRODY XP — TAGI W NARRACJI" w `system_prompt.txt` z listą tagów: `[BEAT_COMPLETE]` (+30), `[QUEST_COMPLETE]` (+40), `[DUNGEON_CLEAR]` (+75), `[DISCOVERY:lore:...]` (+10), `[DISCOVERY:secret_location:...]` (+10), `[XP_GRANT:powod:N]` (+5–25, cap 50/sesja). MG dostał też instrukcję "bądź szczodry — po 5-10 turach powinno wpaść 30-50 XP". Dodatkowo: hook BUG-03 (`npc_met`) wywołuje teraz `grant_first_npc_talk` automatycznie — pierwszy raz z imiennym NPC = +5 XP (XS6) bez potrzeby DIALOGUE action.

**Czego się spodziewać:**  
Gracz po 10-15 turach narracyjnych ma 40+ XP (zamiast 9 jak wcześniej). Awanse poziomu pojawiają się w sensownych odstępach (poziom 2 po ~100 XP = jedna pełna sesja).

**Pliki:** `backend/prompts/system_prompt.txt`, `backend/app/api/turns.py`

**Jak przetestować:**
1. Zagraj turę spotkania nowego NPC (`gospodarz Tomek`) — sprawdź `character_xp_grants` — powinien być wpis `exploration.npc_first_talk` +5 XP.
2. Zagraj turę gdzie MG emituje `[BEAT_COMPLETE:found_map]` — sprawdź +30 XP.
3. Po 10-15 turach narracyjnych — łączny XP powinien być 40+.
4. Sprawdź że ten sam NPC drugi raz NIE daje +5 XP (idempotencja).

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/127

---

### BUG-08 — Nowy łotr startuje z pustym plecakiem ✅ (2026-05-25)

**Co zrobiono:**  
Nowa migracja `_ensure_rogue_archetype` w `migrations_admin.py` dodaje wiersz `rogue` do `game_config_archetypes`. Universal kit (zgodnie z decyzją): sztylet, krótki łuk, wytrychy, lina 10m, 2× pochodnia, 3× suchy prowiant, skórzana zbroja. 8 sg, HP 8 (między wojownikiem 10 a uczonym 6). Frontend już wcześniej znał `rogue` (ARCHETYPE_BONUS DEX+2/LCK+1) — brakowała tylko strony DB.

**Czego się spodziewać:**  
Nowy łotr startuje z sensownym zestawem startowym, tak jak wojownik i uczony. Nie wchodzi do groźnych ruin gołymi rękami.

**Pliki:** `backend/app/migrations_admin.py`

**Jak przetestować:**
1. Sprawdź DB: `docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "SELECT * FROM game_config_archetypes WHERE key='rogue';"` — powinno zwrócić wiersz.
2. Stwórz nową postać łotra przez kreator. Sprawdź ekwipunek: sztylet, krótki łuk, wytrychy, lina, 2 pochodnie, 3 prowianty, skórzana zbroja.
3. Sprawdź złoto: 8 sg. HP base: 8 + mod CON.
4. Otwórz Admin → Mechanika → archetypy — rogue widoczny i edytowalny.

**GitHub issue:** https://github.com/szmidtpiotr/ai-gm/issues/128
