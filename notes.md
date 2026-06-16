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
| **U (Plan naprawczy)** | **30/35** | **86% — PRZED Fazą 5 MP (U21–U23 odłożone do FAZY L; otwarte: U26, U27)** |
| **S (Skille i Stany)** | **20/20** | **100% ✅ KOMPLETNE** |
| G (Faza 5 MP) | 0/15 | 0% — start dopiero po U27 go/no-go |
| H (Faza 6) | 0/5 | 0% |
| **FADM (admin rebuild)** | 18/18 | 100% ✅ KOMPLETNE (strangler fig zakończony) |
| **HI (Inspektor Bohatera)** | 0/5 | 0% — narzędzie admina, niezależne od S/L/MP (decyzja 2026-06-15) |
| **TOTAL** | **114/198** | **58%** |

> **2026-06-08:** Praca nad sekcją D **wstrzymana**. Wyrównanie architektury wg pierwotnego planu (CZĘŚĆ AE strangler-fig) — budujemy modularny `admin/` z monolitu admin3. Brief: `docs/V2_ARCHITECTURE/10_ADMIN_REBUILD_STRANGLER.md`. Epic [#401](https://github.com/szmidtpiotr/ai-gm/issues/401).

> ## 🧭 KOLEJNOŚĆ FAZ (decyzja Piotra 2026-06-13) — co implementować dalej
> FAZA U gameplay gotowa, bramka U27 = **NO-GO dla MP**. Kolejność do MP:
> ```
> 1. #578  — fix tekstowego ruchu (bloker NO-GO z U27)        → prompt_hf.md   ✅ ZROBIONE
> 2. FAZA S — CAŁA (S1→S20)                                    → prompt_s.md    ✅ ZROBIONE (20/20)
> 3. FAZA L — CAŁA (L1→L19)                                    → prompt_l.md    ◀ ▶ TU JESTEŚMY
> 4. FAZA 5 — Multiplayer (dopiero teraz)                      → prompt MP (TBD)
> ```
> **Zasada:** całe S przed całym L (zero ryzyka przeróbek — mechanika walki w pełni gotowa przed treścią/balansem lochów). **NASTĘPNE ZADANIE: L1** — wklej `prompt_l.md`. Walka i treść lochów mają korzystać z mechanik FAZY S (statbloki S2, kondycje [APPLY_CONDITION] S8–S14, skala D1–D5).

---

## Playwright — testy i weryfikacja w przeglądarce

**Zainstalowany na .19 (headless).** Chromium headless działa bez display. Zweryfikowane 2026-06-16.

**Zasada: screenshoty ZAWSZE do `temp-img/`, nie do `/tmp/`** — `/tmp/` niewidoczny z Claude Code Piotra (nie przez sshfs). `temp-img/` jest na sshfs, widoczny inline przez Read tool.

```js
// Szablon skryptu (Node ESM w /tmp gdzie playwright zainstalowany)
import { chromium } from 'playwright';
const SHOTS = '/home/claude/projects/DEV_AIGM/temp-img/<nazwa-testu>';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1280, height: 900 });
await page.goto('https://aigm-dev.studio-colorbox.com/', { waitUntil: 'networkidle' });
await page.screenshot({ path: `${SHOTS}/01-nazwa.png` });
await browser.close();
// Potem Read tool na każdym PNG żeby pokazać inline w konwersacji
```

**Gdzie używać w projekcie:**

| Zadanie | Playwright zastępuje/uzupełnia |
|---|---|
| Weryfikacja po fixie UI | `game-screen` (1 shot) → wielokrokowa sesja |
| **L13c** — smoke silnika kafelkowego | Screenshoty kroków przy `/game-smoke-dungeon` |
| **L18** — regresja lochu e2e | Docelowy test w `ai_test_agent/` (Docker Playwright) |
| **L19** — pełny playtest | Screenshoty przy 14 checkpointach |
| **L-doors #697** — weryfikacja drzwi | Screenshot mapy kafla po każdym przejściu |
| Bug reproduction | Odtworzenie dokładnych kroków gracza |
| Admin panel UI | Weryfikacja sekcji `admin/` po zmianach |

**MCP (przyszłość):** `playwright` MCP dodany do `~/.claude.json` (projekt DEV_AIGM). Po restarcie sesji dostępny jako narzędzia inline bez pisania skryptów.

---

## FAZA U — Plan naprawczy używalności (2026-06-11, audyt pełnego specu) — PRZED Fazą 5

> Pełne opisy zadań: `game_mechanics.md` CZĘŚĆ AH. Kolejność wykonania = sekcja "FAZA U — zależności i kolejność" w CZĘŚCI AH (NIE numeracja — U9b/U28–U32/U32b wchodzą przed Blokiem 4). Każde zadanie = GitHub Issue `[TASK] UNN — tytuł` wdrażane `/tdd`; wyjątki U4/U9b/U32b = czyste playtesty /game-smoke (bez TDD, bez nowego issue, raporty do #512/#513).

### Blok 6 — Lochy: stawka — ❌ WCHŁONIĘTE PRZEZ FAZĘ L (redesign 2026-06-12; nie wykonywać jako U)
- [ ] ~~U22~~ → FAZA L: L2/L4 (pre-roll hinty drzwi), L6 (no soft-locks, fallback braku kafelka)
- [ ] ~~U23~~ → FAZA L: L5 (absolutna skala D1–D5 po S2; bez max_scale — poziom wroga zamiast mnożnika)

## FAZA L — Lochy kafelkowe (2026-06-12, redesign) — 🔨 W TOKU (15/25; +L-doors #697,#698 z weryfikacji gracza; FAZA S ✅ kompletna; prompt: prompt_l.md; smoke: /game-smoke-dungeon przy L13c i L19)

> Pełne opisy zadań + 17 decyzji projektowych + tabela kolizji: `game_mechanics.md` CZĘŚĆ AJ. Jeden tryb lochów (kafelkowy, legacy usuwany), rozgałęziony graf przy wejściu, checkpointy po bossach, tryb nieskończony, mapa kafelkowa pod przyciskiem mapy. Kolejność = sekcja "FAZA L — zależności i kolejność" w CZĘŚCI AJ. Każde zadanie = GitHub Issue `[TASK] LNN — tytuł` wdrażane `/tdd`; wyjątki bez TDD: L14–L17 (kontent/batch, weryfikacja Piotra) i L19 (playtest, raport do [SMOKE] FAZA L). Prompt startowy: `prompt_l.md`. Wchłania U21–U23 (Blok 6 FAZY U) i H5 (FAZA 6).

### Blok 4 — UI gracza

> **Dług/poprawki FAZA L po L16 (2026-06-16, weryfikacja gracza na mobile — wszystkie wdrożone na DEV, niezacommitowane, needs-testing):**
> - **L12b [#694]** — obraz kafla jako modal popup (1. wejście + klik kafla na mapie) zamiast inline nad czatem (przykrywał interfejs na mobile); surowy `room_description` zdjęty z modalu i czatu (zostaje paliwem narratora — Decyzja 3); ikona 🖼 w HUD ponownie otwiera widok komnaty. Nadpisuje fragment Decyzji 14 „obraz kafla w scenie".
> - **Mapa lochu [#694]** — była pusta: generator nie oznaczał entry node `visited=true` (tylko ruch oznaczał kolejne). Fix w `enter_dungeon_tiles` + dopatch 41 żywych runów. Mapa pokazuje kafel startowy + fog.
> - **Admin cooldown=0 [#695]** — modal edycji lochu nie zapisywał cooldown 0 (`parseInt(v)||72` zjadało zero). Helper `_intOr` w `dungeons.js`; input min=0. Live krypta_probna: cooldown 0, D1, min_level 1.
> - **Skrzynia [#696]** — (a) przycisk „Otwórz skrzynię" nigdy się nie pokazywał (front sprawdzał `content.chest`, backend trzyma w `content.items`); (b) **loot nie wchodził do inventory** — `_action_open_chest` losował, nie nadawał → dodany `grant_loot_to_character`; (c) modal wyniku skrzyni (rzut DEX + przedmioty + pułapka).
> - **Kodeks lochu [#696]** — karta „Loch kafelkowy" (`dungeon_tiles`) w MECHANIC_CARDS; trigger przy wejściu ORAZ resume/restore (GET dungeon-run zwraca `onboarding_cards`).
> - **D2 string bug** — seed L16 zapisał `dungeon_difficulty='D2'` (string) → `int()` crash przy wejściu; naprawione na INT (D2=2).
- [x] **L-doors [#697]** — Decyzja 2b: generator wypełnia WSZYSTKIE narysowane drzwi kafla. ✅ KOMPLETNE: (A) 4 zaślepki krypty 1-drzwiowe (N/S/E/W, id 26–29, FLUX 768px, opisy PL); (B) generator `_fill_open_doors` (weld + cap-fill); krypta `caps_complete:true`, `open_doors:0`. Endpoint `preview-graph/{cat}`. pytest 6/6 + Playwright. — [#697](https://github.com/szmidtpiotr/ai-gm/issues/697)
- [x] **L-doors2 [#698]** — Decyzja 2b cz.2: endless `go_deeper` domyka drzwi na styku segmentów. ✅ `_attach_endless_segment`: styk TYLKO na drzwiach zapasowych (wolne/zaślepka) po OBU stronach, naprzeciw siebie; nigdy drzwi-ścieżka. Brak zgodnej pary → `extend` przegenerowuje odcinek (12 prób). Inwariant: ZERO null / drzwi-widm / sierot, symetria. pytest 4/4 + Playwright. **Test /playwright-test-report L13c (2026-06-16):** pierwsza wersja fixu (commit 78e6ef0) okazała się niepełna — na realnym grafie kradła drzwi-ścieżkę bossa → 11 sierot + 2 asymetrie na cyklu 2. Naprawione (commit ce9aee8), ponownie zweryfikowane na żywo (cykl 2: 27 węzłów, cykl 3: 42 — wszystko 0/0/0/0). Raport: [#698 comment](https://github.com/szmidtpiotr/ai-gm/issues/698#issuecomment-4718448558). Status: review + needs-testing (czeka na ręczne przejście Piotra). — [#698](https://github.com/szmidtpiotr/ai-gm/issues/698)
- [ ] L13c — 🎮 KAMIEŃ MILOWY (mid-faza): `/game-smoke-dungeon --engine` po Bloku 4 — silnik+UI na kafelkach testowych (przed treścią L14–L16). Łapie bugi grafu/ruchu/mapy/walki/bossa/endless/śmierci/porzucenia ZANIM włożymy treść. Bez TDD, raport do [SMOKE] FAZA L. Checkpointy zależne od treści (opisy PL, zagadki) = N/D. Zaliczone = przebieg silnika bez P0; werdykt min. GRYWALNY Z ZASTRZEŻENIAMI.
  - SMOKE 2026-06-16: pierwszy przebieg **NIEGRYWALNY** (1×P0). Działa: graf/ruch/walka(skala D1–D5)/skrzynia/boss/endless(+1lvl/cykl)/flaga. Defekty: **#684 P0** — brak `import math` → `/dungeons/death` i `/dungeons/exit` zwracają 500; **#685 P1→P0** — entry tile z wrogami = soft-lock. Raport: #686.
  - 🟢 FIX 2026-06-16: oba naprawione na DEV i przetestowane ponownie — death 200 (+72h cd), abandon 200 (+36h cd), 0/20 enters z combat entry. Werdykt engine: **GRYWALNY (bez P0)**. Zmiany w drzewie roboczym FAZA L (niezacommitowane). Zaznaczyć [x] po wizualnej weryfikacji UI + commicie FAZA L; wtedy zamknąć #684/#685.
  - 🟢 FIX 2026-06-16: **#700 P1** — desync tury walki (backend=player, front wisi na „Tura wroga", Atak disabled pod szybkim inputem). Czysty reconciler `combat_reconcile.js` (`reconcileCombatTurn`) — backend=źródło prawdy; wpięty w `pollCombatState` + po turze wroga; precyzyjne flagi `enemyTurnFetchActive`/`playerActionFetchActive` (realny POST vs zalegająca flaga) + watchdog. Playwright 4/4. **review/needs-testing** — ✅ **PRZETESTOWANE** `/playwright-test-report` 2026-06-16 (krypta_probna, [TEST] Łotrzyk, camp 99762): 220 szybkich kliknięć Atak podczas tury wroga → zasłona „Tura wroga" nie utknęła, sterowanie odzyskane bez reloadu, walka rozliczona do zwycięstwa (hero 11/11). 5/5 gałęzi reconcilera OK. Raport: [#700 comment](https://github.com/szmidtpiotr/ai-gm/issues/700#issuecomment-4718238605). Drobiazg kosmetyczny (etykieta `reason`) → [#701](https://github.com/szmidtpiotr/ai-gm/issues/701).

### Blok 5 — Kontent: krypta (bez TDD; pilot → akceptacja → batch)
  - 🟢 FIX 2026-06-16: seed zapisał `dungeon_difficulty='D2'` (string) — `int()` w `dungeon_tile_service` (linie 510/689/1234/1674) rzucał `invalid literal for int() with base 10: 'D2'` przy wejściu. Kolumna trzyma INT (D2=2, jak crypt_of_bones=2). Naprawione: DB UPDATE→2 + seed poprawiony. Re-test enter: `ok:true`, graf zbudowany, difficulty=2.
- [ ] L17 — Kolejne kategorie (goblińskie tunele, ruiny…) — ⛔ PO L19; per kategoria powtórka L14–L16

### Blok 6 — Weryfikacja
- [ ] L18 — Playwright: regresja lochu end-to-end (wejście→walka→drzwi→zagadka→boss→endless→wyjście + mapa)
- [ ] L20a — Portrety wrogów/NPC: persystencja (migracja image_url na game_config_enemies+npcs, update_enemy/update_npc, portret BASE_PROMPT, batch --entity) — naprawia zepsuty zapis istniejącego modala (TDD; przed L19) — [#692](https://github.com/szmidtpiotr/ai-gm/issues/692)
- [ ] L20b — Portrety wrogów/NPC: display u gracza (modal startu walki jak Dice Roll + miniatura w panelu/chipie, fallback emoji; reuse w normalnej kampanii; ożywia [NPC_INTERACTION]) + USUNIĘCIE bloku „Pozycje sprite'ów na kafelku" z edytora kafla (TDD) — [#692](https://github.com/szmidtpiotr/ai-gm/issues/692)
- [ ] L20c — Portrety nieumarłych krypty: pilot 5 → akceptacja Piotra → batch (bez TDD; przed L19) — [#692](https://github.com/szmidtpiotr/ai-gm/issues/692)
- [ ] L19 — 🎮 KAMIEŃ MILOWY: pełny playtest lochu skillem `/game-smoke-dungeon` (na treści krypta po L16: 2 cykle endless, śmierć z checkpointem, porzucenie, mapa, mobile; 14 checkpointów; raport do [SMOKE] FAZA L; bez TDD). Pierwszy kandydat na loch GRYWALNY.

> Poza zakresem FAZY L (zapisane w CZĘŚCI AJ): multiplayer w lochach (tylko kształt danych), rotacja kafelków, leaderboard endless, przedmioty dungeon-exclusive (kontent), pełny podsystem pułapek (wykrywanie/rozbrajanie).

---

## FAZA B — Balans 3 klas + Czary maga (2026-06-14, sesja projektowa — decyzje w game_mechanics.md CZĘŚĆ AK)

> Pełne definicje liczb + system czarów + fazy adaptacji + decyzje: `game_mechanics.md` CZĘŚĆ AK. Założenia: warrior=tank (mało INT), rogue=zwinny/najwięcej skilli/mniej HP niż warrior, mag=słaby fizycznie/nadrabia czarami. Audyt ujawnił 4 rozjazdy kod↔DB↔design. Czary z `rpg_spells_design_doc.md` (50 szt.). Każde zadanie = GitHub Issue `[TASK] BNN` wdrażane `/tdd`. **Blok 1 standalone** (przerywnik — można PRZED/równolegle z FAZĄ L). **Blok 2 niezależny od L** (po FAZIE S ✅). **Blok 3 ⛔ wymaga FAZY 5 (MP/towarzysze) + systemu reakcji.**

### Blok 3 — Czary Faza 2 (⛔ WYMAGA FAZY 5 + system reakcji)
- [ ] B14 — Ally-target (group_heal, haste, stoneskin_ally, divine_shield_ally, mass_*) — ⛔ wymaga MP/towarzyszy (FAZA 5)
- [ ] B15 — Summony (familiar, elemental, animate_dead, shadow_clone) jako kombatant-towarzysz — ⛔ duża dobudowa silnika walki
- [ ] B16 — System reakcji (blink, mirror_image redirect, globe_invulnerability) — ⛔ okno reakcji w silniku
- [ ] B17 — (D3) Czary CHA (charm_person, mass_fear) — wg decyzji D3

> **Decyzje do potwierdzenia (CZĘŚĆ AK.6):** D1 HP 10/8/6 (przyjęte roboczo) vs 12/10/8+retune wrogów · D2 rogue sneak attack cecha vs generyczny hidden · D3 mag CHA-czary tak/nie.
> Poza zakresem FAZY B (Faza 2 czarów): pełny system towarzyszy/petów, leaderboard czarów, czary rytualne poza walką.

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

## FAZA 6 — Długoterminowe: głos, obrazy, offline-gen

_Observability wydzielone do FAZY O (H1 „log writer/metryki" = O1/O2). Tu zostaje infra długoterminowa niezwiązana z mapą/observability._

- [ ] ~~H1~~ → FAZA O (O1/O2: `game_events` + `event_logger` zastępują „lekki log writer"; H1 wchłonięte)
- [ ] H2 — Text-to-speech — per single player opt-in (F5TTS na hoście .16)
- [ ] H3 — Konfiguracja image gen pipeline na .170 (FLUX.1-schnell + ComfyUI)
- [ ] H4 — Konfiguracja Ollama na .170 dla offline content gen (admin AI Kreator)

---

## Zrobione dodatkowe

Standalone bugixy i feature'y spoza głównej architektury A-H.

- [ ] #C-acc — Acceptance harness C1–C19 (pytest 13/13 + Playwright LLM-play) — `scripts/acceptance_c_series.sh`, `docs/ACCEPTANCE_C_SERIES.md` — commit 687f7ed; RED backlog: C9 (modal Ucz się), C10/C11 (questy)
- [ ] [#400](https://github.com/szmidtpiotr/ai-gm/issues/400) — Admin spectator + resume: admin z player frontendu widzi WSZYSTKIE kampanie (dropdown wyboru usera, default własny), podgląda read-only i wznawia (re-attach bohatera z historii tur + aktywacja). Endpointy gated is_admin. TDD 7/7 + Playwright. Bug po drodze: campaigns.updated_at nie istnieje → created_at (awaits-testing)

---

## FAZA O — Observability + Mapa węzłów (PO FAZIE L) 6/10

_Spec: `docs/V2_ARCHITECTURE/22_FAZA_O_OBSERVABILITY_ARCHMAP.md` (łączy Phase 11 observability z mapą architektury `tools/archmap/`). Start prompt: `prompt_o.md`. Nie blokuje FAZY 5 MP._
_Uwaga: tabele `game_events`/`llm_call_log` już istnieją od #587 (migracja) — O1 częściowo zrobione, zostaje `event_logger.py` + payloady._
_Wchłania H1 z FAZY 6 (stary „observability design / log writer") — zastąpione przez O1/O2._

Tor 1 — Observability:
- [x] O1 — `game_events`+`llm_call_log` + `event_logger.py` (tabele są od #587; brak serwisu helpera) — [#702](https://github.com/szmidtpiotr/ai-gm/issues/702) d04b6bc
- [x] O2 — Zapis zdarzeń z serwisów (combat/śmierć/beat/LLM) wg payloadów §Part 1 — [#704](https://github.com/szmidtpiotr/ai-gm/issues/704) 7c28c0e
- [x] O3 — Panel admina „Statystyki i Logi” (KPI + 4 zakładki, endpointy analytics) — [#705](https://github.com/szmidtpiotr/ai-gm/issues/705) 381e5fd
- [x] O4 — Serwer MCP (`mcp_server/server.py`, 9 narzędzi, docker service) — [#706](https://github.com/szmidtpiotr/ai-gm/issues/706) 76ab35c
- [x] O5 — Test MCP z Claude Code (10 przykładowych zapytań) — playtest ✅; fix `get_campaign_summary` (campaign_catalog_entities → campaign_known_npcs)

Tor 2 — Mapa węzłów:
- [x] O6 — Mapa: cron overlay na .61 (refresh.sh 03:30) + opcjonalne wydzielenie repo `archmap` — [#707](https://github.com/szmidtpiotr/ai-gm/issues/707)
- [x] O7 — Mapa: pozostałe podsystemy (turn-flow+LLM seam, admin, world, dungeons) — [#708](https://github.com/szmidtpiotr/ai-gm/issues/708) 70959ce
- [x] O8 — Mapa↔observability: pełna heat-map (usunięto `_phase11`, 6 źródeł heat, węzeł MCP w admin-map) — [#709](https://github.com/szmidtpiotr/ai-gm/issues/709) 4c5d05b
- [ ] O9 — (opcjonalnie) MCP serwuje mapę (`get_architecture_map`)
- [ ] O10 — Mapa: interaktywny UX (pływające panele + persist layout, popup issue z body+komentarzami na żywo, reset układu) — część zrobiona w pilocie, reszta po O7

> **Pilot gotowy (2026-06-16):** `tools/archmap/architecture-map.html` (combat, 27 węzłów) + generator nakładki z GitHub issues + strażnik driftu + instrukcja `INSTRUKCJA.md`. Generator przetestowany na żywym repo (24/106 issues dopasowane). UX (O10) częściowo: pływający pasek filtrów z persist + przeciągany popup issue z live body+komentarzami z GitHub API.

---

# ✅ FAZY UKOŃCZONE — archiwum

_Zrobione fazy i zrobione pod-sekcje faz częściowo ukończonych. Nagłówki zduplikowane: otwarte zadania zostają u góry, zrobione tu. Nic nie usunięte._

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

## FAZA U — Plan naprawczy używalności (2026-06-11, audyt pełnego specu) — PRZED Fazą 5  —  ✅ zrobione (przeniesione)
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

### Blok 4 — Baza danych jako rdzeń (5/5)
- [x] U10 — Effect schema lockdown — **decyzja C (hybryda, 2026-06-13):** zachowano nazwy typów z kodu (periodic_save/static_stat_modifier/block_action), bo walidator już istniał i działał + FAZA S na nim bazuje; dodano `backend/app/schemas/effect_schema.json` jako pojedyncze źródło prawdy, LCK + cele pochodne (ac/attack_bonus/damage_bonus/initiative), audyt `scripts/effect_json_audit.py` (169==169, 0 strat; 23 legacy do ręcznej decyzji → U11/FAZA S). — [#554](https://github.com/szmidtpiotr/ai-gm/issues/554)
- [x] U11 — Unifikacja przedmiotów 3 tabele → game_items (sub-issues U11a schema+backfill / U11b odczyt / U11c zapis+admin) — [#555](https://github.com/szmidtpiotr/ai-gm/issues/555) **needs-testing**
  - [x] U11a — CREATE TABLE game_items + backfill (140 rek.: 27 weapon + 26 armor + 59 item + 28 consumable) + FK columns (game_item_key NULL w char_inventory + loot_entries). Stare tabele niezmienione. — [#556](https://github.com/szmidtpiotr/ai-gm/issues/556) **needs-testing**
  - [x] U11b — przełączenie odczytu: serwisy czytają z game_items; stare tabele read-only — [#557](https://github.com/szmidtpiotr/ai-gm/issues/557) **needs-testing**
  - [x] U11c — dual-write: create/update/delete weapon+item, smart_entry, approve_entity, forge, import katalogu piszą też do game_items (re-read legacy → upsert; jedno mapowanie = backfill U11a). Stare tabele DEPRECATED (drop po 2 tyg., decyzja Piotra). 9/9 pytest GREEN + live verify create/edit/delete. **UWAGA: 18 testów shop/loot/inventory czerwone z PRE-ISTNIEJĄCYCH luk fixture'ów U11b (`no such table: game_items` / `no such column gi.armor_coverage` w izolowanych DB testów) — nie regresja U11c, należą do #557.** — [#558](https://github.com/szmidtpiotr/ai-gm/issues/558) **needs-testing**
- [x] U12 — db_lint (skrypt + endpoint + przycisk w admin Narzędzia + krok w deploy_dev.sh) — [#559](https://github.com/szmidtpiotr/ai-gm/issues/559) (pierwotnie, zamknięte) → **dokończone + zahartowane** [#560](https://github.com/szmidtpiotr/ai-gm/issues/560) **needs-testing**. #559 zostawiło 3 luki: endpoint BEZ autoryzacji (dziura bezp.), brak 4 checków ze specu (dup-key/loot-weight/rarity/weight_kg), CLI poza obrazem backendu (deploy step nie działał). #560 naprawia wszystkie 3. 9/9 pytest + 2/2 Playwright GREEN; CLI w kontenerze exit 1 (10 realnych warningów effect_json = lista zadań dla treści, zgodnie ze specem).
- [x] U13 — Content pipeline (seed_lint_service: świeża baza ← schemat → seedy 01–15 → run_lint U12 + walidatory U10; CLI twin host+kontener; krok w deploy_dev.sh; docs/CONTENT_PIPELINE.md) — seedy 01–15 CLEAN exit 0. **Naprawiono format efektów:** `DAMAGE_DIE_RE` w admin_config rozszerzony o modyfikator `+N`/`-N` (`2d4+2`) zgodnie z runtime rollerem — 8 warningów effect_json mikstur znikło. created_by='seed' egzekwowane (check [SEED_OWNER]). 9/9 pytest + 2/2 Playwright GREEN — [#561](https://github.com/szmidtpiotr/ai-gm/issues/561) **needs-testing**
- [x] U14 — Pełny reset bohatera przy nowej kampanii (mana już była; dorzucone conditions sheet+tabela, rentale active→expired, pop flagi sandbox; XP/złoto/ekwipunek/zaklęcia nietknięte; guard wznowienia zachowany) — [#562](https://github.com/szmidtpiotr/ai-gm/issues/562) **needs-testing**

### Blok 5 — Widoczność mechanik (6/6)
- [x] U15 — Widoczne rany wroga w walce: etykieta tieru + kropka koloru na chipach inicjatywy; jedno źródło prawdy `WOUND_TIERS` (label+kolor+kara) w `wound_utils.py`, derywacja w economy_service + endpoint /config/wound-thresholds + frontend. **Premisa specu ("Ranny" 26–50% ma karę 0) była nieaktualna — drabina kar 0/−1/−2/−4 już istniała; decyzja Piotra: ujednolicić progi + UI, kary bez zmian.** — [#563](https://github.com/szmidtpiotr/ai-gm/issues/563) **needs-testing**
- [x] U16 — Cost preview + pasek durability + komunikat anti-farm. **Decyzja Piotra (2026-06-13): rozszerzone o pełne ekrany gracza** — sklep `[OPEN_SHOP]` był parsowany ale nigdy renderowany; brak UI naprawy/kuźni; trwałość nie wystawiana w endpointach. U16 zbudowało: modal sklepu (kup/sprzedaj z ceną+saldem po, komunikat nadpodaży), pasek trwałości w ekwipunku+karcie+slotach, ostrzeżenie ≤20% w HUD walki, naprawę i kuźnię afiksów z cost-preview w karcie przedmiotu. Backend: durability w /inventory(+detail), sell_item +oversupply, GET affix-costs. **Domknięte w U16:** (1) dodano migrację `affixes_json` do main.py (żywa baza DEV jej nie miała mimo #462) → apply/reroll afiksów persystuje; (2) naprawiono brak nagłówka auth w fetch cost-preview (repair-cost/affix-costs/gold → 401, karty cicho znikały) → `apiRequest()`; (3) **aktywowano uśpioną trwałość #467** (zgoda Piotra 2026-06-13): durability nigdy nie była inicjalizowana przy zdobyciu broni/zbroi (NULL = nieśledzona), więc pasek U16 nie miał czego pokazać i sprzęt nigdy się nie zużywał — `grant_loot_to_character` ustawia teraz durability_current=max (durability_base z configu albo wg rzadkości 100/150/200) + `backfill_missing_durability()` (10 wierszy na DEV). Mechanika #467 (zużycie w walce, kara −50% przy 0) działała już wcześniej, była tylko martwa bez inicjalizacji. 11/11 pytest GREEN; potwierdzone: nowy bohater ma Short Sword 100/100 z paskiem w karcie. — [#564](https://github.com/szmidtpiotr/ai-gm/issues/564) **needs-testing**
- [x] U17 — Celebracja dropu afiksowego + porównanie z założonym — karta po claimie dla broni/zbroi specjalnej (afiks LUB rarity≥2): kolor rzadkości + afiksy z opisem + diff statów vs założony (↑/↓/=, „brak porównania" bez ekwipunku) + przycisk Załóż. Diff liczy backend (`compare_item_metrics`). Endpoint `GET /inventory/{cid}/{inv_id}/drop-comparison`. 17/17 pytest + 3/3 Playwright GREEN; karta potwierdzona zrzutem. Weryfikacja „w lochu" pominięta (Blok 6 poza zakresem). — [#565](https://github.com/szmidtpiotr/ai-gm/issues/565) **needs-testing**
- [x] U18 — Dziennik gracza (Zadania / Wątki / Kronika; endpoint `GET /api/campaigns/{id}/journal`; `player_visible` na seeds — domyślnie true dla seedów z akcji gracza, false dla sekretów GM Planu). Backend `journal_service.build_journal` komponuje character_quests + narrative_state seeds/events + ukończone beaty (odwrotna chronologia, numer tury). Frontend: panel Dziennik rozszerzony o 3 sekcje. 7/7 pytest + 2/2 Playwright GREEN; endpoint potwierdzony na żywej kampanii 64 (4 questy + beaty + filtr sekretów). Render sekcji potwierdzony w DOM; pełny zrzut in-game zablokowany przez 502 LLM na wejściu do kampanii (osobny problem infra DEV). — [#570](https://github.com/szmidtpiotr/ai-gm/issues/570) **needs-testing**
- [x] U19 — Recap "Poprzednio w Twojej przygodzie…" po >24h przerwy: endpoint `GET /campaigns/{id}/recap` (read-only, backend decyduje o triggerze >24h z `campaign_turns.created_at`), `build_recap()` komponuje zapisane summary gracza + 2 ostatnie tury (czyszczone z JSON/tagów) + aktywne questy; karta auto na wejściu + „Przypomnij mi" w dzienniku; **bez nowego callu LLM**. 6/6 pytest + 2/2 Playwright GREEN; karta potwierdzona zrzutem (kampania 64, last turn −2d → should_show). — [#571](https://github.com/szmidtpiotr/ai-gm/issues/571) **needs-testing**
- [x] U20 — Onboarding: poprawki triggerów kart. Retarget karty death_save na **pierwszy spadek HP<25%** (zamiast 1. rzutu na śmierć; czyta świeże HP z sheet w injectorze). Karta XP dopisana o instrukcję wydania PD (Odpoczynek→★ Długi→📖 Ucz się), karta rzutu ujednolicona o „Biegłość". **3 nowe karty:** durability (<50% trwałości założonego sprzętu), raids/napady (dziki hex + złoto>100), crafter (rozmowa z NPC `is_crafter`). **Decyzja Piotra (2026-06-13):** crafter via nowa kolumna `npcs.is_crafter` + migracja oznaczająca kowali (9 NPC na DEV) — żywa baza nie miała tej flagi ani flow rozmowy z rzemieślnikiem (kucie idzie z karty przedmiotu U16). Injector dostaje `character` (3 tory turns.py) + sygnał `npc_dialogue`. 13/13 pytest + 1/1 Playwright GREEN; live: HP 1/10 → payload `onboarding_cards:['death_save']` w torze streamingowym. — [#572](https://github.com/szmidtpiotr/ai-gm/issues/572) **needs-testing**

### Blok 6 — Lochy: stawka — ❌ WCHŁONIĘTE PRZEZ FAZĘ L (redesign 2026-06-12; nie wykonywać jako U)
- [x] ~~U21~~ → FAZA L: L7 (semantyka checkpointów; UWAGA: śmierć=koniec runu zamiast restartu — zmiana względem pierwotnego U21) — [#676](https://github.com/szmidtpiotr/ai-gm/issues/676)
### 🎯 Weryfikacja Bloku 4 (celowana; po U20, PRZED U24; poza licznikiem U)
- [x] B4V — `/game-test-player-screenshot` jednego scenariusza sklep+trwałość+przedmiot na koncie Demo. **Po co:** od U32b minął cały Blok 4 (unifikacja 3 tabel→game_items, dual-write, aktywacja trwałości #467, nowy sklep z U16) BEZ playtestu — najcięższy zestaw zmian FAZY U; żółta flaga = 18 czerwonych testów shop/loot/inventory z U11c (#557/#558). Tańsze niż pełny dwutrybowy smoke; pełny smoke i tak będzie w U27. **Bez TDD, bez nowego feature-issue** — defekty → osobne issues `[BUG] B4V — ...` (bug + needs-testing). Prompt: `prompt_b4v.md`. Zaliczone = sklep zdejmuje/dolicza złoto z saldem po, pasek trwałości widoczny i spada po walce, przedmiot z lootu trafia do ekwipunku z game_items. Każdy ❌ w tych trzech = defekt Bloku 4 do naprawy PRZED U27.
  - **WYNIK 2026-06-13: BLOK 4 OK (grywalny)** — kampania B4V (id 73), bohater [TEST] Wojownik (id 2), DEV. Wszystkie 3 mechaniki ✅ dla gracza:
    - **SKLEP ✅** — zakup shortsword 200→186 gp (paid 14 = buy_price_gp), sprzedaż bandaża 186→187 gp (earned 1); saldo w UI = 187 zł. Uwaga doc: złoto siedzi w kolumnie `characters.gold_gp`, NIE w `sheet_json.$.gold` (zalecane SQL w promptcie zwróciłoby NULL).
    - **TRWAŁOŚĆ ✅** — założona broń 88→87→86→85 przez 3 ataki (−1/trafienie); pasek trwałości renderowany w ekwipunku.
    - **PRZEDMIOT z game_items ✅ funkcjonalnie** — kupiony shortsword (inv 77) trafia do ekwipunku, resoluje się z katalogu `game_items` po kluczu (label „Short Sword", durability). **Z zastrzeżeniem P2 → [#573](https://github.com/szmidtpiotr/ai-gm/issues/573):** kolumna `game_item_key` nigdy nie zapisywana (0/25 wierszy w całej bazie); loot_service/shop_service wciąż czytają z legacy `game_config_*`; `thug` ma puste `loot_table_key` (brak dropu). Nie blokuje gracza (dual-write sync), ale do uprzątnięcia przed single-source game_items — prawdopodobne źródło 18 czerwonych testów #557/#558.
  - **Werdykt:** Blok 4 zaliczony, jeden defekt P2 (#573) niewidoczny dla gracza. → wracaj do prompt.md → U24. P2 nie blokuje U27.

### Blok 7 — Ekonomia: bezpieczniki
- [x] U24 — Napad: ostrzeżenie + rzut obronny + próg biedy 50gp + max 1/24h — [#574](https://github.com/szmidtpiotr/ai-gm/issues/574) **needs-testing**. Counterplay na istniejącym robbery_service (F8/#468): tura ostrzeżenia (złoto nietknięte) → tura rzutu obronnego d20+stat (DEX bandyci / WIS kieszonkowiec) vs DC wg poziomu z zamka {8,12,16,20,24}; sukces=brak straty, porażka=−20%; próg biedy 50gp + limit 1/24h realne/kampania w iniekcji encountera. Live na kampanii 73 (hero 2, 187gp): ostrzeżenie→robbery_state=warned (gold 187) → rzut DEX+2≥DC8 sukces (gold 187, encounter wyczyszczony, last_robbery_at ustawiony, gate rate_limited_24h aktywny). 14/14 pytest + 3/3 Playwright GREEN.
- [x] U25 — Pity timer afiksów (3 bossy bez afiksu → gwarancja T1+; 3 rerolle bez zmiany → inny afiks). Liczniki w tabeli `affix_pity` (per postać `boss_drop`, per przedmiot `reroll:<inv>`) — przeżywają restart. Boss wykrywany po `enemy.tier='boss'` → flaga `active_combat.boss_defeated` → `claim_post_combat_loot`. `roll_weapon_affixes(force_min_one)` gwarantuje afiks niezależnie od loot_tier; reroll wyklucza obecny klucz przy 4. próbie. Progi 3/3 = wartości startowe (Numbers Policy). 13/13 pytest + 3/3 Playwright GREEN; live e2e na DEV (3 dry boss kills → drop `["sharp"]` → reset). — [#575](https://github.com/szmidtpiotr/ai-gm/issues/575) **needs-testing**
- [x] U26 — Telemetria ekonomii: centralna `change_gold()` + kafelek Ekonomia w admin Overview — [#576](https://github.com/szmidtpiotr/ai-gm/issues/576) **needs-testing**. **Decyzja (2026-06-13): reuse istniejącej `character_gold_log` (Stage 11, #64) zamiast nowej `economy_log`** — dodano kolumnę `campaign_id` (migracja+backfill), zbudowano `change_gold(conn, cid, delta, source, *, campaign_id, meta, allow_negative)` (mutacja gold_gp + journal atomowo, conn-owned, bez commitu). Refactor na nią: shop (buy/sell via `apply_character_gold_delta`), spend_gold (service — wcześniej BEZ logu = źródło driftu), crafter (repair/craft), robbery, durability. `categorize_source()` mapuje surowe nazwy na kubełki ENUM (loot/sell/buy/service/robbery/resurrection/repair/craft/quest_reward/starter_gold/admin_cheat/other) tylko do raportu (stored source bez zmian — anti_farm zależy od `shop_sell`). Kafelek "Ekonomia 7 dni" w admin Overview (`economy_7d` w `/api/admin/overview`). db_lint `_check_gold_drift` (saldo≠suma delt → warning). 13/13 pytest + 3/3 Playwright GREEN; live e2e: change_gold path + agregacja + GOLD_DRIFT potwierdzone na DEV.

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
- [x] U27 — `docs/ACCEPTANCE_USABILITY.md` (checklista A/B/C, loch ⏸) + re-playtest 2 trybów (`/game-smoke`) → [GATE] [#577](https://github.com/szmidtpiotr/ai-gm/issues/577) **needs-testing**. **Wynik bramki:** Nowa=GRYWALNY Z ZASTRZEŻENIAMI (P1 #578 ruch tekstowy, P2 #579 kowal pusty / #580 zegar 2 źródła), Gotowa=GRYWALNY (2 beaty auto-complete, GM Plan z szablonu). Wszystkie kryteria A/B/C ✅ poza **B1/B6** (tekstowy ruch + guard anty-desync → #578). **Decyzja Piotra 2026-06-13: NO-GO — Multiplayer wstrzymany, #578 naprawione.** Raporty: [#512](https://github.com/szmidtpiotr/ai-gm/issues/512#issuecomment-4699444206), [#513](https://github.com/szmidtpiotr/ai-gm/issues/513#issuecomment-4699444975).
  - [x] **#578 NAPRAWIONE** (review, needs-testing) — root cause: U30 directional fast-path był tylko w `create_turn_stream` (UI gracza), nie w JSON `create_turn` (smoke) → fałszywy fail B1; guard `travel_narrated_without_move` (U30.4) nigdzie w żywym torze → fałszywe B6. Fix: wspólny helper `execute_directional_travel` w obu handlerach + `guard_travel_desync` wpięty w oba tory (`turn_pipeline.py`). 7/7 pytest + 1/1 Playwright GREEN; live: JSON `{0,1}→{0,0}`, streaming `{1,0}→{0,1}`. **Po fixie B1 ✅ (oba endpointy), B6 ✅ (guard wpięty).** MP nadal wstrzymany (decyzja Piotra; FAZA S + FAZA L też wymagane przed FAZĄ G). P2 #579/#580 otwarte (nie blokują).

---

## FAZA S — Skille i Stany (2026-06-12, rozszerzenie mechaniki) — ✅ UKOŃCZONA (S1–S20, 2026-06-14; werdykt playtestu: GRYWALNE Z ZASTRZEŻENIAMI [#615], dług promptu [#616]) → następna: CAŁA FAZA L

> Pełne opisy zadań: `game_mechanics.md` CZĘŚĆ AI. Źródło danych: `skills_conditions_design_doc.md` (korzeń repo). Kolejność = sekcja "FAZA S — zależności i kolejność" w CZĘŚCI AI (S1→S4 → S5→S7 → [U10!] S8→S14 → S15→S19 → S20). Każde zadanie = GitHub Issue `[TASK] SNN — tytuł` wdrażane `/tdd`; wyjątek S20 = czysty playtest (bez TDD, raport do issue [SMOKE] FAZA S). Prompt startowy: `prompt_s.md`.

### Blok 1 — Fundament rzutu
- [x] S1 — Margines sukcesu: 4 stopnie wyniku testu umiejętności (zmiana zablokowanej mechaniki — zgoda 2026-06-12) — [#581](https://github.com/szmidtpiotr/ai-gm/issues/581)
- [x] S2 — Staty wrogów: stats_json + archetypy + seed heurystyką (nadpisuje decyzję CZĘŚĆ AB) — [#582](https://github.com/szmidtpiotr/ai-gm/issues/582)
- [x] S3 — Staty NPC + lazy generation archetypu — [#583](https://github.com/szmidtpiotr/ai-gm/issues/583)
- [x] S4 — Testy przeciwne na prawdziwych statach (aktor-agnostycznie; podwalina MP) — [#584](https://github.com/szmidtpiotr/ai-gm/issues/584)

### Blok 2 — Skille: batch danych + hooki
- [x] S5 — Seed ~16 skilli kategorii A (czyste testy) + countery + keyword map U7 — [#585](https://github.com/szmidtpiotr/ai-gm/issues/585) (18 skilli, 18 counterów opposed/dc, 7 kategorii ryzyka U7; katalog LLM 35 skilli)
- [x] S6 — Haggling: targowanie wpięte w ceny sklepu — [#586](https://github.com/szmidtpiotr/ai-gm/issues/586)
- [x] S7 — Gamble: hazard z prawdziwą stawką złota — [#601](https://github.com/szmidtpiotr/ai-gm/issues/601)

### Blok 3 — Prymitywy efektów + kondycje parami — ⛔ WYMAGA U10
- [x] S8 — Batch kondycji z istniejących klocków (on_fire, frozen, lite: confused/insane/panicked/charmed/cursed) + tag [APPLY_CONDITION] — [#603] (nowy prymityw `dot` dodany do U10 — decyzja A; `_combatant_stat_modifier` czyta teraz schema-zgodny `static_stat_modifier`; tag dokleja effect_json + invalid_reference)
- [x] S9 — Prymityw stacking_levels + kondycja exhausted — [#604](https://github.com/szmidtpiotr/ai-gm/issues/604)
- [x] S10 — Prymityw escalating_dot + kondycja hemorrhage — [#605](https://github.com/szmidtpiotr/ai-gm/issues/605)
- [x] S11 — Prymityw reroll + inspired + cursed (pełny) — [#606](https://github.com/szmidtpiotr/ai-gm/issues/606) (typ efektu `reroll`: player_keep_best/forced_keep_worst; inspired = CHA/WIS +2 + przerzut keep-best; cursed pełny = zły omen 1×/scenę keep-worst; nowy serwis `reroll_service.py` + endpoint `POST /skill-test/reroll` + przycisk „Przerzuć (Zainspirowany)"; Zasada 4 w 4 miejscach; rzuty walki nietknięte)
- [x] S12 — Prymityw extra_action + on_expire_apply + kondycja hasted — [#607](https://github.com/szmidtpiotr/ai-gm/issues/607) (typy `extra_action`/`on_expire_apply` w U10; hasted=DEX+2+darmowa zmiana strefy+exhausted po 3 rundach; `apply_condition_to_player` + przycisk Sandbox; Zasada 4 w 4 miejscach; rzuty walki nietknięte)
- [x] S13 — Prymityw on_zero_hp_save + kondycja blessed — [#608](https://github.com/szmidtpiotr/ai-gm/issues/608) (typ efektu `on_zero_hp_save` w U10: stat+DC+result=stay_at_1hp+uses; blessed=CON DC 12 raz/scenę zostawia 1 HP zamiast nieprzytomności + derived stat `save` +2 defensywny fold w periodic_save; hook w resolve_attack przy HP≤0; Zasada 4 w schema+forge×2+CZĘŚĆ X+prompt; rzuty ataku nietknięte; 13/13 pytest z real-engine + 1/1 Playwright)
- [x] S14 — Prymityw condition_immunity + kondycja rage — [#609](https://github.com/szmidtpiotr/ai-gm/issues/609) (typ efektu `condition_immunity` immune_to[...] + top-level klucz `broken_by`[...]; generyczna bramka `apply_condition_gate` we wszystkich ścieżkach nakładania kondycji; rage=STR+2/damage_bonus+3/immune[slowed,weakened]/broken_by[stunned,confused]/on_expire→exhausted/6 rund; Zasada 4 w schema+validator+forge+CZĘŚĆ X+prompt; rzuty walki nietknięte; 13/13 pytest real-engine + 1/1 Playwright)

### Blok 4 — Zaawansowane mechaniki bojowe (można PRZED Blokiem 3; S18 wymaga S8)
- [x] S15 — System reakcji (pre-deklaracja) + skill dodge — [#610](https://github.com/szmidtpiotr/ai-gm/issues/610) (pierwsza reakcja w grze: flaga `reaction_declared` konsumowana przy 1. trafieniu/rundę; test DEX vs wynik ataku wroga PRZED obrażeniami; sukces=0 dmg, krytyczna porażka=lockout 1 rundy; skill-gated rank≥1; rzuty ataku wroga nietknięte; toggle w Sandbox + UI walki)
- [x] S16 — Reakcja shield_block — [#611](https://github.com/szmidtpiotr/ai-gm/issues/611) (druga reakcja w grze, reużywa frameworku S15; tarcza = założona broń z key `shield`/label `tarcz`; test STR vs atak DC≥12 — sukces redukuje dmg o 1k6+STR, margines≥+5 pełne odparcie, crit-fail tarcza −3 durability; XOR z unikiem; skill `shield_block` STR; bez nowego typu efektu → Zasada 4/CZĘŚĆ X bez zmian; 16/16 pytest real-engine + 3/3 Playwright; rzuty ataku wroga nietknięte)
- [x] S17 — Wrestling: skill nakłada kondycje wrogom (opposed STR vs STR) — [#612](https://github.com/szmidtpiotr/ai-gm/issues/612) (pierwszy skill, którego SUKCES mechanicznie nakłada kondycję na wroga; akcja bojowa gate engaged, konsumuje turę; generyczny prymityw `_apply_skill_outcome_conditions` + 3 kolumny skill_counters `on_success/on_crit/on_critfail_self_condition` — Zasada 1, zero `if skill_key==`; sukces→slowed, margines≥+5→stunned, crit-fail→gracz slowed; reuse apply_condition_to_combatant/_to_player; BEZ nowego typu efektu → CZĘŚĆ X/Zasada 4 bez zmian; rzuty ataku nietknięte; 13/13 pytest real-engine + 2/2 Playwright; live e2e na DEV)
- [x] S18 — Prymityw behavior_override + pełne confused/berserk/panicked — [#613](https://github.com/szmidtpiotr/ai-gm/issues/613) (nowy typ efektu `behavior_override`: random_table_k4/attack_nearest/flee; confused podniesiony do k4, panicked do flee, berserk NOWA kondycja; wróg z berserk atakuje najbliższego niezależnie od frakcji — nowa ścieżka obrażeń wróg→wróg w resolve_attack; +3 atak/+3 obrażenia/-3 AC foldowane generycznie; player-side banner k4 bez przejęcia tury; przy okazji naprawiono ukryty bug `_block` UnboundLocalError z S16 przy pudle wroga; Zasada 4 w 4 miejscach; rzuty ataku nietknięte; 17/17 pytest real-engine + 1/1 Playwright)
- [x] S19 — Kondycja hidden: untargetable + ambush_bonus — [#614](https://github.com/szmidtpiotr/ai-gm/issues/614) (dwa nowe typy efektów `untargetable` (wróg pomija ukrytego) + `ambush_bonus` (+2k6 pierwszy atak, oddzielny add po mnożniku, zdejmuje kondycję); top-level `granted_by:{skill,dc}` = ODWROTNOŚĆ cure (stealth DC 14 nakłada hidden) + `detect_dc` (wróg WIS save przy poszukiwaniu); helpery `_combatant_is_untargetable`/`_roll_ambush_bonus`/`add_condition_to_character` + `skill_service._match_grantable_condition`; Zasada 4 w 5 miejscach; rzuty ataku nietknięte; 19/19 pytest real-engine + 1/1 Playwright; live e2e DEV sandbox 77: wróg nie trafia ukrytego 10→10, zasadzka +7 zdejmuje hidden)

### Kamień milowy
- [x] S20 — 🎮 Playtest FAZY S (Sandbox sweep + /game-smoke; raport do [SMOKE] FAZA S; bez TDD) — [#615](https://github.com/szmidtpiotr/ai-gm/issues/615) (Sandbox sweep 15/15 kondycji PASS vs design doc; Arm 2 LLM: werdykt GRYWALNE Z ZASTRZEŻENIAMI — 0×P0, 0×P1, 1×P2 [#616] pod-emisja tagów GAMBLE/haggling/APPLY_CONDITION w swobodnej grze; mechanika silnika zdrowa, dług = dyscyplina promptu; liczby = startowe, tuning należy do Piotra)

> Poza zakresem FAZY S (zapisane w CZĘŚCI AI): disease/broken_limb (zegar świata), crafting mechaniczny (trade_craft/alchemy = narracyjne), pełne charmed/insane, skutki inwentarzowe pickpocket/torture.

---

## FAZA SF — Frontend FAZY S: pasek akcji + warstwa informacji zwrotnej (2026-06-15, post-S20)

> Pełny opis + język wizualny (`/interface-design`): `game_mechanics.md` CZĘŚĆ AI → „FAZA SF". Skąd: audyt frontendu po S20 — akcje FAZY S podłączone, ale pasek walki upycha 7 przycisków (na telefonie nieczytelny) i brak warstwy „dlaczego" (k4/omen/darmowa akcja/odporność/poziom wyczerpania). Decyzja Piotra 2026-06-15: 3 przyciski **[Atak] · [Akcja ▾] · [Ucieczka]**, „Akcja" otwiera bottom sheet. **Domyślnie tylko frontend gracza, ZERO zmian mechaniki/endpointów** — WYJĄTEK (dozwolony): SF8 (drobne rozszerzenie payloadu rzutu o `breakdown[]`, bez zmiany liczenia). SF9 okazał się czysto frontendowy (prezentacja powodu + gating przycisku). Każde zadanie = `[TASK] SFNN` wdrażane `/tdd` (test Playwright UI). Reużyć tokeny dark-fantasy, bump `?v=`. Prompt startowy: `prompt_sf.md`.

- [x] SF1 — Pasek 3 filary [Atak]·[Akcja ▾]·[Ucieczka] + bottom sheet (reszta przycisków → arkusz, te same handlery) [#619]
- [x] SF2 — Zawartość arkusza: znacznik kosztu (⏳ tura / ↺ reakcja) + dostępność + powód wyszarzenia (zwarcie/tarcza/mana/strefa) [#620]
- [x] SF3 — Reakcje (Unik/Blok) jako toggle „uzbrojony" [#631] ⚠️ ZASTĄPIONE przez SF10 (decyzja 2026-06-15: model reaktywny zamiast pre-deklaracji)
- [x] SF4 — Pasek statusu gracza: trwałe kondycje z ikoną + skutkiem + poziomem (np. „Wyczerpany 2/2") — wypełnia lukę S9 [#632]
- [x] SF5 — Ulotne komunikaty zdarzeń: zły omen (S11), darmowa akcja hasted (S12), confused/berserk wroga k4 (S18) [#634] — podłączone 3 sygnały obecne w payloadzie gracza; S14 odporność + player-side k4 (confused gracza) ODŁOŻONE jako drobne rozszerzenie payloadu (out of scope, odnotowane w #634)
- [x] SF6 — Karta rzutu: stawka hazardu „Ryzykujesz X zł" (S7/#616) + słowny stopień marginesu [#635] **needs-testing** — baner stawki (`#dice-stake-banner`, czyta `pending.gamble.stake`) widoczny przez cały rzut + słowo marginesu (z nawiązką/na styk/o włos wg |`sr.margin`|) przy Sukces/Porażka. Pure-helpery `sf6StakeLabel`/`sf6MarginDegree`. ZERO backendu. 3/3 Playwright GREEN + wizualna 390px OK; deployed DEV (?v=635)
- [x] SF7 — Ikony 8 kondycji w COND_BADGE_MAP (on_fire/exhausted/hidden/rage/blessed/hasted/hemorrhage/inspired) [#636] **needs-testing** — 8 glifów + window.COND_BADGE_MAP expose; klucze=kanon katalogu; 2/2 Playwright kontrakt GREEN + wizualna 390px OK; ZERO backendu; bump ?v=636
- [x] SF8 — Karta rzutu: rozbicie wyniku po NAZWANYM źródle [#637] **needs-testing** — karta ataku (dymek logu) + **okno kości ataku** + overlay testu umiejętności rozbijają wynik po polskiej nazwie składnika (`🎲 14 +2 Siła +3 Ranga +2 Biegłość = 21`), dodatnie zielone `--success` / ujemne czerwone `--danger`. Okno kości ataku: rozliczenie przeniesione PRZED animację kości, by pokazać rozbicie na karcie wyniku (parytet z testem umiejętności; dwell 2.8 s gdy są składniki). Zweryfikowane na żywej walce (#84): `🎲 17 +1 Siła = 18`. ⚠️ KOREKTA ZAKRESU vs spec: audyt kodu wykazał, że kondycje/rana/afiksy **NIE wchodzą do rzutu GRACZA** (tylko stat+ranga+biegłość+broń; `_combatant_stat_modifier` działa tylko dla wrogów). Wszystkie realne składniki JUŻ są w payloadzie → SF8 okazał się **CZYSTY FRONTEND, ZERO backendu** (wyjątek `breakdown[]` niepotrzebny). Pure-helpery `sf8AttackBreakdown`/`sf8SkillBreakdown`/`sf8BreakdownHtml` (window, kontrakt). 5/5 Playwright GREEN + wizualna 390px OK (dymek + okno kości); bump `?v=637b`. ODŁOŻONE (osobny ticket mechaniczny): wliczenie kondycji/rany do rzutu gracza (S8/S9 dziś nie obejmują rzutów gracza).
- [x] SF9 — 🐛 BUG: wskrzeszenie nie da się włączyć w adminie + mylący komunikat u gracza [#638] **needs-testing** — **Diagnoza PEWNA (2026-06-15, test API):** backend OK (curl PATCH utrwala). GŁÓWNA przyczyna: select „Tryb" w System→Wskrzeszenie (`system.js:154`) ma FIKCYJNE opcje (fixed/percent_of_xp/unlimited), backend zna inne (`VALID_MODES`: xp_revert/gold_percent/gold_recent_days/item_loss/admin_free) → zapis leci ze złym mode → 422 → cały PATCH (z `enabled`) odrzucony → „mimo kliknięcia nie zapisuje". Fix: (1) ✅ HOTFIX 2026-06-15 — poprawiono opcje selecta na 5 prawdziwych trybów + opis (system.js, ?v=31→32; zapis configu znów działa); (2) ✅ [#638] front gracza: `handleResurrect` rozróżnia `preview.reason` — pure-helper `sf9DisabledReason` (`resurrection_disabled`→„Wskrzeszenia wyłączone przez Mistrza Gry", `no_uses_remaining`→„Brak pozostałych wskrzeszeń", fallback) wystawiony na `window` (kontrakt); 3/3 Playwright GREEN + wizualna 390px OK; bump `?v=638`; ZERO backendu; (3) ✅ DECYZJA Piotra 2026-06-15: zostaje UKRYWANIE przycisku przy `!enabled` (już w kodzie — `#resurrect-btn` `hidden` + `showDeathScreen` odsłania tylko gdy `enabled`); opcję „wyszarz+powód" odrzucono. ⚠️ Czysto frontend gracza. Uwaga: globalny stan włączony ręcznie API 2026-06-15.
- [x] SF10 — Reaktywny modal uniku/bloku (ZASTĘPUJE pre-deklarację S15/S16 + toggle SF3) [#633] **needs-testing** — okno reakcji przy trafieniu (pending_reaction, pauza), modal Przyjmij/Unik/Blok bez liczby obrażeń, timeout 8 s=take, 1/rundę, toggle usunięty. 6/6 pytest + 46 regresji + 2/2 Playwright GREEN; deployed DEV. Rzut ataku wroga nietknięty.
- [x] SF — 🎮 Kamień: playtest czytelności [#639] **needs-testing** — sweep 390px (kampania #84) + przegląd warstwy feedbacku przez realne ścieżki renderu: pasek 3 filary [Atak·Akcja·Ucieczka] + bottom sheet OK; pasek statusu z ikonami + poziom „Wyczerpany 2/2" OK; SF5 ulotne (omen/pośpiech/k4) OK; SF6 stawka „🪙 Ryzykujesz 5 zł" + margines (z nawiązką/na styk/o włos) OK; SF8 rozbicie po nazwanym źródle OK; SF9 komunikaty wskrzeszenia OK; SF10 reaktywny modal (#633 GREEN). Brak błędów JS UI walki. Werdykt czytelności = Piotr (raport w #639). **FAZA SF KOMPLETNA (SF1–SF10 + kamień).**

---

## FAZA L — Lochy kafelkowe (2026-06-12, redesign) — 🔨 W TOKU (15/24; FAZA S ✅ kompletna; prompt: prompt_l.md; smoke: /game-smoke-dungeon przy L13c i L19)  —  ✅ zrobione (przeniesione)
### Blok 1 — Silnik grafu
- [x] L1 — Konfiguracja kafelkowa lochu w DB + admin (tile_category_key, tile_count, boss_tile_id, endless_growth_n — dziś modal zbiera, baza nie zapisuje) — [#670](https://github.com/szmidtpiotr/ai-gm/issues/670)
- [x] L2 — Generator rozgałęzionego grafu + dungeon_run v2 (odnogi, fog, door hints, powtórki z re-rollem, positions per postać — podwalina MP) — [#671](https://github.com/szmidtpiotr/ai-gm/issues/671)
- [x] L3 — Wejście przez graf: /enter → tylko kafelki; 409 bez kategorii; blok [LOCH] w kontekście narratora (hybryda: opis z DB + koloryzacja LLM) — [#672](https://github.com/szmidtpiotr/ai-gm/issues/672)
- [x] L4 — Ruch przez drzwi: POST /dungeons/move + exit_conditions + deterministyczny start walki + backtracking — [#673](https://github.com/szmidtpiotr/ai-gm/issues/673)

### Blok 2 — Mechaniki na kafelku
- [x] L5 — Walka: absolutna skala D1–D5 (koniec rubber-bandingu; dawne U23; TIER_ENEMY_LEVELS, scale_enemy_for_dungeon_tier, re-roll Decyzja 9, endless %-bonus Decyzja 7, _dungeon_enemy_overrides w initiate_combat) — [#674](https://github.com/szmidtpiotr/ai-gm/issues/674) **needs-testing**
- [x] L6 — Skrzynie (rzut DEX, 3 próby, 30% pułapki), zagadki (3 próby + hinty), pułapki jako efekty, no soft-locks (dawne U22) — [#675](https://github.com/szmidtpiotr/ai-gm/issues/675) **needs-testing**
- [x] L7 — Checkpointy + śmierć kończy run + porzucenie 50% cooldown (dawne U21; NADPISUJE E16-restart) — [#676](https://github.com/szmidtpiotr/ai-gm/issues/676) **needs-testing**
- [x] L8 — Boss, loot, tryb nieskończony ("Wyjdź z łupem / Idź głębiej", segmenty +n, skalowanie cykli) — [#677](https://github.com/szmidtpiotr/ai-gm/issues/677) **needs-testing**

### Blok 3 — Czystka legacy
- [x] L9 — Usunięcie trybu proceduralnego (kod + admin UI + testy legacy; seedy starych lochów is_active=0; DB bez destrukcji) — [#678](https://github.com/szmidtpiotr/ai-gm/issues/678)

### Blok 4 — UI gracza
- [x] L10 — Flaga dungeon_enabled dla graczy (admin toggle, default ON; egzekwowana w API i UI) — [#679](https://github.com/szmidtpiotr/ai-gm/issues/679)
- [x] L11 — Mapa kafelkowa: przycisk mapy w lochu pokazuje graf (odwiedzone obrazki + zarysy za drzwiami + marker pozycji) — [#680](https://github.com/szmidtpiotr/ai-gm/issues/680) **needs-testing**
- [x] L12 — Wybór drzwi: przyciski kierunków pod composerem + klik na mapie + obraz kafelka w scenie + akcje skrzynia/zagadka — [#681](https://github.com/szmidtpiotr/ai-gm/issues/681) **needs-testing**
- [x] L13 — Modale: śmierć / porzucenie / resume / wybór po bossie — [#682](https://github.com/szmidtpiotr/ai-gm/issues/682) **needs-testing**
- [x] L13b — Wejście z ekranu startowego (bohater idle; scalenie trybów D9 w jeden "Wyprawa do lochu") — [#683](https://github.com/szmidtpiotr/ai-gm/issues/683) **needs-testing**
### Blok 5 — Kontent: krypta (bez TDD; pilot → akceptacja → batch)
- [x] L14 — Kategoria "krypta" + 20 definicji kafelków (mix drzwi 6/8/4/2-boss; wrogowie-nieumarli, zagadki, skrzynie) + **4 kafle-zaślepki 1-drzwiowe (N/S/E/W, id 26–29) wymagane przez Decyzję 2b/L-doors #697** — krypta `caps_complete:true`, `open_doors:0` ✅ — [#690](https://github.com/szmidtpiotr/ai-gm/issues/690)
- [x] L15 — Nowy BASE_PROMPT (bogate narysowane wnętrza, 768px) + scripts/generate_tiles_batch.py; pilot 5→akceptacja Piotra→pełny batch 20/20 krypta. Fix: kompozytor skalował 768→512 (#691, geometria proporcjonalna). — [#691](https://github.com/szmidtpiotr/ai-gm/issues/691)
- [x] L16 — Opisy PL kafelków (batch + przegląd Piotra; paliwo narratora) + loch pilotażowy krypta_probna (realizuje H5) — [#693](https://github.com/szmidtpiotr/ai-gm/issues/693)

## FAZA B — Balans 3 klas + Czary maga (2026-06-14, sesja projektowa — decyzje w game_mechanics.md CZĘŚĆ AK)  —  ✅ zrobione (przeniesione)
### Blok 1 — Tożsamość klas (naprawa bugów, PILNE)
- [x] [#624](https://github.com/szmidtpiotr/ai-gm/issues/624) — B1 — Rogue staty: DEX+2/LCK+1 zamiast INT+2/WIS+1 — osobna gałąź `rogue` w `_build_character_sheet` (`characters.py:205`) + odwrotność w `_core_bases_from_stored_stats:440`. **Bug krytyczny** (rogue dziś dostaje staty maga)
- [x] [#642](https://github.com/szmidtpiotr/ai-gm/issues/642) — B2 — Rogue HP base 8: `ARCHETYPE_BASE_HP["rogue"]` 10→8 (`vitality_service`); DB seed już = 8 (`migrations_admin.py:2892`, bez migracji); kreator pokazuje 8 w DWÓCH miejscach (`_wizardCalcHP` + etykieta karty archetypu). Ordering warrior 10 > rogue 8 > mag 6. **Uwaga:** DB `game_config_archetypes.hp_base` dla warrior zdryfował do 12 (kolumna NIE czytana przy tworzeniu postaci — char HP liczy `vitality_service`, więc gra niezmieniona) — osobny task do decyzji Piotra
- [x] [#644](https://github.com/szmidtpiotr/ai-gm/issues/644) — B3 — Rogue budżet skilli: `SKILL_BUDGET["rogue"]`=10/9 (slots/active) + `ARCHETYPE_SKILL_WEIGHTS["rogue"]` (bias złodzieja/zwiadowcy: stealth/lockpick/sleight_of_hand/acrobatics/awareness/investigation) + `lockpick`+`acrobatics` dodane do `CREATION_SKILL_POOL` (inaczej bias martwy) — `character_creation_config.py`. Rogue 9 aktywnych > warrior 7, bez fallbacku warrior. **Uwaga:** ścieżka kampanijna `POST /campaigns/{id}/characters` (`characters.py:2393`) wymusza warrior dla rogue (starter loot) — żywa ścieżka to hero-first `POST /characters` (poprawna); osobny task do decyzji Piotra
- [x] [#645](https://github.com/szmidtpiotr/ai-gm/issues/645) — B4 — Rogue sneak attack jako cecha klasy (+1d6 z ukrycia). **Decyzja D2 rozstrzygnięta (Piotr 2026-06-15): cecha klasy** (nie generyczny hidden). Helper `_sneak_attack_bonus(sheet)` (rogue-only, `combat_service`) dolicza `sneak_attack` PONAD generyczny `ambush_bonus` (reuse okna `hidden` S19, bez duplikatu kondycji), raz, po mnożniku (nie podwajany na nat20). Wartość startowa `1d6` (Numbers Policy — tuning po B5/B13). 9/9 pytest + 1/1 Playwright GREEN
- [x] [#646](https://github.com/szmidtpiotr/ai-gm/issues/646) — B5 — Test balansu regresyjny: pytest 3-klasowy (HP ordering warrior>rogue>scholar, staty per klasa, rogue skille>warrior, przeżywalność band) — rozszerzenie `test_issue475_combat_balance.py` o 7 testów (`test_b5_*`). Czyta realne źródła prawdy (`ARCHETYPE_BASE_HP`, `SKILL_BUDGET`, `_build_character_sheet`) — siatka regresyjna pilnująca, że tożsamość 3 klas (B1–B4) nie cofnie się. **Wyjątek bez cyklu TDD** (sam test = deliverable, brak nowego kodu produkcyjnego). Próg „mag w melee ginie" = ≥100% straty HP (nie wymyślony band — przy HP 6 expectation = śmierć); 12/12 GREEN. **Domyka Blok 1 (tożsamość klas).**
- [x] [#622](https://github.com/szmidtpiotr/ai-gm/issues/622) — S17-EXT **Część A (solo) ZROBIONE (2026-06-15):** udane zapasy (`SUCCESS`/`CRITICAL_SUCCESS`) z `wrestling` rank ≥ 3 → słabszy darmowy cios w tej samej turze (rzut bronią, obrażenia ÷2 floor min 1, BEZ nat-20-double, BEZ ponownego wyzwalania zapasów, jeden cios = jeden event `wrestling_followup`). Reuse ekonomii `extra_action` (S12): wrestling woła `advance_turn` RAZ — follow-up nie pochłania kolejnej akcji. Rank 1–2 = czysta kontrola jak dziś (baza nietknięta). `combat_service.resolve_wrestling` + karta `wrestling_followup` w `app.js?v=622`. 6/6 pytest real-engine + 13/13 backward-compat #612 + 1/1 Playwright GREEN. **Część B (MP przewaga dla sojuszników):** ⛔ FAZA 5 (towarzysze + reakcje). Spec: `game_mechanics.md` → S17 → „S17-EXT"

### Blok 2 — Czary maga Faza 1 (ST/self/heal/kontrola; po FAZIE S ✅)
- [x] [#648](https://github.com/szmidtpiotr/ai-gm/issues/648) — B6 — Schema + seed czarów z `rpg_spells_design_doc.md` adoptowalnych teraz (atak ST, heal self, self-buff AC, kondycje) — tier/DC/mana wg docu. **Wdrożone (2026-06-15):** 16 nowych czarów Faza 1 zaseedowanych do `game_config_spells` (10→26) przez idempotentny blok `v2-spells-faza-b-seed` w `migrations_admin.py` — **bez zmian schematu** (istniejące kolumny pokrywają wszystko). Atak ST: fire_bolt/frost_bolt/acid_splash/lightning_arrow/ice_lance/inferno_strike. Heal-self: minor_heal. Self-buff obronny: ward_of_iron/mage_armor. Kondycje (effect_type → ISTNIEJĄCY klucz `game_config_conditions`, zero duplikatu): frost_grip→slowed, hex→cursed, poison_touch→poisoned, blind→blinded, confusion→confused, stun_bolt→stunned. Narrative: detect_magic (pod start L1 = B8). `rank2/rank3_json`=NULL (skalowanie rang = tuning po B7/B13). Silnik przyjmuje nowe czary bez nowego kodu (dispatch po `spell_type` — zweryfikowane: minor_heal leczy 1d6+INT, fire_bolt 1d8). **Poza B6:** AoE→B11 (po #595), summon/ally/reakcje→Blok 3, naliczanie kondycji w walce→B9, absorpcja tarcz→B10, CHA charm→D3. 19/19 pytest + 2/2 Playwright GREEN.
- [x] [#649](https://github.com/szmidtpiotr/ai-gm/issues/649) — B6a — 🐞 Atak czarem w walce: (1) zawis tury — `handleCombatSpellAttack` (`app.js`) brak `finally` → `combatBusy` zostaje `true`, watcher tury wroga (`!combatBusy`) nie odpala, widać dopiero po F5; (2) brak animacji kości (normalny atak woła `playCombatDiceRoll`, czar nie). **Bug grywalności P0** — blokuje playtest B13
- [x] [#650](https://github.com/szmidtpiotr/ai-gm/issues/650) — B6b — 🐞 Narracja ataku czarem opisuje fizyczną broń (laska jako melee) zamiast magii — ten sam payload `kind:'player_attack'` bez kontekstu czaru; wstrzyknąć nazwę zaklęcia + flagę „atak magiczny" do promptu narracji. **Bug P1**
- [x] [#651](https://github.com/szmidtpiotr/ai-gm/issues/651) — B6c — ✨ Atak czarem jako rozwijany przycisk przy „Atak" (analogicznie do opcji pod „Akcja") + lista czarów atakujących — UX, frontend
- [x] [#652](https://github.com/szmidtpiotr/ai-gm/issues/652) — B7 — Tier-gating nauki (max_tier=ceil(level/2), integracja z XP: 75/50/100 — **arcane_points martwe, waluta = XP**) + **model trafienia czaru (DEC D-spell rozstrzygnięta 2026-06-15)**: czary atakujące BEZ ZMIAN (d20+INT vs unik, #475 nietknięte); czary nie-atakujące = **pojedynek INT_mag vs stat obrony celu** (WIS=umysł: confused/cursed/blinded/charmed · CON=ciało: slowed/frozen/stunned/poisoned — reuse #584 opposed stats + `_combatant_stat_modifier`); **zwrot ½ many przy oporze** wroga (pełna mana gdy łapie / przy miscast). Goblin-tępak (WIS 8) nie obroni umysłu; caster (WIS 14) oporny. Tier → bramka nauki + koszt many (nie stały DC)
- [x] [#655](https://github.com/szmidtpiotr/ai-gm/issues/655) — B8 — Startowy zestaw maga L1 = `fire_bolt`+`minor_heal`+`ward_of_iron`+`detect_magic` (atak/heal/obrona/utility, 4× tier 1). **Decyzja D-obronna (Piotr 2026-06-15): `ward_of_iron` (tier 1), NIE `mage_armor` (tier 2)** — spójność z bramką nauki L1 z B7 (`max_tier=ceil(lvl/2)=1`); dziś oba placeholdery (prawdziwa tarcza=B10). `grant_starting_spells` (`spell_service`) grantuje nowy zestaw nowym scholarom; migracja `v2-spells-faza-b-b8-starter-backfill` dosiewa 4 czary istniejącym magom **NIE-destrukcyjnie** (INSERT OR IGNORE — stare `magic_bolt`/`mend_wounds`/`magic_light` zostają). 7/7 pytest + 1/1 Playwright GREEN; backfill potwierdzony na 3 scholarach DEV (każdy ma 4 nowe + stare).
- [x] [#656](https://github.com/szmidtpiotr/ai-gm/issues/656) — B9 — Mapowanie kondycji czarów na FAZA S w walce — reużycie, nie duplikat. **Wdrożone (2026-06-15):** gałąź `spell_type=='effect'` w `combat_service.resolve_attack` (przed ścieżką ataku/obrażeń) → helper `_resolve_effect_spell_in_combat` woła `spell_service.resolve_combat_effect_spell` (nowy; pojedynek INT vs WIS/CON z B7 [#652], NIE rzut na unik). Łapie → `apply_condition_to_combatant` (kondycja FAZY S, zero duplikatu); opór → kondycja NIE nałożona + `mana_refund_on_resist` (½ many, floor); Nat 1 → miscast (pełna mana). Czar kontroli NIE zadaje obrażeń, tury NIE zaawansowuje (parytet z atakiem). 6 czarów: frost_grip→slowed(CON), hex→cursed(WIS), poison_touch→poisoned(CON), blind→blinded(WIS), confusion→confused(WIS), stun_bolt→stunned(CON). `sleep`→`sleeping` **wykluczony** (brak kondycji w katalogu FAZY S → łagodne odbicie). Czary atakujące nietknięte (#475). Frontend `_handleCombatAttackResult` renderuje łapie/opór/miscast bez liczby obrażeń (`app.js?v=656`). 13/13 pytest + 1/1 Playwright GREEN; smoke na realnym katalogu DEV (frost_grip→slowed, save CON, mana 2). **Decyzja D-spell domknięta w praktyce — model trafienia wpięty do silnika.**
- [x] [#657](https://github.com/szmidtpiotr/ai-gm/issues/657) — B10 — Pula absorpcji / temp-HP dla tarcz (ward_of_iron, mage_armor). **Wdrożone (2026-06-15):** gałąź `spell_type=='defense'` w `combat_service.resolve_attack` (wzorzec B9) → `_resolve_defense_spell_in_combat`: odejmij PEŁNĄ manę, ustaw `absorb_hp` na combatancie gracza (NIE stackuje — re-cast = świeża pula), ZERO obrażeń wrogowi, log `spell_defense`. Helper `_apply_absorption(p,dmg,out)` wpięty w OBIE ścieżki obrażeń wroga (po uniku/bloku, PRZED HP). `spell_service.defense_absorb_amount` czyta `effect_json.absorb` (fallback wg tieru). Migracja: **dodano brakującą kolumnę `effect_json` do `game_config_spells`** (`v2-spells-effect-json-col`) + set `ward_of_iron={"absorb":6}` / `mage_armor={"absorb":10}` (NIE-destrukcyjnie). **Naprawiony ukryty bug:** dotąd rzut czaru obronnego w walce wpadał w ścieżkę ataku i zadawał `2d6`. Frontend: defense-cast → „🛡 Tarcza aktywna — pochłonie N", badge `🛡 N` przy HP gracza w panelu walki (`app.js?v=657`). Wartości startowe (Numbers Policy): ward 6/T1/2many, mage 10/T2/3many; płaskie, combat-scoped. 12/12 pytest + 1/1 Playwright GREEN; migracja potwierdzona na DEV (ward 6, mage 10).
- [x] [#659](https://github.com/szmidtpiotr/ai-gm/issues/659) — B11 — AoE multi-target maga (burning_arc/chain/fireball). **Wdrożone (2026-06-15):** gałąź `spell_type=='attack_aoe'` w `combat_service.resolve_attack` (po B10, przed ST) → `_resolve_aoe_spell_in_combat`: 1 rzut d20 vs cel główny (honoruje #595 `target_id`), trafienie → osobna kość obrażeń na każdy cel. `aoe=1` (obszar: burning_arc/fireball) = wszyscy żywi; `aoe=0` (łańcuch: chain_lightning) = maks 3 (`_AOE_CHAIN_MAX_TARGETS`). Mana z góry, Nat 1 → miscast, Nat 20 → 2× per cel. Loot/XP/death-log reużyte per wróg (wzorzec single-target). Frontend: blok `attack_aoe` w `_handleCombatAttackResult` renderuje `aoe_hits[]`, komunikat "N celów trafionych (K pada)", loot zbierany z `h.dead`. Helper `_aoe_target_ids(living, aoe_flag)` testowalny izolowanie. **Domknięcie (2026-06-15):** dodano realny helper `_aoe_target_ids` (poprzedni stan miał inline `others[:2]` — funkcja go nie używała) + refaktor doboru celów na helper + `out["xp_granted"]` agregowane ze wszystkich zabitych (wcześniej tylko per-hit). Dispatch SELECT bez kolumny `aoe` (izolowane fikstury B9/B10 jej nie miały → handler dociąga `aoe` osobno, wzorzec B10/effect_json). Bump `app.js?v=659-b11-aoe`. 10/10 pytest + 86/86 regresja czarów (B6–B12) + 1/1 Playwright (kontrakt danych) GREEN; **dowód silnikowy w Sandbox DEV:** fireball (aoe=1) → 3/3 gobliny padają, mana 11→5, XP 9, victory; chain_lightning (aoe=0) przy 5 wrogach → cap 3 trafione, 2 nietknięte. **needs-testing**
- [x] [#658](https://github.com/szmidtpiotr/ai-gm/issues/658) — B12 — Admin: czary w panelu + Smart Entry dla `game_config_spells`. **Audyt: większość już istniała** (backend `/api/admin/spells` CRUD + Smart Entry `game_config_spells` w `WRITABLE_TABLES`/schemacie od B6/B7; zakładka **Czary** w `content.js`). **B12 domknął FRONTEND:** (1) wpięcie czarów do Kreatora AI — `SE_TABLE_LABELS`+=`Czary`, mapa `_openSmartEntryForCurrentTab`+=`spells→game_config_spells` (wcześniej klik Kreator AI na Czarach dawał „nie obsługuje tej zakładki"); (2) ręczny formularz `_openSpellForm` rozszerzony do pełnego schematu (`spell_type`/`effect_stat`/`effect_type`/`effect_duration`/`aoe`/`rank2_json`/`rank3_json`; `target_zone` poprawione single/aoe/self→any/self/engaged/ranged). Bump `?v=39→40`. Backend bez zmian (pytest 6/6 strażnik kontraktu Smart Entry + Playwright 2/2 RED→GREEN UI).
- [x] [#663](https://github.com/szmidtpiotr/ai-gm/issues/663) — B13 — Playtest: mag solo grywalny (heal/tarcza/atak/kontrola w realnej walce). **Werdykt: MAG GRYWALNY (2026-06-15).** fire_bolt ✅ atak czarem (dmg 5, mana 9→7) · ward_of_iron ✅ absorpcja tarczy (pool 6 soaks enemy hits) · frost_grip ✅ kondycja `slowed` na wrogu (single → CON) · minor_heal ✅ leczenie w walce (healed +2, hp 6→7). **Bug P0 znaleziony i naprawiony:** `minor_heal` (spell_type='heal') brak dispatcha → wpadał w ścieżkę ataku (zabijał wroga za heal_die dmg); fix: `_resolve_heal_spell_in_combat` + dispatch blok [#666](https://github.com/szmidtpiotr/ai-gm/issues/666). 95/95 pytest GREEN (B6–B13). Raport → [#663 komentarz](https://github.com/szmidtpiotr/ai-gm/issues/663#issuecomment-4711587747). **Domyka Blok 2 (czary Faza 1).** needs-testing

## FAZA HI — Inspektor Bohatera (admin) (2026-06-15 — decyzje w game_mechanics.md CZĘŚĆ AL) [7/7]

> Narzędzie admina: podgląd+edycja żywego bohatera (ekwipunek dodaj/usuń/załóż, staty, skille, zaklęcia, kondycje, złoto, XP, questy) — jak monitor kampanii, ale dla bohatera. **~90% backendu już istnieje** (reuse cheat/xp/inventory/spells); dopisać tylko 3 luki + czysty GET. Decyzje Piotra: (1) nowa sekcja nawigacji „Bohaterowie" + link z monitora kampanii; (2) reuse cheat + 3 luki (set skill rank, set mana, add/remove condition); (3) audyt `admin_audit_log` + ostrzeżenie konto #1013 + blokada edycji w trakcie walki/tury. **Niezależne od S/L/MP — intermezzo kiedy Piotr zechce** (rekomendacja: po FAZIE L). Każde zadanie = `[TASK] HINN` wdrażane `/tdd`. Prompt startowy: `prompt_hi.md`.

- [x] HI1 — Backend: czysty `GET /admin/characters/{id}/full` (agregat) + 3 luki (set skill rank, set mana, add/remove condition) + audyt mutacji w `admin_audit_log` + guard `live_locked` (409 gdy aktywna walka/tura) — [#623](https://github.com/szmidtpiotr/ai-gm/issues/623)
- [x] HI2 — Sekcja „Bohaterowie": nawigacja (`index.html` SECTIONS+PORTED, bump ?v) + `sections/heroes.js` lista hero-first (filtr status/owner) + szkielet modalu inspektora; baner #1013 + live-lock — [#625](https://github.com/szmidtpiotr/ai-gm/issues/625)
- [x] HI3 — Inspektor zak. Arkusz: edycja statów/skilli/HP/many/poziomu/kondycji/złota/XP przez reuse endpointów; re-fetch `/full` po zapisie; respekt 409 live-lock — [#626](https://github.com/szmidtpiotr/ai-gm/issues/626)
- [x] HI4 — Inspektor zak. Ekwipunek (dodaj/usuń/załóż + trwałość) + Zaklęcia (naucz/awansuj) + Questy (dodaj/zalicz); cienki guard+audyt inspektora dla equip+zaklęć (nowy `inspector_guard.py`) — [#627](https://github.com/szmidtpiotr/ai-gm/issues/627)
- [x] HI5 — Link „🧍 Otwórz inspektora" z monitora kampanii (`campaigns.js`, zakł. Przegląd) → reuse `openInspector` (export z `heroes.js`, bump `?v=37`); kontrakt bezpieczeństwa (audyt + 409 live-lock) dziedziczony z HI1/HI4, potwierdzony end-to-end — [#628](https://github.com/szmidtpiotr/ai-gm/issues/628)
- [x] HI6 — Opcja „🔓 Wymuś edycję" (force) gdy bohater live-locked (walka/tura): toggle w banerze modalu odblokowuje kontrolki, mutacje lecą z `force:true` (omija 409); #1013 twardo read-only (force nie omija); wymuszona edycja nadal audytowana; bump `?v=38` — [#629](https://github.com/szmidtpiotr/ai-gm/issues/629)
- [x] HI7 — Arkusz: grupowanie skilli „Posiadane" (rank ≥1) nad „Niewyuczone" (rank 0), każda grupa A→Z + licznik; czysto prezentacyjne nad `/full`; bump `?v=39` — [#630](https://github.com/szmidtpiotr/ai-gm/issues/630)

---

## FAZA 5 — Multiplayer (sesja projektowa 2026-06-12 — decyzje w game_mechanics.md CZĘŚĆ AC)  —  ✅ zrobione (przeniesione)
- [x] G20 — Eksport-książka: nowelizacja kampanii lokalnym modelem (Bielik 11B / Ollama na .170), offline; działa też dla solo — **prototyp CLI gotowy** (`book_export_service.py`, pilot 3 rozdz. z kamp. #546); UI/modal odłożone do FAZY G — [#547](https://github.com/szmidtpiotr/ai-gm/issues/547)

## FAZA 6 — Observability + Długoterminowe  —  ✅ zrobione (przeniesione)
- [x] ~~H5~~ — GPU pipeline: tile → LLM Vision → opis → DB → ZREALIZOWANE JAKO L16 (FAZA L, 2026-06-16) — [#693](https://github.com/szmidtpiotr/ai-gm/issues/693)

## FADM — Przebudowa Admin Panelu (strangler-fig) ✅ KOMPLETNE 2026-06-09

Monolit `admin_panel_v3` (19 447 linii) → modularny `frontend/admin/` (14 sekcji ES). P0-P17 kompletne. admin3 usunięty; `/admin3/` → 301 → `/admin/`. Epic [#401](https://github.com/szmidtpiotr/ai-gm/issues/401).

- [x] FADM-P0 — Bootstrap skorupy `admin/` + shared utils (api/table/toast/modal/form) — [#402](https://github.com/szmidtpiotr/ai-gm/issues/402) ✅ 2026-06-08
- [x] FADM-P1 — Port sekcji overview — [#403](https://github.com/szmidtpiotr/ai-gm/issues/403) ✅ 2026-06-08
- [x] FADM-P2 — Port sekcji mechanics — [#404](https://github.com/szmidtpiotr/ai-gm/issues/404) ✅ 2026-06-08
- [x] FADM-P3 — Port sekcji content (+ D5 item VIEW) — [#405](https://github.com/szmidtpiotr/ai-gm/issues/405) ✅ 2026-06-08
- [x] FADM-P4 — Port sekcji world (+ D7 encountery) — [#406](https://github.com/szmidtpiotr/ai-gm/issues/406) **← następne**
- [x] FADM-P5 — Port sekcji map — [#407](https://github.com/szmidtpiotr/ai-gm/issues/407)
- [x] FADM-P6 — Port sekcji campaigns (+ B6/B7/D6) — [#408](https://github.com/szmidtpiotr/ai-gm/issues/408)
- [x] FADM-P7 — Port sekcji dungeons — [#409](https://github.com/szmidtpiotr/ai-gm/issues/409)
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

## Zrobione dodatkowe  —  ✅ zrobione (przeniesione)
- [x] [#595](https://github.com/szmidtpiotr/ai-gm/issues/595) — wybór celu ataku w walce z wieloma wrogami: backend honoruje `target_id` (czysty helper `_select_player_target` — żywy wróg, melee bramkowane strefą, fallback=auto), endpoint `resolve-attack` przekazuje `target_id`, front: klikalne wiersze wrogów + podświetlenie celu 🎯. **Odblokowuje B11 (AoE).** 7/7 pytest + 1/1 Playwright + dowód silnikowy w Sandbox (skeleton 0/10, goblin 10/10). **#595a follow-up:** po zabiciu celu z focusem 🎯 przeskakuje na następnego żywego wroga (`_nextLivingEnemyId`, kolejność inicjatywy) zamiast się czyścić — +1/1 Playwright. **review/needs-testing**
- [x] [#372](https://github.com/szmidtpiotr/ai-gm/issues/372) — Opening scene zawsze w lesie: wyodrębniono `build_opening_plan_context()` + 16 testów TDD — commit 88c1d9a
- [x] [#397](https://github.com/szmidtpiotr/ai-gm/issues/397) — Opening scene zawsze "budzisz się w lochu": system_prompt OTWARCIE SESJI dopuszcza miasta/tawerny, zakaz tropu przebudzenia — commit 635b72f
- [x] [#398](https://github.com/szmidtpiotr/ai-gm/issues/398) — Header HP bar 50% mimo 30/30: enterGame() woła updateHeaderStats() — commit 635b72f
- [x] [#389](https://github.com/szmidtpiotr/ai-gm/issues/389) — LLM 429 TPM rate-limit: retry z backoffem w OpenAIDriver.generate_stream (max 3 próby, retry-after header)
- [x] [#390](https://github.com/szmidtpiotr/ai-gm/issues/390) — Zegar in-game nie tykał: advance_clock() dostał minutes= keyword + sub-hour accumulation
- [x] [#355](https://github.com/szmidtpiotr/ai-gm/issues/355) — C1 STORY_STALE nie działał w streaming path + escalation (10+ silniej, 15+ kritycznie) — commit 3eb0c2c
- [x] [#391](https://github.com/szmidtpiotr/ai-gm/issues/391) — C1 TRAVEL_HINT pills: sugestie odkrytych lokacji obok STORY_STALE (TDD, 4/4 GREEN) — commit 69044c0 — Playwright regression GREEN z prawdziwym LLM (OpenAI)
- [x] [#392](https://github.com/szmidtpiotr/ai-gm/issues/392) — LLM narrative death bez HP check: [RESTRICT] blok w system_prompt (TDD, 3/3 GREEN) — commit 1806324 — Playwright regression GREEN z prawdziwym LLM (OpenAI)
- [x] [#616](https://github.com/szmidtpiotr/ai-gm/issues/616) — SMOKE FAZA S P2: hazard (S7) nie ruszał złotem w swobodnej grze. Fix: `skill_service.detect_gamble_intent()` + pre-LLM most intent→tag w `turns.py` — gdy gracz deklaruje stawkę, syntetyzuje `[GAMBLE:stawka:DC:n]` PRZED skanerem skilli/U7 i przepuszcza przez istniejący tor S7 (walidacja stawki/limit/wypłata bez zmian). TDD 6/6 pytest + 1/1 Playwright GREEN; live e2e DEV: „stawiam 5 złota" → gold 192→197 (+5), gamble_scene_count=1. Targowanie/APPLY_CONDITION poza zakresem tej iteracji.
- [x] [#566](https://github.com/szmidtpiotr/ai-gm/issues/566) — Walka: narracja ataku blokowana „Walka trwa!" + brak karty rzutu. Root cause: `sendCombatNarration` POST-ował pakiet `__AI_GM_COMBAT_ROLL_V1__` na zwykły `/turns`, który blokuje bezwarunkowo (strumieniowy ma gwardię `current_turn=='player'` + emituje [GM_ROLL]). Fix: repoint na `_sendTurnStream` + guard COMBAT_ROLL w `_maybe_handle_blocked_player_combat_turn`. 2/2 pytest + 1/1 Playwright GREEN. **needs-testing**
- [x] [#567](https://github.com/szmidtpiotr/ai-gm/issues/567) — Walka: generyczny „Wróg" (key='enemy') wybierany bo słowo „wróg" pasowało do etykiety placeholdera w `_resolve_enemy_key_from_context`. Fix: pomijanie generycznych placeholderów (`_GENERIC_ENEMY_KEYS/_LABELS`) + polska nazwa fallbacku „Napastnik" w `_create_pending_combat_enemy`. 3/3 pytest + 1/1 Playwright GREEN. **needs-testing**
- [x] [#568](https://github.com/szmidtpiotr/ai-gm/issues/568) — Walka: „brak lootu po zwycięstwie" — **WERDYKT: RNG, nie bug**. `roll_loot` rzuca każdy wpis niezależnie wg wagi (loot_enemy: 50/40/15%) → P(nic)≈25%. Ścieżka grant niezmieniona. Uwaga: `drop_chance=0.8` na wrogu nieużywana w roll_loot (do ew. decyzji projektowej). 3/3 pytest + 1/1 Playwright GREEN (dowody). **needs-testing**
- [x] [#569](https://github.com/szmidtpiotr/ai-gm/issues/569) — Walka: widoczny modal rzutu k20 (3D) przy ataku (parytet z testami umiejętności). `playCombatDiceRoll` reużywa dice-overlay + DICE.dice_box, odsprzężona od resolveSkillTest; wpięta w `handleCombatAttack` po wylosowaniu d20. 1/1 Playwright GREEN. **needs-testing**
- [x] [#621](https://github.com/szmidtpiotr/ai-gm/issues/621) — Walka: strukturalny `skip_turn` ignorowany → `slowed`/`stunned` bez efektu (zapasy „nic nie dają", wróg atakował mimo wygranej). Root cause: `evaluate_current_turn_conditions` blokował turę tylko dla `type=="block_action"`; nowy format `effects:[{"type":"skip_turn",chance,...}]` nieczytany (legacy płaski tylko gdy `effects` puste). Fix: handler `skip_turn` w pętli strukturalnej — losuje `chance` (default 1.0), trafienie → `block_action`. Dotyczy wszystkich źródeł slowed/stunned (też czary). TDD 4/4 pytest + 1/1 Playwright GREEN. **needs-testing**
- [x] [#395](https://github.com/szmidtpiotr/ai-gm/issues/395) — Aktywny preset LLM jako jedyne źródło prawdy: spójna tożsamość endpointu (provider+base_url+model z jednego źródła), leniwa hydratacja presetu w świeżych procesach, `LLMConfigError` zamiast cichego fallbacku do Ollama/gemma (TDD, 8/8 GREEN) — commit 526cfdd — zweryfikowane, zamknięte
- [x] [#396](https://github.com/szmidtpiotr/ai-gm/issues/396) — Admin3 Narzędzia→Playwright odpala wszystkie suity ux (regression/acceptance/admin3); test-agent skan rekursywny + run po ścieżce/grupie; nowy admin3 smoke 16/16 GREEN — commit 6058f90 (TDD 7/7 GREEN)
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
- [x] [#578](https://github.com/szmidtpiotr/ai-gm/issues/578) — U30 hardening: ruch tekstowy na torze JSON `/turns` (parytet ze streamingiem) + guard `travel_narrated_without_move` wpięty w żywy tor (wspólny helper `execute_directional_travel`/`guard_travel_desync`). 7/7 pytest + 1/1 Playwright. **review/needs-testing**
- [x] [#567](https://github.com/szmidtpiotr/ai-gm/issues/567) — generyczny placeholder „Wróg" → „Napastnik" (guard etykiet w `_roll_card_enemy_identity` + relabel seed). 3/3 pytest + 1/1 Playwright. **review/needs-testing**
- [x] [#580](https://github.com/szmidtpiotr/ai-gm/issues/580) — zegar `ingame_hours`: write-through kolumny w `clock_service` (koniec rozjazdu kolumna↔flaga) + backfill 22 wierszy DEV. 2/2 pytest + 1/1 Playwright. **review/needs-testing**
- [x] [#579](https://github.com/szmidtpiotr/ai-gm/issues/579) — puste sklepy wiejskie: domyślny stock wg roli (`_default_stock_for_npc`) gdy `shop_inventory_json` pusty; wpięte w display + buy. 3/3 pytest + 1/1 Playwright. **review/needs-testing**
- [x] [#573](https://github.com/szmidtpiotr/ai-gm/issues/573) — część 1: `game_item_key` zapisywany przy grancie + backfill 26/26 wierszy DEV. 4/4 pytest + 1/1 Playwright. Część 2 (pełny read-switch na game_items + drop legacy) → osobne zadanie **U11d**. **review/needs-testing**
- [x] [#589](https://github.com/szmidtpiotr/ai-gm/issues/589) — Mapa: globalna generacja świata dawała HEX/romb; nowy helper `_world_hex_coords()` (pełny kwadrat, usunięty cube-constraint) w `hex_world.py`. 2/2 pytest + Playwright. **review/needs-testing** _(grupa #589+#590)_
- [x] [#590](https://github.com/szmidtpiotr/ai-gm/issues/590) — Mapa: podgląd/edycja wpisów „Do zatwierdzenia"/„Floating" — modal `openLocDetailModal` + enrich floating SELECT + `update_location_fields()` + PATCH `/locations/{key}/edit`. 4/4 pytest + Playwright. **review/needs-testing** _(grupa #589+#590)_
- [x] [#588](https://github.com/szmidtpiotr/ai-gm/issues/588) — Kampanie multi-select martwy (rowCheck/toggleAll undefined); wydzielone do `shared/selection.js`, wpięte w campaigns.js. Playwright GREEN. **review/needs-testing** _(grupa #588+#591)_
- [x] [#591](https://github.com/szmidtpiotr/ai-gm/issues/591) — Tabele admin: resize kolumn (persist localStorage) + filtr per-kolumna; `enableColumnResize`/`enableColumnFilters`/`enhanceTable` w `shared/table.js`, wiring centralny w index.html. Playwright GREEN. **review/needs-testing** _(grupa #588+#591)_
- [x] [#587](https://github.com/szmidtpiotr/ai-gm/issues/587) — Przegląd→Zdarzenia: brakujące endpointy analytics; dodane `get_events`/`get_llm` + routy + tabele `game_events`/`llm_call_log` (migracja). 4/4 pytest + 2/2 Playwright. **review/needs-testing**
- [x] [#592](https://github.com/szmidtpiotr/ai-gm/issues/592) — Wiedza: +4 wpisy mechanik FAZY U (durability/raids/affix pity/economy telemetry); `FAZA_U_KNOWLEDGE_TIPS` + seed w migrations_admin. 3/3 pytest + Playwright. **review/needs-testing**
- [x] [#593](https://github.com/szmidtpiotr/ai-gm/issues/593) — Web Push pełny stack: `pywebpush` w requirements, VAPID env z .env, frontend SW register + `enablePushNotifications` + przycisk w Ustawieniach. 5/5 pytest + 3/3 Playwright; `/vapid-public-key`→200. E2E na prawdziwym urządzeniu **review/needs-testing**
- [verify] [#568](https://github.com/szmidtpiotr/ai-gm/issues/568) — brak lootu po zwycięstwie: **zweryfikowane jako RNG, nie bug** (24/30 dropów itemów + złoto w teście empirycznym). Rekomendacja: zamknąć.
- [stale-fixed → do zamknięcia po weryfikacji wizualnej] #566 (sendCombatNarration→stream), #518/#520/#522/#534/#535/#549/#553 (U30/U5-6/U28-29/HF-6/7/9/11) — kod naprawiony, czekają na wizualną weryfikację Piotra.
- [x] [#594](https://github.com/szmidtpiotr/ai-gm/issues/594) — unifikacja onboarding + knowledge_book: niezależne flagi `show_in_onboarding` + `show_in_knowledge` (jeden wpis może być widoczny w OBU miejscach), seed MECHANIC_CARDS→DB z obiema flagami, `onboarding_service._card_content()` czyta z DB (gate show_in_onboarding) z fallbackiem do dict, `/knowledge-tips` filtruje show_in_knowledge, admin Wiedza: 2 checkboxy + 2 badge. 3/3 pytest + 37 onboarding regresja + 1/1 Playwright. **review/needs-testing**
- [x] [#587–#593] zgłoszone z batcha admin-panel (#587 Zdarzenia analytics, #588 multi-select kampanii, #589 mapa hex→kwadrat, #590 edycja pending/floating, #591 resize/filtr tabel, #592 wpisy Wiedzy FAZY U, #593 pełny stack Web Push) + fix 500 (commit 68d2484): tabele bug_reports/user_push_subscriptions/voice_hosts/ui_texts + klucz LLM w overview.
