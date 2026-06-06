# AI-GM — Master Task Checklist
_Ostatnia aktualizacja: 2026-06-06 (Faza -1 A1+A12 committed)_

Pełna lista tasków z `game_mechanics.md` CZĘŚĆ 7. Aktualizuj `[x]` po weryfikacji na DEV.

**Schemat kodów:** A=Faza -1 | B=Faza 0 | C=Faza 1 | D=Faza 2 | E=Faza 3 | F=Faza 4 | G=Faza 5 (MP) | H=Faza 6

| Faza | Ukończone | Total |
|------|-----------|-------|
| A (Faza -1) | 13/13 | 100% ✅ |
| B (Faza 0) | 7/7 | 100% ✅ |
| C (Faza 1) | 0/18 | 0% |
| D (Faza 2) | 0/13 | 0% |
| E (Faza 3) | 0/28 | 0% |
| F (Faza 4) | 0/21 | 0% |
| G (Faza 5 MP) | 0/15 | 0% |
| H (Faza 6) | 0/5 | 0% |
| **TOTAL** | **20/120** | **17%** |

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

- [x] B1 — Tabela `world_state_snapshots` (campaign_id, turn_number, state_json) — commit 6579e9a
- [x] B2 — Rozbudowa session_flags: scene_enemies, scene_npcs, active_quests, player_conditions — commit c7db68d
- [x] B3 — Gate Mechaniki — middleware walidujący akcje gracza PRZED LLM — commit c7db68d
- [x] B4 — Parser intencji gracza (ATTACK/MOVE/TALK/REST → walidacja przez Gate) — commit c7db68d
- [x] B5 — Auto-zapis snapshotu World State po każdej turze narracyjnej — commit 48ce52b
- [x] B6 — Admin UI — World State History (zakładka w Campaign Monitor, diff między turami) — commit 48ce52b
- [x] B7 — DEV Inspector — panel diagnostyczny dla adminów (intent + gate + world state per kampania) — commit e9f29c3

---

## FAZA 1 — Rdzeń pętli (core loop)

