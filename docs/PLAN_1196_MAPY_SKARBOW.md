# PLAN WDROŻENIA #1196 — Mapy skarbów

> Plan dla agenta implementującego. Zwiad kodu wykonany 2026-07-11 — wszystkie odwołania file:line zweryfikowane w kodzie na branchu `develop`. Sam nie zmieniaj decyzji projektowych D1–D7 bez zgody Piotra.

## DLA AGENTA — jak wykonać

**Wszystkie decyzje D1–D7 domknięte (Piotr, 2026-07-11). Można kodować.**

1. Rób **etap po etapie** wg §12 (E1→E7), w kolejności — każdy etap ma zależności.
2. TDD: pytest **tylko dla nowych plików** (docker cp na `ai-gm-dev-backend-1`, `pytest tests/test_treasure_*.py -v`) — **nigdy pełna suita** (Piotr uruchamia ją sam).
3. Backend = kod bake'owany: po zmianie Pythona rebuild na `.61` — `docker compose -f docker-compose.dev.yml up -d --build backend`.
4. Frontend ŻAR = `frontend/front-v2/`, build na `.61` (`sudo npm run build`), dist bind-mounted. **Nie dotykaj `frontend/front/`** (zamrożony).
5. Weryfikuj na `https://aigm-dev.studio-colorbox.com/`. Commity na `develop`, push przez `.61` (`sudo -u piotrszmidt git push`).
6. Na koniec: implementation-record issue wg szablonu #18 (labels `enhancement` + `needs-testing` + `review`), komentarz z SHA na #1196.
7. **Pułapki krytyczne:** `world_hexes` (map_level=0) **tylko odczyt** (mapa Kresów Piotra); import-cycle loot↔treasure = importy lokalne w funkcji; test ciosu strażnika idzie ścieżką reakcji (#1313) — testuj przez serwis, nie pełną turę; fragment-nośnik nie może trafić do `loot_snapshot_json` skarbu.

## 0. Decyzje projektowe (przyjęte defaulty — Piotr może nadpisać)

| # | Decyzja | Wybór (POTWIERDZONE przez Piotra 2026-07-11, poza D3) |
|---|---|---|
| D1 | Zasięg skarbu | **Jednorazowe, per bohater.** Skarby generowane mają `character_id` = bohater który zbiera fragmenty; wykop = `state='found'`, znika. Zero kolizji między graczami. Skarby zakopane przez admina też jednorazowe; mogą mieć `character_id=NULL` (otwarte, kto pierwszy) LUB przypisane do konkretnego bohatera na event. |
| D2 | Kanały zdobywania fragmentów v1 | **Wszystkie trzy w v1:** (a) loot z wrogów, (b) plotki (`treasure_site`), (c) sklep / czarny rynek nocny. E7 **wchodzi do v1**, nie jest opcjonalny. |
| D3 | Generator | **Model A — w pełni automatyczny, admin nie musi brać udziału.** Gdy gracz **skompletuje mapę** (dowolnym kanałem D2), system: (1) losuje loot **jak drop po zabiciu przeciwnika** (`roll_loot` z tabeli tieru region+1) i **zamraża go** na rekordzie skarbu, (2) ustala **heks** gdzie leży skarb. Gdy gracz tam dotrze, **LLM prowadzi narracyjnie** (hint wstrzyknięty deterministycznie) i buduje historię, a gracz musi **znaleźć** skarb (test percepcji + opcjonalny strażnik). Ręczne zakopywanie admina zostaje jako **opcjonalne narzędzie eventowe**, nie jest wymagane do działania feature'u. |
| D4 | Akcja kopania + znacznik | **Fabularnie, bez przycisku akcji.** Heks ze skarbem jest **wyraźnie oznaczony na mapie** jako „nieodkryty skarb" (jak znaczniki na mapie lokacji którą robiliśmy). Wejście = tekst gracza („kopię", „szukam skrytki") łapany deterministycznie przed LLM; rozstrzygnięcie mechaniczne (test percepcji + strażnik + wykop). **Po znalezieniu skarbu znacznik z mapy znika** (`state='found'` → `is_treasure=false`). |
| D5 | Tożsamość mapy / grupowanie fragmentów | **Po stabilnym `treasure_id`, NIE po nazwie.** Każda mapa = rekord `world_treasures` (`id` + `map_key`). Fragment = `character_map_fragments(treasure_id, part_no)`. Komplet = `count(part) ≥ total_parts`. Licznik liczony per `treasure_id` („Mapa «X» — 3/4"). Gracz z kawałkami wielu map = wiele rekordów, każdy własny licznik — brak kolizji gdy żadna niekompletna. Nazwa = tylko `label` do wyświetlenia (nazwy LLM dryfują — nie ufamy, lekcja #1279/#1294). |
| D6 | Mapa jednoczęściowa + granty itemem | **`total_parts=1` = cała mapa naraz** (bez zbierania). Trzy ścieżki grantu itemu-mapy, wszystkie przechwytywane w `grant_loot_to_character`: (a) **cała mapa od NPC/LLM** (goły `treasure_map`) → treasure `total_parts=1` → od razu komplet; (b) **fragment generyczny** (`fragment_mapy_skarbow`) → serwis dokłada `part_no` do niekompletnej auto-mapy bohatera; (c) **fragment autorski/wieloczęściowy** (klucz `tm_<mapkey>_<n>` lub `effect_json.treasure_map`) → linkuje do konkretnej mapy+część. Item-nośnik NIE ląduje jako martwy wiersz w ekwipunku — renderowany w sekcji „Mapy skarbów" z treasure-tabel. |
| D7 | Loot skaluje się z liczbą części (admin) | **Więcej części = lepszy loot** (żeby zbieranie wieloczęściowych miało sens). `total_parts` steruje jakością: mnożnik złota + dodatkowe rzuty / bonus tieru per część. Reguła **konfigurowalna przez admina** (pola na `world_treasures`, override per mapa) + domyślna w Numbers Policy. |

Dodatkowe rozstrzygnięcie względem treści issue: issue proponuje „fragment jako item z flagą". Zwiad wykazał, że ścieżka grantu (`grant_loot_to_character`, `loot_service.py:891-916`) **stackuje po `item_key`** — różne fragmenty by się zlewały, a drop/sell psułby kolekcję. Dlatego **model hybrydowy** (D5/D6):
- item-nośnik (fragment lub cała mapa) w loot tables / grantach narratora to zwykły item (XOR nietknięty, zero zmian w schemacie loot entries),
- ale grant jest **przechwytywany** w `grant_loot_to_character` i zamiast wiersza w `character_inventory` powstaje/aktualizuje się rekord w `world_treasures` + `character_map_fragments`. Tożsamość mapy = `treasure_id` (D5), nie nazwa. Ekwipunek UI czyta „Mapy skarbów" z dedykowanego źródła.
- **Fix bug ze scenariusza [SBX-SCN] #1196:** obecnie `treasure_map` (item_type='quest', `effect_json=NULL`) ląduje jako martwy, nieklikalny wiersz — bo klikalność to `can_use = consumable|map` (`loot_service.py:1252`), a mapy fog-reveal wymagają `item_type='map'` + payload `map_reveal` (osobna mechanika #1123, NIE kopanie). Nasze przechwycenie sprawia, że `treasure_map` staje się **aktywną mapą skarbu** (rekord + ✕ na mapie), a nie świstkiem.

## 1. Mapa istniejących klocków (wynik zwiadu — używaj, nie buduj od zera)

| Klocek | Gdzie | Do czego |
|---|---|---|
| Wzorzec tabeli kolekcji per-bohater | `migrations_admin.py:6076-6091` (`character_bestiary`), `:6115-6130` (`character_rumors`) | `character_map_fragments` + `world_treasures` — ten sam idiom: `_ensure_*_schema`, idempotentne CREATE, UNIQUE, indeks |
| Deterministyczny pre-LLM shortcut | `_maybe_services_shortcut`, `turns.py:2560`, wywołanie `turns.py:5675` | wzorzec dla `_maybe_dig_shortcut` (przed `_route_skill_turn`) |
| Test umiejętności (popup kości) | `_commit_pending_skill_test` `turn_skill_router.py:15`; wzorzec pending `turn_skill_router.py:53-91`; resolve `turns.py:7742` | test WIS/percepcji przy kopaniu; d20 commitowany serwerowo |
| Spawn walki poza narracją | `combat_service.initiate_combat(campaign_id, char_id, [enemy_key])` `combat_service.py:4535` | walka ze strażnikiem |
| Hook zwycięstwa / kill-credit | `_credit_bestiary_kill` `combat_service.py:5201-5232` (tu wpięte bestiary + confirm plotek) | po pokonaniu strażnika → wydanie lootu skarbu |
| Loot roll + grant | `get_loot_table` `loot_service.py:509`, `roll_loot` `:541`, `grant_loot_to_character` `:815-943` | wykop = roll wskazanej tabeli + złoto (`roll_gold_drop` `:714`) |
| Pozycja gracza (heks) | `game_sessions.session_flags.current_hex` (odczyt np. `turn_intent.py:26`, zapis `location_state_service.set_position`) | bramka „stoisz na heksie skarbu" |
| Plotki — zamknięty słownik celów | `rumor_service._pick_target` `rumor_service.py:37-103`, `_FLAVOUR` `:106-110`, `confirm_rumors_for` `:149-176` | nowy `target_type='treasure_site'`; schema nie wymaga zmian (`target_type`/`target_key` = TEXT) |
| Atlas (on-read, nie pisze) | `atlas_service.get_atlas` `atlas_service.py:44-125`, `_empty_atlas` `:144-149` | nowa sekcja `treasure_sites` agregowana z `world_treasures` |
| Mapa gracza ŻAR — badge na hexie | `WorldMap.tsx:661-667` (gwiazdka questowa — wzorzec), flagi per-hex budowane w `turns.py:8558-8568`, typ `WorldHex` `types.ts:235-247` | znacznik ✕ skarbu (`is_treasure`) |
| Modal hexa gracza | `WorldMap.tsx:409-520` (`selectHex` `:189`) | przycisk „Szukaj skrytki" |
| Ekwipunek ŻAR | `PanelInventory.tsx` — sekcje `groupBackpack` `lib/sheet.ts:329`, wzorzec extra-payload `useSheetData.ts:121-128` | sekcja „Mapy skarbów" z licznikiem 2/3 |
| Admin mapa — modal hexa | `_wbRenderDetail` `frontend/admin/sections/map.js:1657-1694`, save `_wbSaveHex` `:1634` | przycisk „🗺 Zakop skarb" |
| Admin monitor kampanii | `campaigns.js` tab Mapa `:860`, overlay indicators `:360-366` | wskaźnik skarbu + lista aktywnych map gracza |
| Item fabularny w narracji | `inventory_context_service.py` (sekcje #1304) | wzmianka o fragmentach w kontekście narratora (opcjonalnie, kolor) |

**Uwaga-pułapka:** `world_hexes` na DEV ma kolumny `map_level`, `region`, `parent_hex_id` dodane ALTER-em (nie w CREATE `migrations_admin.py:3597-3614`). Overworld = `map_level=0 AND is_active=1`. **Nie dotykaj `world_hexes` (map_level=0)** poza odczytem — mapa Kresów należy do Piotra.

## 2. Model danych (E1)

Migracje w `migrations_admin.py`, idiom `_ensure_*_schema` jak bestiariusz.

```sql
CREATE TABLE IF NOT EXISTS world_treasures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  map_key TEXT,                                   -- D5: stabilny klucz mapy (autorska mapa / generowana tm_<hex8>); tożsamość, NIE nazwa
  label TEXT,                                     -- D5: nazwa do wyświetlenia (może pochodzić od LLM/NPC/admina)
  hex_q INTEGER NOT NULL,
  hex_r INTEGER NOT NULL,
  map_level INTEGER NOT NULL DEFAULT 0,          -- v1: zawsze 0 (out of scope: mapy lokalne)
  region TEXT,
  loot_table_key TEXT,                            -- źródło rzutu przy kompletowaniu; NULL dla adminowego z jawnym snapshotem
  loot_snapshot_json TEXT,                        -- D3: loot ZAMROŻONY w chwili skompletowania mapy (rzut jak drop z wroga)
  gold_snapshot INTEGER NOT NULL DEFAULT 0,       -- złoto zamrożone przy kompletowaniu
  gold_bonus INTEGER NOT NULL DEFAULT 0,          -- dodatkowe złoto ponad snapshot (np. event admina)
  guardian_enemy_key TEXT,                        -- NULL = bez strażnika
  dc INTEGER NOT NULL DEFAULT 12,                 -- test odnalezienia (Medium)
  total_parts INTEGER NOT NULL DEFAULT 1,         -- D6: 1 = cała mapa naraz; N = do zebrania. Komplet = count(part) >= total_parts
  loot_tier_bonus INTEGER NOT NULL DEFAULT 0,     -- D7: bonus tieru lootu (admin/generator; skaluje z total_parts)
  gold_mult REAL NOT NULL DEFAULT 1.0,            -- D7: mnożnik złota (skaluje z total_parts)
  extra_loot_rolls INTEGER NOT NULL DEFAULT 0,    -- D7: dodatkowe rzuty loot table (skaluje z total_parts)
  character_id INTEGER,                           -- D1: bohater który zbiera; NULL tylko dla otwartego eventu admina
  campaign_id INTEGER,
  state TEXT NOT NULL DEFAULT 'buried',           -- buried | found  (buried = na mapie ✕; found = znika)
  created_by TEXT NOT NULL DEFAULT 'generated',   -- generated | admin | npc
  created_at TEXT DEFAULT (datetime('now')),
  found_at TEXT,
  found_by_character_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_world_treasures_hex ON world_treasures(hex_q, hex_r, map_level);
CREATE INDEX IF NOT EXISTS idx_world_treasures_char ON world_treasures(character_id, state);
CREATE INDEX IF NOT EXISTS idx_world_treasures_mapkey ON world_treasures(map_key, character_id);

CREATE TABLE IF NOT EXISTS character_map_fragments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  campaign_id INTEGER,
  treasure_id INTEGER NOT NULL,                   -- FK world_treasures.id  (D5: grupowanie po tym, nie po nazwie)
  part_no INTEGER NOT NULL,                        -- 1..total_parts
  acquired_at TEXT DEFAULT (datetime('now')),
  source TEXT DEFAULT 'loot',                     -- loot | rumor | shop | npc | admin
  UNIQUE(character_id, treasure_id, part_no)
);
CREATE INDEX IF NOT EXISTS idx_char_map_fragments ON character_map_fragments(character_id, treasure_id);
```

**D5/D6 identyfikacja mapy przy grancie** (którą mapę uzupełnia przychodzący item):
- **cała mapa** (`total_parts=1`): goły `treasure_map` (NPC/LLM) → nowy rekord, część 1, komplet natychmiast.
- **fragment generyczny** (`fragment_mapy_skarbow`): serwis dokłada `part_no` do **istniejącej niekompletnej** auto-mapy bohatera (`character_id=?`, `map_key LIKE 'tm_%'`, `count(part)<total_parts`); brak → tworzy nową (`total_parts` z Numbers Policy, np. 3).
- **fragment autorski** (`tm_<mapkey>_<n>` lub item z `effect_json.treasure_map={map_key,part_no,total_parts,...}`): linkuje do rekordu o tym `map_key` dla bohatera (tworzy przy pierwszym kawałku), część = `part_no`.

**Katalogowe item-nośniki (seed w migracji, `created_by='seed'`)** — nowy `item_type='treasure_map'` (odróżnia od fog-reveal `item_type='map'`; klucz detekcji przechwycenia):
- `fragment_mapy_skarbow` — „Fragment mapy skarbów", `item_type='treasure_map'`, opis fabularny.
- `treasure_map` — „Mapa skarbu", `item_type='treasure_map'` (**migracja UPDATE** istniejącego wiersza z `item_type='quest'` → `'treasure_map'`, żeby granty NPC/LLM łapały się przechwycenia).
- autorskie wieloczęściowe: klucze `tm_<mapkey>_<n>` z `effect_json.treasure_map={map_key,part_no,total_parts,loot_table_key?,guardian?,dc?}` (Kuźnia/forge/plan mogą je tworzyć — poza v1-core, ale schemat gotowy).
- `value_gp=0` → item-nośniki nie pojawiają się w zwykłych sklepach (filtr `value_gp<=0`, `shop_service.py:512`).

**Przechwycenie (fix bug scenariusza):** grant dowolnego itemu o `item_type='treasure_map'` (lub kluczu z tego zestawu / prefiksie `tm_`) jest łapany w `grant_loot_to_character` → trafia do treasure-tabel, **nie** tworzy martwego wiersza w `character_inventory`.

**Kanał czarnego rynku (E6, D2):** fragment/mapa na czarnym rynku wymaga jawnej pozycji w stocku z ceną. Filtr odrzuca `value_gp<=0` → użyj wpisu z ceną (`shop_inventory_json` shady-NPC z `price_gp`) i rozszerz `buy_item`, by po zakupie wywołać przechwycenie `treasure_service.grant_map_item(source='shop')` zamiast wkładać item do ekwipunku. Szczegół w E6.

## 3. Backend service — `treasure_service.py` (E2)

Nowy plik `backend/app/services/treasure_service.py`. Kontrakt jak `bestiary_service`/`rumor_service`: **DB-error tolerant, nigdy nie wywala tury** (try/except + log).

- `grant_map_item(conn, character_id, campaign_id, item_key, effect_json=None, source='loot') -> dict | None` — **jeden dispatcher (D6)** dla wszystkich trzech ścieżek:
  1. **Rozpoznaj typ** po `item_key`/`effect_json`:
     - `effect_json.treasure_map` obecne → autorska mapa: `map_key`, `part_no`, `total_parts` (+ opcjonalnie loot_table/guardian/dc) z payloadu.
     - klucz `fragment_mapy_skarbow` → fragment generyczny auto-mapy.
     - inaczej (`treasure_map` / cokolwiek `item_type='treasure_map'` bez payloadu) → **cała mapa** (`total_parts=1`).
  2. **Znajdź/utwórz rekord `world_treasures`** dla bohatera:
     - autorski → po `(map_key, character_id)`; brak → utwórz (`_generate_treasure` z parametrami z payloadu, `total_parts` z payloadu).
     - generyczny → istniejąca niekompletna auto-mapa bohatera; brak → `_generate_treasure(total_parts=Numbers.parts)`.
     - cała → zawsze nowy rekord `total_parts=1`.
  3. INSERT `character_map_fragments(treasure_id, part_no)` (part_no autorski z payloadu; generyczny/cała = kolejny wolny). UNIQUE chroni przed dublem tej samej części.
  4. **Jeśli komplet (`count(part) ≥ total_parts`):** `_finalize_treasure(...)` — losuje loot **jak drop z wroga** (`get_loot_table(loot_table_key)`, bez bramki `drop_chance`) **× `extra_loot_rolls+1` rzutów** (D7) + `roll_gold_drop × gold_mult`, tier podbity o `loot_tier_bonus`; **zamraża** w `loot_snapshot_json`/`gold_snapshot`. `is_treasure=true` na mapie.
  5. Zwróć `{treasure_id, map_label, part_no, collected, total_parts, complete: bool, hint_region, hex?}` — heks tylko gdy `complete`. Do toasta + sekcji „Mapy skarbów".
- `_generate_treasure(conn, campaign_id, character_id, *, total_parts, loot_table_key=None, guardian=None, dc=12, map_key=None, label=None)` — deterministyczny (D3, bez LLM): losuj heks z `world_hexes` `map_level=0 AND is_active=1 AND location_key IS NULL`, preferuj region bieżącej pozycji, wyklucz heks startowy + heksy istniejących skarbów bohatera; `loot_table_key` = podany lub tabela regionu tieru +1 (fallback: najlepsza istniejąca aktywna — **NIE** twórz nowych tabel w locie); `guardian_enemy_key` = podany lub 50% losowy nie-boss z `encounter_pool` heksu/regionu; **D7:** ustaw `loot_tier_bonus`/`gold_mult`/`extra_loot_rolls` z reguły skalowania wg `total_parts` (Numbers Policy); `map_key` = podany lub `tm_<hex8>`.
- `get_treasure_maps(conn, character_id) -> dict` — mapy zgrupowane per `treasure_id`: `{treasure_id, map_label, collected, total_parts, complete, state, hex?}`; **współrzędne heksu ujawniane tylko gdy `complete`**.
- `maybe_treasure_arrival_hint(conn, campaign_id, character_id, q, r) -> str | None` — **narracyjne prowadzenie (D3):** wywoływane przy wejściu na heks (obok `check_hex_enter_trigger`, `turn_intent.py:44`). Jeśli na `(q,r)` leży `state='buried'` skarb bohatera z **kompletną** mapą → zwróć hint dla narratora („W tym miejscu wg mapy ukryty jest skarb — poprowadź gracza, niech go szuka; nie ujawniaj wprost lokalizacji"). Hint wstrzykiwany jak `rumor_text` (`turn_pipeline.py:1216`), żeby LLM zbudował scenę.
- `attempt_dig(conn, campaign_id, character_id) -> dict` — bramki (kolejno): kompletna mapa istnieje → jej heks == `session_flags.current_hex` → `state='buried'`. Zwraca `{eligible: false, reason}` (→ fall-through do zwykłej tury) albo buduje `pending_skill_test` (percepcja/WIS, `dc` skarbu) wzorcem `turn_skill_router.py:53-91` z `source='treasure_dig'` + `treasure_id` w pending.
- `resolve_dig_success(conn, campaign_id, character_id, treasure_id) -> dict` — po sukcesie testu:
  - strażnik istnieje i żyje → `initiate_combat(campaign_id, character_id, [guardian_enemy_key])` + `session_flags.pending_treasure_loot = {treasure_id}`; wypłata dopiero po zwycięstwie (hook przy zakończeniu walki zwycięstwem — agent: znajdź gdzie combat kończy się wygraną i wydawany jest loot wroga, tam skonsumuj flagę → `_payout`),
  - bez strażnika → od razu `_payout(...)`.
- `_payout(...)` — wydaj **zamrożony snapshot** (`loot_snapshot_json` + `gold_snapshot` + `gold_bonus`) przez `grant_loot_to_character(source='treasure')` (item-nośnik NIE może być w snapshocie — żeby nie zapętlić przechwycenia); `state='found'`, `found_at`, `found_by_character_id`; `confirm_rumors_for(campaign_id, 'treasure_site', str(treasure_id))`; zwróć podsumowanie do narracji. **`state='found'` → znacznik ✕ znika z mapy (D4).**
- Porażka testu: tura mija, skarb zostaje `buried`, można próbować ponownie (bez limitu w v1 — Numbers Policy).

**Integracja grantu (przechwycenie — D6, fix bug):** w `grant_loot_to_character` (`loot_service.py:891-916`, gałąź stack-by-item_key) — **przed** INSERT/UPDATE inventory sprawdź, czy `item_type=='treasure_map'` (lub klucz z zestawu nośników / prefiks `tm_`). Jeśli tak → wywołaj `treasure_service.grant_map_item(...)` (przekaż `item_key` + `effect_json`), **nie** wstawiaj wiersza do `character_inventory`, i dodaj do zwracanej listy wpis dla toasta `{label: '<map_label> (n/total)' | 'Mapa skarbu', item_type: 'treasure_map', map_progress: {...}}`. Uwaga na import cycle (loot→treasure→loot przy payout): payout woła `grant_loot_to_character`, więc snapshot skarbu **nie może** zawierać item-nośnika; import w funkcji (local import) jak inne serwisy. Ta sama ścieżka obsługuje grant od NPC/LLM (narrator `[GRANT_ITEM key=treasure_map]` → `grant_loot_to_character` → przechwycenie).

**Loot tables:** dodaj wpis `fragment_mapy_skarbow` (weight ~4, qty 1/1) do kilku istniejących tabel regionalnych zwykłych wrogów — seed w migracji, `created_by='seed'`. NIE do tabel bossów ani tabel skarbów.

## 4. Turn pipeline — intent kopania (E2)

- `_maybe_dig_shortcut(conn, campaign_id, text)` w `turns.py`, wywołany **przed** `_route_skill_turn` (obok `_maybe_services_shortcut`, `turns.py:5675`).
- Trigger: regex słów kluczowych („kopię", „wykopuję", „odkopuję", „rozkopuję", „szukam skrytki", „szukam schowka", „szukam skarbu") — word-boundary, case-insensitive.
- Deleguje do `treasure_service.attempt_dig`. Gdy `eligible=false` → **fall through do normalnej tury LLM** (żadnego bloku — gracz może kopać narracyjnie gdzie chce, po prostu nie ma tam skrytki). Gdy eligible → zwróć `skill_test_pending` (istniejący popup kości ŻAR skonsumuje — #1299).
- Rozszerz resolve testu (`turns.py:7742`) o gałąź `pending.source == 'treasure_dig'` → `resolve_dig_success` / narracja porażki.
- **Narracyjne prowadzenie (D3):** przy wejściu na heks — obok `check_hex_enter_trigger` (`turn_intent.py:44`) wywołaj `treasure_service.maybe_treasure_arrival_hint(...)`; zwrócony hint dopnij do podpowiedzi narratora tą samą drogą co `rumor_text` (`turn_pipeline.py:1216`), by LLM zbudował scenę odnalezienia skarbu.

## 5. Endpointy (E2/E3)

Gracz (`backend/app/api/characters.py` + `turns.py`):
- `GET /api/characters/{id}/treasure-maps` → `get_treasure_maps` (obok atlasu, `characters.py:~1221`).
- Kopanie idzie wyłącznie przez intent w turze (`_maybe_dig_shortcut`, D4 fabularne) — **brak osobnego endpointu przycisku**.
- Rozszerz per-hex payload `get_campaign_world_map` (`turns.py:8558-8568`) o `is_treasure: bool` — tylko dla heksów kompletnych, niewykopanych map bohatera.

Admin (`backend/app/routers/hex_world.py` lub `admin.py`):
- `POST /api/admin/world-treasures` — ręczne zakopanie `{hex_q, hex_r, loot_table_key, guardian_enemy_key?, dc?, total_parts?, character_id?, label?, loot_tier_bonus?, gold_mult?, extra_loot_rolls?}`. Gdy pola skalowania (D7) puste → wylicz z `total_parts` regułą domyślną.
- `GET /api/admin/world-treasures` — lista + filtr state.
- `DELETE /api/admin/world-treasures/{id}`.
- `GET /api/admin/campaigns/{id}/treasure-maps` — podgląd fragmentów/map bohatera w monitorze kampanii.

## 6. Frontend ŻAR — `frontend/front-v2/` (E4)

Build na `.61` (`sudo npm run build`), dist bind-mounted.

1. **WorldMap** — pole `is_treasure` w `WorldHex` (`types.ts:235`), **wyraźny znacznik nieodkrytego skarbu** ✕ (Phosphor `XCircle`/`Crosshair`, styl ember, wyraźniejszy niż POI — to ma się rzucać w oczy jak znaczniki na mapie lokacji) wzorem gwiazdki questowej (`WorldMap.tsx:661-667`) + pozycja w legendzie (`:399-404`). Backend daje `is_treasure=true` **tylko** dla heksów z `state='buried'` kompletnej mapy bohatera — po `state='found'` flaga znika, więc **znacznik automatycznie schodzi z mapy (D4)**.
2. **Modal hexa** (`WorldMap.tsx:409-520`) — gdy `is_treasure` i gracz stoi na heksie → **podpowiedź tekstowa** „Tu może być zakopana skrytka — spróbuj przeszukać" (bez przycisku akcji; D4 fabularne). Gracz wraca do composera i pisze że kopie. (Znacznik ✕ + wpis w ekwipunku niosą „gdzie".)
3. **PanelInventory** — nowa pod-sekcja „Mapy skarbów" (dane z `GET /treasure-maps`, nowy hook obok `useSheetData`): **karta per `treasure_id`** (D5), tytuł = `map_label`, licznik `collected/total_parts` (1/1 dla całej mapy od NPC), po skompletowaniu „Cel: heks (q,r) — region". Item-nośnik NIE pokazuje się już jako martwy wiersz w plecaku (przechwycony w grancie, D6) — to naprawia bug „nieklikalna Mapa skarbu" ze scenariusza. Kompletna mapa = karta „aktywna" z podpowiedzią jak działać (podróż na heks + kopanie).
4. Toast po zdobyciu części/mapy — wzorzec extra-payload `map_reveal` (`useSheetData.ts:121-128`, `PanelInventory.tsx:121-139`); treść „Mapa «X» — 2/3 części" albo „Zdobyto mapę skarbu — cel na mapie świata".

**Nie dotykaj `frontend/front/`** (zamrożony). Ledger `frontend_design.md` Sekcja 7: nowy wpis F-NN.

## 7. Admin UI (E5)

1. `map.js` `_wbRenderDetail` (`:1657-1694`): przycisk „🗺 Zakop skarb" → mini-modal (label, loot_table_key select, guardian select opcjonalny, DC, **liczba części `total_parts`**, oraz **skalowanie lootu D7**: `loot_tier_bonus`/`gold_mult`/`extra_loot_rolls` — z podpowiedzią „im więcej części, tym lepszy loot"; puste = auto z `total_parts`) → `POST /api/admin/world-treasures`. Wskaźnik ✕ na heksach ze skarbem `state='buried'` w renderze buildera.
2. `campaigns.js` monitor: w tabie Mapa — wskaźnik skarbu na overlay (wzorzec `:360-366`); w tabie Przegląd — sekcja „Mapy skarbów gracza" z `GET /api/admin/campaigns/{id}/treasure-maps`.
3. Bump `?v=N` w importach zmienionych modułów admina.

## 8. Synergie (E3)

- **Plotki:** w `_pick_target` (`rumor_service.py:37-103`) nowa gałąź (priorytet między lokacją a wrogiem): bohater ma skarb `buried` z ≥1 fragmentem i niekompletny → `target_type='treasure_site'`, `target_key=str(treasure_id)`; flavour w `_FLAVOUR`: „Mówią, że ktoś widział resztę takiej mapy…" (tekst PL, bez zdradzania współrzędnych). Confirm przy wykopaniu (już w `_payout`). Opcjonalnie (jeśli tanie): plotka `treasure_site` może też **wydać fragment** (`source='rumor'`) — wtedy to drugi kanał D2.
- **Atlas:** nowa sekcja `treasure_sites` w `get_atlas` (`atlas_service.py:57-119`) + `_empty_atlas`: skarby `found` bohatera (label heksu, region, data). Read-only, agregacja po `_hero_campaign_ids` nie jest potrzebna — `world_treasures.found_by_character_id` wystarczy.

## 9. Numbers Policy (wartości startowe — Sandbox-tunable)

| Parametr | Start | Uwaga |
|---|---|---|
| Części auto-mapy generycznej | 3 | `total_parts` dla `fragment_mapy_skarbow`; mapa od NPC = 1 |
| DC odnalezienia | 12 (Medium) | per skarb, admin może nadpisać |
| Waga fragmentu w loot tables | 4 (=4%) | tylko tabele zwykłych wrogów |
| Tier lootu skarbu (baza) | region +1 | fallback: najlepsza aktywna tabela |
| **Skalowanie lootu wg części (D7)** | `gold_mult = 1 + 0.5×(total_parts−1)`; `extra_loot_rolls = (total_parts−1)//2`; `loot_tier_bonus = 0` | reguła domyślna; admin nadpisuje per mapa. 1-częściowa = baza, 4-częściowa ≈ ×2.5 złota + 1 extra rzut |
| Szansa na strażnika (generator) | 50% | nie-boss z puli regionu |
| Limit prób kopania | brak | porażka = stracona tura |

## 10. Testy (E6)

Pytest (docker cp na `ai-gm-dev-backend-1`, tylko nowe pliki — NIE pełna suita):
- `test_treasure_service.py`: `grant_map_item` trzy ścieżki D6 (cała mapa od NPC→instant complete; fragment generyczny→dokładanie części do tej samej auto-mapy, komplet po 3; fragment autorski→link po map_key+part_no), grupowanie D5 (kawałki 2 różnych map = 2 rekordy, żaden kompletny), skalowanie lootu D7 (1 vs 4 części → gold_mult + extra_loot_rolls), generator (heks bez lokacji, wykluczenia, guardian), attempt_dig bramki (zły heks / niekomplet / found), payout (loot+gold, state, jednorazowość), przechwycenie w grant_loot_to_character (item-nośnik nie ląduje w inventory), plotka treasure_site pick+confirm, atlas sekcja.
- Uwaga na pułapkę żywego testu strażnika: cios wroga idzie ścieżką reakcji (patrz #1313) — testuj przez serwis, nie pełną turę.

Playwright (`ai_test_agent/playwright/` — bind-mounted, żywe od razu):
- fragment w sekcji „Mapy skarbów" po grancie, ✕ na mapie po komplecie, przycisk „Szukaj skrytki" → popup kości.

## 11. Dokumentacja + proces

- **Księga Zasad** (`frontend/front/rules/index.html`, `/rules/`): rozdział/wpis „Mapy skarbów" — prosa + przykład + TOC + anchor; ta sama PR. (Księga opisuje, nie definiuje.)
- `frontend_design.md` — wpis F-NN (sekcja map + inventory ŻAR).
- **Implementation record issue** wg szablonu #18 (labels `enhancement` + `needs-testing` + `review` — feature graczowy, kolejka wizualna Piotra).
- Commity na `develop`, push przez `.61` (`sudo -u piotrszmidt git push`), komentarz z SHA na #1196.
- Rebuild backend na `.61`: `docker compose -f docker-compose.dev.yml up -d --build backend` (kod bake'owany — sam restart nie wystarczy).

## 12. Etapy (kolejność wdrożenia)

| Etap | Zakres | Zależy od |
|---|---|---|
| E1 | Migracje: `world_treasures`, `character_map_fragments`, seed itemu fragmentu, seed wpisów loot | — |
| E2 | `treasure_service.py` + przechwycenie grantu + `_maybe_dig_shortcut` + gałąź resolve testu + walka ze strażnikiem | E1 |
| E3 | Endpointy gracza + admin + plotki + atlas | E2 |
| E4 | ŻAR: badge ✕, modal hexa, sekcja ekwipunku, toast | E3 |
| E5 | Admin UI: zakop skarb, monitor kampanii | E3 |
| E6 | Sklep/czarny rynek (D2): fragment kupowalny u podejrzanych typów nocą — `location_tags` + night_economy | E1–E3 |
| E7 | Pytest + Playwright + Księga + ledger + issue record | E2–E6 |

## 13. Out of scope (za issue)

- Skarby na mapach lokalnych (`map_level=1`) — v2.
- **Łańcuchy skarbów** (skarb → hak → kolejna mapa jako nagroda). Mapy **wieloczęściowe** (`total_parts>1`) SĄ w zakresie (D6); łańcuchy = osobny etap. (Hak fabularny jako część `loot_snapshot` — item fabularny — dozwolony, ale bez auto-tworzenia nowej mapy.)
- MP: grant fragmentów działa przez istniejący `distribute_mp_loot` (przechwycenie per postać); kopanie w MP dozwolone dla bohatera z kompletną mapą, ale dedykowany flow MP (podział lootu skarbu na drużynę) — v2, odnotuj w issue record.
