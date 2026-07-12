# STATUS — gdzie jesteśmy (captain's log)

> **Po co ten plik:** czytasz go na starcie sesji żeby w 30 sek wiedzieć gdzie jesteśmy.
> Po polsku, narracja — NIE lista zadań (ta jest w **GitHub Issues + Milestones = „Plan"**) i NIE spec (`game_mechanics.md`).
> **Claude utrzymuje ten plik** — aktualizuje sekcje na końcu każdej sesji. Ty tylko czytasz.
>
> Trzy sekcje: **CO ROBIMY TERAZ** · **OSTATNIO ZROBIONE** · **UWAŻAJ (pułapki)**.

_Ostatnia aktualizacja: 2026-07-12 (sesja BL-C3 #1338 — UI rzemiosła: zakładka Rzemiosło w ŻAR + admin CRUD przepisów + Smart Entry, Krok 11 / bramka S11)_

---

## 🎯 CO ROBIMY TERAZ

**Zadania = GitHub Issues + Milestones (Plan).** Rozkład faz: FAZA 5 Multiplayer 33 · **FIX 23** · FAZA L 12 · FAZA B 11 · FAZA 6 6 · FAZA LB 2 · FAZA SF 1.

**FOKUS: milestone `FIX` — bieżące bugi z przejść kampanii.** Cel: mechanika **sprawdzona i grywalna** → to brama do Multiplayera (FAZA 5 świadomie WSTRZYMANA aż single-player grywalny).

**Stan faz:**
- FAZA L (lochy) — praktycznie skończona i GRYWALNA (L19, 14/14 checkpointów na mobile).
- FAZA 5 Multiplayer — 33 issues (backlog, planowane); start dopiero po wyczyszczeniu FIX.

**Następne sensowne (milestone FIX, otwarte):** #751 (przepłata za posiłek), #746 (angielskie nazwy łupów), #757 (inventory klucz zamiast nazwy), #734 (brak mikstury w walce). Decyzja A/B przed startem (`design`): #733, #747, #753, #744.

---

## ✅ OSTATNIO ZROBIONE (ostatnie sesje)

**FAZA BL — Bestie i Łupy 2.0 (milestone #26):** silnik kompozycyjny spotkań + loot 2.0.
- **#1338 BL-C3 (Krok 11 / bramka S11)** — UI rzemiosła (#1199 kroki 6-7): zakładka **Rzemiosło u rzemieślnika NPC** w ŻAR + zarządzanie przepisami w adminie. **ŻAR (front-v2):** nowy modal `CraftingOverlay.tsx` lokacyjny (jak Usługi, NIE npc-owy jak sklep — przepisy z `crafter_type` wszystkich rzemieślników lokacji), otwierany deterministycznym chipem **„Rzemiosło" 🔨** (`OPEN_CRAFTING:<locKey>` — parytet z „Usługi", omija LLM). Chip wystawia `suggested_actions.py` gdy `crafting_service.location_has_crafting(loc)` (nowy helper). Lista przepisów jako karty: **podświetlenie zielone + badge „Starczy"** gdy bohater ma wszystkie komponenty (`hasAllComponents` po `useInventory`), chipy składników 🧩 z licznikiem **have/need** (zielony/czerwony), opłata usługi, przycisk **Wytwórz** (blokada „Brak komponentów"/„Za mało złota"). Po craftcie toast (+ „zniżka krasnoluda") i invalidacja `["character"]`+`["inventory"]` → liczniki i złoto odświeżają się na żywo. Hooki `useLocationCrafting`/`useCraft` (`GET /locations/{ref}/crafting`, `POST /characters/{id}/craft` z #1336). Store `crafting`+`openCrafting`/`closeCrafting`. **Admin:** zakładka **Przepisy** w Zawartość (tabela edit PATCH/delete DELETE via `_ROW_REGISTRY`, `inputs_json` jako textarea JSON) + nowe endpointy CRUD `GET/POST/PATCH/DELETE /api/admin/recipes` (self-contained, ADMIN_SQLITE_PATH) + descriptor Smart Entry dla `game_config_recipes` (required key/label/output_type/crafter_type; single_choice na typach; tworzenie „🤖 Nowy przepis" → Kreator AI). Build ŻAR na .61 (`sudo npm run build`, v0.1.0→**0.2.0**), wpis **F-85** w `frontend_design.md`. Weryfikacja: admin CRUD GET/POST/PATCH/DELETE OK; Smart Entry schema+list OK; `location_has_crafting` True/False OK; **craft e2e** (mikstura z ziół, [SBX] Eldric): komponenty skonsumowane, złoto 50→45, `potion_healing_minor` w ekwipunku (jako `item_key` przez ścieżkę game_items U11c — parytet z #1336). Wymagało S9 (#1336). review (wizualne)+needs-testing.
- **#1337 BL-C2 (Krok 10 / bramka S10)** — zbieranie ziół w podróży (akcja terenowa zasilająca rzemiosło #1199). Deterministyczna intencja „zbieram zioła" (`herb_gathering_service.is_gather_intent` — rdzenie czasownik+obiekt, **dane nie prompt**; `trigger_keywords` na skillu `survival`) → shortcut `_maybe_herb_shortcut` PRZED LLM wystawia test **WIS** (Przetrwanie/`survival`) z DC wg terenu hexa (`world_hexes.hex_type`: las/bagno **8**, równiny/wzgórza **12**, góry/pustkowia/`grania`/`ruins` **16**). Rozstrzygnięcie w `/skill-test/resolve` (source `herb_gathering`): **1–3 zioła** wg marginesu (+1/5 pkt, cap 3), **Nat 20** → dodatkowo rzadkie zioło (fallback dorodny okaz), **Nat 1** → trująca pomyłka (**1 obrażenie**, brak ziół), zwykła porażka → nic. **Cooldown 1×/hex/dzień gry** w `session_flags['herb_cooldowns']` (klucz `"q,r"` → `ingame_hours//24`) — kolejna próba tego dnia = „to miejsce już ogołocone" bez testu. Zioła = komponenty (`component_type='herb'`) z BL-B3; pula **tylko grantowalna** (JOIN `game_items` aktywne — bo tamtędy waliduje `grant_loot_to_character`; obecnie `healing_herb`, dwa pozostałe zioła BL-B3 wciąż `is_active=0`/poza `game_items`). 28/28 pytest; live na Demo (Drundor w lesie): Nat1 → -1 HP + narracja trucizny, cooldown → komunikat ogołocenia, sukces d20=16 → `healing_herb`×3 w ekwipunku (source `herb_gather`). Wymagało S9 (#1336 crafting). review+needs-testing.
- **#1336 BL-C1 (Krok 9 / bramka S9)** — rzemiosło core (light, wg #1199). Nowa tabela `game_config_recipes` (klucz, `inputs_json` `[{item_key,qty}]`, `output_type`, `output_key`, `service_cost_gold`, `crafter_type` smith/herbalist, `is_hidden` DEFAULT 0 — pole pod BL-D2, tu zawsze 0) + seed 3 przepisów startowych: **mikstura z ziół** (2× `healing_herb` + `korzen_zmornika` → `potion_healing_minor`, 5 gp), **ostrzenie broni +1 dmg** (`kiel_wilczy` + `ruda_zelaza`, afiks `craft_hone` na egzemplarzu — **NIE kumuluje się**, 15 gp), **naprawa pancerza** (`wolf_pelt`×2 → odnowienie durability, 8 gp). `crafting_service.py`: walidacja komponentów → konsumpcja z `character_inventory` → wynik; zniżka krasnoluda (kowalskie oko #969, reuse `DWARF_SHOP_DISCOUNT` 15%) na koszt usługi. Kolumna `npcs.crafter_type` + backfill z heurystyki nazwy (zielar/kowal). Endpointy `GET /api/locations/{id}/crafting` (przepisy lokalnych rzemieślników) + `POST /api/characters/{id}/craft`. 6/6 pytest; live na Demo u zielarki Agaty (brzezino) — krasnolud craft mikstury, koszt 5→4 gp (zniżka), komponenty skonsumowane, mikstura w ekwipunku. Wymagało S8 (#1335 komponenty). review+needs-testing.
- **#1334 BL-B2 + #1335 BL-B3 (Krok 8 / bramka S8)** — rebalans dropu + komponenty rzemieślnicze. #1334: `fragment_mapy_skarbow` wycięty z 72 tabel per-wróg → TYLKO tierowe (std 5/elite 10/boss 15); narracyjne śmieci (klepsydra/lutnia/wędka) wagi 30-45 → cap 8; standard ≥40% użytkowych. #1335: kolumny `is_component`/`component_type`/`created_by` na `game_config_items`; 20 komponentów (14 nowych Kresy, `created_by='seed'`) — kły/skóry/rudy/esencje/zioła; wpięcie do loot tierowego + tematycznie per-wróg (wilk→kieł/skóra, pająk→gruczoł, szkielet→pył); **zwierzęta dropią komponenty zamiast złota** (loot_wolf/spider/bear/rat gold=0); ŻAR ekwipunek badge 🧩 + sekcja Komponenty; Smart Entry pola component. 2 skrypty idempotentne; pytest 10/10; wolf 30 rzutów → komponenty, gold=0. Wymagało S7 (#1333). review+needs-testing.
- **#1333 BL-B1 (Krok 7 / bramka S7)** — loot tierowy: drop wroga = **unia** tabeli per-wróg (unikaty) + wspólnej tabeli tierowej (`loot_tier_weak/standard/elite/boss`), deduplikacja po kluczu. Migracja idempotentna wycięła 52 generyki z 79 tabel per-wróg → seed 259→235 wpisów. `loot_tier` bywa zaśmiecony słowami loch-tierów → fallback na enum `tier`. 6/6 pytest, realny drop na Demo. Wymagało S6 (#1345 SMOKE-A pool-widen, zaliczone). review+needs-testing.
- Wcześniej: #1345 S6 (pool-widen), #1332 rangi wroga, #1331 Power Score, #1330/#1329 admin/anti-repeat.

**Audyt kampanii #99791 (A–D) — domknięty:**
- #775 — zapłata „mieszek z monetami" dawała 0 zł → parser grant_item→grant_gold (łamało ekonomię).
- #776 — questy dostawy/wymiany nie domykały się → `[QUEST_COMPLETE]` flipuje status.
- #755 — tagi mechaniczne (QUEST_SUGGEST itp.) wyciekały do narracji na mobile → front wycina tagi.
- #777 — zakładki Stan/Decyzje/Zdarzenia puste dla kampanii narracyjnych → emisja game_events.
- #779 — nowa zakładka 🎯 Questy+XP w monitorze kampanii.
- #780 — atak z zaskoczenia + ogólna bramka intencji po zdobyciu przewagi.

**Bugi gameplay / loch:**
- #766 — sklep otwierał się na zwykłe deklaracje (skUPiam/przygLADam) → regex granice słów.
- #740 — podwójna narracja wstępna przy wejściu do lochu → usunięty dublujący room_narrative.
- #767 — KRYTYCZNY: granie bohaterem przejmowało cudzą aktywną kampanię (korupcja danych) → guard.
- #743 — crash przy zakładaniu rękawic → slot `hands`.
- #759/#722/#721/#745 — bugi grafu lochu i zagadek (boss osiągalny za wcześnie, zagadki).
- **#756** — duplikacja questów co turę → zweryfikowane Playwright 2026-06-19 ✅.
- **#742** — sklep w lochu (guard dungeon-mode) + odświeżenie ekwipunku po buy/sell → TDD 4/4 + Playwright 3/3 + visual test 2026-06-19 ✅.

---

## ⚠️ UWAŻAJ (pułapki / kruche miejsca)

- **#516 BLOCKED** — smoke P1 wywala się na braku tabeli `character_rentals` (migracja F13). Trzeba najpierw odblokować migracją.
- **Backend = obraz Dockera.** `docker compose restart` NIE łapie zmian Pythona — zawsze `--build` (patrz CLAUDE.md).
- **Piloty lochów ruiny/zamek niegrane end-to-end** — content-complete ale bez pełnego przejścia; #733/#734 przeniesione do nowego lochu katakumby_mroku (#738).
- **PROD (.62 / main)** — nic tam nie wchodzi bez Twojego wyraźnego „tak". DEV (.61 / develop) = auto-commit.

---

## 📌 Jak czytać resztę
- **Plan** (GitHub Issues + Milestones, zakładka w pluginie) = **jedyne źródło zadań**. Milestone = faza. ← tu bierzesz pracę.
- **`notes.md`** (góra) = ściąga komend + „jak pracujemy"; (niżej) archiwum faz + proza/decyzje. NIE lista zadań.
- **`game_mechanics.md`** — spec mechanik (jak gra MA działać).
- GitHub Issue — pełna analiza każdego zadania (root cause + fix + acceptance + komentarze).
