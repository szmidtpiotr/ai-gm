---
name: game-smoke-dungeon-pw
description: >-
  Playwright-driven full-mode smoke playtest of the AI-GM tile DUNGEON (FAZA L): same run as
  /game-smoke-dungeon (enter tile graph, move through doors, scaled combat, chests, riddles, boss,
  endless/exit, death-with-checkpoint, abandon) but played through the REAL player UI via the
  Playwright MCP browser. Verifies UI-only dungeon mechanics the API path cannot see — the tile
  MAP overlay, direction D-pad, zone columns, the SF10 reaction modal, chest/riddle dialogs, the
  endless/exit modal, the abandon-warning modal — with an inline-screenshot report + P0/P1/P2
  defect issues. Use when the user types /game-smoke-dungeon-pw, or asks "czy loch jest grywalny
  end-to-end w prawdziwym UI". For the API-only variant use /game-smoke-dungeon. For ONE issue use
  /playwright-test-report.
---

# game-smoke-dungeon-pw — obchód Lochu kafelkowego przez prawdziwe UI (Playwright)

Bliźniak `/game-smoke-dungeon`, ale grany **przez przeglądarkę** (Playwright MCP, `mcp__playwright__*`).
Cel ten sam: **„czy w loch da się grać end-to-end?"** — z naciskiem na to, co gracz widzi i klika.
Mechaniki ze specu: `game_mechanics.md` CZĘŚĆ AJ (17 decyzji). Werdykt bez zagranego przebiegu w UI jest nieważny.

Browser na `.19` uderza wprost w `https://aigm-dev.studio-colorbox.com/`. Bez docker test-agenta.

## Po co osobny wariant PW (vs API /game-smoke-dungeon)

