---
name: game-smoke-dungeon
description: >-
  Full-mode smoke playtest of the AI-GM tile DUNGEON (FAZA L): Claude plays a real dungeon run
  end-to-end with the real LLM — enter via tile graph, move through doors, fight scaled combat,
  open chests, solve riddles, beat a boss, choose endless/exit, die-with-checkpoint, abandon —
  verifying each checkpoint against the DB. Not tied to a single issue — the deliverable is a
  checkpoint table + P0/P1/P2 defect issues. Use when the user types /game-smoke-dungeon, asks
  "czy loch jest grywalny end-to-end", or runs the FAZA L smoke milestones (L13c mid-phase, L19
  final). For testing ONE dungeon issue use /game-test-player-screenshot instead.
---

# game-smoke-dungeon — obchód całego trybu Lochu kafelkowego (FAZA L)

Cel: odpowiedzieć na **„czy w loch da się grać end-to-end?"** — nie „czy endpoint odpowiada".
Gra się PRAWDZIWY przebieg lochu z PRAWDZIWYM LLM. Werdykt bez zagranego przebiegu jest nieważny.
Mechaniki ze specu: `game_mechanics.md` CZĘŚĆ AJ (17 decyzji projektowych).

## ⛔ KONTRAKT (jak /game-smoke)

- Weryfikacja TYLKO przez realny przebieg lochu. Żadnych skrótów przez serwisy/SQL zamiast ruchu.
- Tylko konto Demo (user_id=1). Nigdy user_id=1013.
- Bohatera, kampanii ani przebiegu po teście NIE usuwać.
- SQL wyłącznie do ODCZYTU (weryfikacja checkpointów), przez SSH+docker exec (nigdy sshfs).
- Limit: 30 tur/akcji na run (loch jest dłuższy; nowe checkpointy walki). Po limicie: raport, nawet niekompletny.

## Wywołanie

```
/game-smoke-dungeon              # pełny przebieg na lochu z treścią (krypta, po L16)
/game-smoke-dungeon --engine     # tryb silnik+UI na kafelkach testowych (przed treścią; L13c)
```

## Krok 1 — Setup

