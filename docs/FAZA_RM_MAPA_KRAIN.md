# FAZA RM — Mapa: wsparcie 6 krain + kolejne jako DLC-update

> Realizuje issue **#917** (z lore #911 / wizytówki #905). Decyzja Piotra (2026-06-29):
> **model HYBRYDA**, pełen plan teraz, teren generowany przez Claude zgodnie z kanonem
> wizytówki/LORE_v1, każda lokacja przypisana do krainy.
>
> Ten dokument **OPISUJE** zadania. Statusy żyją w **GitHub milestone "FAZA RM — Mapa wielu krain (#917)"**
> (jedyne źródło prawdy o postępie — zgodnie z konwencją projektu od 2026-06-21).

---

## 0. Model docelowy — HYBRYDA (przeczytaj zanim ruszysz kod)

**Jeden ciągły kontynent-kanon**, podzielony na **6 krain** (LORE_v1):
Koronne Niziny · Kresy · Czarnobór · Siwe Granie · Wybrzeże Łez · Martwe Pustkowia.

- **Kanon = ciągły** — wszystkie krainy leżą w jednej siatce heksów (`world_hexes`, `map_level=0`),
  na **absolutnych** koordynatach `q,r`. Krainy stykają się granicami, nie nakładają.
- **Region = tag** — każdy heks i każda lokacja ma kolumnę `region` (NOT NULL).
- **DLC = modularne** — content każdej krainy pakowany jako **osobny plik-seed**
  (`data/regions/region_<key>.json`), zszywany w mistrz-mapę po absolutnych koordynatach.
  Dodanie krainy = dorzucenie pliku + flip statusu `coming`→`live`. Brak pliku =
  **zablokowana granica** (frontier) z teaser-labelem ("ku Siwym Graniom" — **już jest w seedzie**).

### Stan obecny (punkt startu)
- `world_hexes`: 50×50 = 2500 heksów, **wszystko = Kresy**, brak kolumny region. Jest `map_level`
  (0=świat, 1=sublokacja ML), `parent_hex_id`, `location_key`→`game_locations`, fog via
  `discovered_in_campaign_id`. Index `(q,r)`.
  Schema: `backend/app/migrations_admin.py:3445`, kolumny ML: `backend/app/main.py:359-360`.
- `game_locations`: jest `world_hex_q/r`, `placement`, `biome`, `parent_key`. **Brak region.**
  Schema: `backend/app/migrations_admin.py:713`.
- 6 krain + przypisanie ~30 makro-lok = **tylko w lore** `docs/world/LORE_v1_KANON.md` (sekcja 3).
- Seed: 1 plik `docs/world/world_map_seed.json` (cały świat). Skrypty: `scripts/seed_world_map.py`,
  `scripts/snapshot_world_map.py`. Generator: `scripts/generate_kresy_map.py`.
- Endpointy: `backend/app/routers/hex_world.py` — wszystkie query mają zaszyte `map_level=0`,
  zero filtra region. Travel/pathfinding: `backend/app/services/hex_travel_service.py`.
  Sub-mapy ML: `backend/app/services/local_hex_service.py`. Admin UI: `frontend/admin/sections/map.js`.

---

## 1. Zasady projektowe FAZY RM (każda zmiana ma je spełniać)

1. **Kanon mapy = pliki w git, DB = cache.** Nigdy nie edytuj `world_hexes` (map_level=0) bez
   `snapshot_world_map.py` → commit. (Reguła z CLAUDE.md, rozszerzona na pliki per-region.)
2. **Jeden ciągły kontynent.** Koordynaty absolutne, krainy się nie nakładają, granice się stykają.
3. **Region jest zawsze.** Każdy heks i każda lokacja ma `region` (NOT NULL, domyślnie `'kresy'`).
   ML-sub-mapy (map_level=1) dziedziczą region z heksa-rodzica.
4. **Teren zgodny z kanonem.** Biomy per kraina wg LORE_v1 i wizytówki — generuje Claude
   (RM5), nie procedura losowa bez profilu. Profile biomów: patrz RM5.
5. **DLC bezpiecznie.** Dodanie krainy = nowy plik + flip statusu. Nigdy nie wycieraj istniejących
   krain. Brak pliku = `locked` frontier, nie crash.

---

## 2. Słownik krain (kanon — enum + biome-profile)