API path nie dotyka warstwy UI. Te checkpointy są **UI-only** i tylko ten wariant je weryfikuje:
- **Mapa kafelkowa** (przycisk mapy → graf: odwiedzone + zarysy za drzwiami + marker pozycji) — L11
- **D-pad kierunków** pod composerem (ruch przez drzwi) — L12 (capture dopiero przy dragu, nie tapie — #957)
- Baner walki: kolumny **DYSTANS / ZWARCIE**, chipy 🏹/⚔
- Modal reakcji **SF10** (Przyjmij / Unik / Blok)
- Dialogi skrzyni (rzut DEX, próby) i zagadki (próby + podpowiedzi)
- Modal **„Wyjdź z łupem / Idź głębiej"** po bossie; modal ostrzegawczy **porzucenia**
- Popup kości; pasek many (Mag); picker mikstur

## ⛔ KONTRAKT

- **Tylko realny przebieg w UI** przez Playwright MCP. SQL/endpointy backendu
  (`http://192.168.1.61:8100`) tylko jako *nudge* setupowy; efekt widziany przez gracza MUSI być zrzucony z UI.
- Tylko konto Demo (`user_id=1`, login `demo`/`demo`). Nigdy `piotrszmidt` (`user_id=1013`).
- Bohatera, kampanii ani przebiegu po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU dowodów, przez SSH+docker exec (nigdy sshfs).
- **Każdy screenshot pokazuje DOWÓD** (po akcji wyzwalającej), nie „loch otwarty". `Read` PNG inline przed opisem.
- Screenshoty → `temp-img/<RUN>/NN-label.png`, NIGDY `/tmp/`.
- Limit: ~30 kroków/akcji na run (loch dłuższy). Po limicie: raport, nawet niekompletny.
- Zamknij browser na końcu (`mcp__playwright__browser_close`).

## Wywołanie

```
/game-smoke-dungeon-pw              # pełny przebieg na lochu z treścią (krypta, po L16)
/game-smoke-dungeon-pw --engine     # silnik+UI na kafelkach testowych (przed treścią; L13c)
```

## Krok 1 — Setup

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 scripts/setup_hero_pool.py          # warrior_id/scholar_id/rogue_id
```

**Bohater:** warrior (domyślnie) — loch combat-heavy; ma 20 strzał na start (CP6e). Dla skrzyń/zagadek rogue (DEX) bywa lepszy.

**Loch do testu** — sprawdź aktywny loch kafelkowy z kategorią i kafelkami:
```bash
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT key, tile_category_key, tile_count, boss_tile_id, endless_growth_n FROM game_dungeons WHERE is_active=1 AND tile_category_key IS NOT NULL;"'
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT category_key, COUNT(*) FROM dungeon_tiles GROUP BY category_key;"'
```
- **Pełny tryb:** użyj `krypta_probna` (L16). Brak → STOP, zgłoś że treść (L14–L16) niegotowa.
- **--engine:** brak kategorii z kafelkami → zaseeduj MINIMALNĄ testową (3–4 kafelki: wejście 2-drzwiowe,
  walka, boss) `created_by='seed'` przez `POST /admin/dungeon-tiles/ai-create` lub seed — TYLKO do testu silnika;
  odnotuj w raporcie że to kafelki testowe bez obrazków.

**Cooldown:** świeży `character_dungeon_runs` (423 przy wejściu) → wyzeruj (admin/cheat) lub inny bohater z puli.

Katalog runu:
```bash
RUN="$(date +%Y%m%d_%H%M%S)_smoke-dungeon-pw"
mkdir -p /home/claude/projects/DEV_AIGM/temp-img/$RUN
```

## Krok 2 — Otwórz i zaloguj się (Playwright MCP)

```
mcp__playwright__browser_navigate  → https://aigm-dev.studio-colorbox.com/
mcp__playwright__browser_snapshot
mcp__playwright__browser_type       #login-username = "demo"
mcp__playwright__browser_type       #login-password = "demo"
mcp__playwright__browser_click      #login-form button
mcp__playwright__browser_wait_for   ("Moi Bohaterowie")
```
Selektory logowania: `#login-username`, `#login-password`, `#login-form button`. Świeże refy: `browser_snapshot`.

Wejdź do lochu przez UI (kampanie → kafelek Lochy / przycisk wejścia do `krypta_probna`).

## Krok 3 — Scenariusz (checkpointy = /game-smoke-dungeon + warstwa UI)

Graj akcjami przez UI: D-pad kierunków, klik drzwi, composer, przyciski walki. Każdy checkpoint =
zrzut PO akcji + `Read` PNG + dowód. Kolejność elastyczna — przebieg prowadzi, checklist pilnuje.

| # | Checkpoint | Mechanika | Dowód UI (screenshot) + opcjonalnie SQL |
|---|---|---|---|
| 1 | Wejście tworzy graf kafelkowy (nie liniowy); UI pokazuje kafelek startowy | L2/L3 | zrzut wejścia; `character_dungeon_runs` graf z odnogami; 409 gdy loch bez kategorii |
| 2 | Blok [LOCH] = opis kafelka z DB + koloryzacja LLM (nie zmyślone) | L3, Decyzja 3 | zrzut narracji; detale z `dungeon_tiles.description_pl` |
| 3 | **D-pad/drzwi:** przyciski kierunków pod composerem przesuwają pozycję; backtracking działa | L4/L12, #957 | zrzut D-padu + zrzut po ruchu; pozycja w `character_dungeon_runs` zmienia się |
| 4 | **Mapa kafelkowa:** przycisk mapy → graf (odwiedzone + zarysy za drzwiami + marker pozycji) | L11 | zrzut mapy lochu — odwiedzone widoczne, niewidziane = zarys, marker na bieżącym |
| 5 | **Walka — UI stref T34:** baner kolumny **DYSTANS / ZWARCIE**, chipy 🏹/⚔; przycisk Zbliż się/Cofnij się | L4/L5 | zrzut banera z kolumnami |
| 6 | **Walka — skala + #826 + SF10 + ammo + mikstura:** (a) poziom wroga = `TIER_ENEMY_LEVELS[tier]`, NIE skalowany do bohatera; (b) gate strefy: melee w innej strefie → „poza zasięgiem", tura NIE spada; (c) pancerz = redukcja (min 1 dmg, Nat20 ignoruje); (d) **modal SF10** Przyjmij/Unik/Blok gdy wróg trafia; (e) *(łuk)* strzał konsumuje ammo, po walce pill odzysku 40%; (f) Akcja→Mikstura → HP↑ + tura spada | L4-L6 | zrzuty: karta obrażeń z liczbami, modal SF10, licznik ammo, picker mikstur; HP w `combatants` przed/po |
| 7 | **Skrzynia:** dialog rzutu DEX, do 3 prób, ryzyko pułapki; brak soft-locka po porażce | L6 | zrzut dialogu skrzyni + wyniku; próby w stanie runu |
| 8 | **Zagadka:** dialog do 3 prób + podpowiedzi; po 3 porażkach przejście możliwe | L6 | zrzut dialogu zagadki; `riddle_key` rozliczone |
| 9 | **Boss** po `tile_count` kafelkach + loot w UI | L8 | zrzut walki z bossem + „Zdobyto…"; `boss_tile_id` |
| 10 | **Modal po bossie:** „Wyjdź z łupem / Idź głębiej" (tryb nieskończony) | L8 | zrzut modalu wyboru; „głębiej" → segment +n |
| 11 | **Endless:** skalowanie +1 lvl wrogów/cykl (po lvl10 +15% HP/dmg) | L8, Decyzja 7 | zrzut wroga 2. cyklu; poziom > 1. cyklu |
| 12 | **Śmierć KOŃCZY run** (nie restart pokoju); checkpoint po bossie | L7, Decyzja 6 (NADPISUJE E16) | zrzut ekranu śmierci/końca; run `status` zakończony, NIE restart od kafelka 1 |
| 13 | **Porzucenie:** modal ostrzegawczy + 50% cooldown | L7/L13 | zrzut modalu ostrzegawczego; `character_dungeon_runs` cooldown = 50% `cooldown_hours` |
| 14 | **Flaga `dungeon_enabled` OFF:** brak wejścia (gate API i UI — przycisk ukryty/wyszarzony) | L10 | zrzut UI z ukrytym przyciskiem po toggle admin OFF; `/enter` blokowany |
| 15 | Spójność: narracja nie zmyśla kafelków/drzwi spoza grafu | Decyzja 3 | przegląd zrzutów; każda sprzeczność narracja↔graf = defekt |

Pary przed/po (HP, ammo, mana) = dwa zrzuty z opisem różnicy.

Minimum zrzutów kluczowych: CP4 (mapa), CP6d (modal SF10), CP9 (boss), CP12 (śmierć/checkpoint).

**--engine** (przed treścią): pomiń checkpointy zależne od treści — 2 (opisy PL), 8 (zagadki, jeśli brak
w kafelkach testowych) — oznacz N/D „brak treści (L14–L16)". Resztę (graf, D-pad, mapa, walka+#826+T34+SF10,
boss, endless, śmierć, porzucenie, flaga) graj normalnie.

