# PLAN WDROŻENIA #1196 — Mapy skarbów

> Plan dla agenta implementującego. Zwiad kodu wykonany 2026-07-11 — wszystkie odwołania file:line zweryfikowane w kodzie na branchu `develop`. Sam nie zmieniaj decyzji projektowych D1–D4 bez zgody Piotra.

## 0. Decyzje projektowe (przyjęte defaulty — Piotr może nadpisać)

| # | Decyzja | Wybór |
|---|---|---|
| D1 | Zasięg skarbu | Skarby **generowane** są per bohater (`character_id` na `world_treasures`) — każdy poluje na swoje, zero kolizji. Skarby **zakopane przez admina** mają `character_id=NULL` = globalne, jednorazowe (kto pierwszy). |
| D2 | Kanały zdobywania fragmentów v1 | (a) loot z wrogów, (b) plotki (`treasure_site`). Sklep / czarny rynek → **out of scope v1** (osobny etap E7 opcjonalny). |
| D3 | Generator | Deterministyczny (bez LLM), on-demand: pierwszy fragment dla bohatera tworzy skarb. Plus ręczne zakopywanie admina z zakładki Mapa. |
| D4 | Akcja kopania | Free-text intent („kopię", „szukam skrytki") łapany deterministycznie przed LLM **+** przycisk „Szukaj skrytki" w modalu hexa na mapie gracza (ŻAR). |

Dodatkowe rozstrzygnięcie względem treści issue: issue proponuje „fragment jako item z flagą". Zwiad wykazał, że ścieżka grantu (`grant_loot_to_character`, `loot_service.py:891-916`) **stackuje po `item_key`** — różne fragmenty by się zlewały, a drop/sell psułby kolekcję. Dlatego **model hybrydowy**:
- w loot tables fragment jest zwykłym wpisem `item_key='fragment_mapy_skarbow'` (XOR nietknięty, zero zmian w schemacie loot entries),
- ale grant tego klucza jest **przechwytywany** w `grant_loot_to_character` i zamiast wiersza w `character_inventory` powstaje wiersz w `character_map_fragments` (tabela z issue). Ekwipunek UI czyta fragmenty z dedykowanego źródła, nie z inventory.

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
  hex_q INTEGER NOT NULL,
  hex_r INTEGER NOT NULL,
  map_level INTEGER NOT NULL DEFAULT 0,          -- v1: zawsze 0 (out of scope: mapy lokalne)
  region TEXT,
  loot_table_key TEXT NOT NULL,
  gold_bonus INTEGER NOT NULL DEFAULT 0,          -- dodatkowe złoto ponad tabelę
  guardian_enemy_key TEXT,                        -- NULL = bez strażnika
  dc INTEGER NOT NULL DEFAULT 12,                 -- test odnalezienia (Medium)
  total_fragments INTEGER NOT NULL DEFAULT 3,
  character_id INTEGER,                           -- D1: NULL = globalny (admin), inaczej per bohater
  state TEXT NOT NULL DEFAULT 'buried',           -- buried | found
  created_by TEXT NOT NULL DEFAULT 'generated',   -- generated | admin
  created_at TEXT DEFAULT (datetime('now')),
  found_at TEXT,
  found_by_character_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_world_treasures_hex ON world_treasures(hex_q, hex_r, map_level);
CREATE INDEX IF NOT EXISTS idx_world_treasures_char ON world_treasures(character_id, state);

