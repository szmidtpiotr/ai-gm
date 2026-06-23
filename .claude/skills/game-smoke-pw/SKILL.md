---
name: game-smoke-pw
description: >-
  Playwright-driven full-mode smoke playtest of AI-GM: same scenario as /game-smoke (movement,
  NPC, quest, combat, shop, rest+XP, beats) but played through the REAL player UI via the
  Playwright MCP browser instead of the API. Verifies UI-only mechanics the API path cannot see
  — zone columns DYSTANS/ZWARCIE, the SF10 reaction modal (Przyjmij/Unik/Blok), the dice popup,
  the mana bar, the spell dropdown — with an inline-screenshot report + P0/P1/P2 defect issues.
  Use when: the user types /game-smoke-pw nowa-kampania or /game-smoke-pw gotowa-kampania, or
  asks "czy tryb X jest grywalny end-to-end w prawdziwym UI". For the faster API-only variant use
  /game-smoke. For testing ONE specific issue use /playwright-test-report.
---

# game-smoke-pw — obchód całego trybu gry przez prawdziwe UI (Playwright)

Bliźniak `/game-smoke`, ale grany **przez przeglądarkę** (Playwright MCP, `mcp__playwright__*`),
nie przez API. Cel ten sam: **„czy w ten tryb da się grać?"** — z naciskiem na to, co gracz
NAPRAWDĘ widzi i klika. Werdykt bez zagranych tur w UI jest nieważny.

Browser na `.19` uderza wprost w `https://aigm-dev.studio-colorbox.com/`. Bez docker test-agenta.

## Po co osobny wariant PW (vs API /game-smoke)

`/game-smoke` gra przez `play_turn.py` (ścieżka API) — NIE dotyka warstwy UI. Te checkpointy są
**UI-only** i tylko ten wariant je weryfikuje:
- Baner walki: kolumny **DYSTANS / ZWARCIE**, chipy inicjatywy 🏹/⚔, przyciski Zbliż się/Cofnij się
- Modal reakcji **SF10** (Przyjmij / Unik / Blok) gdy wróg trafia
- Popup kości (dice prompt) w turze i Stage 2 obrażeń
- Pasek **many** Maga w HUD; rozwijane menu Atak (czary atakujące) / Akcja→Zaklęcie
- Picker mikstur w walce; modal nauki XP/czaru
- Karta rzutu umiejętności z **marginesem ±N** i stopniem sukcesu

## ⛔ KONTRAKT

- **Tylko realne tury w UI** przez Playwright MCP. Żadnych wywołań serwisów/SQL ZAMIAST gry.
  SQL/endpointy backendu (`http://192.168.1.61:8100`) wolno użyć tylko jako *nudge* setupowy
  (np. start walki gdy narracja nie chce), ale efekt widziany przez gracza MUSI być zrzucony z UI.
- Tylko konto Demo (`user_id=1`, login `demo`/`demo`). Nigdy `piotrszmidt` (`user_id=1013`).
- Kampanii i postaci po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU dowodów stanu, przez SSH+docker exec (nigdy sshfs).
- **Każdy screenshot pokazuje DOWÓD** testowanej rzeczy (po akcji wyzwalającej), nie „gra otwarta".
- Screenshoty → `temp-img/<RUN>/NN-label.png`, NIGDY `/tmp/`. Zawsze `Read` PNG inline przed opisem.
- Limit: ~20 kroków na run. Po limicie: raport, nawet niekompletny — zaznacz czego nie osiągnięto.
- Zamknij browser na końcu (`mcp__playwright__browser_close`).

## Wywołanie

```
/game-smoke-pw nowa-kampania
/game-smoke-pw gotowa-kampania
```

## Krok 1 — Setup bohatera + kampanii

Reużyj infrastruktury `/game-test-player` (setup robi się przez skrypt, GRA przez UI):

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 scripts/setup_hero_pool.py          # warrior_id/scholar_id/rogue_id
```

- **nowa-kampania:** `python3 scripts/setup_campaign.py --issue 512 --archetype warrior`
  (kampania `#512`; jeśli istnieje z turami — świeża przez UI „Nowa kampania"). Dla pełnego
  pokrycia czarów/many zrób DRUGI run jako **scholar** (mana, czary, AoE, miscast).
- **gotowa-kampania:** kampania Z SZABLONU — w UI hub → kafelek gotowej kampanii / „Wczytaj
  przygodę". Wybierz pierwszy opublikowany szablon. Tytuł `#513-runN`.

Utwórz katalog runu:
```bash
RUN="$(date +%Y%m%d_%H%M%S)_smoke-pw-<archetype>"
mkdir -p /home/claude/projects/DEV_AIGM/temp-img/$RUN
```

