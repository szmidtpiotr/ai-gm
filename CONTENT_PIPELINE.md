# Content Pipeline — jak treść wchodzi do gry (U13)

> Dokument dla Piotra, prostym językiem. Opisuje **skąd bierze się treść gry**
> (bronie, przedmioty, wrogowie, lokacje, NPC, questy), **trzema drogami** którymi
> może wejść, i **jak sprawdzić że jest zdrowa**. Cel: zawsze wiesz którą drogą co dodać.

---

## 1. Co to jest „treść gry"

Treść = wszystko co da się włożyć do świata, a nie jest kodem ani rozgrywką gracza.
Trzyma się to w tabelach bazy danych. Najważniejsze:

| Tabela | Co trzyma |
|---|---|
| `game_config_weapons` | bronie |
| `game_config_items` | przedmioty (w tym mikstury/zwoje) |
| `game_config_consumables` | rzeczy jednorazowego użytku |
| `game_config_enemies` | wrogowie |
| `game_items` | **ujednolicony katalog** (U11) — bronie+pancerze+przedmioty+konsumpcyjne w jednym |
| `game_config_loot_tables` / `_loot_entries` | tabele łupów i ich wpisy |
| `game_locations` | lokacje świata |
| `npcs` | postacie niezależne |
| `campaign_templates` | szablony gotowych kampanii |
| `game_config_spells`, `game_config_affixes`, `game_dungeons` | zaklęcia, afiksy, lochy |

Reszta tabel (kampanie, bohaterowie, tury) to **stan rozgrywki**, nie treść — tym
pipeline się nie zajmuje.

---

## 2. Trzy drogi wejścia treści — i kiedy której użyć

### Droga A — Seedy SQL (`data/seeds/01_*.sql … 15_*.sql`)
**Kiedy:** treść kanoniczna, bazowa, która ma być w KAŻDEJ świeżej instalacji
(podstawowe bronie, startowi wrogowie, świat startowy, szablony kampanii).

- Pliki numerowane 01–15 wczytują się **w kolejności** (zależności: bronie przed łupami itd.).
- Każdy rekord ma `created_by='seed'` (tam gdzie tabela ma taką kolumnę).
- Wzór wpisu: `INSERT OR IGNORE INTO …` — bezpieczny do ponownego uruchomienia.
- **To jest „prawda bazowa"** — jak coś ma istnieć od zera, idzie tutaj.

### Droga B — Panel admina (`/admin/` → Zawartość / Świat)
**Kiedy:** ręcznie dodajesz/edytujesz pojedynczy przedmiot, broń, wroga, lokację, NPC
— na żywej bazie, od ręki, bez deployu.

- Formularze w sekcji **Zawartość** (bronie/przedmioty/konsumpcyjne/tabele łupów)
  i **Świat** (lokacje/NPC/wrogowie/reguły).
- Jest też **🤖 Kreator AI (Smart Entry)** — opisujesz słowami czego chcesz,
  LLM wypełnia formularz, Ty zatwierdzasz. Zapis trafia od razu do bazy.
- Zapis przez admina przechodzi **walidację effect_json** (ten sam standard co seedy).

### Droga C — LLM w trakcie gry (pending → approve)
**Kiedy:** narrator (LLM) w trakcie kampanii wymyśla nową lokację/NPC, gdy nic z bazy
nie pasuje. Taka treść wchodzi jako **„oczekująca" (pending)**, nie od razu kanoniczna.

- Trafia do kolejki **Świat → Oczekujące** (lokacje: Mapa → Do zatwierdzenia).
- Ty **zatwierdzasz (approve)** → staje się stałą treścią; albo odrzucasz.
- Zasada gry (U28/U29): LLM tworzy nowe **tylko gdy brak dopasowania** w bazie —
  najpierw szuka istniejącej lokacji/NPC.

> **Reguła kciuka:** stałe i bazowe → **Droga A (seed)**. Ręczna pojedyncza zmiana
> teraz → **Droga B (admin)**. Coś co świat „dorobił" w trakcie gry → **Droga C
> (pending/approve)**.

---

## 3. Jeden standard dla wszystkich trzech dróg

Niezależnie od drogi, treść musi spełniać **ten sam standard jakości**. Pilnują tego
dwa narzędzia:

- **db_lint (U12)** — audyt **żywej bazy**. Sprawdza wiszące FK, brakujące pola,
  złe enumy/zakresy, duplikaty kluczy, niepoprawny `effect_json`. Uruchamiasz
  przyciskiem w **/admin/ → Narzędzia → DB Lint** albo w deployu.
