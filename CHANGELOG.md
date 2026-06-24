# Changelog — AI-GM

Format: `vX.Y.Z — YYYY-MM-DD — opis`

---

## v1.5.6 — 2026-06-24 — Czar AoE maga + panel wizytówki + poprawki walki i lochów

Seria poprawek i dwóch nowych funkcji po v1.5.4: mąg dostaje czar obszarowy w starterze, administracja — prosty panel edycji wizytówki, a walka i lochy zbierają kilka gryzących bugów (wyścig animacji kości, pętla śmierci po wskrzeszeniu, widoczność kart walki).

### Added

**B11b — czar `spark_burst` (AoE tier 1) w starterze maga (#983)**
- Mąg startuje teraz z `spark_burst` — czar ataku obszarowego pierwszego tieru, dodany do startowego zestawu zaklęć.

**W15 — panel edycji wizytówki w adminie (#920)**
- Nowy panel CMS-lite w sekcji Świat → Wizytówka: edycja treści strony showcase bez potrzeby deployu.

### Fixed

- **#967** (uzupełnienie): dodatkowy guard CSS `body.combat-active !important` — header nie ucieka przy scrollu nawet w edge-case'ach po zmianie rozmiaru okna.
- **#734**: wejście do walki w lochu używa teraz `pollCombatState` zamiast przestarzałego `loadCombatState` — spójne z resztą flow walki.
- **#982**: fallback na lokację-rodzica w `_get_location_npcs` — NPC przypisane do pod-lokacji widoczne w głównej lokacji.
- **#984**: guard `_diceAnimationActive` w `pollCombatState` — eliminuje wyścig gdzie poll nadpisywał animację kości.
- **#985**: po wskrzeszeniu aktywna walka jest kończona — zapobiega nieskończonej pętli śmierci w turze wroga.
- **#986**: karta walki poprawnie wyświetla reakcję `take` zamiast pustego stanu.

---

## v1.5.4 — 2026-06-24 — Regeneracja planu GM + kompaktowy interfejs walki i przygody + dopięcie multiplayera + historia kampanii

Duża porcja dopracowania interfejsu gracza i mechaniki: GM może teraz odbudować zepsuty plan kampanii jednym przyciskiem, walka i pasek przygody dostały kompaktowy, czytelny układ, multiplayer został domknięty i przetestowany end-to-end, a stare kampanie da się zarchiwizować i przeglądać.

### Added

**Regeneracja planu GM — ratunek dla „uproszczonych" planów (#966, #968)**
- W panelu admina (monitor kampanii → zakładka „Plan GM") pojawił się przycisk **„Wygeneruj plan na nowo"**. Działa nawet gdy kampania w ogóle nie ma planu (pusty stan), nie tylko gdy plan jest zepsuty.
- API zwraca teraz status `plan_degraded` — system rozpoznaje, kiedy plan kampanii jest „uproszczony" (słaby model na PROD nie potrafił wygenerować pełnego planu w JSON) i sygnalizuje to w panelu.
- Regeneracja jest **świadoma historii** (`history-aware`): nowy plan kontynuuje dotychczasową rozgrywkę zamiast zaczynać kampanię od zera — uwzględnia to, co już się wydarzyło.

**Archiwum kampanii — podgląd zakończonych przygód (#900)**
- Zakończone kampanie można zarchiwizować; pojawia się osobna sekcja „Historia" z podglądem przebiegu.
- Przeglądarka historii (read-only) — nakładka z turami archiwalnej kampanii, bez ryzyka edycji.
- Przed przepisaniem bohatera do nowej kampanii pojawia się **modal potwierdzenia** (żeby nie zgubić starej przygody przez przypadek).

**Wczytywanie mapy świata z kanonu (#958)**
- Nowy przycisk **„Wczytaj mapę (z kanonu)"** + endpoint — admin może odtworzyć mapę Kresów z zatwierdzonego pliku-źródła, nie tylko zapisać.

### Changed / UI

**Kompaktowy banner walki — Wariant D (#967)**
- Nowy układ paska walki: jedna linia na uczestnika z **wbudowanym paskiem HP** (inline) — zwarcie informacji, mniej zajętego ekranu.
- Naprawiono znikanie górnej belki: w trakcie walki pasek przygody **nie chowa się** przy przewijaniu (górna belka już nie „ucieka").

**Kompaktowy pasek przygody (#952)**
- Pasek przygody zwinięty do **jednego rzędu**: menu pod ikoną ☰, scalony HUD lochu (pora dnia + godzina jako jeden chip), usunięte zbędne ikony mapa/widok.
- Naprawione auto-ukrywanie: nie chowa się przy przewijaniu programowym, reaguje na tap (tap-to-reveal), belka rośnie przy otwarciu menu.

**Drobne poprawki interfejsu gracza**
- #965: usunięto 4 nieaktualne funkcje deweloperskie/testowe z zakładki Ustawienia gracza.
- #953: rozwijanie tury — zamiana `webkit-line-clamp` na `max-height` (niezawodne rozwijanie długich tur).
- #951: przesuwanie zakładek karty postaci — dynamiczne rozpoznawanie widocznych zakładek zamiast zepsutej stałej kolejności.
- #897: spójny zestaw ikon SVG w dolnej nawigacji (zamiast emoji).
- #896: koniec mignięcia tła na ekranie logowania (FOUC) — tło wczytywane z localStorage.
- #899: przycisk „wstecz" na ekranie listy kampanii.
- #950: czat drużyny — trwały stan przyklejenia, przeciąganie i minimalizacja do ikony.
- #901: Księga Zasad otwiera się w nowej karcie zamiast nakładki iframe.
- #955: trwały zapis flagi „tester" (`is_tester`) przez panel admina.

### Fixed — Multiplayer (domknięcie FAZY 5)

- #961: `POST /combat/start` w kampanii MP trafia teraz do silnika walki multiplayer (`start_mp_combat`).
- #962: akcja wskrzeszenia uruchamia pętlę auto-rozstrzygania tur przeciwników w walce MP.
- #963: w czacie drużyny nadawca „szeptu" jest normalizowany do nazwy postaci (zamiast loginu).
- #959: po narracji otwierającej automatycznie otwiera się kolejna runda zbierania akcji (`done → collecting`).
- #954: przyciski usuń/opuść na kartach lobby i aktywnej gry MP.
- #957: D-pad w lochu — chwytanie wskaźnika dopiero przy przeciąganiu, nie przy zwykłym tapnięciu.

### World / Balans

- #933: rejestracja typów heksów Kresów (`hex_types`) + powiązanie osad z `location_key`.
- #824 (LB5): skalowanie **liczby** przeciwników wg wielkości drużyny (a nie ich poziomu/siły).

### Wizytówka (showcase)
- Dedykowana sekcja **Multiplayer („Graj razem")** + link w nawigacji.
- Aktualizacja treści o v1.5.3 (lobby MP end-to-end, trwała mapa świata, reroll).

### Testy / infra (dev-only, bez wpływu na grę)
- Nowe skille do testów grywalności: `/game-smoke-pw`, `/game-smoke-dungeon-pw`, `/game-smoke-mp-pw` (warianty przez prawdziwe UI Playwright) + nowy `/test-inreview` (masowy runner issue z etykietą `review`).
- Odbudowa harnessu testowego multiplayera: pytest GREEN + Playwright 3/3, weryfikacja kompletu zadań FAZY 5.
- Masowy przegląd issue „in-review": **40/40** FAZA B+L+MP-G zamknięte, skan 65 issue (55 zamknięte), partie FIX-B/C/D (7/7, 9/9, 2/2) zweryfikowane i zamknięte.
- Poprawki schematu testowej bazy (kolumny z późniejszych migracji: `quiet_start`/`quiet_end`/`team_tz` itd.).
- Dokumentacja w `notes.md`: sekcja testowania multiplayera (3 warstwy) + opis skilli smoke.

---

## v1.5.3 — 2026-06-23 — Multiplayer lobby działa end-to-end (GF7) + trwała mapa świata + reroll 100/350/700

### Added

**Trwała mapa Kresów — kanon w pliku (#933-related)**
- `docs/world/world_map_seed.json` = kanoniczne źródło mapy; DB `world_hexes` (map_level=0) to tylko cache
- Przycisk admin „Zapisz mapę (kanon)" → endpoint `POST /api/admin/world/snapshot-map` → commit pliku; tylko zatwierdzony snapshot przeżywa wipe DB
- `scripts/seed_world_map.py` (idempotentny) + `scripts/snapshot_world_map.py`; auto-seed na końcu `deploy_dev.sh`
- Ochrona: agenty/migracje nie ruszają `world_hexes` (map_level=0) bez jawnej zgody

### Fixed

**Multiplayer UI — lobby i czat działają end-to-end (GF7, #927, #932–#939)**
- #934: kafelek „Multiplayer" na ekranie kampanii — wejście do lobby widoczne dla gracza
- #935: `openMultiplayerLobby()` używał złego klucza ekranu `'create-lobby-screen'` (powinno być `'create-lobby'`) — lobby nie otwierało się wcale
- #932: `create_lobby` INSERT pomijał `model_id` (NOT NULL) → 500; domyślna wartość `'default'`
- #937: brak tabeli `campaign_invites` w `RAW_MIGRATIONS` → 500 przy starcie serwera
- #938: brak tabeli `party_messages` + kolumna `whisper_to` + jawny `created_at` w INSERT
- #939: HTML czatu drużyny + aktywacja MP UI dla non-spectator przy dołączeniu do kampanii
- #949: przycisk wysyłania na mobile wychodził poza kontener (`.composer__input` bez `min-width:0`)

**Reroll statystyk — koszty przywrócone do 100 / 350 / 700 (#943)**
- Decyzja Piotra (wariant A): reroll tańszy od apply → koszty 100/350/700 (poprzednia wersja błędnie podwoiła na 200/650/1500)
- Tabela w `game_mechanics.md` zaktualizowana; testy zsynchronizowane

### Tests / infra
- #942: migracja fixtures do `_fixtures_schema` — 8 paczek (shop, spells AOE, combat, loot, dungeon boss, admin cheat, faza 8)
- #941: guard przed wyciekiem lokacji testowych do generacji świata (prefix `test_` + sufiks `time.time()`)
- #930: izolacja stanu modułu `llm_service` w testach (autouse fixture)
- #927: E2E Playwright dla GF7 — weryfikacja lobby HTTP 200 + czat drużyny

---

## v1.5.2 — 2026-06-22 — Multiplayer FAZA 5 dokończona (G7–G31) + czary maga B14–B17 (siatka 26→34) + interaktywna Księga Zasad + pathfinding lochów

### Added

**Multiplayer — FAZA 5 dokończona, runy G7–G31 (#791–#813, #784)**
- G16 (#784): `character_campaign_state` — izolacja HP/mana per-kampania (bohater w wielu MP naraz)
- G7 (#791): sekwencyjny silnik walki dla multiplayer
- G8 (#792): rzuty dwustopniowe w rundzie MP (planer → kod → narrator)
- G9 (#793): timer walki 2 min + push „Twoja kolej" per tura
- G17 (#794): powalenie zamiast śmierci w walce MP
- G10 (#795): loot per-gracz z filtrem klasy + złoto dzielone równo
- G18 (#796): warstwowe podsumowania rund MP (layer 0/1/2)
- G11 (#797): catch-up po powrocie (missed rounds + reset nieobecności)
- G12 (#798): spóźnialscy — start z niepełnym składem + narracyjne wprowadzenie
- G13 (#799): kick → bohater do `idle` z zachowaniem XP/złota/ekwipunku
- G19 (#800): widzowie (spectators) — backend + policy/mute/mute routes
- G30 (#801): twardość rund — WAL + idempotencja + state-machine + retry + `force_sweep`
- G21 (#802): heartbeat `last_seen` + flaga online + push „Drużyna w komplecie"
- G22 (#803): drabina nieobecności — autopilot opt-in + auto-handoff hosta
- G23 (#804): pętla zaangażowania — wyważone haki + away-recap dla wracających
- G24 (#805): blokada edycji po zamknięciu rundy + `withdraw_action`
- G25 (#806): onboarding-podsumowanie dla późnych dołączeń do aktywnej kampanii
- G26 (#807): skalowanie poziomu drużyny (max-1) + catch-up XP ×1.5
- G27 (#808): cicha pora drużyny (zawieszenie sweepu + wyciszenie pushy)
- G28 (#809): reguły spójności głosu narratora w prompt systemowym MP
- G29 (#810): ochrona przed prompt-injection w akcjach graczy MP
- G31 (#811): metryka Prometheus `mp_round_completed_total` (retencja rund)
- G15 (#813): scentralizowane flagi balansu MP (`mp_balance.py`)

**Czary maga — system B (#820–#823, #868) — siatka czarów 26 → 34**
- B14 (#820): czary na sojusznika — heal/tarcza single-ally + warianty `group_*`/`mass_*`
- B15 (#821): summony jako kombatant-towarzysz
- B16 (#822): system reakcji czarów — `mirror_image`/`blink`/`globe_invulnerability`
- B17 (#823): czary kontroli umysłu — `charm_person` + `mass_fear` (D3: INT)

**Interaktywna Księga Zasad `/rules/` (#868)**
- Rozdziały + podstrony + edycja z poziomu admina; konwencja „aktualizuj /rules/ w tym samym PR" przy zmianach reguł gracza

**Lochy**
- #869: mapa lochu — klik w kafel = pathfinding (BFS) sekwencja ruchów; trasowanie do pierwszego kafla mgły (granicznego)

**Powiadomienia**
- N2 (#602): zunifikowany multichannel dispatcher `notify()`
- #593: diagnostyka push — ślad kroków na ekranie + endpoint gotowości serwera

### Fixed
- #734: mikstura w środku walki = akcja zużywająca turę
- #829: walka 3D dice — odtwarzanie box+container per rzut (mirror panelu admina)
- #728: dungeon cooldown=0 respektowany (brak nieaktualnego timera)
- #720: popup ujawnienia łupu bossa

---

## v1.5.1 — 2026-06-21 — Multiplayer FAZA 5 (G1–G6) + zaproszenia przez link (#866) + dopięcie walki (dual-wield/grapple/akcje) + fixy lochów

### Added

**Multiplayer — FAZA 5, runy G1–G6 (#785–#790)**
- G1 (#785): wymuszanie timera rund — sweep wygasłych rund + migracje DB
- G2 (#786): licznik ostrzeżeń o nieobecności gracza
- G3 (#787): ręczny vote-to-kick w multiplayer
- G4 (#788): współdzielony world state dla rund MP
- G5 (#789): rozwiązywanie konfliktów wg kolejności inicjatywy
- G6 (#790): głosowanie drużyny nad ruchem po heksach

**Zaproszenia do kampanii MP przez link (#866)**
- `/?join=TOKEN` kieruje niezalogowanego na rejestrację (nie login) z notką o zaproszeniu
- `consumePendingJoin()` — token przeżywa w localStorage, konsumowany po logowaniu/weryfikacji email → auto-dołączenie do kampanii
- `APP_BASE_URL` ustawiony dla DEV i PROD — linki w mailach (invite/verify/reset) były `http:///` (pusty host)

**Walka — dopięcie systemów**
- #859: przycisk „Użyj mikstury/przedmiotu" w pasku akcji walki
- #858: bandaż = uniwersalne leczenie w walce (class-agnostic)
- #861: render dual-wield w UI walki — drugi cios off-hand + badge parowania
- #863: reguły off-hand equip — lekkie bronie either-hand + tarcze, blok dwuręcznych
- #864: ożywione pole `attacks_per_turn` — wróg N>1 atakuje N razy/turę
- #773: mechanika obezwładnienia (grapple) poza walką — bramka + kondycja „schwytany"
- #719: regression guards dla modala uniku (opposed dodge)

**Lochy**
- #741: D-pad lochu przeciągany + zapamiętana pozycja + środek ⊕ otwiera mapę

### Fixed
- #865: rozwijanie kluczy riddle przy wejściu do lochu (symetria z resume)
- #860: blokada short/long rest podczas aktywnej walki
- #746: polskie etykiety łupu w modalu walki + komunikat o złocie

---

## v1.5.0 — 2026-06-20 — Admin Panel Mobile (M0–M5) + redesign obrony walki + dual-wield/amunicja + FAZA LB (lochy onboarding) + audyt kampanii

### Added

**Redesign modelu obrony walki (#826) — zmiana zablokowanej mechaniki (za zgodą)**
- Jeden rzut obronny na trafienie (koniec double jeopardy). Pancerz (`ac_base`/AC) = **redukcja obrażeń**, nie próg trafienia: `armor = max(0, ac_base − 10)`, min 1 dmg/trafienie, Nat 20 ignoruje pancerz
- Margines ataku → obrażenia: `+1 dmg` za każde pełne 5 pkt nadwyżki; Nat 20 ×2 osobno. Symetryczny gracz↔wróg
- Helpery `apply_defense_model` / `compute_enemy_attack_hit` w `combat_service.py`; wartości startowe strojone w Sandboxie (`MARGIN_DAMAGE_STEP`, `MARGIN_DAMAGE_BONUS`, `ARMOR_REDUCTION_OFFSET`). Supersedes #753, pokrywa #744
- Karta ataku wroga pokazuje pasywny unik (d20+ZRC) zamiast vs AC (#828); kalkulacja redukcji pancerza widoczna w karcie obrażeń (#851, #853)

**Walka — nowe systemy**
- **Dual-wield (#598)**: mechanika walki dwoma broniami + dokumentacja CZĘŚĆ AB
- **Amunicja + regeneracja po walce (#764, #765)**: system amunicji + post-combat recovery
- **Atak z zaskoczenia (#780)**: sneak attack + bramka intencji po zdobyciu przewagi
- **Nowoczesne kości 3D (#829)**: `@3d-dice/dice-box-threejs` dla rzutów walki + fallback 2D (Stage 2 damage); modal uniku wroga w rzutach (#719), reveal lootu bossa (#720)
- **Przełącznik narracji walki**: gracz + globalny switch admina; konfigurator stylu kości w adminie z live-preview (#850)
- Combat Sandbox w `/admin/` wywołuje prawdziwy silnik walki (#727); serwer domyka turę po ataku gracza (#848)

**Admin Panel Mobile (milestone #9, fazy M0–M5)** — pełna responsywność @390px
- M0: guard layout-viewport (#830), szuflada nawigacji hamburger + 18 sekcji (#831), card-view tabel + scroll/sticky hybryda (#832), formularze 2→1-col + touch-targety 44px (#833), hex mapa SVG scaling + edit (#834)
- M1: scroll zakładek + card-view dla Overview/Push (#835), Campaigns modal (#836), Zgłoszenia (#837), Gracze (#838), System (#839)
- M2–M4: card-view tabel — Zawartość (#854), Świat (#855), Mechaniki (#856), Lochy (#843), Kuźnia (#844)
- M5: touch-targety ≥44px (#845), pełna obsługa dotykowa hex mapy — pinch-zoom/pan/tap (#846); spec milestone w `docs`

**FAZA LB — lochy onboarding + głębsze + balans solo lvl1**
- Rest-on-cleared-tile (#735): realne leczenie na oczyszczonym kafelku + flaga heal%/charges per loch (backend + frontend pill/przycisk)
- Soft-init: bohater pierwszy w turn_order w 1. walce runu (#736)
- Lochy seedowe: `krypta_probna` onboarding (#737, tile_count=3, boss ~18HP, rest 100%), `katakumby_mroku` głębszy (#738, min_level=3), boss `undead_champion`
- Egzekwowanie `min_level` lochów — 403 + lock w pickerze (#739)
- Balans solo lvl1: ease-in budżetu pierwszych komnat (#733), sustain drop na zwycięstwie (#729, #732), watchdog nakładki kości (#730), honor `cooldown_hours=0` (#269e2a8)

**FAZA L17/L20 — kontent lochów + portrety**
- Nowe kategorie kafli (60 tiles każda): jaskinie, goblińskie tunele (#723), ruiny twierdzy, nawiedzony zamek; per-category base_prompt + generic seeder; piloty `jaskinia_probna`, `goblin_probna`
- L20: persystencja + display portretów wrogów/NPC w walce gracza (modal + init-chip) (#692, #724); portrety nieumarłych krypty (#725)
- 91 nowych kafli (aigm_00571–00660) + 642 kafle batch + sync archmap overlay

**Monitor kampanii + instrumentacja (live-debug)**
- Zakładki w monitorze: 🎯 Questy+XP (#779), 🗓 Zdarzenia game_events per-kampania (#781), rejestr `dice_rolls` + API + MCP tool (#754)
- Instrumentacja narracyjna: `game_events` + `turn_decisions` zapisywane (#777); czytniki MCP + `state_changes` + confidence (#760, #761, #762)
- `QUEST_COMPLETE` flipuje status questa + przyznaje XP (#776); kontrakt time-skip LLM — `time_advance_minutes`/`advance_to_time_of_day` (#758)

**Kontent i admin**
- Builder efektu on-use konsumabli — `damage_enemy` + `apply_condition(target=enemy)` (#771)
- Generacja obrazów NPC (parytet z wrogami: batch, config, galeria, persystencja promptu); batch portretów wrogów
- Admin Bohaterowie: katalog zbroi + usuwanie bohatera; raport bug z załącznikiem screenshot; przeciągalny FAB 🐞 (#668)

**Tooling / proces**
- `mass-implement` v2 — config-driven, drop-in, tryb LIST + numeracja fix_list (1..n)
- Auto-sync `fix_list.md` z kolumną TO DO board; przejście systemu zadań na GitHub issues+milestones (Plan board)
- Skill `game-smoke` (full-mode playtest); STATUS.md/KOMENDY.md captain-log; ledger `frontend_design.md` F-NN dla zmian w `frontend/front/`

### Fixed

**Combat-gate (wstrzykiwanie walki przez LLM)**
- Ujednolicona bramka startu walki: negacja + obecność w scenie + przyjazny NPC + reverse-inject (#535, #596, #534, #520); source-aware target validation (#774). 30/30 testów

**Loch**
- Backtrack z komnaty zagadki nie ustawia `cleared=True` (#847); panel zagadki widoczny po rozwiązaniu (#745); resolve string-key zagadki w GET dungeon-run (#721); zagadki blokują ruch naprzód (#722)
- Boss zawsze w najgłębszej komnacie (#759); minimapa odwrócona oś Y N=góra (#718); pojedyncza narracja wejścia (#740); `scene_enemies` czyszczone przy zmianie lokacji non-combat (#825)
- Backend re-linkuje bohatera po wyjściu z lochu — kampania nie znika z listy (#752); relink nie porywa cudzej kampanii (#767); abandon z modala resume czyści run + cooldown właściwemu bohaterowi (#699)

**Sklep / ekonomia**
- Blokada sklepu w trybie lochu + refresh ekwipunku po kupnie/sprzedaży (#742); posiłek w karczmie 2GP zamiast 5GP nocleg (#751); regex trade-intent z granicami słów (#766); akceptacja `item_type=gear` w buy handler (#783); pieniężny `grant_item` (mieszek monet) → `grant_gold` (#775)

**Ekwipunek / przedmioty**
- Inventory pokazuje nazwę narracyjnego itemu zamiast klucza (#757); podział sekcji wg używalności `can_use` (#770); slot `hands` dla rękawic (#743); zbroja admin-added widoczna w doll (#778); Rogue dostaje startowe itemy (#749)
- Kreator skilli — budżet netto, obniżenie zwraca punkt (#747)

**Kampania / postać**
- Twardy guard przejęcia cudzej kampanii (same-user też) (#767, #49476d7); wskrzeszenie reaktywuje zakończoną kampanię (#647); dedup questów wg podobieństwa celu + inject aktywnych questów do LLM (#756)
- Skill keyword: `udaję` (idiom ruchu) false-matchował Oszustwo → Stealth (#763)

**Lokacja**
- Preferuj canonical lokacje w fuzzy match dla `move` (#522); `**markdown**` zamiast surowego `<strong>` w prozie podróży (#643); blok ŚWIAT nie nadpisuje sceny wnętrza sub-lokacji (#750); desync tury walki UI↔backend (#701, #700)

**Mobile / inne**
- Streaming narration nie wycieka tagów mechaniki (#755); spell heal OOC pokazuje animację kości (#653, #90fe15f); SmartEntry obsługuje spells + clear `_loaded` na re-init (#852)

### Assets
- 91 kafli lochów (aigm_00571–00660) + 642 kafle batch (2026-06-17) + portrety wrogów/NPC

### Removed
- Trial graphify (werdykt SKIP — agent nawiguje przez Bash grep, tool-hook nigdy nie odpala)

---

## v1.4.0 — 2026-06-16 — FAZA L (lochy kafelkowe) + FAZA O (observability + archmap) + fixy walki i lokacji

### Added

**FAZA L — Lochy kafelkowe (L1–L16)**
- Silnik lochu kafelkowego: generowanie proceduralnych map z kafli PNG, tryb endless (go_deeper), checkpoint krypty, cooldowny, skalowanie wrogów (#684–#698)
- 40+ kafli krypty: kategoria nieumarłych (L14, 20 kafli 768px), kafle zaślepki N/S/E/W (L16), kafle krypty 26–29 (caps_complete)
- Generator domyka wszystkie narysowane drzwi na styku segmentów; endless styk tylko na drzwiach zapasowych z retry (#697, #698)
- Dungeon UI: loch-scoped narration, osobny widok gracza podczas lochu (#687–#689)
- Skrypty: batch generacja 768px, seed/verify, kompozytor kafli (L15)

**FAZA O — Observability + Archmap (O1–O10)**
- Tabele `game_events` / `llm_call_log` z indeksami; hooki w 4 serwisach (turns, combat, LLM, dungeon) (#702–#704)
- Panel admina **Statystyki i Logi**: 4 zakładki (eventy, LLM calls, KPI, logi), 5 endpointów analytics (#705)
- Serwer MCP AI-GM: narzędzia `search_events`, `get_architecture_map`, `get_campaign_summary` + docker-compose + testy (#706, #710)
- **Archmap** — interaktywna mapa architektury kodu: 5 map (combat, turn-flow, admin, world, dungeons), heat-map live z game_events+llm_call_log, node-map.json, węzeł MCP (#708, #709, #711)
- Archmap UX: TTL cache 10min, przycisk Reset układu, embed treści issues w overlay (#711)
- Cron refresh archmap na .61 o 03:30 (#706)

**Walka i UX**
- Pakiet 9 bugfixów walki: #660–#669 (trafienia, kondycje, animacje, skrót narracji maga)

### Fixed

**Lokacja startowa — eliminacja sentinela "Start"**
- `characters.location = "Start"` (reset-progress) tworzył śmieciowe lokacje `Start {campaign_id}` w `game_locations` (#715)
- `resolve_starting_hex`: wykrywa sentinel "Start"/"Start N" → losuje prawdziwą canonical lokację
- `finalize_sheet`: ta sama detekcja → LLM dostaje spójną prawdziwą lokację
- `turns.py`: lazy opening używa `session.current_location`, nie NULL `char.location`
- Kampania startuje losowo 50% osada / 50% dzikie tereny zamiast zawsze wilderness
- DB cleanup: 113 osieroconych lokacji Start N usuniętych

**Admin panel i inne**
- Plakietka środowiska (DEV/PROD) z hostname zamiast hardcoded
- Zakładki Statystyki: `display:block` naprawia ukryte panele po kliknięciu
- `item` dodany do whitelist endpointu review — `Unknown entity type: item`
- Desync tury walki UI ↔ backend naprawiony (#700)
- `get_campaign_summary` MCP: poprawiona nazwa tabeli

### Assets
- Dungeon tiles 26–29 (FLUX-generated, 768px, format krypty)

---

## v1.3.2 — 2026-06-15 — FAZA S/B/SF/HI: silnik skilli i stanów, balans klas, feedback walki, Inspektor Bohatera

### Added
- **FAZA S — silnik Skilli i Stanów (S1–S19)**: backend silnika skilli/stanów (+ ogon FAZY U); pełny suite pytest real-engine dla S2–S19 oraz Playwright e2e (regression) dla S8–S19 i #582–#601; domknięcie fazy S20 playtest + infra
- **FAZA S/U frontend**: karty rzutu z marginesem sukcesu i przerzutem, kondycje w Sandboxie, targowanie w sklepie, panele admin world/forge/map
- **FAZA B (Blok 1+2) — balans 3 klas + czary maga Faza 1 (B1–B12)**: przebalansowanie wojownika/maga/łotrzyka; pierwsza fala czarów maga; łotrzyk dostaje bonus DEX+2/LCK+1 zamiast bonusów maga (#624, B1)
- **FAZA SF — warstwy feedbacku walki (SF5–SF9)**: kamień #639, krytyki #641; walka mobilna — pasek 3-filarowy + bottom sheet akcji (#619/#620, SF1/SF2)
- **FAZA HI — Inspektor Bohatera (7/7)**:
  - HI1 — backend Inspektora: odczyt arkusza + 3 luki edycji + audyt + guard (#623)
  - HI2/HI3 — sekcja Bohaterowie w adminie + zakładka Arkusz w Inspektorze (#625/#626)
  - HI4 — equip / zaklęcia / questy z poziomu Inspektora (backend, guard+audyt) (#627)
  - frontend Inspektora Bohatera (#627/#628/#629/#630) + pytest kontraktów i Playwright
  - dokumentacja: notes FAZA HI + game_mechanics CZĘŚĆ AL
- **Panel wskrzeszania (admin)**: tryby kosztu wskrzeszenia zamiast sztywnego fixed/percent/unlimited
- **#594 — onboarding + Wiedza**: unifikacja kart onboardingu i `knowledge_book` przez kolumnę `kind`; niezależne flagi widoczności (jeden wpis, obie powierzchnie); audyt + refresh treści Wiedzy (`_refresh_knowledge_content`)
- Prompty startowe FAZ + design zaklęć (dokumentacja statusów SF/HI/B/skip-turn)

### Changed
- **SF10** — reaktywny modal uniku/bloku zamiast pre-deklaracji (#633)
- **#640** — narracja walki skrócona do 2–3 zdań (scoped do aktywnej walki)
- **#621** — kondycje `skip_turn` (slowed/stunned) pomijają turę w walce

### Fixed
- **Crash startu PROD (B8a)** — migracja `v2-spells-faza-b-b8-starter-backfill` (dosiew startowych czarów scholarom) biegła PRZED `v2-spells-faza-b-seed`, więc INSERT do `character_spells` odwoływał się do jeszcze niezaseedowanych czarów (`fire_bolt`/`minor_heal`/`ward_of_iron`/`detect_magic`) → `FOREIGN KEY constraint failed` → abort startupu → deploy fail. DEV nie wykrył (0 scholarów); PROD ma 10. Naprawiono kolejność: seed czarów przed backfillem postaci. Zweryfikowano na kopii bazy PROD (40 czarów nadanych, 4 zaseedowane)
- **#618** — spójne bazowe HP: kreator pokazuje prawdziwe wartości, dodano klucz `rogue`
- **#617** — kreator postaci: przywrócona animacja rzutu + podłączone nowe skille (FAZA S)
- **#616** — deterministyczny tor hazardu: stawka rusza złotem w swobodnej grze
- **admin** — utworzenie brakujących tabel `bug_reports`/`push`/`voice`/`ui_texts` + klucz presetu LLM

---

## v1.3.1 — 2026-06-14 — FAZA U: Blok 4 ekonomia/UX + unifikacja przedmiotów + usability (U11–U26)

### Added
- **U11 — Unifikacja przedmiotów → `game_items`** (#555/556/557/558): jedna tabela zamiast 3 (weapons/armor/items/consumables); migracja + backfill 140 rekordów; przełączenie odczytu serwisów; dual-write (create/update/delete, smart_entry, approve, forge, import katalogu)
- **U13 — Content pipeline** (#561): `seed_lint_service` (świeża baza → schemat → seedy 01–15 → lint U12+U10); CLI host+kontener; krok w `deploy_dev.sh`; `docs/CONTENT_PIPELINE.md`
- **U16 — Cost preview + ekrany gracza** (#564): modal sklepu (kup/sprzedaj, saldo po, nadpodaż), pasek trwałości w ekwipunku/karcie/slotach, ostrzeżenie ≤20% w HUD walki, naprawa + kuźnia afiksów z podglądem kosztu; **aktywacja uśpionej trwałości #467** (inicjalizacja durability przy zdobyciu sprzętu + backfill)
- **U17 — Celebracja dropu afiksowego** (#565): karta po claimie dla broni/zbroi specjalnej — kolor rzadkości, afiksy, diff statów vs założony, przycisk Załóż
- **U18 — Dziennik gracza** (#570): Zadania / Wątki / Kronika; `journal_service` (questy + narrative_state + ukończone beaty, filtr sekretów GM)
- **U19 — Recap "Poprzednio…"** (#571): karta po >24h przerwy (summary + 2 ostatnie tury + aktywne questy), bez nowego calla LLM
- **U25 — Pity timer afiksów** (#575): 3 bossy bez afiksu → gwarancja T1+; 3 rerolle bez zmiany → inny afiks (liczniki w `affix_pity`, przeżywają restart)
- **U26 — Telemetria ekonomii** (#576): centralna `change_gold()` (mutacja + log atomowo) we wszystkich torach (shop/spend_gold/crafter/robbery/durability); kafelek "Ekonomia 7 dni" w admin Overview; `db_lint` gold-drift check
- Eksport książki kampanii (Bielik, #547); suite regresyjny pytest + Playwright dla #547, #560–#581 i zadań U12–U25

### Changed
- **U14 — Pełny reset bohatera** przy nowej kampanii (#562): conditions, rentale active→expired, pop flag sandbox; XP/złoto/ekwipunek/zaklęcia nietknięte
- **U15 — Widoczne rany wroga** (#563): etykieta tieru + kropka koloru na chipach inicjatywy; jedno źródło `WOUND_TIERS` w `wound_utils.py`
- **U20 — Onboarding** (#572): retarget karty death_save na pierwszy spadek HP<25%; 3 nowe karty (durability / napady / crafter); flaga `npcs.is_crafter`
- **U24 — Counterplay napadu** (#574): tura ostrzeżenia → rzut obronny d20+stat vs DC wg poziomu; próg biedy 50gp; limit 1/24h

### Fixed
- **Crash startu PROD (U11a)**: backfill `game_items` robił `int(rarity)`, ale legacy tabele PROD trzymają rzadkości słownie (common/rare/uncommon) → ValueError → startup abort → deploy fail. Dodano `_as_int()` + `_normalize_legacy_rarities()` (słowo→int w tabelach źródłowych przed backfillem; domyka też runtime loot/durability)
- **U12 — db_lint zahartowany** (#559→#560): dodana autoryzacja endpointu (była dziura), 4 brakujące checki, CLI w obrazie backendu
- Weryfikacja Bloku 4 (B4V): sklep zdejmuje/dolicza złoto z saldem, trwałość spada po walce, loot trafia do ekwipunku z `game_items`
- Issues #566–#569, #573, #578–#581 (combat roll block, generic enemy label, loot RNG, combat dice modal, `game_item_key`, text/move desync, shop default stock, clock sync, success margin)

---

## v1.3.0 — 2026-06-13 — FAZA U: pancerz LLM, system hexów świata, effect schema lockdown

### Added

**Blok 9 — Świat: hex ↔ lokacje ↔ ruch (U28–U32, #540, #541, #544, #546, #548)**
- Placement engine: backend osadza lokacje z bazy przy odkryciu hexa (terrain_tags + placement)
- Blok [ŚWIAT] dla LLM: hex + lokacje z opisami + NPC + sąsiedzi + kandydaci z bazy
- Ruch mechaniczny: POST /travel (klik mapy = podróż, intent MOVE rozstrzygany przed LLM, anty-desync guard)
- Scena z bazy: ENTER_LOCATION ładuje scene_npcs/scene_enemies z przypisań; travel pills z prawdziwych danych

**Blok 3 — Pancerz na LLM: spójność narracja↔stan (U5–U9, #528, #530–#533)**
- Centralny parser tagów LLM + tabela llm_tag_errors (telemetria halucynacji)
- Uogólniony wzorzec odmowy (korekta narracji przy odrzuconym tagu) + SKILL_CHECK safety net + DC lock {8,12,16,20,24}
- Beat fallback (objective_type) + GM Plan hardening (retry + fallback, kampania startuje zawsze)

**U10 — Effect schema lockdown (#554)**
- backend/app/schemas/effect_schema.json jako pojedyncze źródło prawdy formatu effect_json
- Dodano LCK (7. statystyka) + cele pochodne (ac/attack_bonus/damage_bonus/initiative)
- scripts/effect_json_audit.py — audyt integralności (read-only, raport rekordów do ręcznej decyzji)

### Fixed

- Hotfixy FAZY U: scene_enemies clear po walce, quest persistence do character_quests (#523, #524)
- HF-3: Gotowa Kampania startuje z poprawnym GM Planem (#525)
- HF-5/6/7/8: XP hooks import, gate negation, COMBAT_START target validation, beat objective_type (#535, #536, #538, #539)
- character_rentals + campaign_known_npcs migracje; known-npcs V2 table (#516, #529)
- Session expiry czyści kontekst bohatera/kampanii; init nie nadpisuje loginu; fix race tła

---

## v1.2.7 — 2026-06-11 — Affix system, economy F1-F21, effect builder, SPEND_GOLD, bugfixy

### Added

**Affix System F1-F2b (#461–#462, #484)**
- F1: typowane Effect Objects w silniku walki (damage_bonus, heal_on_hit, ac_bonus, static_stat_modifier, apply_condition, narrative_only)
- F2: loot engine losuje afiksy per dungeon tier przy dropach wrogów
- F2b: loot_tier na game_config_enemies + roll afiksów dla dropów wrogów

**Affix Builder F3 (#463)**
- POST/PATCH/DELETE /api/admin/affixes — pełne CRUD
- Zakładka Afiksy w Admin → Zawartość z Effects Builder (wizualny row-builder)

**Effect JSON Builder (#485, #486)**
- Wizualny row-builder effect_json w modalu edycji broni/zbroi/przedmiotów (Admin → Zawartość)
- Inline builder w Forge → Szablony → modal entity (broń/przedmiot/mikstura)

**Gracz widzi afiksy (#487)**
- Modal szczegółów przedmiotu pokazuje sekcję AFIKSY (amber header) z nazwą + opisem efektu po polsku

**Economy sinks F4-F16 (#464–#476)**
- F4 SPEND_GOLD: tag w narracji → automatyczne odejmowanie złota za usługi NPC (gospoda, uzdrowiciel, kowal, stajnia…) + prompt systemowy + seed danych
- F5: Wskrzeszenie jako gold sink
- F6: crafter_service — apply/reroll/upgrade affiksu z API
- F7: durability_service — zużycie, kara do ataku, naprawa + hooki combatu
- F8: robbery_service — kradzież złota w spotkaniu + seed
- F9: dynamiczny ekwipunek sklepu filtrowany po lokacji + poziomie gracza
- F10: modyfikator CHA wpływa na ceny kupna (rabat/narzut)
- F11: ujednolicenie price_gp + wycena afiksów
- F12: anty-farmowa degresja cen sprzedaży + logowanie item_key
- F13/F14: sweep wygasłych wynajmów + usunięcie martwego kodu
- F15: balans walki — atak bandyty +3→+4
- F16: model analityczny ekonomii + skalibrowane sinki

**Advanced systems F17-F21 (#477–#481)**
- F17: hidden trait system (pula, przypisanie, ujawnienie + admin API)
- F18: nieliniowe progi XP konfigurowalne z Admina
- F19: globalne stany śmierci NPC (is_dead + propagacja)
- F20: mechaniczne efekty pory dnia (fazy + konfigurowalne bonusy)
- F21: World State history diff — compute_snapshot_diff + endpoint /diff

**Gracz — quest w kartcie postaci**
- Cel questu + nagroda widoczne w panelu Karty Postaci
- World State w adminie pokazuje aktywny quest

### Fixed
- #504: C10 QUEST_SUGGEST brakujący w ścieżce non-streaming + błędny import strip
- #472: anti_farm_service — bug kierunku delty (< 0 → > 0)

### Tests
- Playwright specs: #464 SPEND_GOLD, #466 crafter, #467 durability, #468 robbery
- pytest: test_issue464_spend_gold_prompt, run_llm_tag_compliance
- UX audit player frontend 2026-06-10

---

## v1.2.6 — 2026-06-10 — Lochy pełna treść, onboarding, Uczony zaklęcia, bugfixy

### Added

**Uczony — zaklęcia poza walką (#483)**
- `POST /api/campaigns/{id}/cast-spell` — endpoint dla nieofensywnych zaklęć poza walką
- `/czar [zaklęcie]` slash command z podpowiedziami (autocomplete z ikonami i kosztem many)
- Przyciski „Rzuć / Lecz / Użyj" w zakładce Zaklęcia — atak zablokowany poza walką
- Magiczne Światło (`magic_light`) — nowe zaklęcie narracyjne tier 1, koszt many 0; backfill do wszystkich istniejących Uczonych

**System lochów — Faza 3 pełna treść (E15–E22)**
- **E15** (#430) — Snapshot stanu świata (HP, EXP, gold, inventory, world_state) przy wejściu do lochu
- **E16** (#431) — Przywróć snapshot + restart runu od pokoju 1 przy śmierci w lochu
- **E17** (#432) — 5 tierów rzadkości łupu (Zwykły/szary → Legendarny/złoty), mapowanie difficulty→rarity; boss zawsze Epic+
- **E18** (#433) — Trudność i cooldown lochu edytowalne w panelu admina (Admin → Lochy)
- **E19** (#434) — Offline pipeline LLM Vision do generowania opisów kafelków lochu (Ollama + llava)
- **E19b** (#459) — Generator promptów AI dla kafelków (`ai-create` endpoint), podgląd + zapis do DB
- **E19c** (#460) — Redesign compositora kafelka: cienka ramka, płaskie markery drzwi, przycisk Generuj Opis
- **E21** (#436) — Klik hexu lochu na mapie świata → bezpośrednie otwarcie pickera lochów (bez dialogu podróży)
- **E22** (#437) — Wznowienie niedokończonego runu lochu: picker pokazuje „▶ Wznów ekspedycję" z numerem komnaty; **fix:** endpoint `active-run` pomijał wszystkie kampanie z powodu błędnego filtra `mode='dungeon'`

**System onboardingu (E23–E28)**
- **E23** (#438) — Tabela `seen_mechanics` per gracz + endpointy GET/POST mark-seen
- **E24** (#439) — Backend triggery kart onboardingowych przy pierwszym wystąpieniu 6 mechanik (rzut, walka, obrażenia, XP, złoto, test śmierci)
- **E25** (#440) — Nieblokujący overlay z kartą onboardingową; przycisk „Rozumiem" → mark-seen; karta wyświetla się tylko raz
- **E26** (#441) — Kodeks: biblioteka przeczytanych kart mechanik otwierana z nagłówka gry (ikona ksiązki), nawigacja strzałkami
- **E28** (#443) — Tutorial kampania „Moja Pierwsza Przygoda": modal dla nowego gracza z opcją Tak/Pomiń; `is_tutorial` flag w DB; kampania nie jest proponowana przy kolejnych kampaniach

**Panel admina**
- (#482) — Licznik oczekujących elementów (badge) na pozycji „Świat" w nawigacji; aktualizacja po zatwierdzeniu/odrzuceniu
- (#482) — Kolumna „Data utworzenia" w zakładce Oczekujące dla wrogów, NPC, broni i przedmiotów
- Sortowanie kolumn we wszystkich tabelach admina (klik nagłówka, ikona kierunku)

**Inne**
- **D3** (#378) — Kontekst pamięci NPC injektowany do LLM per tura; endpoint `GET /admin/campaigns/{id}/known-npcs`
- **E5** (#420) — Blokada martwego bohatera: `hero_blocked` flag; `GET /campaigns` i `POST /turns` zwracają 423 gdy bohater dead
- **E2** (#417) — Inline descriptions w kreatorze postaci zamiast duplikowanych tooltipów
- Animacje rzutów kośćmi w kreatorze — wartości statystyk „kręcą się", ikony kości migają przy wejściu na krok

### Fixed

- **#437** — `GET /api/dungeons/active-run` nigdy nie pasował do żadnej kampanii (filtr `mode='dungeon'`, wszystkie kampanie mają `mode='solo'`)
- **D10** (#385) — Reset motywu wizualnego przy wylogowaniu; selektor motywu w ekranie profilu gracza
- **#408** — Plan GM: sceny wyświetlane jako `<details open>` z pełną treścią; bieżąca scena pokazuje hooki (NPC/lokacje/przedmioty)
- **SB-2** (#456) — Synchronizacja `scene_enemies` i `player_conditions` do kolumn `world_state` w DB
- **SB-3/SB-4** (#457) — Pominięcie skanowania słów kluczowych; ponowne wyświetlanie istniejącego `SKILL_TEST_PENDING`
- **SB-5** (#458) — Auto-resolve skill testu gdy `committed_d20` jest już ustawiony
- Naprawiono sortowanie gwiazdek rzadkości — `data-sort-val` z wartością numeryczną zamiast HTML
- Inicjalizacja sortowania przez `MutationObserver` — wykrywa leniwie ładowane tabele
- `sqlite3.Row` konwertowane do dict w funkcjach logowania (eliminacja `AttributeError`)
- Montowanie `frontend/images/tiles/` do kontenera backendu (serwowanie wygenerowanych kafelków)
- Usunięto wymaganie drzwi przy zapisie kafelka (blokada save/image deadlock)

---

## v1.2.5 — 2026-06-09 — FADM strangler fig ukończony + E1–E14

### Added / Changed / Fixed
- **FADM strangler fig ukończony** — modularny admin shell `/admin/` zastępuje monolityczny admin3; 18 faz, 14 sekcji portowanych
- Kuźnia (Forge) portowana do `/admin/#forge` jako ES moduł (P14); admin3 wycofany z zerową funkcjonalnością (P15)
- Ekran logowania natywny w `/admin/` — `doLogin`/`doLogout`, token w localStorage (P13)
- **SSE heartbeat fix** — group-run Playwright nie zrywa SSE (`network error`) przy ~90s ciszy startu; natychmiastowy hello + keepalive co 15s (P16/P452)
- Admin3 wycofany — `/admin3/` → redirect 301 → `/admin/`; katalog `admin_panel_v3/` usunięty (P17)
- E1–E14: player HUD quest bar, creator tooltips, campaign end/death stats, story gravity, template workflow, generic encounters, level scaling

---

## v1.2.4 — 2026-06-08 — Admin panel modularny (FADM) + onboarding theme + D7–D10

### Added
- FADM (cała faza): nowy modularny panel admin `/admin/` — port wszystkich sekcji z monolitu admin3 (P0–P12): overview, mechanics, content, world, map, campaigns, dungeons, players, tools, system, invites, bug-reports, push, knowledge
- D10 #385: onboarding — wybór motywu wizualnego (dark_fantasy / classic), zapis per user w `game_mode_flags`, stosowany przy każdym logowaniu
- D9 #384: hub kampanii — 5 trybów z flagami dostępności (Nowa / Gotowa / Loch / Loch-kafelki / Multiplayer)
- D8 #383: ekran profilu gracza — edycja email, lista znajomych, ustawienia LLM Connect
- D7 #382: encountery generyczne, gate `safe_for_rest`, dwell decay, interwał config w admin
- FAB bug-report dla testerów w player UI (#405)

### Fixed
- Naracja skill_test injektuje lokację i last-turn context (#1214)
- Mapa świata generuje klastry Voronoi zamiast random hex-po-hex (#407)
- Bugged porty FADM — invites/email auth, bug-reports/push endpoints, Playwright scroll

---

## v1.2.3 — 2026-06-07 — Harness testów C1–C19 + panel Playwright w admin3

### Added
- Harness testów akceptacyjnych C1–C19 (pytest + Playwright), uruchamialny z admin3 → Narzędzia → 🎭 Playwright — każde zadanie jako osobny test
- Panel Playwright w admin3 odpala wszystkie suity (regression / acceptance / admin3) z UI; skan rekursywny + run po pliku lub grupie
- Smoke testy admin3 (dev-login + 14 sekcji bocznego menu)
- Regression Playwright dla #355 (STORY_STALE) i #390 (zegar in-game)

### Fixed
- #394 — przycisk „Atakuj" pozostawał aktywny po wygranej walce
- #395 — aktywny preset LLM jako jedyne źródło prawdy (brak cichego fallbacku do Ollama/gemma)
- #391 — TRAVEL_HINT gdy brak odkrytych hexów
- #390 — zegar in-game tyka (advance_clock obsługuje `minutes=` + akumulacja)
- reset_test_env: czyści `model_id` kampanii + zapewnia wiersz `game_sessions`

---

## v1.2.2 — 2026-06-07 — Faza 1 Core Loop (C9-C19)

### Added
- **C17** — Inventory context injection — LLM dostaje faktyczny ekwipunek postaci per turę (koniec halucynacji "straciłeś wszystko")
- **C18** — Nowe kampanie startują na wcześniej odkrytych hexach (nie na pustkowiu)
- **C19** — Bohater wchodzi w nową kampanię z pełnym HP i maną
- **C10-C13** — Systemowe tagi QUEST_SUGGEST, SPEND_GOLD, mechaniczne śledzenie questów, reguła złota w system_prompt
- **C14-C16** — Hero-first flow, error boundary na loadHeroes, modal potwierdzenia kasowania kampanii
- **C9** — Modal długiego odpoczynku — "Ucz się" UI z levelupem

### Fixed
- Opening scene zawsze generowana z kontekstem planu GM (nie domyślny las)
- Pasywna obserwacja nie wyzwala zbędnego rzutu Awareness
- Streaming LLM URL fix, BUILD_CAMP gate, debug bloki usunięte z player UI

---

## v1.2.1 — 2026-06-06 — Faza 1: World Loop Core (C1-C8)

### Added / Fixed
- **C1** — STORY_STALE: po 5 turach bez zmiany lokacji LLM sugeruje ruch (#355)
- **C2** — Walidacja ruchu mechaniczna: hex, terrain, World State update (#356)
- **C3** — Gate walki: sprawdzanie scene_enemies przed każdym ATTACK (#357)
- **C4** — wound_penalty utility: unifikacja hp_current/hp_max → roll modifier (#360)
- **C5** — Symetria ran: wound_penalty dla wrogów (nie tylko gracza) (#358)
- **C6** — Progi ran frontend/backend: stałe z API zamiast hardcode (#359)
- **C7** — XP spend skill: poprawne koszty (100/75/150 XP), rank ceiling=3 (#361)
- **C8** — XP spend stat: koszty per game_mechanics.md (50/100/200/400), ceiling=19, CON→hp_max (#362)

---

## v1.2.0-dev — 2026-06-06 — Faza 1: World Loop Core

In progress (Faza 1 — C tasks).

### Added
- **C1** — STORY_STALE injection: after 5 turns without location change, LLM suggests leaving (#355)

### Changed
- Admin panel v3 is now the sole admin interface (`/admin3/`)
- `/admin` → `/admin3/` redirect via Nginx

---

## v1.1.0 — 2026-06-05 — Faza 0: World State Machine

Faza 0 (B tasks) — 100% complete.

### Added
- **B1** — World State Machine (WSM) — action validation gate (#336)
- **B2** — WSM: MOVEMENT action with hex validation (#337)
- **B3** — Gate mechanic (locked gates, key items, quests) (#338)
- **B4** — NPC memory per campaign (first-talk flag, persistent attitude) (#339)
- **B5** — Campaign Kompas — hints panel for available actions (#340)
- **B6** — World State history viewer (admin + player) (#352)
- **B7** — DEV Inspector panel (admin debug overlay in player UI) (#354)

### Changed
- Dungeon system refactored to use WSM
- Combat zones (engaged/ranged) fully wired to WSM

---

## v1.0.0 — 2026-06-01 — Faza -1: Cleanup & Foundation

Faza -1 (A tasks) — 100% complete.

### Added
- **A4** — Git version tagging system (v1.0.0, v1.1.0-dev, v1-stable)
- **A5** — Maintenance notification middleware + player banner
- **A7** — Admin panel v3 routing (/admin3/)
- **A12** — Game config seed to git; player data stays private

### Removed
- Dead code: voice-service (708MB), observability stack, docs/OLD (~1.1GB total)

### Fixed
- DB schema: missing columns in game_locations
- Deploy scripts: dirty-check ignore untracked files

---

## v0.3 — metrics-dashboards-dev

Observability stack (Grafana/Loki/Prometheus). Deprecated — removed in A1.

## v0.2 — observability-dev

Loki logging integration.

## v0.1 — phase0-complete

Initial working game loop: login, character, campaign, combat, inventory.