| key | label | status startowy | biome-profil (RM5) | lore-kotwice |
|---|---|---|---|---|
| `koronne_niziny` | Koronne Niziny | coming | plains, town, road, river | Vilnograd, Volhynia, Klasztor Iskry |
| `kresy` | Kresy | **live** (istnieje) | plains, heath, village, forest | Strzegwacht, Wolfsmark, Rudnik, Kamionka |
| `czarnobor` | Czarnobór | coming | forest, swamp, lake | Bór Zmarłych, Bagienna Knieja |
| `siwe_granie` | Siwe Granie | coming (pilot RM7) | snow, mountain, tundra, hills | Kopalnia Czarnego Hutmana, Krzyż Gór |
| `wybrzeze_lez` | Wybrzeże Łez | coming | sea, coast, swamp | Czarnogród, Zatoka Topielców |
| `martwe_pustkowia` | Martwe Pustkowia | coming | heath, ruins, tundra | Pustkowie Solne, Świątynia Pradawnych |

---

## 3. Zależności i kolejność

Łańcuch liniowy: **RM1 → RM2 → RM3 → RM4 → RM5 → RM6 → RM7**

- **Blok fundament:** RM1 (schema), RM2 (lore→data).
- **Blok silnik:** RM3 (query region-aware), RM4 (seed/snapshot per-region).
- **Blok content:** RM5 (generacja terenu per-kraina).
- **Blok UX+DLC:** RM6 (admin UI), RM7 (DLC pilot Siwe Granie + runbook).

RM5 może iść równolegle po RM4 (potrzebuje formatu pliku z RM4), ale domyślnie liniowo.
Agent bierze **pierwsze niezrobione** zadanie wg tego łańcucha.

---

## 4. Zadania

### RM1 — Schema: kolumna `region` + tabela `world_regions`
**Cel prostym językiem:** Damy mapie i lokacjom „naklejkę" z nazwą krainy. Dziś silnik nie wie,
że Strzegwacht leży w Kresach, a Vilnograd w Koronnych Nizinach — po tym zadaniu będzie wiedział.
Bez tego nic dalej nie ruszy.
**Dla agenta:**
- Migracja w `backend/app/migrations_admin.py` (wzór: jak ML w `backend/app/main.py:359-360`,
  idempotentny `ALTER ... ADD COLUMN` w try/except).
- `world_hexes`: `ADD COLUMN region TEXT NOT NULL DEFAULT 'kresy'`.
- `game_locations`: `ADD COLUMN region TEXT` (NULL dozwolony — backfill w RM2).
- Nowa tabela `world_regions(key TEXT PK, label TEXT, color TEXT, status TEXT
  CHECK(status IN ('live','coming','locked')) DEFAULT 'coming', entry_q INTEGER, entry_r INTEGER,
  sort_order INTEGER, note TEXT)`. Seed 6 wierszy ze słownika sekcji 2 (Kresy = `live`, reszta `coming`).
- Reindeks: zamień `idx_world_hexes_coords (q,r)` na `UNIQUE(q,r,map_level,region)`
  (sprawdź `migrations_admin.py:3470`). Dodaj `idx (region, map_level)`.
- Backfill: cały istniejący `world_hexes` → `region='kresy'` (default to robi). NIE ruszaj danych poza tym.
- **Nie** edytuj `world_hexes` map_level=0 ręcznie poza migracją kolumn (PIOTR-OWNED).
**Weryfikacja:**
- `docker exec ai-gm-dev-backend-1 python -c "..."` lub SQL: `PRAGMA table_info(world_hexes)` pokazuje `region`;
  `PRAGMA table_info(game_locations)` pokazuje `region`; `SELECT count(*) FROM world_regions` = 6.
- `SELECT DISTINCT region FROM world_hexes` = tylko `kresy`. Liczba heksów map_level=0 niezmieniona (2500).
- pytest: nowy `test_region_schema.py` — kolumny istnieją, world_regions ma 6 wpisów, Kresy=live.

### RM2 — Lore → dane: przypisanie ~30 makro-lokacji do krain
**Cel prostym językiem:** Przepiszemy z dokumentu lore do bazy, która lokacja należy do której
krainy. Po tym każda osada/loch „wie", w jakiej krainie się znajduje.
**Dla agenta:**
- Źródło: `docs/world/LORE_v1_KANON.md` sekcja 3 (6 krain + lokacje 🟢) + tabela sekcji 2 tego dokumentu.
- Skrypt `scripts/assign_location_regions.py` (idempotentny): mapuje `game_locations.key`/`label` → `region`.
  Mapowanie zaszyte jawnie w skrypcie (dict key→region), bez zgadywania LLM. Loguje niezmapowane.