## Krok 4 — Defekty (issue od razu)

Szablon #18, jak /playwright-test-report Step 4:
```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-LOCH-PW — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<akcja, oczekiwane vs faktyczne, repro UI, screenshot>"
```
Priorytety: **P0** = przebieg nieprzechodzalny w UI (soft-lock, śmierć restartuje pokój, wejście pada,
D-pad nie działa) · **P1** = psuje doświadczenie (mapa nie pokazuje pozycji, brak modalu SF10/wyboru/porzucenia,
rubber-banding, narracja↔graf sprzeczna, złe liczby) · **P2** = kosmetyka.

## Krok 5 — Upload zrzutów na GitHub

Jak /playwright-test-report Step 5:
```bash
TAG=$(gh release list --repo szmidtpiotr/ai-gm --limit 1 --json tagName --jq '.[0].tagName')
for f in /home/claude/projects/DEV_AIGM/temp-img/$RUN/*.png; do
  gh release upload "$TAG" "$f" --repo szmidtpiotr/ai-gm --clobber
done
```

## Krok 6 — Raport (inline screenshoty, prosty polski)

Komentarz do issue `[SMOKE] FAZA L` (utwórz, jeśli nie ma) — **zdjęcia INLINE pod nagłówkiem każdego kroku**:

```markdown
## 🎮 game-smoke-dungeon-pw — <tryb pełny/--engine> — <data>
**Loch:** key | **Bohater:** id | **Archetype:** warrior/scholar/rogue | **Akcji:** N | **Cykli endless:** M

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Przebieg krok po kroku
#### 1. <co testowano>
![<alt: co widać>](URL_01)
- **Co widać:** <konkret z ekranu>
- **Werdykt:** ✅ DZIAŁA / ❌ PROBLEM → #issue

(…wszystkie checkpointy w kolejności, każdy ze zrzutem inline; mapa, boss, śmierć obowiązkowo…)

### Podsumowanie — co poprawić (🔴→🟡, linki do issue)
### Defekty: P0: n · P1: n · P2: n
```

## Krok 7 — notes.md + commit

Zaktualizuj notes.md (L13c lub L19 + link raportu) — `[x]` TYLKO gdy przebieg ukończony i wszystkie P0 zgłoszone.
Commit na `develop` przez `sudo -u piotrszmidt git` na `.61`, referuj issue. Push. Krótki komunikat: werdykt, liczba problemów, link.

## Gotchas

- Rate limit TPM → 502: czekaj 60 s; model `gpt-4.1-mini` tnie koszt.
- 423 przy wejściu = cooldown — wyzeruj (admin/cheat) lub inny bohater.
- Walka w lochu deterministyczna z silnika (Decyzja 4) — żadnych tagów COMBAT_START od LLM; LLM narruje walkę bez startu silnika → defekt P0.
- **Popup kości realny w UI** — obsłuż go, inaczej tura nie pójdzie. 3D tylko 1. rzut/sesję (#829).
- **CP3 D-pad (#957):** wskaźnik łapany dopiero przy dragu, nie przy tapie — tap w kierunek = ruch, drag = pan mapy.
- **CP5/CP6 (UI walki):** `browser_snapshot` po refy kolumn/przycisków; modal SF10 = Przyjmij/Unik/Blok.
- **CP6c pancerz:** `armor = max(0, enemy.ac_base − 10)`; min 1 dmg/cios; Nat20 ignoruje pancerz.
- **CP6d warunek SF10:** modal tylko gdy bohater ma `dodge`/`shield_block` rank≥1; brak → N/D, nie defekt.
- **CP6e ammo:** brak ammo → strzał zablokowany BEZ spalenia tury; odzysk 40% per wystrzelona sztuka.
- Nie wymuszaj checkpointów łamiąc fikcję — nieosiągnięty organicznie po limicie → N/D z powodem.
- `--engine` na kafelkach testowych: brak obrazków/opisów PL to NIE defekt (treść = L14–L16).
- Zamknij browser na końcu.
