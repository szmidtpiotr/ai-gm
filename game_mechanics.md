# Game Mechanics — Redesign od Podstaw

> **Cel tego dokumentu:** Zaprojektować jak gra POWINNA działać, naprawić fundamentalne błędy projektowe, i zdefiniować kolejność implementacji od zera.
>
> **Ostatnia aktualizacja:** 2026-06-05
>
> ---
>
> ## INSTRUKCJA DLA AGENTÓW LLM
>
> **Ten plik jest głównym źródłem kontekstu projektowego dla całego projektu AI-GM.**
>
> Kiedy pracujesz nad GitHub Issues, TDD, lub jakimkolwiek zadaniem implementacyjnym:
>
> 1. **Szukaj kodu zadania** w **CZĘŚĆ 7** (poniżej) — master lista implementacyjna. **Schemat kodów:** A=Faza -1, B=Faza 0, C=Faza 1, D=Faza 2, E=Faza 3, F=Faza 4, G=Faza 5 (MP), H=Faza 6. Numery sekwencyjne w obrębie sekcji (B1, B2, ... B6).
> 2. **Szukaj kontekstu decyzji projektowej** w sekcji tematycznej (CZĘŚĆ X = Afiksy, CZĘŚĆ AB = Walka/Rany, CZĘŚĆ AC = Multiplayer, CZĘŚĆ AF = Ekonomia, CZĘŚĆ AG = Infrastruktura, itd.).
> 3. **Każda decyzja projektowa** ma blok `> **Zasada projektowa**` + `> **Dlaczego?**` + `> **Co odrzucono?**` — przeczytaj je zanim zaczniesz kodować.
> 4. **GitHub Issues** powinny mieć w tytule kod zadania (`[TASK] B3 — ...`) i odwoływać się do tej sekcji w treści.
> 5. **notes.md** w katalogu głównym = bieżące notatki robocze (otwarte pytania, decyzje z sesji). Sprawdź go gdy coś nie jest jasne.
>
> ### Mapa sekcji (szybka nawigacja)
>
> | Sekcja | Temat |
> |--------|-------|
> | CZĘŚĆ 7 | **Master lista implementacyjna** — start tutaj |
> | CZĘŚĆ 1–6 | Diagnoza + architektura (World State, Questy, XP, Admin Queue, Onboarding) |
> | CZĘŚĆ X | Unified Effects System + Affix System |
> | CZĘŚĆ Y | System Narracji Kampanii (tagi, parsery, Narrative State) |
> | CZĘŚĆ Z | Gotowe Kampanie (Campaign Templates, Forge) |
> | CZĘŚĆ AA | Lochy (Dungeon Mode) |
> | CZĘŚĆ AB | Walka, Rany, Model Wroga |
> | CZĘŚĆ AC | Multiplayer |
> | CZĘŚĆ AD | Flow UI poza grą (ekrany, nawigacja) |
> | CZĘŚĆ AE | Admin Panel (audyt admin_panel_v3, strangler-fig migration) |
> | CZĘŚĆ AF | Złoto i Ekonomia (sinki, crafting, durability) |
> | CZĘŚĆ AG | Infrastruktura (.170=RTX3060, .16=GTX1660, workload rules) |
> | CZĘŚĆ 10 | Zasady projektowe (5 reguł) |
> | CZĘŚĆ 10b | Observability — odłożone do prod deployment |
>
> ### Kluczowe zależności (nie łam ich)
>
> ```
> Effects (F1) → Afiksy (F2) → Crafting (F6) + Admin buildery
> Rany (C4/10/11) → Walka MP (G7)
> World State (B) → ALL: Gate, MP, NPC pamięć, Narracja
> Onboarding karty (E23-E28) → PO systemach które uczą
> ```
>
> ---

---

## ⚠️ UWAGA: PLIK CZĘŚCIOWO ODTWORZONY

> Oryginalny plik utracony 2026-06-05 (reset dysku .61). Odtworzono z kontekstu sesji Claude.
> Sekcje CZĘŚĆ 1-6 i CZĘŚĆ X-AG (szczegółowe decyzje projektowe) wymagają uzupełnienia.
> Master lista implementacyjna (CZĘŚĆ 7) jest kompletna na podstawie `notes.md`.

---

## CZĘŚĆ 7 — Master Lista Implementacyjna

> Kolejność implementacji. Nie zmieniaj kolejności bez aktualizacji zależności.

---

### FAZA A — Procedury wstępne ✅ UKOŃCZONA