- [ ] C1 — Fix Bug 1 — LLM musi sugerować ruch hex po N turach bez zmiany lokacji — [#355](https://github.com/szmidtpiotr/ai-gm/issues/355)
- [ ] C2 — Walidacja ruchu mechaniczna (nowy hex, terrain, lokacja check, update World State) — [#356](https://github.com/szmidtpiotr/ai-gm/issues/356)
- [ ] C3 — Fix Bug 2 — Gate walki (scene_enemies check przed każdym ATTACK) — [#357](https://github.com/szmidtpiotr/ai-gm/issues/357)
- [ ] C4 — Unifikacja wound_penalty: refactor z sheet-only na hp_current/hp_max — [#360](https://github.com/szmidtpiotr/ai-gm/issues/360)
- [ ] C5 — Symetria ran: wound_penalty dla wrogów (nie tylko gracza) — [#358](https://github.com/szmidtpiotr/ai-gm/issues/358)
- [ ] C6 — Ujednolicenie progów ran frontend/backend — [#359](https://github.com/szmidtpiotr/ai-gm/issues/359)
- [ ] C7 — XP Spend — endpoint spend_skill (wszystkie archetypy) — [#361](https://github.com/szmidtpiotr/ai-gm/issues/361)
- [ ] C8 — XP Spend — endpoint spend_stat (wszystkie archetypy) — [#362](https://github.com/szmidtpiotr/ai-gm/issues/362)
- [ ] C9 — UI długiego odpoczynku — modal "Ucz się" (lista zakupów XP) — [#363](https://github.com/szmidtpiotr/ai-gm/issues/363)
- [ ] C10 — System questów — QUEST_SUGGEST tag + walidacja backend — [#364](https://github.com/szmidtpiotr/ai-gm/issues/364)
- [ ] C11 — Mechaniczne śledzenie postępu questów (auto-complete per akcja) — [#365](https://github.com/szmidtpiotr/ai-gm/issues/365)
- [ ] C12 — `[SPEND_GOLD:X]` tag — kwota z tabeli/configu, NIE z LLM — [#366](https://github.com/szmidtpiotr/ai-gm/issues/366)
- [ ] C13 — Instrukcja "tylko złoto GP" w system_prompt (usunięcie waluty srebrnej) — [#367](https://github.com/szmidtpiotr/ai-gm/issues/367)
- [ ] C14 — Hero-first fix: startCharacterWizard() tylko z Heroes screen — [#368](https://github.com/szmidtpiotr/ai-gm/issues/368)
- [ ] C15 — Error boundary dla API failures (toast zamiast białego ekranu) — [#369](https://github.com/szmidtpiotr/ai-gm/issues/369)
- [ ] C16 — Delete confirmation modals (kampania, postać) — [#370](https://github.com/szmidtpiotr/ai-gm/issues/370)
- [ ] C17 — Kontekst ekwipunku postaci — injection listy przedmiotów i złota do LLM per tura — [#373](https://github.com/szmidtpiotr/ai-gm/issues/373)
- [ ] C18 — Fix Bug 3: kampanie startują na istniejących hexach, nie nowych obrzeżach — [#374](https://github.com/szmidtpiotr/ai-gm/issues/374)

---

## FAZA 2 — Systemy + Narracja

- [ ] D1 — Pending flow przedmiotów (GRANT_ITEM nieznanego klucza → auto-screen → pending=true)
- [ ] D2 — Pending flow wrogów (analogicznie do D1)
- [ ] D3 — NPC pamięć w World State (NPC_MEMORY tag → context injection przy kolejnej wizycie)
- [ ] D4 — Auto-screening admin queue (Poziom 1 tech validation + Poziom 2 LLM scoring)
- [ ] D5 — Item VIEW — podgląd przedmiotu w inventory (tooltip/modal)
- [ ] D6 — Narracja: tagi, parsery, Narrative State struktura
- [ ] D7 — Encountery generyczne (adventure_hooks + gameconfig_encounter_templates unifikacja)
- [ ] D8 — Ekran profilu gracza (konto, znajomi, ustawienia LLM)
- [ ] D9 — Ekran kampanii — 5 trybów (Nowa/Gotowa/Loch/Loch-kafelki/Multiplayer)
- [ ] D10 — Onboarding animacja + wybór motywu (nowy gracz)
- [ ] D11 — Confirm password na rejestracji
- [ ] D12 — Szybka nawigacja Hub → Gra (bez przeładowania)
- [ ] D13 — Mobile layout — weryfikacja responsywności wszystkich ekranów

---

## FAZA 3 — Jakość + Treść

- [ ] E1 — Player HUD (HP/Mana, Złoto, Questy, XP bar, Czas) — aktualizacja per tura
- [ ] E2 — Kreator bohatera — tooltips (archetyp, statystyki, umiejętności z przykładami)
- [ ] E3 — Ekran zakończenia kampanii (podsumowanie + LLM epitafium)
- [ ] E4 — Ekran śmierci (epitafium + statystyki + Wskrześ/Nowy bohater)
- [ ] E5 — Zamknięcie dostępu do kampanii martwego bohatera (hero_status=dead)
- [ ] E6 — Narracja: kompresja, historia, tagi narracyjne
- [ ] E7 — Rozbudowa `campaign_templates` (required_npc_keys, required_beats, player_visible)
- [ ] E8 — Ekran wyboru gotowej kampanii dla gracza (karty, trudność, opisy)
- [ ] E9 — Story Gravity: trigger = next_required_beat nie odpalony przez N tur
- [ ] E10 — Forge: walidacja wymaganych NPC/lokacji przy publikacji szablonu
- [ ] E11 — Template Narrative State pre-seeding
- [ ] E12 — Workflow publikacji szablonów (draft → review → published)
- [ ] E13 — Encountery generyczne — rozbudowa puli adventure_hooks
- [ ] E14 — Skalowanie encounterów per poziom gracza
- [ ] E15 — Snapshot stanu przy wejściu do lochu
- [ ] E16 — Przywróć snapshot przy śmierci w lochu + restart
- [ ] E17 — Rarity tierów loot w lochach (5 tierów)
- [ ] E18 — Cooldown UI lochów w Admin Panelu
- [ ] E19 — LLM Vision: obrazek → opis kafelka (task na maszynie .170)
- [ ] E20 — Admin UI tile manager (obrazki, drzwi, opisy kafelków)
- [ ] E21 — Wejście do lochu z mapy hex kampanii
- [ ] E22 — Resume niedokończonego runu lochu
- [ ] E23 — Seen_mechanics tracking per gracz
- [ ] E24 — Backend trigger kart onboarding (first mechanic occurrence)
- [ ] E25 — Karty onboarding UI (nieblokujące overlay, "Rozumiem")
- [ ] E26 — Biblioteka kart (gracz może wrócić do przeczytanych)
- [ ] E27 — Karty dla nowych mechanik (afiksy, crafting, MP) — gdy systemy gotowe
- [ ] E28 — Tutorial kampania "Moja Pierwsza Przygoda"

---

## FAZA 4 — Rozbudowa: Efekty, Afiksy, Ekonomia

- [ ] F1 — Unified Effects System — przepisanie effect_json na typed objects
- [ ] F2 — Affix System — game_config_affixes + affixes_json na inventory row
- [ ] F3 — Admin buildery afiksów i efektów
- [ ] F4 — `[SPEND_GOLD:X]` tag z tabeli/configu (jeśli nie w Fazie 1)
- [ ] F5 — Włączenie + konfiguracja wskrzeszenia jako gold sink
- [ ] F6 — Sink afiksów: NPC is_crafter, nałóż/reroll afiks (T1=150g, T2=500g, T3=1200g)
- [ ] F7 — Trwałość (durability): punktowa per cios, penalty przy 0, naprawa
- [ ] F8 — Napady: encounter kradnący % złota
- [ ] F9 — Dynamiczny asortyment sklepu (lokacja+poziom)
- [ ] F10 — CHA na kupno (nie tylko sprzedaż)
- [ ] F11 — Unifikacja ceny → jeden price_gp
- [ ] F12 — Anti-farm: malejąca cena przy spam-sprzedaży
- [ ] F13 — Background expire wynajmu (sweep)
- [ ] F14 — Usunięcie martwego economy_service kodu
- [ ] F15 — Balans walki → mikstury potrzebne
- [ ] F16 — Balans całości (ceny, dropy, sinki) — playtest
- [ ] F17 — Hidden Trait system (LLM sugeruje z puli, trigger kontekstowy, reveal)
- [ ] F18 — Rosnące progi XP (konfigurowalne z Admin Panelu)
- [ ] F19 — Globalne stany NPC (śmierć NPC między kampaniami)
- [ ] F20 — Mechaniczne efekty pory dnia (noc/świt bonusy, game_config)
- [ ] F21 — World State History UI dla admina (zakładka, diff między turami)

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