- **seed_lint (U13)** — audyt **seedów PRZED wejściem**. Buduje świeżą bazę,
  wgrywa seedy 01–15, puszcza na nich te same checki. Łapie błąd zanim trafi
  do bazy. Uruchamia się w `deploy_dev.sh` (krok informacyjny) i ręcznie.

### Jak czytać wynik lintu
- **exit 0 / „CLEAN"** — czysto, nic do roboty.
- **exit 1 / „WARNINGS"** — ostrzeżenia = **lista zadań treści** (np. mikstura bez
  poprawnej wartości leczenia). Gra działa, ale warto dopieścić.
- **exit 2 / „ERRORS"** — realny błąd (wiszący FK, duplikat klucza, odrzucony plik
  seedu). **To trzeba naprawić** — psuje integralność.

### Format `effect_json` (najczęstsze pole, które linty sprawdzają)
Efekty przedmiotów (leczenie, mana, kondycje) zapisuje się jako JSON:
```json
{"schema_version":1,"effect_category":"consumable_immediate",
 "effects":[{"type":"heal_hp","value":"2d4+2"}]}
```
- `value` może być liczbą (`12`) albo kostką: `2d4`, `1d6`, `2d4+2`, `1d4-1`
  (modyfikator `+N`/`-N` jest dozwolony — silnik gry to obsługuje, U13).
- Dozwolone typy efektów i kategorie pilnuje walidator U10
  (`backend/app/schemas/effect_schema.json`).

---

## 4. Krok po kroku — dodanie nowego przedmiotu/wroga/NPC (Droga B, admin)

1. Wejdź na `https://aigm-dev.studio-colorbox.com/admin/` i zaloguj się.
2. **Przedmiot/broń:** lewy panel → **Zawartość** → odpowiednia zakładka →
   **➕ Nowy** (albo **🤖 Kreator AI** i opisz słowami).
3. **Wróg:** **Świat** → Wrogowie → **➕ Nowy**. Każdy wróg dostaje automatycznie
   tabelę łupów `loot_<klucz>`.
4. **Lokacja / NPC:** **Świat** → Lokacje / NPC → **➕ Nowy**.
5. Wypełnij pola — gwiazdka `*` = wymagane. Etykieta pola robi się zielona gdy OK.
6. **Zapisz**. Jeśli `effect_json` jest niepoprawny — zapis zostanie odrzucony
   z komunikatem (ten sam standard co linty).
7. Po zapisie odpal **/admin/ → Narzędzia → DB Lint** żeby potwierdzić exit 0.

---

## 5. Jak dodać treść bazową (Droga A, seed)

1. Otwórz właściwy plik w `data/seeds/` (np. `04_weapons.sql` dla broni).
2. Dopisz `INSERT OR IGNORE INTO …` wzorując się na istniejących wpisach.
3. Tabela z kolumną `created_by`? → ustaw `'seed'`.
4. Uruchom seed-lint zanim wdrożysz:
   ```bash
   docker compose -f docker-compose.dev.yml cp data/seeds backend:/tmp/seeds
   docker compose -f docker-compose.dev.yml exec -T backend \
     python scripts/lint_seeds.py --seeds-dir /tmp/seeds
   ```
   Musi być **0 ERRORS**. Warnings = lista do dopieszczenia, nie blokują.
5. Commit + `./scripts/deploy_dev.sh` (krok seed-lint odpali się automatycznie).

---

## 6. Eksport / backup treści

- **Backup całej bazy DEV:** `./scripts/backup.sh` → plik w `./backups/`.
- **Eksport samej konfiguracji treści:** `bash scripts/export_game_config.sh`
  → `data/game_config_seed.sql` (snapshot do przeniesienia/odtworzenia).
- **Import konfiguracji:** `bash scripts/seed_game_config.sh dev`
  (robi auto-backup przed importem → `./backups/imports/`, retencja 30 dni).

---

## 7. Ściąga — gdzie co jest

| Element | Ścieżka |
|---|---|
| Seedy treści | `data/seeds/01_*.sql … 15_*.sql` |
| Walidator effect_json (U10) | `backend/app/services/admin_config.py` + `app/schemas/effect_schema.json` |
| db_lint (U12) | `backend/app/services/db_lint_service.py`, endpoint `GET /api/admin/db-lint` |
| seed_lint (U13) | `backend/app/services/seed_lint_service.py`, CLI `scripts/lint_seeds.py` |
| Krok w deployu | `scripts/deploy_dev.sh` (DB Lint + Seed Lint) |