- [x] A1 — Dead code cleanup (~1.9GB) — usunięcie nieużywanych zasobów
- [x] A2 — Audyt schematu DB — lista tabel do migracji/usunięcia
- [x] A3 — PROD restoration na .62 + freeze starego kodu (tag v1.0-legacy)
- [x] A4 — Version tagging (git tag)
- [x] A5 — Maintenance notification workflow (banner dla graczy podczas deployów)
- [x] A6 — Parity check admin2 vs admin3
- [x] A7 — Redirect /admin → /admin3
- [x] A8 — Usunięcie admin2 z serwera
- [x] A9 — Usunięcie frontend/admin_panel_v2/ z repo
- [x] A10 — Nowa skorupa admin panelu (thin shell + nav)
- [x] A11 — Shared utilities admin (api.js, toast.js, modal.js, table.js)
- [x] A12 — Game config seed — data/game_config_seed.sql w git; skrypty export/import

---

### FAZA B — World State (fundament danych)

> Blokuje wszystko dalej. GitHub issues: #347–#354

- [x] B1 — Tabela world_state_snapshots (campaign_id, turn_number, state_json) — #347
- [x] B2 — Rozbudowa session_flags: scene_enemies, scene_npcs, active_quests, player_conditions — #348
- [x] B3 — Gate Mechaniki — middleware walidujący akcje gracza PRZED LLM — #349
- [x] B4 — Parser intencji gracza (ATTACK/MOVE/TALK/REST) — #350
- [ ] B5 — Auto-zapis snapshotu World State po każdej turze narracyjnej — #351
- [ ] B6 — Admin UI — World State History (zakładka w Campaign Monitor) — #352
- [ ] B7 — DEV Inspector: live intent + world state debugger — #354

---

### FAZA C — Rdzeń pętli (core loop)

> Wymaga: B3 (Gate) + B1 (World State)

- [ ] C1 — Fix Bug 1 — LLM musi sugerować ruch hex po N turach bez zmiany lokacji
- [ ] C2 — Walidacja ruchu mechaniczna (nowy hex, terrain, lokacja check, update World State)
- [ ] C3 — Fix Bug 2 — Gate walki (scene_enemies check przed każdym ATTACK)
- [ ] C4 — Unifikacja wound_penalty: refactor z sheet-only na hp_current/hp_max
- [ ] C5 — Symetria ran: wound_penalty dla wrogów (nie tylko gracza)
- [ ] C6 — Ujednolicenie progów ran frontend/backend
- [ ] C7 — XP Spend — endpoint spend_skill (wszystkie archetypy)
- [ ] C8 — XP Spend — endpoint spend_stat (wszystkie archetypy)
- [ ] C9 — UI długiego odpoczynku — modal "Ucz się" (lista zakupów XP)
- [ ] C10 — System questów — QUEST_SUGGEST tag + walidacja backend
- [ ] C11 — Mechaniczne śledzenie postępu questów (auto-complete per akcja)
- [ ] C12 — [SPEND_GOLD:X] tag — kwota z tabeli/configu, NIE z LLM
- [ ] C13 — Instrukcja "tylko złoto GP" w system_prompt (usunięcie waluty srebrnej)
- [ ] C14 — Hero-first fix: startCharacterWizard() tylko z Heroes screen
- [ ] C15 — Error boundary dla API failures (toast zamiast białego ekranu)
- [ ] C16 — Delete confirmation modals (kampania, postać)

---

### FAZA D — Systemy + Narracja

> Wymaga: Faza C działająca

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

### FAZA E — Jakość + Treść

> Wymaga: Faza C + D działające