- Po backfillu `game_locations.region`: zsynchronizuj heksy — dla każdej lokacji `placement='placed'`
  ustaw `world_hexes.region` heksa pod `world_hex_q/r` (jeśli różny od krainy lokacji → log konflikt, nie nadpisuj na ślepo).
- Commit przypisania (mapowanie = kanon, commit = zgoda Piotra).
- Lokacje `floating` (bez koordynatów) dostają region z mapy lore; jeśli brak w lore → `region=NULL` + log do ręcznego przeglądu.
**Weryfikacja:**
- SQL: `SELECT region, count(*) FROM game_locations GROUP BY region` — rozkład na 6 krain, lista NULL-i krótka i wytłumaczona.
- Strzegwacht/Wolfsmark/Rudnik = `kresy`; Vilnograd = `koronne_niziny`; Kopalnia Czarnego Hutmana = `siwe_granie`.
- pytest: `test_location_region_backfill.py` — known-lokacje mają poprawny region; zero crashy przy re-runie skryptu.

### RM3 — Query region-aware (silnik czyta region)
**Cel prostym językiem:** Nauczymy silnik gry pracować „na jednej krainie naraz" — ruch, spotkania,
podmapy będą wiedziały, w której krainie się dzieją. Fundament pod to, by nieodblokowane krainy były niewidoczne.
**Dla agenta:**
- `backend/app/routers/hex_world.py`: `GET /api/admin/world/map` — dodaj opcjonalny `?region=` (domyślnie wszystkie `live`);
  zwracaj `region` w każdym heksie + listę `regions` (z `world_regions`). POST/PATCH hex akceptuje `region` (domyślnie dziedziczy z istniejącego heksa pod q,r albo z body).
- `backend/app/services/hex_travel_service.py`: pathfinding (`_load_hex_graph`/odpowiednik) filtruje po krainach `live`; przejście do heksa w krainie `locked`/`coming` = zablokowane z komunikatem „Kraina niedostępna".
- Encounter spawn: pula spotkań respektuje region heksa (na razie dziedziczy istniejącą logikę, ale nie miesza puli między krainami).
- `backend/app/services/local_hex_service.py`: tworząc map_level=1 sub-mapę, ustaw `region` = region heksa-rodzica (parent_hex_id). Backfill istniejących ML-heksów do regionu rodzica.
**Weryfikacja:**
- `GET /api/admin/world/map?region=kresy` zwraca tylko heksy Kresów + `regions` z 6 wpisami i statusami.
- pytest: `test_hex_region_query.py` — filtr region działa; pathfinding nie przekracza granicy do `coming`/`locked`; nowa ML-sub-mapa dziedziczy region rodzica.
- Smoke: istniejąca kampania w Kresach gra dalej bez zmian (regresja zero).

### RM4 — Seed/snapshot per-region (paczki DLC jako pliki)
**Cel prostym językiem:** Rozbijemy jeden wielki plik mapy na osobne pliki per kraina, które da się
dorzucać jak „paczki DLC". Mistrz-mapa powstaje ze zszycia wszystkich aktywnych paczek.
**Dla agenta:**
- Format `data/regions/region_<key>.json`: `{region, label, status, w, h, hexes:[{q,r,hex_type,label,atmosphere,encounter_chance}]}` — koordynaty ABSOLUTNE w kontynencie.
- `scripts/seed_world_map.py`: dodaj `--region <key>` (seeduje jedną krainę) + tryb „stitch" (zszyj wszystkie `data/regions/*.json` o statusie `live`). Zachowaj idempotencję i safeguard (<50 heksów = odmowa).
- `scripts/snapshot_world_map.py`: dodaj `--region <key>` → dump tylko heksów danej krainy do `region_<key>.json`. Domyślnie snapshot wszystkich live krain do osobnych plików.
- Migracja istniejącego `world_map_seed.json` → `region_kresy.json` (jednorazowy split, skrypt `scripts/split_seed_into_regions.py`). Stary plik zostaje jako legacy/backup.
- `hex_world.py` restore/snapshot endpointy → operują per-region.
**Weryfikacja:**
- `data/regions/region_kresy.json` istnieje, ~2500 heksów, koordynaty zgodne ze starym seedem (diff = 0 różnic w q,r,hex_type).
- `python scripts/seed_world_map.py --force` (stitch) odtwarza dokładnie 2500 heksów Kresów; `--region kresy` to samo.
- pytest: `test_region_seed_stitch.py` — split→stitch round-trip zachowuje wszystkie heksy; safeguard działa.

