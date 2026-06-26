---
name: game-smoke-race-pw
description: >-
  Playwright-driven race playability smoke test for AI-GM dwarf race (#969).
  Same 12 checkpoints as /game-smoke-race but played through the REAL player UI via
  Playwright MCP browser. Verifies race mechanics the API path cannot see:
  wizard step 0 race card, character sheet ⛏ badge + Cechy rasowe section,
  shop price with visible -15% discount, repair button, toughness in damage numbers,
  spell list showing rdzeń-spells not magic_bolt, rdzeń miscast flavor in narrator.
  Two runs: warrior (CPs 1-6, 10-11) and scholar (CPs 7-10, 12).
  Use when: user types /game-smoke-race-pw warrior or /game-smoke-race-pw scholar.
  For API-based mechanics check use /game-smoke-race.
---

# game-smoke-race-pw — testy grywalności krasnoluda przez prawdziwe UI

Bliźniak `/game-smoke-race`, ale grany **przez przeglądarkę** (Playwright MCP, `mcp__playwright__*`).
Cel ten sam: **„czy granie krasnoludem jest kompletne?"** — z naciskiem na to co gracz WIDZI.
Werdykt bez zagranych tur w UI jest nieważny.

Browser na `.19` uderza wprost w `https://aigm-dev.studio-colorbox.com/`.

## Po co osobny wariant PW (vs API /game-smoke-race)

`/game-smoke-race` gra przez `play_turn.py` i service-level pytest — NIE dotyka warstwy UI.
Te checkpointy są **UI-only** i tylko ten wariant je weryfikuje:

- **Krok 0 kreatora:** karty rasy (Człowiek / Krasnolud) widoczne; klik „Wybierz" → wizard kontynuuje
- **Badge ⛏️ Krasnolud** na karcie postaci (skrytej dla człowieka)
- **Sekcja Cechy rasowe** z 4 kartami cech (Twardy jak kamień, Kowalskie oko, Wzrok górnika, Rdzeń-magia)
- **Cena w sklepie -15%**: liczba w UI odpowiada `floor(base × 0.85)`
- **Przycisk „Reperuj"** widoczny dla krasnoluda w UI (niewidoczny dla człowieka)
- **Karta obrażeń** w walce: pole `toughness_reduction` = 2 od poison/dark/rdzen
- **Lista czarów uczonego**: vein_tremor + rdzen_shield, brak magic_bolt w UI
- **Narrator miscast** (Nat1/Nat2 dla krasnoluda): tekst zawiera „żył", „krew" lub „Rdzeń"

## ⛔ KONTRAKT

- **Tylko realne tury w UI** przez Playwright MCP. SQL/API tylko jako dowód stanu, nie zamiast UI.
- Tylko konto Demo (`user_id=1`, login `demo`/`demo`). Nigdy `piotrszmidt` (`user_id=1013`).
- Kampanii i postaci po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU przez SSH+docker exec (nigdy sshfs).
- **Każdy screenshot = dowód** testowanej rzeczy. „Gra otwarta" bez czegoś widocznego = nie zaliczone.
- Screenshoty → `temp-img/<RUN>/NN-label.png`, NIGDY `/tmp/`. Zawsze `Read` PNG inline.
- Limit: ~20 kroków na run. Po limicie: raport, nawet niekompletny.
- Zamknij browser na końcu (`mcp__playwright__browser_close`).

## Wywołanie

```
/game-smoke-race-pw warrior      # Run A: UI-only CPs + 3 tury wojownikiem
/game-smoke-race-pw scholar      # Run B: UI-only CPs + 3 tury magiem z rdzeń-czarami
/game-smoke-race-pw all          # oba runy sekwencyjnie
```

## Krok 1 — Setup

```bash
# Upewnij się że [TEST] krasnoludy istnieją w DB
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-smoke-race
python3 scripts/setup_dwarf_pool.py
# → {"warrior_id": int, "scholar_id": int, "ok": true}
```

Utwórz katalog runu:
```bash
RUN="$(date +%Y%m%d_%H%M%S)_smoke-race-pw-<warrior|scholar>"
mkdir -p /home/claude/projects/DEV_AIGM/temp-img/$RUN
```

## Krok 2 — Otwórz i zaloguj się

```
mcp__playwright__browser_navigate  → https://aigm-dev.studio-colorbox.com/
mcp__playwright__browser_snapshot   (refy elementów)
mcp__playwright__browser_type       #login-username = "demo"
mcp__playwright__browser_type       #login-password = "demo"
mcp__playwright__browser_click      #login-form button
mcp__playwright__browser_wait_for   ("Moi Bohaterowie" / ekran bohaterów)
```

Selektory logowania: `#login-username`, `#login-password`, `#login-form button`.

## Krok 3A — Run A: Krasnolud Wojownik

### CP-UI-1: Wizard Krok 0 — wybór rasy

Kliknij **„Nowy bohater"** / **„+"** na ekranie bohaterów. Poczekaj na Krok 0.

| Co zweryfikować | Screenshot |
|---|---|
| Dwie karty rasy widoczne: **Człowiek** i **Krasnolud** | `01-wizard-step0.png` |
| Karta Krasnolud ma tytuł „Krasnolud" i opis cech | widać w zrzucie |
| Po kliknięciu „Wybierz" przy Krasnolud → krok 1 | `02-wizard-step1-after-race.png` |

```
mcp__playwright__browser_click      [Wybierz przy krasnolud]
mcp__playwright__browser_snapshot
mcp__playwright__browser_take_screenshot → temp-img/$RUN/02-wizard-step1-after-race.png
```

Przejdź wizard do końca (wpisz imię → daj staty → wybierz skille → zakończ).
Zanotuj `character_id` z URL lub przez `browser_evaluate`.

### CP-UI-2: Badge ⛏️ Krasnolud na karcie postaci

Wejdź w kartę postaci. Upewnij się że badge jest widoczny.

| Co zweryfikować | Screenshot |
|---|---|
| `#sheet-race-badge` widoczny (display != none) | `03-sheet-race-badge.png` |
| Badge ma ikonę ⛏️ i tekst „Krasnolud" | widać w zrzucie |
| Sekcja **Cechy rasowe** z 4 kartami widoczna | `04-sheet-racial-traits.png` |

```
mcp__playwright__browser_evaluate   → document.getElementById('sheet-race-badge').style.display
mcp__playwright__browser_take_screenshot → temp-img/$RUN/03-sheet-race-badge.png
mcp__playwright__browser_evaluate   → document.getElementById('sheet-racial-section').style.display
mcp__playwright__browser_take_screenshot → temp-img/$RUN/04-sheet-racial-traits.png
```

Weryfikacja SQL (dowód uzupełniający):
```bash
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT race, json_extract(sheet_json, '\''$.stats.CON'\'') as con FROM characters WHERE id=<char_id>"'
```

### CP-UI-3: Sklep — cena -15% dla krasnoluda

Idź turą do sklepu lub NPC-handlarza. Sprawdź cenę dowolnego itemu.

| Co zweryfikować | Screenshot |
|---|---|
| Cena w UI = `floor(base_price × 0.85)`, np. mikstura 20g → 17g | `05-shop-discount.png` |
| Tura zakupowa kończy się sukcesem (gold spada o zdyskontowaną kwotę) | `06-after-purchase.png` |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/05-shop-discount.png
```

Weryfikacja SQL: `character_gold_log` — `amount` = `floor(base × 0.85)`.

### CP-UI-4: Przycisk „Reperuj" widoczny

Na ekranie postaci (lub HUD podczas gry) sprawdź przycisk reperacji.

| Co zweryfikować | Screenshot |
|---|---|
| Przycisk „Reperuj" / ikonka młota widoczna | `07-repair-button.png` |
| Po kliknięciu: HP+20, gold-20 widoczne w UI | `08-after-repair.png` |

```
mcp__playwright__browser_evaluate   → !!document.querySelector('[data-action="dwarf-repair"]') || !!document.querySelector('#dwarf-repair-btn')
mcp__playwright__browser_take_screenshot → temp-img/$RUN/07-repair-button.png
```

### CP-UI-5: Walka — karta obrażeń z toughness_reduction

Wejdź w walkę z wrogiem z typem poison/dark/rdzen (np. Pająk → poison, szkielet/krypta → dark).

| Co zweryfikować | Screenshot |
|---|---|
| Karta trafienia wroga pokazuje `toughness_reduction=2` lub podobny komunikat | `09-toughness-reduction.png` |
| HP spada mniej niż bez twardości (base_dmg - 2) | HUD HP vs `combatants[].hp` |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/09-toughness-reduction.png
```

### CP-UI-10: 3 tury bojowe krasnoludem — brak błędów

Zagraj 3 tury. Obserwuj czy nie ma błędów (czerwone banery, HTTP 500 w narracji).

| Co zweryfikować | Screenshot |
|---|---|
| 3 tury kończą się normalną narracją (brak błędów) | `10-turn3-ok.png` |
| HUD HP/gold/XP aktualizuje się | zrzut HUD |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/10-turn3-ok.png
```

## Krok 3B — Run B: Krasnolud Uczony (rdzeń-magia)

Użyj [TEST] Krasnolud Uczony (scholar) lub utwórz go przez wizard z rasą krasnolud + archetype scholar.
Otwórz istniejącą kampanię uczonego lub utwórz nową.

### CP-UI-7: Lista czarów — rdzeń-spells, brak magic_bolt

Otwórz listę czarów (w UI → Zaklęcia lub sekcja czarów na karcie postaci).

| Co zweryfikować | Screenshot |
|---|---|
| Lista zawiera `vein_tremor` i `rdzen_shield` | `11-spells-rdzen.png` |
| Lista NIE zawiera `magic_bolt` | widać w zrzucie |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/11-spells-rdzen.png
```

### CP-UI-8: Miscast rdzeń-flavor w narracji

Zagraj turą z cast czaru w walce. Jeśli rzut = Nat1 lub Nat2 → miscast.
Jeśli miscast nie wystąpi w 5 turach → oznacz N/D.

| Co zweryfikować | Screenshot |
|---|---|
| Narracja miscast zawiera „żył", „krew", „Rdzeń", „trzęsienie" | `12-miscast-rdzen.png` |
| NIE zawiera zwrotów human-miscast: „fala arkany", „Twoja moc" | |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/12-miscast-rdzen.png
```

### CP-UI-9: Race lock — próba nauki human-only czaru

Spróbuj nauczyć się czaru `magic_bolt` przez UI (jeśli istnieje przycisk „Ucz się" na liście czarów).

| Co zweryfikować | Screenshot |
|---|---|
| UI wyświetla odmowę lub przycisk jest wyłączony | `13-race-lock-ui.png` |
| Brak możliwości nauki human-only czarów w interfejsie | |

Jeśli UI nie ma przycisku nauki dla nieznanego czaru → N/D (mechanika w API, pokryta pytest CP9).

### CP-UI-12: 3 tury magiczne — rdzeń-czar + mana

Zagraj 3 turami z rzucaniem rdzeń-czarów (vein_tremor lub rdzen_shield).

| Co zweryfikować | Screenshot |
|---|---|
| Mana spada po rzucie czaru (pasek many w HUD) | `14-mana-after-cast.png` |
| Narracja zawiera klimat rdzeń-magii | `15-turn3-rdzen.png` |
| Brak błędów HTTP 500 | HUD bez czerwonego baneru |

```
mcp__playwright__browser_take_screenshot → temp-img/$RUN/14-mana-after-cast.png
mcp__playwright__browser_take_screenshot → temp-img/$RUN/15-turn3-rdzen.png
```

## Krok 4 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm \
  --title "[BUG] SMOKE-RACE-PW — <opis>" \
  --label "bug,smoke-defect,needs-testing" \
  --body "<run, checkpoint, oczekiwane vs faktyczne, screenshot (załącz PNG)>"
```

**P0** = krasnolud niezdatny do gry (crash, brak badge, wizard blokuje) · **P1** = mechanika działa ale UI nie pokazuje (brak toughness w karcie, brak rdzeń-flavor) · **P2** = kosmetyka.

## Krok 5 — Raport

Komentarz do issue #969:

```
## 🎮 game-smoke-race-pw <warrior|scholar> — <data>
**Browser:** Playwright MCP | **URL:** https://aigm-dev.studio-colorbox.com/
**Krasnolud:** warrior_id / scholar_id | **Tur:** N

### Werdykt Run A (warrior): GRYWALNY / Z ZASTRZEŻENIAMI / NIEGRYWALNY
### Werdykt Run B (scholar): ...

### Checkpointy UI
| # | Checkpoint | Wynik | Screenshot / Dowód |
(12 wierszy: ✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+ na run, z opisem co widać)
```

## Gotchas

- **Wizard Krok 0**: jeśli nie widać kart rasy → sprawdź `wizard.js?v=N` w `/`, wersja musi zawierać `_wizardStep0Submit`. Jeśli brak → problem z cache.
- **Badge skryty dla człowieka**: `#sheet-race-badge` ma `style="display:none"` dla human — to poprawne. Dla dwarfa MUSI być widoczny (`display` = `inline-flex` lub podobny).
- **Miscast Nat1+Nat2 dla krasnoluda**: szansa 2/20 = 10% na cast → przy 10 turach powinien wystąpić. Jeśli nie — wymuś niski poziom, niskie staty (mag lvl1 ma małe mana = częste rzuty).
- **Toughness w kartach**: karta obrażeń (roll-card) może nie pokazywać `toughness_reduction` jako osobnego pola — sprawdź zamiast HP delta (HP po = HP przed − (dmg − 2)).
- **Screenshoty do `/tmp/`**: nie! Zawsze `temp-img/$RUN/`. `/tmp/` nie widoczny przez sshfs.
- Zamknij browser: `mcp__playwright__browser_close`.

## Automatyczne testy (bez LLM, jako baseline)

Przed runem PW uruchom bazowe testy żeby upewnić się mechanika działa:

```bash
# pytest (18/20 GREEN — bez LLM)
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 \
  pytest tests/playability/test_race_playability.py -v'

# Playwright deterministyczne specy (6/6 GREEN)
ssh claude@192.168.1.61 'docker exec ai-gm-dev-test-agent-1 \
  npx playwright test --config=playwright/playwright.config.js \
  playwright/ux/race/race_smoke.spec.js 2>&1 | tail -10'
```

Jeśli któreś faili → napraw najpierw, zanim ruszasz PW.
