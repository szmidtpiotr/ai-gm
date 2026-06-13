# AI-GM — Master Task Checklist
_Ostatnia aktualizacja: 2026-06-12 (dodano FAZĘ S — Skille i Stany, 20 zadań; opisy w game_mechanics.md CZĘŚĆ AI)_

Pełna lista tasków z `game_mechanics.md` CZĘŚĆ 7. Aktualizuj `[x]` po weryfikacji na DEV.

**Schemat kodów:** A=Faza -1 | B=Faza 0 | C=Faza 1 | D=Faza 2 | E=Faza 3 | F=Faza 4 | G=Faza 5 (MP) | H=Faza 6

| Faza | Ukończone | Total |
|------|-----------|-------|
| A (Faza -1) | 13/13 | 100% ✅ |
| B (Faza 0) | 7/7 | 100% ✅ |
| C (Faza 1) | 19/19 | 100% ✅ |
| D (Faza 2) | 14/14 | 100% ✅ |
| E (Faza 3) | 28/28 | 100% ✅ (E1–E28 wszystkie ✅) |
| F (Faza 4) | 21/21 | 100% ✅ (F1✅ F2✅ F2b✅ F3✅ F4✅ F5✅ F6✅ F7✅ F8✅ F9✅ F10✅ F11✅ F12✅ F13✅ F14✅ F15✅ F16✅ F17✅ F18✅ F19✅ F20✅ F21✅) |
| **U (Plan naprawczy)** | **13/35** | **37% — PRZED Fazą 5 MP** |
| **S (Skille i Stany)** | **0/20** | **0% — zaplanowane 2026-06-12; po/przeplatane z FAZĄ U; Blok 3 wymaga U10** |
| G (Faza 5 MP) | 0/15 | 0% — start dopiero po U27 go/no-go |
| H (Faza 6) | 0/5 | 0% |
| **FADM (admin rebuild)** | 18/18 | 100% ✅ KOMPLETNE (strangler fig zakończony) |
| **TOTAL** | **105/193** | **54%** |