- [ ] E1 — Player HUD (HP/Mana, Złoto, Questy, XP bar, Czas) — aktualizacja per tura
- [ ] E2 — Kreator bohatera — tooltips (archetyp, statystyki, umiejętności z przykładami)
- [ ] E3 — Ekran zakończenia kampanii (podsumowanie + LLM epitafium)
- [ ] E4 — Ekran śmierci (epitafium + statystyki + Wskrześ/Nowy bohater)
- [ ] E5 — Zamknięcie dostępu do kampanii martwego bohatera (hero_status=dead)
- [ ] E6 — Narracja: kompresja, historia, tagi narracyjne
- [ ] E7 — Rozbudowa campaign_templates (required_npc_keys, required_beats, player_visible)
- [ ] E8 — Ekran wyboru gotowej kampanii dla gracza (karty, trudność, opisy)
- [ ] E9 — Story Gravity: trigger = next_required_beat nie odpalony przez N tur (5/10/15, lvl3 OFF)
- [ ] E10 — Forge: walidacja wymaganych NPC/lokacji przy publikacji szablonu
- [ ] E11 — Template Narrative State pre-seeding (narrative_hooks → World State przy starcie)
- [ ] E12 — Workflow publikacji szablonów (draft → review → published)
- [ ] E13 — Encountery generyczne — rozbudowa puli adventure_hooks
- [ ] E14 — Skalowanie encounterów per poziom gracza
- [ ] E15 — Snapshot stanu przy wejściu do lochu
- [ ] E16 — Przywróć snapshot przy śmierci w lochu + restart
- [ ] E17 — Rarity tierów loot w lochach (5 tierów, mapowanie difficulty→rarity)
- [ ] E18 — Cooldown UI lochów w Admin Panelu
- [ ] E19 — LLM Vision: obrazek → opis kafelka (task na maszynie .170)
- [ ] E20 — Admin UI tile manager (obrazki, drzwi, opisy kafelków)
- [ ] E21 — Wejście do lochu z mapy hex kampanii
- [ ] E22 — Resume niedokończonego runu lochu
- [ ] E23 — Seen_mechanics tracking per gracz (nie per postać)
- [ ] E24 — Backend trigger kart onboarding (first mechanic occurrence)
- [ ] E25 — Karty onboarding UI (nieblokujące overlay, "Rozumiem")
- [ ] E26 — Biblioteka kart (gracz może wrócić do przeczytanych)
- [ ] E27 — Karty dla nowych mechanik (afiksy, crafting, MP) — dodać gdy systemy gotowe
- [ ] E28 — Tutorial kampania "Moja Pierwsza Przygoda" (domyślnie ON + przycisk Pomiń)

---

### FAZA F — Rozbudowa: Efekty, Afiksy, Ekonomia

> Kluczowa zależność: F1→F2→F6+F3

- [ ] F1 — Unified Effects System — przepisanie effect_json na typed objects
- [ ] F2 — Affix System — game_config_affixes + affixes_json na inventory row
- [ ] F3 — Admin buildery afiksów i efektów
- [ ] F4 — [SPEND_GOLD:X] tag z tabeli/configu (jeśli nie w Fazie C)
- [ ] F5 — Włączenie + konfiguracja wskrzeszenia jako gold sink
- [ ] F6 — Sink afiksów: NPC is_crafter, nałóż/reroll afiks (T1=150g, T2=500g, T3=1200g)
- [ ] F7 — Trwałość (durability): punktowa per cios, penalty przy 0, naprawa tier_rate x brak_pkt
- [ ] F8 — Napady: encounter kradnący % złota
- [ ] F9 — Dynamiczny asortyment sklepu (lokacja+poziom)
- [ ] F10 — CHA na kupno (nie tylko sprzedaż)
- [ ] F11 — Unifikacja ceny → jeden price_gp
- [ ] F12 — Anti-farm: malejąca cena przy spam-sprzedaży
- [ ] F13 — Background expire wynajmu (sweep)
- [ ] F14 — Usunięcie martwego economy_service kodu
- [ ] F15 — Balans walki → mikstury potrzebne
- [ ] F16 — Balans całości (ceny, dropy, sinki) — playtest
- [ ] F17 — Hidden Trait system (LLM sugeruje z puli, trigger kontekstowy, LLM narruje reveal)
- [ ] F18 — Rosnące progi XP (konfigurowalne z Admin Panelu)
- [ ] F19 — Globalne stany NPC (śmierć NPC między kampaniami)
- [ ] F20 — Mechaniczne efekty pory dnia (noc/świt bonusy, game_config)
- [ ] F21 — World State History UI dla admina (zakładka, diff między turami)

---

### FAZA G — Multiplayer

> Po solidnym solo. Zależy od WSZYSTKICH systemów solo.

- [ ] G1 — Timer enforcement — background sweep co ~30s w main.py
- [ ] G2 — Absencja: token [BRAK AKCJI], licznik ostrzeżeń, reset po powrocie
- [ ] G3 — Vote-to-kick + auto-kick 2-os (host potwierdza) + zaproszenie zastępstwa
- [ ] G4 — Kolejka inicjatywy MP (faza ruchu, faza akcji)
- [ ] G5 — Synchronizacja World State MP (scene_enemies wspólne, player_conditions per player)
- [ ] G6 — Chat głosowy / tekstowy między graczami (WebSocket)
- [ ] G7 — Walka MP — osobne tury, wspólni wrogowie, symetria ran
- [ ] G8 — Loot MP — podział między graczy (vote lub host-decision)
- [ ] G9 — Kampania MP — template z multi-hero slots
- [ ] G10 — Spectator mode (readonly WebSocket stream)
- [ ] G11 — Replay ostatniej sesji (z world_state_snapshots)
- [ ] G12 — Friendship + party invite system
- [ ] G13 — MP lobby UI (tworzenie, dołączanie, kick)
- [ ] G14 — Observability MP (dodatkowe metryki)
- [ ] G15 — Stress test MP (symulacja 4 graczy równocześnie)