Reużyj infrastruktury `/game-test-player`:

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-test-player
python3 scripts/setup_hero_pool.py          # warrior_id/scholar_id/rogue_id
```

**Bohater:** warrior (domyślnie) — loch jest combat-heavy. Warrior ma ammo (20 strzał na start) — istotne dla CP5e. Dla testu skrzyń/zagadek rogue (DEX) bywa lepszy.

**Loch do testu** — sprawdź, że istnieje aktywny loch kafelkowy z kategorią i kafelkami:
```bash
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT key, tile_category_key, tile_count, boss_tile_id, endless_growth_n FROM game_dungeons WHERE is_active=1 AND tile_category_key IS NOT NULL;"'
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT category_key, COUNT(*) FROM dungeon_tiles GROUP BY category_key;"'   # ile kafelków per kategoria
```
- **Pełny tryb:** użyj `krypta_probna` (L16). Brak → STOP, zgłoś że treść (L14–L16) niegotowa.
- **--engine:** jeśli brak kategorii z kafelkami, zaseeduj MINIMALNĄ kategorię testową (3–4 kafelki: 1 wejście 2-drzwiowe, 1 z walką, 1 boss) `created_by='seed'` przez admin API `POST /admin/dungeon-tiles/ai-create` lub bezpośredni seed — TYLKO do testu silnika; odnotuj w raporcie że to kafelki testowe bez obrazków.

**Cooldown:** jeśli bohater ma świeży `character_dungeon_runs` na tym lochu (423 przy wejściu) — wyzeruj cooldown (admin/cheat) albo użyj innego bohatera z puli.

## Krok 2 — Scenariusz (checkpointy = mechaniki FAZY L)

Graj akcjami przez UI gracza / API ruchu lochu. Każdy checkpoint odhacz z DOWODEM (nr akcji +
cytat narracji LUB wynik SQL). Kolejność elastyczna — przebieg prowadzi, checklist pilnuje.

| # | Checkpoint | Mechanika (zadanie) | Dowód (sqlite3 /data/ai_gm.db, ssh+docker exec) |
|---|---|---|---|
| 1 | Wejście tworzy graf kafelkowy (nie liniowy) | L2/L3 | `character_dungeon_runs` ma graf z odnogami; `/enter` zwraca kafelek startowy; 409 gdy loch bez kategorii |
| 2 | Blok [LOCH] w narracji = opis kafelka z DB + koloryzacja LLM | L3, Decyzja 3 | narracja wejścia zawiera detale z `dungeon_tiles.description_pl`, nie zmyślone |
| 3 | Ruch przez drzwi przesuwa pozycję; przyciski kierunków pod composerem | L4/L12 | `POST /dungeons/move`; pozycja w `character_dungeon_runs` zmienia się; backtracking działa |
| 4 | Mapa kafelkowa: przycisk mapy pokazuje graf (odwiedzone + zarysy za drzwiami + marker) | L11 | screenshot mapy lochu; odwiedzone kafelki widoczne, niewidziane = zarys |
| 5 | **Walka na kafelku: skala D1–D5 + model #826 + strefy T34 + reakcje SF10 + konsumpcja:** (a) poziom wroga = `TIER_ENEMY_LEVELS[tier]`, NIE skalowany do bohatera; (b) baner walki ma kolumny **DYSTANS / ZWARCIE**, chipy 🏹/⚔; (c) atak melee na wroga w innej strefie → "poza zasięgiem", tura NIE spada; (d) pancerz = redukcja obrażeń: `armor = max(0, ac_base−10)`, min 1 dmg/cios, Nat20 ignoruje pancerz; (e) *(Warrior z łukiem)* dystansowy atak konsumuje strzałę; po walce: odzysk amunicji 40% szansy per wystrzelona sztuka; (f) gdy wróg trafia gracza z dostępnym `dodge`/`shield_block` → modal **Przyjmij / Unik / Blok** wyświetlony; (g) konsumpcja w walce: Akcja → Mikstura → HP wzrasta + tura spada (lub N/D brak konsumpcji) | L4/L5; poziom wroga w `combatants`; HP przed/po; `advance_turn`; ammo count w `character_inventory`; modal SF10 wyświetlony |
| 6 | Skrzynia: rzut DEX, do 3 prób, ryzyko pułapki | L6 | wpis prób w stanie runu; pułapka = efekt; brak soft-locka po porażce |
| 7 | Zagadka: do 3 prób + podpowiedzi, brak soft-locka | L6 | `riddle_key` rozliczone; po 3 porażkach przejście dalej możliwe |
| 8 | Boss po `tile_count` kafelkach + loot | L8 | walka z `boss_tile_id`; loot przyznany po wygranej |
| 9 | Po bossie: wybór „Wyjdź z łupem / Idź głębiej" (tryb nieskończony) | L8 | modal/wybór; „głębiej" → segment +n, skalowanie cykli |
| 10 | Endless: skalowanie +1 lvl wrogów/cykl (po lvl10 +15% HP/dmg) | L8, Decyzja 7 | poziom wrogów w 2. cyklu > 1. cyklu |
| 11 | Checkpoint + śmierć KOŃCZY run (nie restart pokoju) | L7, Decyzja 6 (NADPISUJE E16) | po 0 HP: run `status` zakończony, NIE restart od kafelka 1; checkpoint po bossie zapisany |
| 12 | Porzucenie: modal ostrzegawczy + 50% cooldown | L7/L13 | `character_dungeon_runs` cooldown = 50% `cooldown_hours`; modal pokazany |
| 13 | Flaga `dungeon_enabled`: wyłączona → brak wejścia (gate w API i UI) | L10 | admin toggle OFF → `/enter` blokowany; przycisk lochu ukryty/wyszarzony |
| 14 | Spójność: narracja nie zmyśla kafelków/drzwi spoza grafu | Decyzja 3 | przegląd przebiegu; każda sprzeczność narracja↔graf = defekt |

Screenshot (skrypt z `/game-screen`, procedura jak w /game-test-player-screenshot Step 7a) PO
checkpointach: 4 (mapa), 8 (boss), 11 (śmierć/checkpoint) — minimum 3 na run.

**--engine** (mid-faza, przed treścią): pomiń checkpointy zależne od treści — 2 (opisy PL), 7
(zagadki, jeśli brak w kafelkach testowych) — oznacz N/D „brak treści (L14–L16)". Resztę (graf,
ruch, mapa, walka+#826+T34+SF10, boss, endless, śmierć, porzucenie, flaga) graj normalnie.

## Krok 3 — Defekty

Każde ❌ = issue:

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-LOCH — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<tura/akcja, oczekiwane vs faktyczne, SQL/screenshot>"
```