CREATE TABLE IF NOT EXISTS character_map_fragments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  campaign_id INTEGER,
  treasure_id INTEGER NOT NULL,                   -- FK world_treasures.id
  fragment_no INTEGER NOT NULL,
  acquired_at TEXT DEFAULT (datetime('now')),
  source TEXT DEFAULT 'loot',                     -- loot | rumor | admin
  UNIQUE(character_id, treasure_id, fragment_no)
);
CREATE INDEX IF NOT EXISTS idx_char_map_fragments ON character_map_fragments(character_id);
```

Katalogowy item-nośnik (seed w migracji, `created_by='seed'`): `game_config_items` key `fragment_mapy_skarbow`, `item_type='quest'`, label „Fragment mapy skarbów", opis fabularny, `value_gp=0` (nie pojawi się w sklepach — filtr `value_gp<=0` w `shop_service.py:512` działa na naszą korzyść w v1), `approved=1`, `review_status='permanent'`.

## 3. Backend service — `treasure_service.py` (E2)

Nowy plik `backend/app/services/treasure_service.py`. Kontrakt jak `bestiary_service`/`rumor_service`: **DB-error tolerant, nigdy nie wywala tury** (try/except + log).

- `grant_fragment(conn, character_id, campaign_id, source='loot') -> dict | None`
  1. Znajdź `world_treasures` `state='buried'` dla bohatera (`character_id = ? OR character_id IS NULL`) z niekompletnym zestawem fragmentów.
  2. Brak → `_generate_treasure(conn, campaign_id, character_id)`.
  3. INSERT kolejnego `fragment_no`; zwróć `{treasure_id, fragment_no, total, complete: bool, hint_region}` — do hinta narratora i toasta.
- `_generate_treasure(...)` — deterministyczny (D3): losuj heks z `world_hexes` `map_level=0 AND is_active=1 AND location_key IS NULL`, preferuj region bieżącej pozycji, wyklucz heks startowy i heksy istniejących skarbów bohatera; `loot_table_key` = tabela regionu tieru +1 (fallback: najlepsza istniejąca aktywna tabela — NIE twórz nowych tabel w locie); `guardian_enemy_key` = 50% szans, losowy nie-boss z `encounter_pool` heksu lub regionu; `dc=12`.
- `get_treasure_maps(conn, character_id) -> dict` — fragmenty zgrupowane per skarb: `{treasure_id, fragments: n/total, complete, state}`; **współrzędne heksu ujawniane tylko gdy `complete`**.
- `attempt_dig(conn, campaign_id, character_id) -> dict` — bramki (kolejno): kompletna mapa istnieje → jej heks == `session_flags.current_hex` → `state='buried'`. Zwraca `{eligible: false, reason}` albo buduje `pending_skill_test` (percepcja/WIS, `dc` skarbu) wzorcem `turn_skill_router.py:53-91` z `source='treasure_dig'` + `treasure_id` w pending.
- `resolve_dig_success(conn, campaign_id, character_id, treasure_id) -> dict` — wywoływane po sukcesie testu:
  - strażnik istnieje i żyje → `initiate_combat(campaign_id, character_id, [guardian_enemy_key])` + zapisz `session_flags.pending_treasure_loot = {treasure_id}`; loot wydany dopiero po zwycięstwie (hook w okolicy `_credit_bestiary_kill` / ścieżki zakończenia walki — agent: znajdź miejsce, gdzie combat kończy się zwycięstwem i wydawany jest loot wroga, tam skonsumuj flagę),
  - bez strażnika → od razu `_payout(...)`.
- `_payout(...)` — `roll_loot` ze wskazanej tabeli (bez bramki `drop_chance` wroga — roll bezpośrednio z `get_loot_table`) + `roll_gold_drop` + `gold_bonus` → `grant_loot_to_character(source='treasure')`; `state='found'`, `found_at`, `found_by_character_id`; `confirm_rumors_for(campaign_id, 'treasure_site', str(treasure_id))`; zwróć podsumowanie do narracji.
- Porażka testu: tura mija, skarb zostaje `buried`, można próbować ponownie (bez limitu w v1 — Numbers Policy).

**Integracja grantu (przechwycenie):** w `grant_loot_to_character` (`loot_service.py:891-916`, gałąź stack-by-item_key) — jeśli `item_key == 'fragment_mapy_skarbow'` → zamiast INSERT/UPDATE inventory wywołaj `treasure_service.grant_fragment(...)` i dodaj do zwracanej listy wpis `{label: 'Fragment mapy skarbów (n/3)', item_type: 'quest', ...}`. Uwaga na import cycle (loot→treasure→loot przy payout): payout woła `grant_loot_to_character` — fragment nie może być w tabeli lootu skarbu, a import w funkcji (local import), jak robią to inne serwisy.

**Loot tables:** dodaj wpis `fragment_mapy_skarbow` (weight ~4, qty 1/1) do kilku istniejących tabel regionalnych zwykłych wrogów — seed w migracji, `created_by='seed'`. NIE do tabel bossów ani tabel skarbów.

## 4. Turn pipeline — intent kopania (E2)

- `_maybe_dig_shortcut(conn, campaign_id, text)` w `turns.py`, wywołany **przed** `_route_skill_turn` (obok `_maybe_services_shortcut`, `turns.py:5675`).
- Trigger: regex słów kluczowych („kopię", „wykopuję", „odkopuję", „rozkopuję", „szukam skrytki", „szukam schowka", „szukam skarbu") — word-boundary, case-insensitive.
- Deleguje do `treasure_service.attempt_dig`. Gdy `eligible=false` → **fall through do normalnej tury LLM** (żadnego bloku — gracz może kopać narracyjnie gdzie chce, po prostu nie ma tam skrytki). Gdy eligible → zwróć `skill_test_pending` (istniejący popup kości ŻAR skonsumuje — #1299).
- Rozszerz resolve testu (`turns.py:7742`) o gałąź `pending.source == 'treasure_dig'` → `resolve_dig_success` / narracja porażki.

## 5. Endpointy (E2/E3)

Gracz (`backend/app/api/characters.py` + `turns.py`):
- `GET /api/characters/{id}/treasure-maps` → `get_treasure_maps` (obok atlasu, `characters.py:~1221`).
- `POST /api/campaigns/{id}/treasure/dig` — ścieżka przycisku (D4); ta sama logika co shortcut.
- Rozszerz per-hex payload `get_campaign_world_map` (`turns.py:8558-8568`) o `is_treasure: bool` — tylko dla heksów kompletnych, niewykopanych map bohatera.

Admin (`backend/app/routers/hex_world.py` lub `admin.py`):
- `POST /api/admin/world-treasures` — ręczne zakopanie `{hex_q, hex_r, loot_table_key, guardian_enemy_key?, dc?, total_fragments?, character_id?}`.
- `GET /api/admin/world-treasures` — lista + filtr state.
- `DELETE /api/admin/world-treasures/{id}`.
- `GET /api/admin/campaigns/{id}/treasure-maps` — podgląd fragmentów/map bohatera w monitorze kampanii.

## 6. Frontend ŻAR — `frontend/front-v2/` (E4)

Build na `.61` (`sudo npm run build`), dist bind-mounted.

1. **WorldMap** — pole `is_treasure` w `WorldHex` (`types.ts:235`), badge ✕ (Phosphor `XCircle`/`Crosshair`, styl ember) wzorem gwiazdki questowej (`WorldMap.tsx:661-667`) + pozycja w legendzie (`:399-404`).
2. **Modal hexa** (`WorldMap.tsx:409-520`) — gdy `is_treasure` i gracz stoi na heksie → przycisk „Szukaj skrytki" → `POST .../treasure/dig` → odpowiedź z `skill_test_pending` przekazana do istniejącego flow popupu kości (wzorzec konsumpcji #1299).
3. **PanelInventory** — nowa pod-sekcja „Mapy skarbów" w bloku Fabularne: karta per skarb, licznik `2/3`, po skompletowaniu „Cel: heks (q,r) — region"; dane z `GET /treasure-maps` (nowy hook obok `useSheetData`).
4. Toast po zdobyciu fragmentu — wzorzec extra-payload `map_reveal` (`useSheetData.ts:121-128`, `PanelInventory.tsx:121-139`).

**Nie dotykaj `frontend/front/`** (zamrożony). Ledger `frontend_design.md` Sekcja 7: nowy wpis F-NN.

## 7. Admin UI (E5)

1. `map.js` `_wbRenderDetail` (`:1657-1694`): przycisk „🗺 Zakop skarb" → mini-modal (loot_table_key select, guardian select opcjonalny, DC, liczba fragmentów) → `POST /api/admin/world-treasures`. Wskaźnik ✕ na heksach ze skarbem `state='buried'` w renderze buildera.
2. `campaigns.js` monitor: w tabie Mapa — wskaźnik skarbu na overlay (wzorzec `:360-366`); w tabie Przegląd — sekcja „Mapy skarbów gracza" z `GET /api/admin/campaigns/{id}/treasure-maps`.
3. Bump `?v=N` w importach zmienionych modułów admina.

## 8. Synergie (E3)

- **Plotki:** w `_pick_target` (`rumor_service.py:37-103`) nowa gałąź (priorytet między lokacją a wrogiem): bohater ma skarb `buried` z ≥1 fragmentem i niekompletny → `target_type='treasure_site'`, `target_key=str(treasure_id)`; flavour w `_FLAVOUR`: „Mówią, że ktoś widział resztę takiej mapy…" (tekst PL, bez zdradzania współrzędnych). Confirm przy wykopaniu (już w `_payout`). Opcjonalnie (jeśli tanie): plotka `treasure_site` może też **wydać fragment** (`source='rumor'`) — wtedy to drugi kanał D2.
- **Atlas:** nowa sekcja `treasure_sites` w `get_atlas` (`atlas_service.py:57-119`) + `_empty_atlas`: skarby `found` bohatera (label heksu, region, data). Read-only, agregacja po `_hero_campaign_ids` nie jest potrzebna — `world_treasures.found_by_character_id` wystarczy.

## 9. Numbers Policy (wartości startowe — Sandbox-tunable)

| Parametr | Start | Uwaga |
|---|---|---|
| Fragmenty na mapę | 3 | `total_fragments` |
| DC odnalezienia | 12 (Medium) | per skarb, admin może nadpisać |
| Waga fragmentu w loot tables | 4 (=4%) | tylko tabele zwykłych wrogów |
| Tier lootu skarbu | region +1 | fallback: najlepsza aktywna tabela |
| Szansa na strażnika (generator) | 50% | nie-boss z puli regionu |
| Limit prób kopania | brak | porażka = stracona tura |

## 10. Testy (E6)

Pytest (docker cp na `ai-gm-dev-backend-1`, tylko nowe pliki — NIE pełna suita):
- `test_treasure_service.py`: grant_fragment (nowy skarb, kontynuacja, komplet), generator (heks bez lokacji, wykluczenia, guardian), attempt_dig bramki (zły heks / niekomplet / found), payout (loot+gold, state, jednorazowość), przechwycenie w grant_loot_to_character (fragment nie ląduje w inventory), plotka treasure_site pick+confirm, atlas sekcja.
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
| E6 | Pytest + Playwright + Księga + ledger + issue record | E2–E5 |
| E7 (opcjonalny, za zgodą) | Sklep/czarny rynek: fragment kupowalny u podejrzanych typów nocą | E1–E3 |

## 13. Out of scope (za issue)

- Skarby na mapach lokalnych (`map_level=1`) — v2.
- Mapy wieloetapowe / łańcuchy skarbów.
- MP: grant fragmentów działa przez istniejący `distribute_mp_loot` (przechwycenie per postać); kopanie w MP dozwolone dla bohatera z kompletną mapą, ale dedykowany flow MP (podział lootu skarbu na drużynę) — v2, odnotuj w issue record.
