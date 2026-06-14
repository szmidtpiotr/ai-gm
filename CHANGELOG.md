# Changelog — AI-GM

Format: `vX.Y.Z — YYYY-MM-DD — opis`

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