Priorytety: **P0** = przebieg nieprzechodzalny (soft-lock, śmierć restartuje pokój, wejście pada) ·
**P1** = psuje doświadczenie (rubber-banding wrogów, narracja↔graf sprzeczna, mapa nie pokazuje pozycji,
brak modalu reakcji, zły pancerz/obrażenia, brak feedbacku) · **P2** = kosmetyka. Priorytet w tytule.

## Krok 4 — Raport

Komentarz do issue `[SMOKE] FAZA L` (utwórz, jeśli nie ma):

```
## 🎮 game-smoke-dungeon — <tryb pełny/--engine> — <data>
**Loch:** key | **Bohater:** id | **Archetype:** warrior/scholar/rogue | **Akcji zagranych:** N | **Cykli endless:** M

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Checkpointy
| # | Checkpoint | Wynik | Dowód |
(14 wierszy: ✅ / ❌ #issue / N/D powód)

### Defekty: P0: n · P1: n · P2: n (linki)
### Screenshoty (3+, z opisem co widać: mapa, boss, śmierć)
```

Po runie: zaktualizuj notes.md (L13c lub L19) — `[x]` TYLKO gdy przebieg ukończony i wszystkie P0 zgłoszone.

## Gotchas

- Rate limit TPM → 502: czekaj 60 s; model `gpt-4.1-mini` w configu kampanii zmniejsza koszt.
- 423 przy wejściu = cooldown runu — wyzeruj (admin/cheat) lub inny bohater z puli.
- Walka w lochu deterministyczna z silnika (Decyzja 4) — żadnych tagów COMBAT_START od LLM; jeśli LLM próbuje narrować walkę bez startu silnika → defekt P0.
- **CP5b–c (strefy):** domyślne strefy przy starcie lochu: Warrior→engaged, Scholar→ranged; wróg-łucznik→ranged. Sprawdź `combatants[].zone` w `active_combat`.
- **CP5d (pancerz):** `armor = max(0, enemy.ac_base − 10)`; ac_base=12 → armor=2; cios 5 dmg → min max(1, 5−2)=3 dmg. Nat20 = bez redukcji pancerza (podwójne obrażenia + pełna kość).
- **CP5e (ammo):** po walce dystansowej sprawdź `character_inventory` ile strzał zostało. Odzysk: `POST /combat/recover-ammo` → każda wystrzelona sztuka 40% szansy na odzysk. Brak ammo → strzał zablokowany BEZ spalenia tury.
- **CP5f (reakcja SF10):** modal pojawia się gdy gracz ma `dodge`/`shield_block` rank ≥1. Jeśli bohater nie ma tych skilli → modal nie wymagany → odnotuj "brak skilli reakcji w sheet_json".
- Nie wymuszaj checkpointów łamiąc fikcję — graj naturalnie; checkpoint nieosiągnięty organicznie po limicie → N/D z powodem, to też wynik.
- `--engine` na kafelkach testowych: brak obrazków/opisów PL to NIE defekt (treść = L14–L16).