### RM5 — Generacja terenu per-kraina (Claude, zgodnie z kanonem)
**Cel prostym językiem:** Wygenerujemy mapy pozostałych 5 krain — góry i śnieg dla Siwych Grani,
las i bagno dla Czarnoboru itd. — tak, by pasowały do opisu świata z wizytówki i lore. Każda kraina
dostaje własny, charakterystyczny teren.
**Dla agenta:**
- Rozbuduj `scripts/generate_kresy_map.py` → `scripts/generate_region_map.py` z parametrem `--region <key>`
  i **biome-profilem per kraina** (tabela sekcji 2). Gradienty już regionalne (góry N, las E, wybrzeże SW) — wykorzystaj.
- Generuj na ABSOLUTNYCH koordynatach: krainy rozmieszczone tak, by stykały się granicami (Siwe Granie = północ od Kresów, Czarnobór = wschód, Wybrzeże Łez = SW, Koronne Niziny = centrum/zachód, Martwe Pustkowia = peryferie). Ustal layout kontynentu (dokument `docs/world/continent_layout.md` z bounding-boxami per kraina).
- Heksy graniczne stykające się z `coming` krainą dostają teaser-label („ku <Krainie>") — spójne z istniejącymi w seedzie.
- Wyjście: `data/regions/region_<key>.json` + podgląd PNG `temp-img/region_<key>.png` (do akceptacji wizualnej Piotra).
- **To zadanie generuje content** — Claude tworzy mapy, ale ich NIE seeduje do live (status `coming`) dopóki Piotr nie zaakceptuje. RM7 odblokowuje pilota.
- Wpisz wygenerowane mapy do działu „Świat" wizytówki (#905) jeśli dotyczy.
**Weryfikacja:**
- Dla każdej z 5 krain istnieje `region_<key>.json` + PNG; biomy zgodne z profilem (np. Siwe Granie: dominują snow/mountain/tundra).
- `docs/world/continent_layout.md` opisuje bounding-boxy — brak nakładania się krain (test geometrii: zero kolizji q,r między plikami).
- pytest: `test_continent_no_overlap.py` — żadne dwa region-pliki nie dzielą koordynatu (q,r).
- Piotr akceptuje wizualnie PNG-i (krok kontroli właściciela).

### RM6 — Admin UI: selektor krainy + statusy
**Cel prostym językiem:** W panelu admina dodamy przełącznik krain — wybierasz krainę, widzisz jej
mapę w jej kolorze, widzisz które są odblokowane (`live`), które czekają (`coming`/`locked`).
**Dla agenta:**
- `frontend/admin/sections/map.js`: selektor krainy (dropdown z `world_regions`), filtr mapy po region,
  kolor tła wg `world_regions.color`, badge statusu (live/coming/locked). Bump `?v=N` przy zmianie modułu.
- Kampania/fog: init mapy gracza = tylko krainy `live`; `coming`/`locked` rysowane jako szara mgła z teaser-labelem.
- Kafelek campaign-modal „🗺 Mapa" (`frontend/admin/sections/campaigns.js`) respektuje region (pokazuje krainę kampanii).
**Weryfikacja:**
- `/admin/#map` — dropdown z 6 krainami; wybór Kresów pokazuje mapę Kresów; `coming` krainy oznaczone.
- Playwright spec (admin map) — selektor zmienia widok, statusy widoczne. Auto-listuje się w Test Runner.
- Konsola bez błędów; `?v=` zbumpowane.

### RM7 — DLC pilot: Siwe Granie + runbook „jak dodać krainę"
**Cel prostym językiem:** Odblokujemy pierwszą nową krainę — Siwe Granie (góry krasnoludów, Kopalnia
Czarnego Hutmana) — jako dowód, że „DLC" działa od początku do końca. I spiszemy instrukcję, jak
dorzucać kolejne.
**Dla agenta:**
- Weź `region_siwe_granie.json` (z RM5), uzupełnij lore-kotwicami (Kopalnia Czarnego Hutmana, Krzyż Gór),
  podepnij lokacje krasnoludzkie (region=`siwe_granie`).
- Seed do live: `seed_world_map.py --region siwe_granie`; flip `world_regions.status` Siwe Granie → `live`.
- Test przejścia granicy: kampania w Kresach dochodzi do północnej granicy → heks „ku Siwym Graniom" teraz prowadzi do realnej krainy (nie blok).
- Runbook `docs/runbooks/add_new_region.md`: krok po kroku (generuj → akceptacja PNG → snapshot/commit → seed --region → flip status → verify). To wzór dla pozostałych 4 krain (osobne issues później).
- Snapshot + commit `region_siwe_granie.json` (kanon).
**Weryfikacja:**
- `SELECT count(*) FROM world_hexes WHERE region='siwe_granie' AND map_level=0` > 0; `world_regions` Siwe Granie = `live`.
- Smoke: kampania przekracza granicę Kresy→Siwe Granie bez crashu; krasnoludzkie lokacje na mapie.
- Runbook istnieje i jest kompletny (Piotr może wg niego odblokować kolejną krainę).
- `/game-smoke` lub `/game-test-player` na kampanii dotykającej granicy.

---

## 5. Poza zakresem FAZY RM (osobne issues później)
- Pełne wygenerowanie+odblokowanie pozostałych 4 krain w live (RM5 tworzy pliki, RM7 odblokowuje tylko Siwe Granie jako pilot; reszta = osobne „DLC" issues wg runbooka RM7).
- Mechaniki rozgrywki specyficzne per kraina (pogoda, modyfikatory) — nie tu.
- Multiplayer cross-region — nie tu.

---

## 6. PROMPT STARTOWY (wklejaj na start każdej sesji, aż milestone pełny)

```
Pracujemy nad FAZĄ RM — wsparcie 6 krain na mapie świata + kolejne jako DLC-update (#917). Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. docs/FAZA_RM_MAPA_KRAIN.md (pełne opisy zadań RM1–RM7, model HYBRYDA, zasady projektowe, słownik krain),
3. GitHub milestone "Mapa wielu krain (Faza RM)" (issues #1028–#1034 = jedyne źródło statusów).

ZAKRES (decyzja Piotra, 2026-06-29):
- Model HYBRYDA: jeden ciągły kontynent-kanon, region=tag na heksie, content per-kraina jako pliki-seed (DLC).
- Teren krain generuje Claude, zgodnie z kanonem LORE_v1 / wizytówki (#905).
- Każda lokacja przypisana do krainy (game_locations.region).
- POZA zakresem: pełne odblokowanie 4 pozostałych krain (RM7 odblokowuje tylko pilota Siwe Granie; reszta = osobne DLC-issues wg runbooka), mechaniki per-kraina, multiplayer cross-region.
- NIE wycieraj world_hexes map_level=0 (PIOTR-OWNED) — tylko migracje kolumn + snapshot+commit.

TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie RM, ani mniej, ani więcej:
1. W milestone "Mapa wielu krain (Faza RM)" znajdź pierwsze nieukończone (bez `done`/zamknięcia) zadanie wg łańcucha RM1→RM2→RM3→RM4→RM5→RM6→RM7 (sekcja 3 specu).
2. Przeczytaj pełny opis (Cel / Dla agenta / Weryfikacja) w docs/FAZA_RM_MAPA_KRAIN.md i SPRAWDŹ w kodzie, czy opis zgadza się z rzeczywistością. Sprzeczność = STOP, opisz prostym językiem, czekaj na decyzję.
3. Issue już istnieje (#1028–#1034) — ustaw label in-progress, usuń backlog. Jeśli czegoś brak, uzupełnij wg szablonu #18.
4. Wdróż zadanie skillem /tdd w trybie auto (bez zatrzymań na pytaniach pośrednich). Wyjątki bez cyklu TDD: RM5 (generacja contentu) i RM7 fragment runbook/playtest — ale z pełnym raportem.
5. Wykonaj sekcję "Weryfikacja" z opisu. Gdzie wskazano /game-smoke lub /game-test-player — użyj.
6. Zaktualizuj issue (label needs-testing + komentarz fix+SHA) i docs/FAZA_RM_MAPA_KRAIN.md jeśli zadanie zmieniło design. Commit+push develop wg konwencji (auto, ref numeru issue) — bez tykania PROD.
7. STOP. Raport po polsku, prostym językiem:
   - co zrobiono i dlaczego (2-4 zdania bez żargonu),
   - "Jak możesz to sam sprawdzić" — krok po kroku (SQL/admin URL https://aigm-dev.studio-colorbox.com/admin/#map lub gra), co kliknąć, co ma się pokazać,
   - co następne w kolejce.

ZASADY ŻELAZNE:
- Tylko DEV (.61). Nigdy PROD.
- Każda zmiana zgodna z zasadami projektowymi FAZY RM (sekcja 1 specu) — region zawsze, kanon=pliki w git, jeden ciągły kontynent, DLC bezpiecznie.
- Nigdy pełny `pytest tests/` — tylko testy zadania.
- Issue zamyka tylko Piotr po weryfikacji wizualnej; label needs-testing zostaje do tego momentu.

Zacznij od kroku 1.
```