---

### FAZA H — Infrastruktura końcowa

- [ ] H1 — PROD deployment pipeline (CI/CD GitHub Actions)
- [ ] H2 — Backup automatyczny PROD (cron + S3/rclone)
- [ ] H3 — Monitoring alerting (Grafana → email/Telegram)
- [ ] H4 — Rate limiting per user (API abuse protection)
- [ ] H5 — GDPR: export danych gracza, usunięcie konta

---

## CZĘŚĆ 1-6 — Diagnoza i Architektura

> ⚠️ Sekcje 1-6 UTRACONE (reset dysku 2026-06-05). Zawierały szczegółowe analizy:
> - CZĘŚĆ 1: Diagnoza aktualnego stanu — co jest zepsute i dlaczego
> - CZĘŚĆ 2: World State — model danych, kolumny game_sessions, snapshots
> - CZĘŚĆ 3: System questów — QUEST_SUGGEST tag, walidacja, śledzenie
> - CZĘŚĆ 4: XP i leveling — progi, spend_skill/spend_stat, archetypes
> - CZĘŚĆ 5: Admin Queue — pending review, auto-screening
> - CZĘŚĆ 6: Onboarding — karty mechanik, tutorial kampania

---

## CZĘŚĆ X — Unified Effects System + Affix System

> ⚠️ UTRACONA — patrz F1-F3 w CZĘŚCI 7.

---

## CZĘŚĆ Y — System Narracji Kampanii

> ⚠️ UTRACONA — patrz D6, E6-E12 w CZĘŚCI 7.
> Kluczowe tagi narracyjne: QUEST_SUGGEST, GRANT_ITEM, SPEND_GOLD, NPC_MEMORY, GRANT_XP.

---

## CZĘŚĆ Z — Gotowe Kampanie (Campaign Templates, Forge)

> ⚠️ UTRACONA — patrz E7-E12, D9 w CZĘŚCI 7.

---

## CZĘŚĆ AA — Lochy (Dungeon Mode)

> ⚠️ UTRACONA — patrz E15-E22 w CZĘŚCI 7.
> Istniejąca implementacja: `backend/app/services/dungeon_service.py`.

---

## CZĘŚĆ AB — Walka, Rany, Model Wroga

> ⚠️ UTRACONA — patrz C3-C6, F15 w CZĘŚCI 7.
> Istniejąca implementacja: `backend/app/services/combat_service.py`.

---

## CZĘŚĆ AC — Multiplayer

> ⚠️ UTRACONA — patrz FAZA G w CZĘŚCI 7.

---

## CZĘŚĆ AD — Flow UI poza grą

> ⚠️ UTRACONA — patrz D8-D13 w CZĘŚCI 7.

---

## CZĘŚĆ AE — Admin Panel

> ⚠️ UTRACONA.
> Aktualny stan: admin_panel_v3 aktywny, v2 usunięty (A6-A9).

---

## CZĘŚĆ AF — Złoto i Ekonomia

> ⚠️ UTRACONA — patrz F4-F14 w CZĘŚCI 7.

---

## CZĘŚĆ AG — Infrastruktura

> ⚠️ UTRACONA.
> Znane: .170 = RTX 3060 (offline gen/Ollama), .16 = GTX 1660 (Piper+Whisper, kernel pinned -23).

---

## CZĘŚĆ 10 — Zasady Projektowe (5 reguł)

> ⚠️ UTRACONA — oryginalne 5 zasad nieznane.
> Z kontekstu sesji znane zasady:
> 1. **Mechanika przed narracją** — każda akcja musi mieć mechaniczny efekt zanim trafi do LLM
> 2. **Gate przed LLM** — World State waliduje akcję synchronicznie, błędy wracają natychmiast
> 3. **No silent failures** — każdy błąd zwraca polską wiadomość do gracza
> 4. **Test first** — TDD: RED → GREEN → REFACTOR dla każdej zmiany
> 5. **Single source of truth** — game_sessions jest jedynym miejscem World State

---

## CZĘŚĆ 10b — Observability

> Odłożone do PROD deployment.
> Stack: Grafana + Loki + Prometheus (observability-dev/ w repo).
