# AI-GM — Master Task Checklist
_Ostatnia aktualizacja: 2026-06-10 (F1 #461 KOMPLETNE; F2 #462 Affix loot roll KOMPLETNE; F2b #484 Enemy loot_tier drop affixes KOMPLETNE; F3 #463 Affix Builder KOMPLETNE)_

Pełna lista tasków z `game_mechanics.md` CZĘŚĆ 7. Aktualizuj `[x]` po weryfikacji na DEV.

**Schemat kodów:** A=Faza -1 | B=Faza 0 | C=Faza 1 | D=Faza 2 | E=Faza 3 | F=Faza 4 | G=Faza 5 (MP) | H=Faza 6

| Faza | Ukończone | Total |
|------|-----------|-------|
| A (Faza -1) | 13/13 | 100% ✅ |
| B (Faza 0) | 7/7 | 100% ✅ |
| C (Faza 1) | 19/19 | 100% ✅ |
| D (Faza 2) | 14/14 | 100% ✅ |
| E (Faza 3) | 27/28 | 96% ⚠️ W TOKU (E1–E26+E28 ✅, E27 deferred) |
| F (Faza 4) | 4/21 | 19% (F1✅ F2✅ F2b✅ F3✅ F4✅) |
| G (Faza 5 MP) | 0/15 | 0% |
| H (Faza 6) | 0/5 | 0% |
| **FADM (admin rebuild)** | 18/18 | 100% ✅ KOMPLETNE (strangler fig zakończony) |
| **TOTAL** | **89/140** | **64%** |

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
- [ ] E27 — Karty dla nowych mechanik (afiksy, crafting, MP) — gdy systemy gotowe (Faza 4+) — [#442](https://github.com/szmidtpiotr/ai-gm/issues/442)
- [x] E28 — Tutorial kampania "Moja Pierwsza Przygoda" (domyślnie ON, Pomiń, instrukcje LLM) — [#443](https://github.com/szmidtpiotr/ai-gm/issues/443)

---

## FAZA 4 — Rozbudowa: Efekty, Afiksy, Ekonomia

- [x] F1 — Unified Effects System — effect_json → typed Effect Objects (schema, silnik, LLM DSL) — [#461](https://github.com/szmidtpiotr/ai-gm/issues/461) — ✅ KOMPLETNE: `damage_bonus` (F1a) + `heal_on_hit` (life-steal, on-hit) + `ac_bonus` (combat-start) + `apply_condition` (on-hit, de-dup) + `static_stat_modifier` (combat-start stats dict) + F1b backward compat + F1d DSL (Smart Entry prompt). 18/18 tests GREEN.
- [x] F2 — Affix System — game_config_affixes + affixes_json na inventory row + loot engine — [#462](https://github.com/szmidtpiotr/ai-gm/issues/462) — ✅ commit 35b864b: `roll_weapon_affixes()` per loot_tier (poor=0, standard=1×T1, rich=2×T1-T2, treasure=3×T1-T3); `grant_loot_to_character` + `grant_dungeon_loot` przyjmują `loot_tier`; dungeon run instance zawiera `loot_tier`; 10 testów pytest + 3 Playwright GREEN.
- [x] F2b — Enemy drop affixes — `loot_tier` na `game_config_enemies` → afiksy na broniach z dropów wrogów — [#484](https://github.com/szmidtpiotr/ai-gm/issues/484) — ✅ commit 2c7dfc1: migracja `loot_tier TEXT DEFAULT NULL`; combatant dict + `_preview_loot_from_roll_items` przechowuje `enemy_loot_tier`; `claim_post_combat_loot` przekazuje do `grant_loot_to_character`; backward compat (NULL = brak afiksów); 9 testów pytest + 3 Playwright GREEN.
- [x] F3 — Admin buildery afiksów i efektów (wizualny UI, nie ręczny JSON) — [#463](https://github.com/szmidtpiotr/ai-gm/issues/463) — ✅ commit db7c638: POST/PATCH/DELETE /api/admin/affixes + zakładka Afiksy w Zawartość + Effects Builder (dropdown typów); 8 testów pytest + 4 Playwright GREEN
- [x] F4 — `[SPEND_GOLD:X]` tag z tabeli/configu (NIE z LLM) — [#464](https://github.com/szmidtpiotr/ai-gm/issues/464) — ✅ commit 100cbef: `build_refusal_text()` + `apply_spend_gold_to_narrative()`; narracja odmowy przy braku złota; non-stream path fixed (tagi leciały do gracza); 8 seed rows game_config_services; 10/10 pytest GREEN
- [ ] F5 — Wskrzeszenie jako gold sink (włączenie + konfiguracja gold_percent) — [#465](https://github.com/szmidtpiotr/ai-gm/issues/465)
- [ ] F6 — Sink afiksów: NPC is_crafter, nałóż/reroll (T1=150g, T2=500g, T3=1200g) — [#466](https://github.com/szmidtpiotr/ai-gm/issues/466)
- [ ] F7 — Trwałość (durability): punktowa per cios, penalty przy 0, naprawa tier_rate — [#467](https://github.com/szmidtpiotr/ai-gm/issues/467)
- [ ] F8 — Napady: encounter kradnący % złota przy porażce/zaskoczeniu — [#468](https://github.com/szmidtpiotr/ai-gm/issues/468)
- [ ] F9 — Dynamiczny asortyment sklepu (lokacja + poziom gracza) — [#469](https://github.com/szmidtpiotr/ai-gm/issues/469)
- [ ] F10 — CHA na kupno — bonus/malus przy zakupach (nie tylko sprzedaży) — [#470](https://github.com/szmidtpiotr/ai-gm/issues/470)
- [ ] F11 — Unifikacja ceny → jeden price_gp + wycena egzemplarza z afiksami — [#471](https://github.com/szmidtpiotr/ai-gm/issues/471)
- [ ] F12 — Anti-farm: malejąca cena sprzedaży przy spam-sprzedaży tego samego type — [#472](https://github.com/szmidtpiotr/ai-gm/issues/472)
- [ ] F13 — Background expire wynajmu — sweep wygasłych tymczasowych bonusów — [#473](https://github.com/szmidtpiotr/ai-gm/issues/473)
- [ ] F14 — Usunięcie martwego economy_service (generate_combat_loot / claim_loot) — [#474](https://github.com/szmidtpiotr/ai-gm/issues/474)
- [ ] F15 — Balans walki → mikstury potrzebne (playtest + tuning DC/damage) — [#475](https://github.com/szmidtpiotr/ai-gm/issues/475)
- [ ] F16 — Balans całości (ceny/dropy/sinki) — pełny playtest — [#476](https://github.com/szmidtpiotr/ai-gm/issues/476)
- [ ] F17 — Hidden Trait system (LLM z puli, trigger kontekstowy, reveal narracyjny) — [#477](https://github.com/szmidtpiotr/ai-gm/issues/477)
- [ ] F18 — Rosnące progi XP konfigurowalne z Admin Panelu — [#478](https://github.com/szmidtpiotr/ai-gm/issues/478)
- [ ] F19 — Globalne stany NPC — śmierć NPC między kampaniami (is_dead globalny) — [#479](https://github.com/szmidtpiotr/ai-gm/issues/479)
- [ ] F20 — Mechaniczne efekty pory dnia (noc/świt bonusy z game_config) — [#480](https://github.com/szmidtpiotr/ai-gm/issues/480)
- [ ] F21 — World State History UI admina (zakładka + diff między turami) — [#481](https://github.com/szmidtpiotr/ai-gm/issues/481)

---

## FAZA 5 — Multiplayer

- [ ] G1 — Timer enforcement — background sweep co ~30s (domknij rundę po deadline)
- [ ] G2 — Absencja: token [BRAK AKCJI], licznik ostrzeżeń, reset po powrocie
- [ ] G3 — Vote-to-kick + auto-kick 2-os + zaproszenie zastępstwa
- [ ] G4 — World State integracja MP (jeden żeton drużyny, współdzielony stan)
- [ ] G5 — Conflict resolution: inicjatywa jako kolejność, "Cel już martwy/zabrany"
- [ ] G6 — Ruch drużyny: głosowanie hex (wszyscy głosują, host bez veta)
- [ ] G7 — Walka MP — reuse silnika turowego solo
- [ ] G8 — Auto-roll kości przez kod w rundzie MP
- [ ] G9 — Timer walki skrócony (2 min) + push "Twoja kolej" per tura
- [ ] G10 — Loot per-gracz z filtrem klasy + złoto dzielone równo
- [ ] G11 — Catch-up po powrocie (narracje pominiętych rund)
- [ ] G12 — Spóźnialscy: wprowadzenie narracyjne + start bez pełnej drużyny
- [ ] G13 — Kick → bohater do `idle` z zachowaniem XP/złota/przedmiotów
- [ ] G14 — Handel między graczami
- [ ] G15 — Skalowanie trudności/loot wg liczby graczy (playtest)

---

## FAZA 6 — Observability + Długoterminowe

- [ ] H1 — Observability design: co logować, schemat metryk, lekki log writer w backendzie
- [ ] H2 — Text-to-speech — per single player opt-in (F5TTS na hoście .16)
- [ ] H3 — Konfiguracja image gen pipeline na .170 (FLUX.1-schnell + ComfyUI)
- [ ] H4 — Konfiguracja Ollama na .170 dla offline content gen (admin AI Kreator)
- [ ] H5 — GPU pipeline: tile → LLM Vision → opis → DB (dungeon tiles offline)

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