> **2026-06-08:** Praca nad sekcją D **wstrzymana**. Wyrównanie architektury wg pierwotnego planu (CZĘŚĆ AE strangler-fig) — budujemy modularny `admin/` z monolitu admin3. Brief: `docs/V2_ARCHITECTURE/10_ADMIN_REBUILD_STRANGLER.md`. Epic [#401](https://github.com/szmidtpiotr/ai-gm/issues/401).

---

## FAZA -1 — Procedury wstępne ✅ UKOŃCZONA (2026-06-06)

- [x] A1 — Dead code cleanup (~1.1GB: voice-service 708M, observability 438M, docs/OLD 6.1M, output) — **0798fb2**
- [x] A2 — Audyt schematu DB — lista tabel do migracji/usunięcia — ✅ table_schema.md
- [x] A3 — PROD restoration na .62 + freeze starego kodu (tag v1.0-legacy) — ✅ .62 working
- [x] A4 — Version tagging (git tag) — ✅ v1.0.0, v1.1.0-dev, v1-stable
- [x] A5 — Maintenance notification workflow (banner dla graczy podczas deployów) — ✅ middleware + UI
- [x] A6 — Parity check admin2 vs admin3 — ✅ v3 pokrywa v2
- [x] A7 — Redirect /admin → /admin3 — ✅ nginx 301
- [x] A8 — Usunięcie admin2 z serwera — ✅ nie serwuje /admin2
- [x] A9 — Usunięcie `frontend/admin_panel_v2/` z repo — ⏳ BLOCKED (unblock 2026-06-19)
- [x] FINF-1 — ~~Potwierdzenie IP hosta GPU~~ ZAMKNIĘTE (RTX3060=.170, GTX1660=.16) — ✅
- [x] A10 — Nowa skorupa admin panelu (thin shell + nav) — ✅ v3 hash nav + localStorage
- [x] A11 — Shared utilities admin (api.js, toast.js, modal.js, table.js) — ✅ hardened
- [x] A12 — Game config seed — `data/game_config_seed.sql` w git; skrypty export/import — **b1bbf66**

---

## FAZA 0 — World State ✅ UKOŃCZONA (2026-06-06)

- [x] B1 — Tabela `world_state_snapshots` (campaign_id, turn_number, state_json) — commit c7db68d + migracja 3da9235
- [x] B2 — Rozbudowa session_flags: scene_enemies, scene_npcs, active_quests, player_conditions — commit c7db68d
- [x] B3 — Gate Mechaniki — middleware walidujący akcje gracza PRZED LLM — commit c7db68d
- [x] B4 — Parser intencji gracza (ATTACK/MOVE/TALK/REST → walidacja przez Gate) — commit c7db68d
- [x] B5 — Auto-zapis snapshotu World State po każdej turze narracyjnej — commit 48ce52b
- [x] B6 — Admin UI — World State History (zakładka w Campaign Monitor, diff między turami) — commit 48ce52b
- [x] B7 — DEV Inspector — panel diagnostyczny dla adminów (intent + gate + world state per kampania) — commit e9f29c3

---

## FAZA 1 — Rdzeń pętli (core loop) ✅ UKOŃCZONA (C1–C19, v1.2.3)

- [x] C1 — Fix Bug 1 — LLM musi sugerować ruch hex po N turach bez zmiany lokacji — [#355](https://github.com/szmidtpiotr/ai-gm/issues/355)
- [x] C2 — Walidacja ruchu mechaniczna (nowy hex, terrain, lokacja check, update World State) — [#356](https://github.com/szmidtpiotr/ai-gm/issues/356)
- [x] C3 — Fix Bug 2 — Gate walki (scene_enemies check przed każdym ATTACK) — [#357](https://github.com/szmidtpiotr/ai-gm/issues/357)
- [x] C4 — Unifikacja wound_penalty: refactor z sheet-only na hp_current/hp_max — [#360](https://github.com/szmidtpiotr/ai-gm/issues/360)
- [x] C5 — Symetria ran: wound_penalty dla wrogów (nie tylko gracza) — [#358](https://github.com/szmidtpiotr/ai-gm/issues/358)
- [x] C6 — Ujednolicenie progów ran frontend/backend — [#359](https://github.com/szmidtpiotr/ai-gm/issues/359)
- [x] C7 — XP Spend — endpoint spend_skill (wszystkie archetypy) — [#361](https://github.com/szmidtpiotr/ai-gm/issues/361)
- [x] C8 — XP Spend — endpoint spend_stat (wszystkie archetypy) — [#362](https://github.com/szmidtpiotr/ai-gm/issues/362)
- [x] C9 — UI długiego odpoczynku — modal "Ucz się" (lista zakupów XP) — [#363](https://github.com/szmidtpiotr/ai-gm/issues/363)
- [x] C10 — System questów — QUEST_SUGGEST tag + walidacja backend — [#364](https://github.com/szmidtpiotr/ai-gm/issues/364)
- [x] C11 — Mechaniczne śledzenie postępu questów (auto-complete per akcja) — [#365](https://github.com/szmidtpiotr/ai-gm/issues/365)
- [x] C12 — `[SPEND_GOLD:X]` tag — kwota z tabeli/configu, NIE z LLM — [#366](https://github.com/szmidtpiotr/ai-gm/issues/366)
- [x] C13 — Instrukcja "tylko złoto GP" w system_prompt (usunięcie waluty srebrnej) — [#367](https://github.com/szmidtpiotr/ai-gm/issues/367)
- [x] C14 — Hero-first fix: startCharacterWizard() tylko z Heroes screen — [#368](https://github.com/szmidtpiotr/ai-gm/issues/368)
- [x] C15 — Error boundary dla API failures (toast zamiast białego ekranu) — [#369](https://github.com/szmidtpiotr/ai-gm/issues/369)
- [x] C16 — Delete confirmation modals (kampania, postać) — [#370](https://github.com/szmidtpiotr/ai-gm/issues/370)
- [x] C17 — Kontekst ekwipunku postaci — injection listy przedmiotów i złota do LLM per tura — [#373](https://github.com/szmidtpiotr/ai-gm/issues/373)
- [x] C18 — Fix Bug 3: kampanie startują na istniejących hexach, nie nowych obrzeżach — [#374](https://github.com/szmidtpiotr/ai-gm/issues/374)
- [x] C19 — Fix Bug 4: bohater startuje nową kampanię z pełnym HP (reset hp_current = hp_max) — [#375](https://github.com/szmidtpiotr/ai-gm/issues/375)

---

## FAZA 2 — Systemy + Narracja

- [x] D1 — Pending flow przedmiotów (GRANT_ITEM nieznanego klucza → auto-screen → pending=true) — [#376](https://github.com/szmidtpiotr/ai-gm/issues/376)
- [x] D2 — Pending flow wrogów (analogicznie do D1) — [#377](https://github.com/szmidtpiotr/ai-gm/issues/377)
- [x] D3 — NPC pamięć w World State (NPC_MEMORY tag → context injection przy kolejnej wizycie) — [#378](https://github.com/szmidtpiotr/ai-gm/issues/378)
- [x] D4 — Auto-screening admin queue (Poziom 1 tech validation + Poziom 2 LLM scoring) — [#379](https://github.com/szmidtpiotr/ai-gm/issues/379)
- [x] D5 — Item VIEW — podgląd przedmiotu w inventory (tooltip/modal) — [#380](https://github.com/szmidtpiotr/ai-gm/issues/380)
- [x] D6 — Narracja: tagi, parsery, Narrative State struktura — [#381](https://github.com/szmidtpiotr/ai-gm/issues/381)
- [x] D7 — Encountery generyczne (adventure_hooks + gameconfig_encounter_templates unifikacja) + gate safe_for_rest + dwell decay + interwał config (admin3) — [#382](https://github.com/szmidtpiotr/ai-gm/issues/382)
- [x] D8 — Ekran profilu gracza (konto + edycja email, znajomi, ustawienia LLM) — [#383](https://github.com/szmidtpiotr/ai-gm/issues/383)
- [x] D9 — Ekran kampanii — 5 trybów (Nowa/Gotowa/Loch/Loch-kafelki/Multiplayer) — hub + dostępność per dane — [#384](https://github.com/szmidtpiotr/ai-gm/issues/384)
- [x] D10 — Onboarding animacja + wybór motywu (nowy gracz) — [#385](https://github.com/szmidtpiotr/ai-gm/issues/385)
- [x] D11 — Confirm password na rejestracji — [#386](https://github.com/szmidtpiotr/ai-gm/issues/386)
- [x] D12 — Szybka nawigacja Hub → Gra (bez przeładowania) — [#387](https://github.com/szmidtpiotr/ai-gm/issues/387)
- [x] D13 — Mobile layout — weryfikacja responsywności wszystkich ekranów — [#388](https://github.com/szmidtpiotr/ai-gm/issues/388)
- [x] D14 — Bugfix: `update_item` ustawia approved=1 przy edycji przedmiotu z approved=0 (`current.approved or 1`) — znaleziony przy D1 — [#399](https://github.com/szmidtpiotr/ai-gm/issues/399)

---

## FAZA 3 — Jakość + Treść

- [x] E1 — Player HUD (HP/Mana, Złoto, Questy, XP bar, Czas) — aktualizacja per tura — [#416](https://github.com/szmidtpiotr/ai-gm/issues/416)
- [x] E2 — Kreator bohatera — tooltips (archetyp, statystyki, umiejętności z przykładami) — [#417](https://github.com/szmidtpiotr/ai-gm/issues/417)
- [x] E3 — Ekran zakończenia kampanii (podsumowanie + LLM epitafium) — [#418](https://github.com/szmidtpiotr/ai-gm/issues/418)
- [x] E4 — Ekran śmierci (epitafium + statystyki + Wskrześ/Nowy bohater) — [#419](https://github.com/szmidtpiotr/ai-gm/issues/419)
- [x] E5 — Zamknięcie dostępu do kampanii martwego bohatera (hero_status=dead) — [#420](https://github.com/szmidtpiotr/ai-gm/issues/420)
- [x] E6 — Narracja: kompresja chapter_summary + seeds injection + ARC_ADVANCE automation — [#421](https://github.com/szmidtpiotr/ai-gm/issues/421)
- [x] E7 — Rozbudowa `campaign_templates` (required_npc_keys, required_beats, player_visible) — [#422](https://github.com/szmidtpiotr/ai-gm/issues/422)
- [x] E8 — Ekran wyboru gotowej kampanii dla gracza (karty, trudność, opisy) — [#423](https://github.com/szmidtpiotr/ai-gm/issues/423)
- [x] E9 — Story Gravity: trigger = next_required_beat nie odpalony przez N tur (5/10/15, L3 domyślnie OFF) — [#424](https://github.com/szmidtpiotr/ai-gm/issues/424)
- [x] E10 — Forge: walidacja wymaganych NPC/lokacji przy publikacji szablonu — [#425](https://github.com/szmidtpiotr/ai-gm/issues/425)
- [x] E11 — Template Narrative State pre-seeding (narrative_hooks z szablonu → World State) — [#426](https://github.com/szmidtpiotr/ai-gm/issues/426)
- [x] E12 — Workflow publikacji szablonów (draft → review → published) — [#427](https://github.com/szmidtpiotr/ai-gm/issues/427)
- [x] E13 — Encountery generyczne — rozbudowa puli adventure_hooks (biome/trigger/level) — [#428](https://github.com/szmidtpiotr/ai-gm/issues/428)
- [x] E14 — Skalowanie encounterów per poziom gracza — [#429](https://github.com/szmidtpiotr/ai-gm/issues/429)
- [x] E15 — Snapshot stanu przy wejściu do lochu — [#430](https://github.com/szmidtpiotr/ai-gm/issues/430)
- [x] E16 — Przywróć snapshot przy śmierci w lochu + restart — [#431](https://github.com/szmidtpiotr/ai-gm/issues/431)
- [x] E17 — Rarity tierów loot w lochach (5 tierów, mapowanie difficulty→rarity) — [#432](https://github.com/szmidtpiotr/ai-gm/issues/432)
- [x] E18 — Cooldown UI lochów w Admin Panelu — [#433](https://github.com/szmidtpiotr/ai-gm/issues/433)
- [x] E19 — LLM Vision: obrazek → opis kafelka (task na maszynie .170) — [#434](https://github.com/szmidtpiotr/ai-gm/issues/434)
- [x] E20 — Admin UI tile manager (obrazki, drzwi, opisy kafelków) — [#435](https://github.com/szmidtpiotr/ai-gm/issues/435) (covered by E19b/E19c)
- [x] E21 — Wejście do lochu z mapy hex kampanii — [#436](https://github.com/szmidtpiotr/ai-gm/issues/436) — 0213eb9
- [x] E22 — Resume niedokończonego runu lochu — [#437](https://github.com/szmidtpiotr/ai-gm/issues/437) — 0213eb9
- [x] E23 — Seen_mechanics tracking per gracz (tabela + endpoint mark-seen) — [#438](https://github.com/szmidtpiotr/ai-gm/issues/438)
- [x] E24 — Backend trigger kart onboarding (first mechanic occurrence: rzut/walka/rana/XP/złoto/death) — [#439](https://github.com/szmidtpiotr/ai-gm/issues/439)
- [x] E25 — Karty onboarding UI (nieblokujące overlay, "Rozumiem") — [#440](https://github.com/szmidtpiotr/ai-gm/issues/440)
- [x] E26 — Biblioteka kart (gracz może wrócić do przeczytanych) — [#441](https://github.com/szmidtpiotr/ai-gm/issues/441)
- [x] E27 — Karty dla nowych mechanik (afiksy, crafting, MP) — gdy systemy gotowe (Faza 4+) — [#442](https://github.com/szmidtpiotr/ai-gm/issues/442)
- [x] E28 — Tutorial kampania "Moja Pierwsza Przygoda" (domyślnie ON, Pomiń, instrukcje LLM) — [#443](https://github.com/szmidtpiotr/ai-gm/issues/443)

---

## FAZA 4 — Rozbudowa: Efekty, Afiksy, Ekonomia

- [x] F1 — Unified Effects System — effect_json → typed Effect Objects (schema, silnik, LLM DSL) — [#461](https://github.com/szmidtpiotr/ai-gm/issues/461) — ✅ KOMPLETNE: `damage_bonus` (F1a) + `heal_on_hit` (life-steal, on-hit) + `ac_bonus` (combat-start) + `apply_condition` (on-hit, de-dup) + `static_stat_modifier` (combat-start stats dict) + F1b backward compat + F1d DSL (Smart Entry prompt). 18/18 tests GREEN.
- [x] F2 — Affix System — game_config_affixes + affixes_json na inventory row + loot engine — [#462](https://github.com/szmidtpiotr/ai-gm/issues/462) — ✅ commit 35b864b: `roll_weapon_affixes()` per loot_tier (poor=0, standard=1×T1, rich=2×T1-T2, treasure=3×T1-T3); `grant_loot_to_character` + `grant_dungeon_loot` przyjmują `loot_tier`; dungeon run instance zawiera `loot_tier`; 10 testów pytest + 3 Playwright GREEN.
- [x] F2b — Enemy drop affixes — `loot_tier` na `game_config_enemies` → afiksy na broniach z dropów wrogów — [#484](https://github.com/szmidtpiotr/ai-gm/issues/484) — ✅ commit 2c7dfc1: migracja `loot_tier TEXT DEFAULT NULL`; combatant dict + `_preview_loot_from_roll_items` przechowuje `enemy_loot_tier`; `claim_post_combat_loot` przekazuje do `grant_loot_to_character`; backward compat (NULL = brak afiksów); 9 testów pytest + 3 Playwright GREEN.
- [x] F3 — Admin buildery afiksów i efektów (wizualny UI, nie ręczny JSON) — [#463](https://github.com/szmidtpiotr/ai-gm/issues/463) — ✅ commit db7c638: POST/PATCH/DELETE /api/admin/affixes + zakładka Afiksy w Zawartość + Effects Builder (dropdown typów); 8 testów pytest + 4 Playwright GREEN
- [x] F4 — `[SPEND_GOLD:X]` tag z tabeli/configu (NIE z LLM) — [#464](https://github.com/szmidtpiotr/ai-gm/issues/464) — ✅ commit 100cbef: `build_refusal_text()` + `apply_spend_gold_to_narrative()`; narracja odmowy przy braku złota; non-stream path fixed (tagi leciały do gracza); 8 seed rows game_config_services; 10/10 pytest GREEN. **Domknięcie (2026-06-11):** dodano sekcję SPEND_GOLD do `system_prompt.txt` (parser istniał, ale LLM nigdy nie wstawiał tagu) — zweryfikowane realną turą: gold 38→33, log `spend_gold_applied inn_night cost=5`; 5/5 pytest + 2/2 Playwright GREEN
- [x] F5 — Wskrzeszenie jako gold sink (włączenie + konfiguracja gold_percent) — [#465](https://github.com/szmidtpiotr/ai-gm/issues/465) — ✅ commit 34d0d8c: retroaktywne TDD — feature istniała od #64 (resurrection_service.py); 13 pytest + 2 Playwright GREEN
- [x] F6 — Sink afiksów: NPC is_crafter, nałóż/reroll (T1=150g, T2=500g, T3=1200g) — [#466](https://github.com/szmidtpiotr/ai-gm/issues/466) — ✅ commit 55cfdc9: `crafter_service.py` (apply/reroll/upgrade affix + cost constants); 3 endpointy POST /craft/apply-affix + /reroll-affix + /upgrade-affix; 22 pytest + 4 Playwright GREEN
- [x] F7 — Trwałość (durability): punktowa per cios, penalty przy 0, naprawa tier_rate — [#467](https://github.com/szmidtpiotr/ai-gm/issues/467) — ✅ commit ad3a585: `durability_service.py` (decrement/penalty/repair + stałe T1=20g T2=50g T3=100g/pt); combat_service 3 hooki; 2 endpointy /repair-item + /repair-cost; 24 pytest + 3 Playwright GREEN
- [x] F8 — Napady: encounter kradnący % złota przy porażce/zaskoczeniu — [#468](https://github.com/szmidtpiotr/ai-gm/issues/468) — ✅ commit b7ff32e: `robbery_service.py` (apply/config/is_robbery); turns.py hook przed combat; 2 robbery seedy w encounter pool; 18 pytest + 3 Playwright GREEN
- [x] F9 — Dynamiczny asortyment sklepu (lokacja + poziom gracza) — [#469](https://github.com/szmidtpiotr/ai-gm/issues/469) — ✅ `shop_service.py` `_get_character_level` + `_item_passes_filters`; `min_level`+`location_tags` na 3 tabelach; `location_key` query param w GET /shop; 12 pytest + 3 Playwright GREEN
- [x] F10 — CHA na kupno — bonus/malus przy zakupach (nie tylko sprzedaży) — [#470](https://github.com/szmidtpiotr/ai-gm/issues/470) — ✅ `_cha_buy_multiplier` (1 - CHA_mod×0.05, klamp 0.5) + `_buy_price`; `buy_price_gp` per item + `buy_multiplier` w odpowiedzi; `buy_item` pobiera zniżoną cenę → `paid_gp`; 11 pytest + 3 Playwright GREEN
- [x] F11 — Unifikacja ceny → jeden price_gp + wycena egzemplarza z afiksami — [#471](https://github.com/szmidtpiotr/ai-gm/issues/471) — ✅ `_catalog_item` używa `COALESCE(price_gp, value_gp/base_price)`; `_affix_price_bonus` T1=+25/T2=+75/T3=+200gp; migracja backfill; 13 pytest + 3 Playwright GREEN
- [x] F12 — Anti-farm: malejąca cena sprzedaży przy spam-sprzedaży tego samego type — [#472](https://github.com/szmidtpiotr/ai-gm/issues/472) — ✅ `anti_farm_service.py`: `get_anti_farm_multiplier` (decay po 3 sprzedażach, okno 24h, min 10%); `sell_item` hook + patch `meta_json` z `item_key`; 13 pytest + 3 Playwright GREEN
- [x] F13 — Background expire wynajmu — sweep wygasłych tymczasowych bonusów — [#473](https://github.com/szmidtpiotr/ai-gm/issues/473) — ✅ commit ac3ca68: `rental_service.expire_rentals(conn, campaign_id, current_turn)`; hook w `turns.py`; 10 pytest + 2 Playwright GREEN
- [x] F14 — Usunięcie martwego economy_service (generate_combat_loot / claim_loot) — [#474](https://github.com/szmidtpiotr/ai-gm/issues/474) — ✅ commit ac3ca68: ~210 linii martwego kodu TASK_22 usunięte; 6 pytest + 2 Playwright GREEN
- [x] F15 — Balans walki → mikstury potrzebne (playtest + tuning DC/damage) — [#475](https://github.com/szmidtpiotr/ai-gm/issues/475) — ✅ `expected_hp_loss_pct` formula; bandyta +3→+4 attack_bonus (próg 60% HP); migracja `_apply_f15_balance_tuning`; 6 pytest + 3 Playwright GREEN
- [x] F16 — Balans całości (ceny/dropy/sinki) — pełny playtest — [#476](https://github.com/szmidtpiotr/ai-gm/issues/476)
- [x] F17 — Hidden Trait system (LLM z puli, trigger kontekstowy, reveal narracyjny) — [#477](https://github.com/szmidtpiotr/ai-gm/issues/477)
- [x] F18 — Rosnące progi XP konfigurowalne z Admin Panelu — [#478](https://github.com/szmidtpiotr/ai-gm/issues/478)
- [x] F19 — Globalne stany NPC — śmierć NPC między kampaniami (is_dead globalny) — [#479](https://github.com/szmidtpiotr/ai-gm/issues/479)
- [x] F20 — Mechaniczne efekty pory dnia (noc/świt bonusy z game_config) — [#480](https://github.com/szmidtpiotr/ai-gm/issues/480)
- [x] F21 — World State History UI admina (zakładka + diff między turami) — [#481](https://github.com/szmidtpiotr/ai-gm/issues/481)

---

## FAZA U — Plan naprawczy używalności (2026-06-11, audyt pełnego specu) — PRZED Fazą 5

> Pełne opisy zadań: `game_mechanics.md` CZĘŚĆ AH. Kolejność wykonania = sekcja "FAZA U — zależności i kolejność" w CZĘŚCI AH (NIE numeracja — U9b/U28–U32/U32b wchodzą przed Blokiem 4). Każde zadanie = GitHub Issue `[TASK] UNN — tytuł` wdrażane `/tdd`; wyjątki U4/U9b/U32b = czyste playtesty /game-smoke (bez TDD, bez nowego issue, raporty do #512/#513).

### Blok 1 — Dokument prawdy
- [x] U1 — Sprzątanie game_mechanics.md (statusy, kolizje kodów D8–D13, wiszące refy F0/FINF-1) — [#509](https://github.com/szmidtpiotr/ai-gm/issues/509)
- [x] U2 — Uzgodnienie spec↔impl ekonomii (reroll droższy niż nałożenie, durability broń-przy-ataku/zbroja-przy-ciosie, stałe craftingu, anti-farm = 24h realne) — [#510](https://github.com/szmidtpiotr/ai-gm/issues/510)
- [x] U3 — Feature-flag Multiplayer w hubie ("Wkrótce", default OFF) — [#511](https://github.com/szmidtpiotr/ai-gm/issues/511)

### Blok 2 — Ground truth
- [x] U4 — Smoke specs Playwright ([SMOKE] issues #512 #513; 9/9 GREEN — pokrywają TYLKO: login, utworzenie kampanii, 1 turę E2E) — [#512](https://github.com/szmidtpiotr/ai-gm/issues/512) [#513](https://github.com/szmidtpiotr/ai-gm/issues/513)
- [x] U4b — Playtest LLM 15 tur × 2 tryby skillem /game-smoke (ruch po hexach, NPC, quest, walka, sklep, odpoczynek+XP, beaty w Gotowej) — defekty P0/P1/P2; werdykt "brak P0" z U4 NIE jest jeszcze potwierdzony — [#512](https://github.com/szmidtpiotr/ai-gm/issues/512) [#513](https://github.com/szmidtpiotr/ai-gm/issues/513) **OBA NIEGRYWALNY — P0: #515 (scene_enemies), P1: #518 #519 #520 #521 #522**

### Hotfixy po U4b (poza licznikiem U; wykonać PRZED U5, w tej kolejności)
- [x] HF-1 — #515 P0: scene_enemies nie czyszczone po resolve_attack → softlock po każdej walce (regresja względem #456: end_combat czyści, ale ścieżka "ostatni wróg pada w resolve_attack" nie woła clear) — [#523](https://github.com/szmidtpiotr/ai-gm/issues/523)
- [x] HF-2 — #521 P1: questy zapisują się tylko do session_flags.active_quests, brak persystencji do character_quests (łamie C10/C11; bez tego auto-complete questów i dziennik U18 nie mają na czym stać) — [#524](https://github.com/szmidtpiotr/ai-gm/issues/524)
- [x] HF-3 — Gotowa Kampania startuje z GM Planem 0 scen (szablon nie zasiewa planu) — normalize_gm_plan list→dict, get_plan arcs→acts, _migrate_template_plan_to_w1 przy starcie — [#525](https://github.com/szmidtpiotr/ai-gm/issues/525)
- [x] HF-4 — po HF-1: ponowny `/game-smoke nowa-kampania` (run z U4b był z poprzedniej sesji, bez pełnej tabeli checkpointów) — [#512-run2](https://github.com/szmidtpiotr/ai-gm/issues/512#issuecomment-4690454578) — Werdykt: GRYWALNY Z ZASTRZEŻENIAMI; P0=0, P1=#518/#522 (znane→U30/U28-29), P2=#526 (character_rentals brak migracji); HF-1 ✅ potwierdzone

### Bugi standalone (poza licznikiem U; wykonać jako przerywnik między zadaniami U albo razem ze wskazanym zadaniem)
- [x] [#529](https://github.com/szmidtpiotr/ai-gm/issues/529) — Admin: zakładka "Znani NPC" niewidoczna w modalu kampanii (bump ?v=18→19 w admin/index.html) + endpoint known-npcs czyta deprecated `npc_locations` zamiast `location_npc_assignments`. Część 2 najlepiej razem z **U31** (ten sam kierunek migracji danych). Diagnoza w issue — kompletna, agent nie musi szukać od zera. — commit 7cb70e1

> **Mapowanie pozostałych P1 — NIE hotfixować, naprawiają je zadania U (naprawa dwa razy = praca wyrzucona):**
> #518 (current_hex wiecznie {0,0}) → **U30** · #520 (narracja walki bez [COMBAT_START]) → **U5/U6** (guard) · #522 (LLM tworzy AI-lokacje zamiast bazy) → **U28/U29**. Dodaj te numery do opisów zadań przy ich realizacji i zamknij issues przy ich odbiorze.

### Blok 3 — Pancerz na LLM (spójność narracja↔stan)
- [x] U5 — Centralny parser tagów + tabela llm_tag_errors + polityka malformed — [#528](https://github.com/szmidtpiotr/ai-gm/issues/528)
- [x] U6 — Uogólniony wzorzec odmowy (korekta narracji przy każdym odrzuconym tagu) — [#530](https://github.com/szmidtpiotr/ai-gm/issues/530)
- [x] U7 — SKILL_CHECK safety net (backend wymusza test przy ryzykownej akcji) + DC lock {8,12,16,20,24} — [#531](https://github.com/szmidtpiotr/ai-gm/issues/531)
- [x] U8 — Beat fallback (objective_type na beatach) + Story Gravity L1/L2/L3 zdefiniowane i włączone — [#532](https://github.com/szmidtpiotr/ai-gm/issues/532)
- [x] U9 — GM Plan hardening (retry + fallback plan, kampania startuje zawsze) — [#533](https://github.com/szmidtpiotr/ai-gm/issues/533)
- [x] U9b — 🎮 KAMIEŃ MILOWY: /game-smoke × 2 tryby po Bloku 3 — GRYWALNY Z ZASTRZEŻENIAMI, zero P0. **Zaliczony WARUNKOWO** (kryterium "zero nowych P1" nie spełnione): #534/#535/#536 → hotfixy HF-5–HF-8 wymagane PRZED U28 (sekcja niżej). Raporty: [#512](https://github.com/szmidtpiotr/ai-gm/issues/512#issuecomment-4692425428), [#513](https://github.com/szmidtpiotr/ai-gm/issues/513#issuecomment-4692464871).

### Hotfixy po U9b (poza licznikiem U; wykonać PRZED U28, w tej kolejności)
- [x] HF-5 — [#536](https://github.com/szmidtpiotr/ai-gm/issues/536) COMMIT: fix XP hooks już w drzewie roboczym (turns.py: `strip_narrative_tags` importowany z `narrative_state_service` zamiast `xp_sources`) — zacommitować + pytest importu; bez commitu następny rebuild cofnie fix — 624f096
- [x] HF-6 — [#535](https://github.com/szmidtpiotr/ai-gm/issues/535) Gate ATTACK regex łapie negację ("nic nie atakuję" → gate_blocked) — word boundary + bypass "nie <czasownik>"; `_NEGATION_ATTACK_PATTERN` + `\buderz\b` dodane; 15/15 testów GREEN
- [x] HF-7 — [#534](https://github.com/szmidtpiotr/ai-gm/issues/534) Walidacja celu COMBAT_START: cel spoza scene_enemies/bazy wrogów albo przyjazny NPC (quest-giver) → odrzucenie tagu + korekta narracji (wzorzec U6) + wpis llm_tag_errors — [#538](https://github.com/szmidtpiotr/ai-gm/issues/538) 8/8 testów GREEN
- [x] HF-8 — CP11: dodać `objective_type` do `key_beats` w szablonach kampanii (bez tego auto-complete beatów z U8 martwy w Gotowej; U32b mierzy checkpoint 11 — "fix przy U32b" za późno, U32b to playtest, nie naprawa) — [#539](https://github.com/szmidtpiotr/ai-gm/issues/539)

### Hotfixy po U32b (defekty wykryte w runach milestone; PRZED Blokiem 4)
- [x] HF-9 — [#551](https://github.com/szmidtpiotr/ai-gm/issues/551) #549 CP3: legacy `ai_generated=1` na hexie nie zastępowana lokacją z bazy — `resolve_chain_travel` czyści location_key gdy ai_generated=1, uruchamia placement engine; 3/3 testów GREEN
- [x] HF-10 — [#552](https://github.com/szmidtpiotr/ai-gm/issues/552) #550 CP11 part 1: kill_enemy beat nie kompletuje przez /combat/resolve-attack (bypass turn_pipeline) — hook `auto_complete_beats_by_event` w `combat_service.resolve_attack` przy dead=True; 5/5 testów GREEN
- [x] HF-11 — [#553](https://github.com/szmidtpiotr/ai-gm/issues/553) #550 CP11 part 2: talk_to_npc/visit_location beat auto-complete w martwym kodzie (`process_v2_turn` nigdy nie wołany w żywym torze) — `auto_complete_talk_to_npc` (button DIALOGUE + free-text scene-NPC match, normalizacja PL diakrytyków) wpięta w oba tory turns.py + `visit_location` w hex_travel; 5/5 testów GREEN, potwierdzone live (kampania 64)

> Luki designu poza hotfixami: **CP8** (zakupy w narracji nie zdejmują złota) → decyzja przy Bloku 7 (U24–U26): rozszerzyć [SPEND_GOLD] na zakupy narracyjne albo sklep wyłącznie przez UI z odmową w narracji. **CP4** (NPC nie wywołany po imieniu) → P2, prawdopodobnie naprawi U29 (blok [ŚWIAT] z NPC z bazy).

### Blok 4 — Baza danych jako rdzeń (2/5)
- [x] U10 — Effect schema lockdown — **decyzja C (hybryda, 2026-06-13):** zachowano nazwy typów z kodu (periodic_save/static_stat_modifier/block_action), bo walidator już istniał i działał + FAZA S na nim bazuje; dodano `backend/app/schemas/effect_schema.json` jako pojedyncze źródło prawdy, LCK + cele pochodne (ac/attack_bonus/damage_bonus/initiative), audyt `scripts/effect_json_audit.py` (169==169, 0 strat; 23 legacy do ręcznej decyzji → U11/FAZA S). — [#554](https://github.com/szmidtpiotr/ai-gm/issues/554)
- [x] U11 — Unifikacja przedmiotów 3 tabele → game_items (sub-issues U11a schema+backfill / U11b odczyt / U11c zapis+admin) — [#555](https://github.com/szmidtpiotr/ai-gm/issues/555) **needs-testing**
  - [x] U11a — CREATE TABLE game_items + backfill (140 rek.: 27 weapon + 26 armor + 59 item + 28 consumable) + FK columns (game_item_key NULL w char_inventory + loot_entries). Stare tabele niezmienione. — [#556](https://github.com/szmidtpiotr/ai-gm/issues/556) **needs-testing**
  - [x] U11b — przełączenie odczytu: serwisy czytają z game_items; stare tabele read-only — [#557](https://github.com/szmidtpiotr/ai-gm/issues/557) **needs-testing**
  - [x] U11c — dual-write: create/update/delete weapon+item, smart_entry, approve_entity, forge, import katalogu piszą też do game_items (re-read legacy → upsert; jedno mapowanie = backfill U11a). Stare tabele DEPRECATED (drop po 2 tyg., decyzja Piotra). 9/9 pytest GREEN + live verify create/edit/delete. **UWAGA: 18 testów shop/loot/inventory czerwone z PRE-ISTNIEJĄCYCH luk fixture'ów U11b (`no such table: game_items` / `no such column gi.armor_coverage` w izolowanych DB testów) — nie regresja U11c, należą do #557.** — [#558](https://github.com/szmidtpiotr/ai-gm/issues/558) **needs-testing**
- [x] U12 — db_lint (skrypt + endpoint + przycisk w admin Narzędzia + krok w deploy_dev.sh) — [#559](https://github.com/szmidtpiotr/ai-gm/issues/559) **needs-testing**
- [ ] U13 — Content pipeline (lint seedów 01–15, walidacja na imporcie, docs/CONTENT_PIPELINE.md)
- [ ] U14 — Pełny reset bohatera przy nowej kampanii (mana + conditions, nie tylko HP)

### Blok 5 — Widoczność mechanik
- [ ] U15 — Widoczne rany wroga w walce (tier + kara; "Ranny" dostaje −1)
- [ ] U16 — Cost preview (naprawa/reroll/wskrzeszenie/usługi) + pasek durability + komunikat anti-farm
- [ ] U17 — Celebracja dropu afiksowego + porównanie z założonym
- [ ] U18 — Dziennik gracza (Zadania / Wątki / Kronika; endpoint /journal; player_visible na seeds)
- [ ] U19 — Recap "Poprzednio…" po >24h przerwy
- [ ] U20 — Onboarding: death saves przy <25% HP, karta XP z instrukcją, karty durability/afiksy/napady/crafter

### Blok 6 — Lochy: stawka — ❌ WCHŁONIĘTE PRZEZ FAZĘ L (redesign 2026-06-12; nie wykonywać jako U)
- [ ] ~~U21~~ → FAZA L: L7 (semantyka checkpointów; UWAGA: śmierć=koniec runu zamiast restartu — zmiana względem pierwotnego U21)
- [ ] ~~U22~~ → FAZA L: L2/L4 (pre-roll hinty drzwi), L6 (no soft-locks, fallback braku kafelka)
- [ ] ~~U23~~ → FAZA L: L5 (absolutna skala D1–D5 po S2; bez max_scale — poziom wroga zamiast mnożnika)

### Blok 7 — Ekonomia: bezpieczniki
- [ ] U24 — Napad: ostrzeżenie + rzut obronny + próg biedy 50gp + max 1/24h
- [ ] U25 — Pity timer afiksów (3 bossy bez dropu → gwarancja; 3 rerolle bez zmiany → inny afiks)
- [ ] U26 — economy_log + centralna change_gold() + kafelek Ekonomia w admin Overview

### Blok 9 — Świat: hex ↔ lokacje ↔ ruch (audyt kodu 2026-06-11; wykonywać PO Bloku 3, PRZED Blokiem 4 — rdzeń gry)
- [x] U28 — Placement engine: terrain_tags + placement na game_locations; backend osadza lokacje przy odkryciu hexa; narzędzie admina dla floating — [#540](https://github.com/szmidtpiotr/ai-gm/issues/540)
- [x] U29 — Blok [ŚWIAT] dla LLM: hex + lokacje z opisami + NPC + sąsiedzi + kandydaci z bazy na żądanie; create tylko przy brak_dopasowania — [#541](https://github.com/szmidtpiotr/ai-gm/issues/541)
- [x] U30 — Ruch mechaniczny: POST /travel (klik mapy = podróż, intent MOVE rozstrzygany przed LLM, anty-desync guard, sync mapy po turze) — [#544](https://github.com/szmidtpiotr/ai-gm/issues/544)
- [x] U31 — Scena z bazy: ENTER_LOCATION ładuje scene_npcs/scene_enemies z location_*_assignments; sub-lokacje — [#546](https://github.com/szmidtpiotr/ai-gm/issues/546)
- [x] U32 — Travel pills z prawdziwych danych + eskalacja anty-stuck w UI (≥5 tur pille, ≥10 banner) — [#548](https://github.com/szmidtpiotr/ai-gm/issues/548)
- [x] U32b — 🎮 KAMIEŃ MILOWY: /game-smoke × 2 tryby po Bloku 9 — pierwszy kandydat na GRYWALNY (bez TDD, bez nowego issue — raporty do #512/#513, porównanie z runem U9b). Oczekiwane ✅: chk 2/3/4/9 (ruch hex, lokacje z bazy, NPC z przypisań, odpoczynek). Każde ❌ na chk 2/3/4 = defekt Bloku 9, naprawić PRZED Blokiem 4. Zaliczone = oba runy GRYWALNY lub Z ZASTRZEŻENIAMI wyłącznie przez P2.
  - **WYNIK 2026-06-13: ZALICZONY** — oba runy GRYWALNY Z ZASTRZEŻENIAMI (wyłącznie P2) po hotfixach HF-9/10/11. Historia:
    - [#549](https://github.com/szmidtpiotr/ai-gm/issues/549) P1 CP3 → **HF-9 [#551]** FIXED: legacy `wschodnia_wioska` (ai_generated=1) czyszczona, placement engine osadza lokację z bazy (ai_generated=0). Potwierdzone oba runy.
    - [#550](https://github.com/szmidtpiotr/ai-gm/issues/550) P1 CP11 → split: kill_enemy via /combat/resolve-attack **HF-10 [#552]** FIXED (combat_service hook); talk_to_npc/DIALOGUE → fix był w martwym kodzie (`process_v2_turn` nigdy nie wołany) → **HF-11 [#553]** FIXED: `auto_complete_talk_to_npc` w żywym torze (button DIALOGUE + free-text scene-NPC match) + `visit_location` w hex_travel. Potwierdzone live (kampania 64: first_combat ✅ + first_merchant ✅).
    - CP2 ✅, CP4 ✅ (gotowa), CP5/6/7/10 ✅; raport nowa-kampania → #512, gotowa-kampania → #513
    - Pozostałe P2 (nie blokują): REST intent nie triggerowany przy "odpoczywam" (nowa-kamp CP9); narracja "goblin"→"szlam"; desync current_location_id vs hex (start_64 vs brzezino, wątek U31-pochodny)

### Blok 8 — Brama do MP (zawsze ostatnie)
- [ ] U27 — docs/ACCEPTANCE_USABILITY.md + pełny re-playtest 3 trybów (w tym kryteria ruchu/lokacji z Bloku 9) → issue [GATE] Go/No-Go MP

---

## FAZA S — Skille i Stany (2026-06-12, rozszerzenie mechaniki) — po/przeplatane z FAZĄ U

> Pełne opisy zadań: `game_mechanics.md` CZĘŚĆ AI. Źródło danych: `skills_conditions_design_doc.md` (korzeń repo). Kolejność = sekcja "FAZA S — zależności i kolejność" w CZĘŚCI AI (S1→S4 → S5→S7 → [U10!] S8→S14 → S15→S19 → S20). Każde zadanie = GitHub Issue `[TASK] SNN — tytuł` wdrażane `/tdd`; wyjątek S20 = czysty playtest (bez TDD, raport do issue [SMOKE] FAZA S). Prompt startowy: `prompt_s.md`.

### Blok 1 — Fundament rzutu
- [ ] S1 — Margines sukcesu: 4 stopnie wyniku testu umiejętności (zmiana zablokowanej mechaniki — zgoda 2026-06-12)
- [ ] S2 — Staty wrogów: stats_json + archetypy + seed heurystyką (nadpisuje decyzję CZĘŚĆ AB)
- [ ] S3 — Staty NPC + lazy generation archetypu
- [ ] S4 — Testy przeciwne na prawdziwych statach (aktor-agnostycznie; podwalina MP)

### Blok 2 — Skille: batch danych + hooki
- [ ] S5 — Seed ~16 skilli kategorii A (czyste testy) + countery + keyword map U7
- [ ] S6 — Haggling: targowanie wpięte w ceny sklepu
- [ ] S7 — Gamble: hazard z prawdziwą stawką złota

### Blok 3 — Prymitywy efektów + kondycje parami — ⛔ WYMAGA U10
- [ ] S8 — Batch kondycji z istniejących klocków (on_fire, frozen, lite: confused/insane/panicked/charmed/cursed) + tag [APPLY_CONDITION]
- [ ] S9 — Prymityw stacking_levels + kondycja exhausted
- [ ] S10 — Prymityw escalating_dot + kondycja hemorrhage
- [ ] S11 — Prymityw reroll + inspired + cursed (pełny)
- [ ] S12 — Prymityw extra_action + on_expire_apply + kondycja hasted
- [ ] S13 — Prymityw on_zero_hp_save + kondycja blessed
- [ ] S14 — Prymityw condition_immunity + kondycja rage

### Blok 4 — Zaawansowane mechaniki bojowe (można PRZED Blokiem 3; S18 wymaga S8)
- [ ] S15 — System reakcji (pre-deklaracja) + skill dodge
- [ ] S16 — Reakcja shield_block
- [ ] S17 — Wrestling: skill nakłada kondycje wrogom (opposed STR vs STR)
- [ ] S18 — Prymityw behavior_override + pełne confused/berserk/panicked
- [ ] S19 — Kondycja hidden: untargetable + ambush_bonus

### Kamień milowy
- [ ] S20 — 🎮 Playtest FAZY S (Sandbox sweep + /game-smoke; raport do [SMOKE] FAZA S; bez TDD)

> Poza zakresem FAZY S (zapisane w CZĘŚCI AI): disease/broken_limb (zegar świata), crafting mechaniczny (trade_craft/alchemy = narracyjne), pełne charmed/insane, skutki inwentarzowe pickpocket/torture.

---

## FAZA L — Lochy kafelkowe (2026-06-12, redesign) — niezależna od U/S; wyjątek: L5 wymaga S2

> Pełne opisy zadań + 17 decyzji projektowych + tabela kolizji: `game_mechanics.md` CZĘŚĆ AJ. Jeden tryb lochów (kafelkowy, legacy usuwany), rozgałęziony graf przy wejściu, checkpointy po bossach, tryb nieskończony, mapa kafelkowa pod przyciskiem mapy. Kolejność = sekcja "FAZA L — zależności i kolejność" w CZĘŚCI AJ. Każde zadanie = GitHub Issue `[TASK] LNN — tytuł` wdrażane `/tdd`; wyjątki bez TDD: L14–L17 (kontent/batch, weryfikacja Piotra) i L19 (playtest, raport do [SMOKE] FAZA L). Prompt startowy: `prompt_l.md`. Wchłania U21–U23 (Blok 6 FAZY U) i H5 (FAZA 6).

### Blok 1 — Silnik grafu
- [ ] L1 — Konfiguracja kafelkowa lochu w DB + admin (tile_category_key, tile_count, boss_tile_id, endless_growth_n — dziś modal zbiera, baza nie zapisuje)
- [ ] L2 — Generator rozgałęzionego grafu + dungeon_run v2 (odnogi, fog, door hints, powtórki z re-rollem, positions per postać — podwalina MP)
- [ ] L3 — Wejście przez graf: /enter → tylko kafelki; 409 bez kategorii; blok [LOCH] w kontekście narratora (hybryda: opis z DB + koloryzacja LLM)
- [ ] L4 — Ruch przez drzwi: POST /dungeons/move + exit_conditions + deterministyczny start walki + backtracking

### Blok 2 — Mechaniki na kafelku
- [ ] L5 — Walka: absolutna skala D1–D5 (koniec rubber-bandingu; dawne U23) — ⛔ WYMAGA S2
- [ ] L6 — Skrzynie (rzut DEX, 3 próby, 30% pułapki), zagadki (3 próby + hinty), pułapki jako efekty, no soft-locks (dawne U22)
- [ ] L7 — Checkpointy + śmierć kończy run + porzucenie 50% cooldown (dawne U21; NADPISUJE E16-restart)
- [ ] L8 — Boss, loot, tryb nieskończony ("Wyjdź z łupem / Idź głębiej", segmenty +n, skalowanie cykli)

### Blok 3 — Czystka legacy
- [ ] L9 — Usunięcie trybu proceduralnego (kod + admin UI + testy legacy; seedy starych lochów is_active=0; DB bez destrukcji)

### Blok 4 — UI gracza
- [ ] L10 — Flaga dungeon_enabled dla graczy (admin toggle, default ON; egzekwowana w API i UI)
- [ ] L11 — Mapa kafelkowa: przycisk mapy w lochu pokazuje graf (odwiedzone obrazki + zarysy za drzwiami + marker pozycji)
- [ ] L12 — Wybór drzwi: przyciski kierunków pod composerem + klik na mapie + obraz kafelka w scenie + akcje skrzynia/zagadka
- [ ] L13 — Modale: śmierć / porzucenie / resume / wybór po bossie
- [ ] L13b — Wejście z ekranu startowego (bohater idle; scalenie trybów D9 w jeden "Loch")

### Blok 5 — Kontent: krypta (bez TDD; pilot → akceptacja → batch)
- [ ] L14 — Kategoria "krypta" + 20 definicji kafelków (mix drzwi 6/8/4/2-boss; wrogowie-nieumarli, zagadki, skrzynie)
- [ ] L15 — Nowy BASE_PROMPT (bogate narysowane wnętrza, 768px) + scripts/generate_tiles_batch.py; pilot 5 obrazków → akceptacja Piotra → pełny batch
- [ ] L16 — Opisy PL kafelków (batch + przegląd Piotra; paliwo narratora) + loch pilotażowy krypta_probna (realizuje H5)
- [ ] L17 — Kolejne kategorie (goblińskie tunele, ruiny…) — ⛔ PO L19; per kategoria powtórka L14–L16

### Blok 6 — Weryfikacja
- [ ] L18 — Playwright: regresja lochu end-to-end (wejście→walka→drzwi→zagadka→boss→endless→wyjście + mapa)
- [ ] L19 — 🎮 KAMIEŃ MILOWY: playtest lochu (2 cykle endless, śmierć z checkpointem, porzucenie, mobile; raport do [SMOKE] FAZA L; bez TDD)

> Poza zakresem FAZY L (zapisane w CZĘŚCI AJ): multiplayer w lochach (tylko kształt danych), rotacja kafelków, leaderboard endless, przedmioty dungeon-exclusive (kontent), pełny podsystem pułapek (wykrywanie/rozbrajanie).

---

## FAZA 5 — Multiplayer (sesja projektowa 2026-06-12 — decyzje w game_mechanics.md CZĘŚĆ AC)

> ⛔ Start dopiero po U27 (go/no-go) **ORAZ po wdrożeniu FAZY L (lochy)** — ostatnia faza gameplay w kolejce (decyzja 2026-06-12). Pełne opisy zadań + decyzje projektowe: `game_mechanics.md` CZĘŚĆ AC. Wyjątek: G20 (eksport-książka) można prototypować wcześniej — wymaga tylko H4 (Ollama na .170) i historii kampanii, działa też dla solo.

- [ ] G16 — Wybór postaci przy zaproszeniu + bohater w wielu kampaniach naraz (rozwój wspólny: poziom/XP/staty/złoto/ekwipunek; stan per kampania: HP/mana/kondycje/pozycja) — fundament modelu danych
- [ ] G1 — Timer enforcement — background sweep co ~30s (domknij rundę po deadline)
- [ ] G2 — Absencja: token [BRAK AKCJI], licznik ostrzeżeń, reset po powrocie; 3 ostrzeżenia → propozycja vote-kick
- [ ] G3 — Vote-to-kick ręczny (większość pozostałych graczy; host niewyrzucalny; 2-os = host wyrzuca sam) + zastępstwo w trakcie kampanii
- [ ] G4 — World State integracja MP (jeden żeton drużyny, współdzielony stan)
- [ ] G5 — Conflict resolution: inicjatywa jako kolejność, "Cel już martwy/zabrany"
- [ ] G6 — Ruch drużyny: głosowanie hex (host bez veta nad zgodną wolą); remis rozstrzyga host (zmiana 2026-06-12)
- [ ] G7 — Walka MP — reuse silnika turowego solo; brak reakcji w 2 min = akcja domyślna (obrona)
- [ ] G8 — Rzuty dwustopniowe: LLM planuje testy → kod rzuca → LLM narruje z wynikami ("🎲 Zwinność: 14 vs DC 12 ✓")
- [ ] G9 — Timer walki skrócony (2 min) + push "Twoja kolej" per tura
- [ ] G17 — Powalenie zamiast śmierci: ocucenie ~25% HP, auto-wstanie po wygranej; wipe = kara złota 10/20/30% wg śr. poziomu drużyny (próg 50 zł, przebudzenie 50% HP w bezpiecznym hexie; nigdy przedmioty/XP)
- [ ] G10 — Loot per-gracz z filtrem klasy + złoto dzielone równo
- [ ] G18 — Streszczenia piętrowe rund MP (świeże rundy → streszczenia rund → rozdziały co ~10 rund; w DB)
- [ ] G11 — Catch-up po powrocie (narracje pominiętych rund)
- [ ] G12 — Spóźnialscy: wprowadzenie narracyjne + start bez pełnej drużyny
- [ ] G13 — Kick → bohater do `idle` z zachowaniem XP/złota/przedmiotów
- [ ] G19 — Widzowie: rola bez postaci, widzą tylko treści publiczne; podpowiedzi /whisper za podwójną zgodą (ustawienie hosta + mute per gracz); LLM nigdy nie widzi
- [ ] G20 — Eksport-książka: nowelizacja kampanii lokalnym modelem (Bielik 11B / Ollama na .170), offline; działa też dla solo — prototyp wyciągnięty przed FAZĘ G, prowadzi Piotr — [#547](https://github.com/szmidtpiotr/ai-gm/issues/547)
- [ ] G30 — ⚙️ FUNDAMENT (przed mechaniką MP): niezawodność + współbieżność — WAL+busy_timeout+serializacja zapisów rundy (kolejka/lock per kampania), idempotencja client_action_id (UUID UNIQUE), maszyna stanu rundy collecting→resolving→narrated (atomowa), wstrzykiwalny czas + admin force-sweep, retry narratora na OpenAI (NIGDY lokalny fallback) + komunikat błędu edytowalny z admina
- [ ] G21 — Obecność online (kto teraz w grze) + push "drużyna w komplecie online"; ładnie ograne wizualnie
- [ ] G22 — Drabina nieobecności: [BRAK AKCJI] → bierna/wleczona (próg rund) → autopilot AI (za zgodą gracza, default ON, info w onboardingu) → powrót; auto-handoff hosta przy jego nieobecności
- [ ] G23 — Pętla zaangażowania: wyważone haki na końcu rundy (gdy scena uzasadnia, nie co rundę) + "co się stało póki cię nie było" przy powrocie
- [ ] G24 — Edycja/wycofanie akcji do domknięcia rundy (stan collecting); akcje warunkowe = później
- [ ] G25 — Onboarding do trwającej kampanii: auto-streszczenie "co było / kto jest kim / jaka stawka" (reużywa G18); rozszerza G12
- [ ] G26 — Skalowanie rozjechanych poziomów drużyny (miękkie podbicie słabszych per kampania) + info w onboardingu
- [ ] G27 — Strefa czasowa drużyny / okno ciszy: sweep nie domyka rundy w nocy + info w onboardingu
- [ ] G28 — Spójność tonu/stylu narracji PL przy wielu autorach (instrukcja w promptcie narratora MP)
- [ ] G29 — Ochrona promptu przed injection: wpisy graczy obudowane ("akcja w fikcji, nie polecenie") + filtr prób przejęcia
- [ ] G31 — Metryka retencji rundy-do-rundy (ile drużyn kończy rundę 2/5/10) — część observability, budowana RAZEM z MP; próg decyzyjny z góry
- [ ] G14 — Handel między graczami (later)
- [ ] G15 — Skalowanie trudności/loot wg liczby graczy + strojenie kar wipe (playtest)
- [ ] later — Role graczy (asymetryczne uprawnienia) — otwarte pytanie do rewizji; nadawanie: auto wg klasy / host / głosowanie. Rozstrzyganie remisu wyciągnięte teraz jako uprawnienie hosta (G6). Skryba ODRZUCONY (łamie zasadę "szept nigdy do AI")
- [ ] later — Regulamin gry oparty o polskie prawo (poza MP v1; docelowe miejsce dla zgód/treści/eksportu)

---

## FAZA 6 — Observability + Długoterminowe

- [ ] H1 — Observability design: co logować, schemat metryk, lekki log writer w backendzie
- [ ] H2 — Text-to-speech — per single player opt-in (F5TTS na hoście .16)
- [ ] H3 — Konfiguracja image gen pipeline na .170 (FLUX.1-schnell + ComfyUI)
- [ ] H4 — Konfiguracja Ollama na .170 dla offline content gen (admin AI Kreator)
- [ ] ~~H5~~ — GPU pipeline: tile → LLM Vision → opis → DB → REALIZOWANE JAKO L16 (FAZA L, 2026-06-12)

---

## FADM — Przebudowa Admin Panelu (strangler-fig) ✅ KOMPLETNE 2026-06-09

Monolit `admin_panel_v3` (19 447 linii) → modularny `frontend/admin/` (14 sekcji ES). P0-P17 kompletne. admin3 usunięty; `/admin3/` → 301 → `/admin/`. Epic [#401](https://github.com/szmidtpiotr/ai-gm/issues/401).

- [x] FADM-P0 — Bootstrap skorupy `admin/` + shared utils (api/table/toast/modal/form) — [#402](https://github.com/szmidtpiotr/ai-gm/issues/402) ✅ 2026-06-08
- [x] FADM-P1 — Port sekcji overview — [#403](https://github.com/szmidtpiotr/ai-gm/issues/403) ✅ 2026-06-08
- [x] FADM-P2 — Port sekcji mechanics — [#404](https://github.com/szmidtpiotr/ai-gm/issues/404) ✅ 2026-06-08
- [x] FADM-P3 — Port sekcji content (+ D5 item VIEW) — [#405](https://github.com/szmidtpiotr/ai-gm/issues/405) ✅ 2026-06-08
- [ ] FADM-P4 — Port sekcji world (+ D7 encountery) — [#406](https://github.com/szmidtpiotr/ai-gm/issues/406) **← następne**
- [ ] FADM-P5 — Port sekcji map — [#407](https://github.com/szmidtpiotr/ai-gm/issues/407)
- [ ] FADM-P6 — Port sekcji campaigns (+ B6/B7/D6) — [#408](https://github.com/szmidtpiotr/ai-gm/issues/408)
- [ ] FADM-P7 — Port sekcji dungeons — [#409](https://github.com/szmidtpiotr/ai-gm/issues/409)
- [x] FADM-P8 — ⏭ RETROAKTYWNIE ANULOWANY (Forge portowano w P14; pierwotny skip cofnięty) — [#410](https://github.com/szmidtpiotr/ai-gm/issues/410)
- [x] FADM-P9 — Port sekcji players — [#411](https://github.com/szmidtpiotr/ai-gm/issues/411)
- [x] FADM-P10 — Port sekcji tools (sandbox/Playwright/Inspector) — [#412](https://github.com/szmidtpiotr/ai-gm/issues/412)
- [x] FADM-P11 — Port sekcji system (LLM presety + config) — [#413](https://github.com/szmidtpiotr/ai-gm/issues/413)
- [x] FADM-P12 — Port sekcji drobnych (invites/push/bugreports) — [#414](https://github.com/szmidtpiotr/ai-gm/issues/414)
### FADM-P13..P17 — domknięcie modularności + usunięcie admin3 (strangler, krok po kroku)
- [x] FADM-P13 — Port ekranu logowania admina do modularnego shella — [#449](https://github.com/szmidtpiotr/ai-gm/issues/449)
- [x] FADM-P14 — Port Forge (Kuźnia) → `sections/forge.js` — [#450](https://github.com/szmidtpiotr/ai-gm/issues/450)
- [x] FADM-P15 — Anti-grób: usuń Forge z monolitu + rewire bounce/banner — [#451](https://github.com/szmidtpiotr/ai-gm/issues/451) _(zależy P13+P14)_
- [x] FADM-P16 — Migracja testów Playwright admin3 → /admin/ — [#452](https://github.com/szmidtpiotr/ai-gm/issues/452) _(zależy P14)_
- [x] FADM-P17 — Decommission admin3 (pliki + nginx + redirects + CLAUDE.md) — [#453](https://github.com/szmidtpiotr/ai-gm/issues/453) ✅ 2026-06-09

---

## Zrobione dodatkowe

Standalone bugixy i feature'y spoza głównej architektury A-H.

- [x] [#372](https://github.com/szmidtpiotr/ai-gm/issues/372) — Opening scene zawsze w lesie: wyodrębniono `build_opening_plan_context()` + 16 testów TDD — commit 88c1d9a
- [x] [#397](https://github.com/szmidtpiotr/ai-gm/issues/397) — Opening scene zawsze "budzisz się w lochu": system_prompt OTWARCIE SESJI dopuszcza miasta/tawerny, zakaz tropu przebudzenia — commit 635b72f
- [x] [#398](https://github.com/szmidtpiotr/ai-gm/issues/398) — Header HP bar 50% mimo 30/30: enterGame() woła updateHeaderStats() — commit 635b72f
- [x] [#389](https://github.com/szmidtpiotr/ai-gm/issues/389) — LLM 429 TPM rate-limit: retry z backoffem w OpenAIDriver.generate_stream (max 3 próby, retry-after header)
- [x] [#390](https://github.com/szmidtpiotr/ai-gm/issues/390) — Zegar in-game nie tykał: advance_clock() dostał minutes= keyword + sub-hour accumulation
- [x] [#355](https://github.com/szmidtpiotr/ai-gm/issues/355) — C1 STORY_STALE nie działał w streaming path + escalation (10+ silniej, 15+ kritycznie) — commit 3eb0c2c
- [x] [#391](https://github.com/szmidtpiotr/ai-gm/issues/391) — C1 TRAVEL_HINT pills: sugestie odkrytych lokacji obok STORY_STALE (TDD, 4/4 GREEN) — commit 69044c0 — Playwright regression GREEN z prawdziwym LLM (OpenAI)
- [x] [#392](https://github.com/szmidtpiotr/ai-gm/issues/392) — LLM narrative death bez HP check: [RESTRICT] blok w system_prompt (TDD, 3/3 GREEN) — commit 1806324 — Playwright regression GREEN z prawdziwym LLM (OpenAI)
- [x] [#395](https://github.com/szmidtpiotr/ai-gm/issues/395) — Aktywny preset LLM jako jedyne źródło prawdy: spójna tożsamość endpointu (provider+base_url+model z jednego źródła), leniwa hydratacja presetu w świeżych procesach, `LLMConfigError` zamiast cichego fallbacku do Ollama/gemma (TDD, 8/8 GREEN) — commit 526cfdd — zweryfikowane, zamknięte
- [ ] #C-acc — Acceptance harness C1–C19 (pytest 13/13 + Playwright LLM-play) — `scripts/acceptance_c_series.sh`, `docs/ACCEPTANCE_C_SERIES.md` — commit 687f7ed; RED backlog: C9 (modal Ucz się), C10/C11 (questy)
- [x] [#396](https://github.com/szmidtpiotr/ai-gm/issues/396) — Admin3 Narzędzia→Playwright odpala wszystkie suity ux (regression/acceptance/admin3); test-agent skan rekursywny + run po ścieżce/grupie; nowy admin3 smoke 16/16 GREEN — commit 6058f90 (TDD 7/7 GREEN)
- [ ] [#400](https://github.com/szmidtpiotr/ai-gm/issues/400) — Admin spectator + resume: admin z player frontendu widzi WSZYSTKIE kampanie (dropdown wyboru usera, default własny), podgląda read-only i wznawia (re-attach bohatera z historii tur + aktywacja). Endpointy gated is_admin. TDD 7/7 + Playwright. Bug po drodze: campaigns.updated_at nie istnieje → created_at (awaits-testing)
- [x] [#393](https://github.com/szmidtpiotr/ai-gm/issues/393) — Playwright panel w admin3 Narzędzia: lista speców, live SSE stream, /playwright-specs + /playwright-run endpointy (TDD 7/7 GREEN)
- [x] [#415](https://github.com/szmidtpiotr/ai-gm/issues/415) — Brakujące endpointy mapy: /hex-terrain-config, POST /generate, DELETE /clear, /locations-map (TDD 11/11 GREEN)
- [x] [#456](https://github.com/szmidtpiotr/ai-gm/issues/456) — SB-2: Stan Świata zawsze pusty — scene_enemies/player_conditions nigdy nie aktualizowane; fix: initiate_combat() → set_world_state_flags(scene_enemies), end_combat() → clear, auto_save_snapshot() → _sync_player_conditions() (TDD 4/4 GREEN + Playwright 2/2)
- [x] [#457](https://github.com/szmidtpiotr/ai-gm/issues/457) — SB-3/SB-4: keyword scan nadpisuje SKILL_TEST_PENDING; guard przed skanem w create_turn + stream; fix is_admin w slash_registry_key_for_dispatch (TDD 2/2 GREEN)
- [x] [#458](https://github.com/szmidtpiotr/ai-gm/issues/458) — SB-5: test umiejętności zablokowany po committed_d20; SB-3/SB-4 guard rozszerzony o inline auto-resolve gdy committed_d20 ustawione; backward compat zachowany (TDD 4/4 GREEN + Playwright 2/2)
- [x] [#455](https://github.com/szmidtpiotr/ai-gm/issues/455) — SB-1: Znajomi NPC tab 404; endpoint GET /admin/campaigns/{id}/known-npcs dodany (impl 492cc65, TDD 9/9 GREEN + Playwright 3/3)
- [x] [#459](https://github.com/szmidtpiotr/ai-gm/issues/459) — E19b: Dungeon tile AI prompt generator — 2 endpointy (generate-image-prompt + ai-create) + 2 przyciski UI + bugfix call_type w 3 miejscach (TDD 10/10 GREEN + Playwright 3/3)
- [x] [#460](https://github.com/szmidtpiotr/ai-gm/issues/460) — E19c: Compositor redesign — cienka ramka 5px + flat amber drzwi-markery + endpoint generate-description (TDD 13/13 GREEN + Playwright 3/3)
- [x] [#485](https://github.com/szmidtpiotr/ai-gm/issues/485) — Effect JSON Builder UI w sekcji Zawartość (Broń/Zbroja/Przedmioty): builder efektów identyczny jak w Afiksach; 15 testów TDD weryfikujących wszystkie 6 typów F1 + Playwright 3/3 GREEN — commit (po budowaniu)
- [x] [#504](https://github.com/szmidtpiotr/ai-gm/issues/504) — C10 QUEST_SUGGEST: fix non-streaming path — błędny import (`xp_sources` → `narrative_state_service`) + brakujący C10 block w non-streaming turns; aktywne questy teraz zapisywane i widoczne w World State; testy 5/5 GREEN + Playwright 2/2 GREEN — commit 5f16534
- [x] [#516](https://github.com/szmidtpiotr/ai-gm/issues/516) — SMOKE P1: brak tabeli character_rentals — dodano CREATE TABLE do ADMIN_MIGRATIONS (F13 migracja była tylko w teście, nie w bazie) — commit 7cb70e1