## Krok 2 — Otwórz i zaloguj się (Playwright MCP)

```
mcp__playwright__browser_navigate  → https://aigm-dev.studio-colorbox.com/
mcp__playwright__browser_snapshot   (refy elementów)
mcp__playwright__browser_type       #login-username = "demo"
mcp__playwright__browser_type       #login-password = "demo"
mcp__playwright__browser_click      #login-form button
mcp__playwright__browser_wait_for   ("Moi Bohaterowie" / ekran bohaterów)
```

Selektory logowania: `#login-username`, `#login-password`, `#login-form button`. Świeże refy:
`browser_snapshot`. Stan którego UI nie pokazuje wprost: `browser_evaluate`.

Wejdź bohaterem do kampanii z setupu (klik karty bohatera → karta kampanii → „Graj").

## Krok 3 — Scenariusz (checkpointy = /game-smoke + warstwa UI)

Graj turami przez composer w UI (wpisz wiadomość → wyślij; obsłuż popup kości gdy się pojawi).
Każdy checkpoint = zrzut PO akcji wyzwalającej + `Read` PNG + dowód (co widać LUB SQL stanu).
Kolejność elastyczna — narracja prowadzi, checklist pilnuje.

| # | Checkpoint | Dowód UI (screenshot) + opcjonalnie SQL |
|---|---|---|
| 1 | Otwarcie renderuje scenę; HUD HP/złoto/XP; **(Mag)** widoczny **pasek many** = `current_mana/max_mana` | zrzut HUD; wartości vs `characters.sheet_json` |
| 2 | **Ruch hex ≥2×** ("idę na północ") — scena/lokacja zmienia się w UI | zrzut przed/po; `session_flags.current_hex` zmienia się |
| 3 | LLM używa lokacji Z BAZY (nazwa w narracji = wpis w `game_locations`) | zrzut narracji; klucz w `game_sessions.current_location_id`, `ai_generated=0` |
| 4 | Rozmowa z NPC przypisanym do lokacji (imię w UI) | zrzut; imię z `location_npc_assignments`/`npc_keys` |
| 5 | Quest przyjęty; **karta rzutu umiejętności pokazuje margines ±N i stopień** (sukces kryt./sukces/porażka/kryt. porażka) — S1 | zrzut karty rzutu z marginesem; wiersz w `character_quests` |
| 6 | **Popup kości:** tura wymagająca rzutu → modal kości; rzut → wynik widoczny na karcie | zrzut popupu kości + zrzut wyniku |
| 7 | **Walka — UI stref T34:** baner ma kolumny **DYSTANS / ZWARCIE**; chipy inicjatywy 🏹/⚔; przycisk **Zbliż się**/**Cofnij się** | zrzut banera z kolumnami i przyciskiem |
| 8 | **Gate strefy:** atak melee na wroga w innej strefie → komunikat „poza zasięgiem", tura NIE spada; po **Zbliż się** atak wychodzi | zrzut komunikatu + zrzut po zbliżeniu; `combatants[].zone` |
| 9 | **Model #826:** karta obrażeń pokazuje redukcję pancerza (min 1 dmg) i/lub bonus z marginesu (≥5 pkt → +1); Nat20 = podwójne + ignoruje pancerz | zrzut karty trafienia z liczbami; HP wroga przed/po |
| 10 | **Reakcja SF10:** wróg trafia gracza z `dodge`/`shield_block` rank≥1 → modal **Przyjmij / Unik / Blok**; wybierz Unik → rozstrzygnięcie widoczne | zrzut modalu reakcji + zrzut wyniku (N/D jeśli bohater bez tych skilli) |
| 11 | Walka kończy cykl: wróg pada → koniec walki → loot w UI; **(łuk)** licznik strzał spadł, pill odzysku amunicji | zrzut „Zdobyto…" + HUD; `character_inventory` |
| 12 | Gate sceny: „atakuję smoka" bez wroga → odmowa, brak walki | zrzut odmowy w narracji |
| 13 | Sklep: kupno/sprzedaż ze zmianą złota = cena z katalogu; **(crafter)** cennik afiksów reroll 100/350/700g / apply 150/500/1200g | zrzut przed/po złota; kwota = katalog/cennik |
| 14 | Odpoczynek + wydanie XP (modal „Ucz się"); **(Mag)** alternatywa: nauka/upgrade czaru za XP (75/50/100) | zrzut modalu + zrzut po; `sheet_json` skill/spell rank |
| 15 | **(Mag) Czary w walce:** rozwijane menu Atak (czar atakujący) / Akcja→Zaklęcie; mana spada po rzucie; **Nat1 = miscast** (mana tracona, komplikacja); czar **AoE** trafia kilka celów | zrzut menu czarów + zrzut many przed/po; `route=spell_*` (N/D nie-Mag) |
| 16 | Konsumpcja w walce: Akcja → **Mikstura** → picker → wypicie HP↑ + tura spada; mikstura znika z plecaka | zrzut pickera + HP przed/po (N/D brak konsumpcji) |
| 17 | Zegar gry tyka, pora dnia zmienia się w HUD | zrzut HUD czasu; `ingame_hours` rośnie |
| 18 | *(tylko gotowa-kampania)* beat fabularny odpala | zrzut narracji beatu; GM Plan przed/po |
| 19 | Spójność: narracja NIE twierdzi nic sprzecznego ze stanem UI | przegląd zrzutów; każda sprzeczność = defekt |

Pary przed/po (HP, złoto, mana, plecak) = dwa zrzuty (`NN-...-przed`, `NN+1-...-po`) z opisem różnicy.

Minimum zrzutów kluczowych (oprócz powyższych): CP7 (kolumny stref), CP10 (modal SF10), CP6 (popup kości).

## Krok 4 — Defekty (issue od razu, przed dalszą grą)

Każde ❌ = issue (szablon #18, jak w /playwright-test-report Step 4):

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-PW — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<tryb, krok, oczekiwane vs faktyczne, repro UI, screenshot>"
```

Priorytety: **P0** = scenariusz nieprzechodzalny w UI (blokuje grę) · **P1** = psuje doświadczenie
(brak modalu/kolumn/feedbacku, sprzeczność narracja↔stan, złe liczby) · **P2** = kosmetyka.

## Krok 5 — Upload zrzutów na GitHub

Jak w /playwright-test-report Step 5 (release assets → URL per plik):
```bash
TAG=$(gh release list --repo szmidtpiotr/ai-gm --limit 1 --json tagName --jq '.[0].tagName')
for f in /home/claude/projects/DEV_AIGM/temp-img/$RUN/*.png; do
  gh release upload "$TAG" "$f" --repo szmidtpiotr/ai-gm --clobber
done
```
Trzymaj mapę label→URL w kolejności zrzutów.

## Krok 6 — Raport (inline screenshoty, prosty polski)

Komentarz do issue trybu (#512 / #513) — **zdjęcia INLINE pod nagłówkiem każdego kroku**, nigdy
galeria na końcu (hard rule z /playwright-test-report Step 6):

```markdown
## 🎮 game-smoke-pw <tryb> — <data>
**Kampania:** id | **Bohater:** id | **Archetype:** warrior/scholar/rogue | **Kroków:** N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Przebieg krok po kroku
#### 1. <co testowano>
![<alt: co widać>](URL_01)
- **Co widać:** <konkret z ekranu>
- **Werdykt:** ✅ DZIAŁA / ❌ PROBLEM → #issue

(…wszystkie checkpointy w kolejności, każdy ze zrzutem inline…)

### Podsumowanie — co poprawić (🔴→🟡, linki do issue)
### Defekty: P0: n · P1: n · P2: n
```

## Krok 7 — notes.md + commit

Zaktualizuj notes.md (status smoke-PW + link do raportu). Commit na `develop` przez
`sudo -u piotrszmidt git` na `.61`, referuj numery issue. Push. Krótki komunikat do usera:
werdykt, liczba problemów, link.

## Gotchas

- Rate limit TPM → 502: czekaj 60 s; model `gpt-4.1-mini` w configu kampanii tnie koszt.
- `route=skill_test`: wpisz „Staram się jak mogę." i kontynuuj.
- **Popup kości jest realny w UI** (inaczej niż w /game-smoke API) — obsłuż go (klik „Rzuć"/akceptacja),
  inaczej tura nie pójdzie. 3D kości renderują tylko 1. rzut/sesję (znany bug #829) — Stage 2 to 2D.
- **CP7/CP10 (UI walki):** użyj `browser_snapshot` by złapać refy kolumn i przycisków banera; modal
  SF10 ma przyciski Przyjmij/Unik/Blok — kliknij świadomie i zrzuć wynik.
- **CP10 warunek:** modal tylko gdy bohater ma `dodge`/`shield_block` rank≥1 w `sheet_json.skills`.
  Brak → modal się nie pojawia → odnotuj N/D „brak skilli reakcji", to nie defekt.
- **CP9 pancerz:** `armor = max(0, enemy.ac_base − 10)`; min 1 dmg/cios; Nat20 ignoruje pancerz.
- Nie wymuszaj checkpointów łamiąc fikcję — graj naturalnie; nieosiągnięty organicznie po limicie → N/D.
- Zamknij browser na końcu.
