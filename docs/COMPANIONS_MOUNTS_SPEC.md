# FAZA TW — Towarzysze podróży i wierzchowce (spec wdrożeniowy)

**Issue bazowe:** #1192 (Towarzysz podróży — hireling / zwierzę)
**Rozszerzenie:** koń/wierzchowiec spięty ze skillem `riding` (Jeździectwo, DEX, DC 12)
**Status:** spec zatwierdzony 2026-07-18. Backend TW1–TW6 WDROŻONE+zweryfikowane; TW7/TW8 prymitywy gotowe (wiring pending); TW9/TW10-UI/TW11 do zrobienia. Statusy per zadanie w §6.
**Zakres:** PEŁNY system od razu — najemnik, tropiciel, pies (kombatanci) + koń/muł (wierzchowce, poza walką)

---

## 1. Decyzje projektowe (Piotr, 2026-07-18)

1. **Zakres v1 = pełny system**: wszystkie typy towarzyszy + wierzchowce w jednym wdrożeniu (fazowane na zadania TW1–TW11 poniżej).
2. **Nabycie konia — wszystkie ścieżki**: najem dzienny, kupno na własność w stajni, ORAZ grant narracyjny (nagroda questowa / decyzja GM / admin cheat).
3. **Koń w walce**: NIE jest kombatantem. Daje opcję ucieczki z encountera podróżnego (test `riding`). Zero zmian w rdzeniu walki dla wierzchowców.
4. **Skill `riding` daje wszystkie 4 efekty**: szybsza podróż per ranga, większy dzienny budżet marszu, test ucieczki z encountera, gate rangi na pełną prędkość (bez rangi koń idzie stępa).

Towarzysze bojowi (najemnik/pies/tropiciel) walczą po stronie gracza wg #1192 — na szablonie summonów B15.

---

## 2. Model danych

### 2.1 `game_config_companions` (katalog, content-as-code #1202)

```sql
CREATE TABLE IF NOT EXISTS game_config_companions (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('mount','hireling','animal')),
    hp_base INTEGER NOT NULL DEFAULT 10,
    attack_json TEXT,          -- NULL = nie walczy (wierzchowce); {"attack_bonus":3,"damage_dice":"1d6"}
    daily_cost INTEGER NOT NULL DEFAULT 0,   -- najem gp/dzień; 0 = nie do najęcia
    buy_cost INTEGER,          -- kupno gp; NULL = nie do kupienia
    upkeep_cost INTEGER NOT NULL DEFAULT 0,  -- pasza/utrzymanie gp/dzień dla OWNED
    passive_json TEXT,         -- patrz 2.3
    region_tags TEXT,          -- CSV; NULL = wszędzie
    description TEXT,
    note TEXT,                 -- tekst informacyjny dla GM (jak w enemies)
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT 'seed',
    created_at TEXT, updated_at TEXT
);
```

### 2.2 `character_companions` (stan per postać)

```sql
CREATE TABLE IF NOT EXISTS character_companions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    companion_key TEXT NOT NULL,
    custom_name TEXT,          -- imię nadane przez gracza (koń może mieć imię)
    current_hp INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'active'
        CHECK(state IN ('active','dead','dismissed')),
    ownership TEXT NOT NULL DEFAULT 'hired' CHECK(ownership IN ('hired','owned')),
    acquired_at TEXT NOT NULL,
    last_upkeep_day INTEGER,   -- march_day ostatniego rozliczenia
    unpaid_days INTEGER NOT NULL DEFAULT 0,
    underfed INTEGER NOT NULL DEFAULT 0  -- mount bez paszy → traci bonus szybkości
);
CREATE INDEX IF NOT EXISTS idx_char_companions_char ON character_companions(character_id, state);
```

**Sloty (egzekwowane w serwisie, nie w SQL):** naraz max **1 towarzysz bojowy** (`hireling`/`animal`) + **1 wierzchowiec** (`mount`). Próba najęcia drugiego → 409 z czytelnym komunikatem.

### 2.3 `passive_json` — słownik pasywów (wszystkie opcjonalne)

| Klucz | Typ | Kto | Efekt |
|---|---|---|---|
| `travel_speed_mult` | float | mount | bazowy mnożnik czasu marszu (koń 0.75); skalowany rangą riding, patrz §3.1 |
| `daily_cap_bonus_h` | float | mount | +h do soft/hard cap marszu (koń: +2) |
| `escape_enabled` | bool | mount | odblokowuje opcję ucieczki z encountera (§3.3) |
| `encounter_chance_mult` | float | animal | pies ostrzega — mnożnik szansy encountera (0.8) |
| `terrain_speed_mult` | obiekt | hireling | tropiciel: `{"las":0.8}` — mnożnik `travel_hours` per hex_type |
| `carry_bonus_kg` | int | mount/hireling | **v1: informacyjne** (brak systemu udźwigu — `weight_kg` istnieje tylko jako dana) |

### 2.4 Seedy startowe (Numbers Policy: wartości STARTOWE, tuning w Sandboxie)

| key | label | type | hp | attack | daily | buy | upkeep | pasywy |
|---|---|---|---|---|---|---|---|---|
| `horse` | Koń wierzchowy | mount | 20 | — | 4 | 60 | 1 | speed 0.75, cap +2h, escape |
| `mule` | Muł juczny | mount | 16 | — | 2 | 30 | 1 | speed 0.9, cap +2h, carry 60 kg |
| `dog_tracker` | Pies gończy | animal | 8 | +2 / 1d4 | 1 | 15 | 0 | encounter_chance_mult 0.8 |
| `mercenary` | Najemnik | hireling | 14 | +3 / 1d6 | 5 | — | 0 | carry 20 kg |
| `tracker` | Tropiciel | hireling | 10 | +2 / 1d4 | 4 | — | 0 | terrain las 0.8 |

Seedy `INSERT OR IGNORE`, `created_by='seed'` (konwencja + lint `seed_lint_service`).

---

## 3. Mechaniki

### 3.1 Wierzchowiec × skill `riding` (podróż)

Skill istnieje i jest w pełni podpięty: seed `migrations_admin.py:1372`, DC 12 (`:3348`), trigger keywords „wsiadam na konia, galopem, konno…" (`:4545`), testy `test_issue585_skill_seed.py`.

**Efektywny mnożnik czasu marszu konno** (gate rangi — bez rangi stępa):

| Ranga riding | Mnożnik (koń, baza 0.75) |
|---|---|
| R0 | ×0.85 (stępa — koń pomaga, ale jeździec słaby) |
| R1 | ×0.75 |
| R2 | ×0.70 |
| R3 | ×0.65 |

Implementacja: tabela `RIDING_RANK_MULT = {0: 0.85, 1: 0.75, 2: 0.70, 3: 0.65}` w nowym `companion_service.py`; dla muła bonus rangi połowiczny (baza 0.9, R3 → 0.85). Mnożnik komponuje się z pogodą/eventami dokładnie jak istniejące: `weather_service.get_march_multiplier()` (`hex_travel_service.py:837`) i event `travel_hours_multiplier()` (`:849`). Punkty wpięcia: `step_cost` w A* (`:173`), `_terrain_cost` (`:2167`), split `cost`/`budget_cost` (`:966-992`), `estimate_route_hours` (`:2146` — estymata #1405 MUSI pokazywać czas konny).

**Budżet dzienny konno:** `DAILY_SOFT_CAP 8.0 → 10.0`, `DAILY_HARD_CAP 12.0 → 14.0` (`:203-206`) — bonus `daily_cap_bonus_h` z pasywów aktywnego wierzchowca, doliczany w `_world_budget_interrupt` (`:998`).

**Underfed:** wierzchowiec `owned` bez opłaconej paszy 2+ dni → `underfed=1` → bonusy szybkości i capów wyłączone (mnożnik 1.0) do czasu nakarmienia (opłata w stajni lub upkeep przy odpoczynku). Narracyjnie: koń wychudzony.

### 3.2 Utrzymanie (day-tick)

Rozliczenie przy zmianie `march_day` (reset dzienny w `hex_travel_service.py:809-830`) oraz przy długim odpoczynku (`rest_service.py`):

- `hired`: potrąć `daily_cost` przez `economy_service.change_gold(..., "companion_upkeep", ...)` (ledger `character_gold_log`). Brak złota → `unpaid_days += 1`; przy `unpaid_days >= 2` towarzysz odchodzi (`state='dismissed'`) + komunikat w `system_events` (#1379).
- `owned` mount: potrąć `upkeep_cost` (pasza). Brak złota → `underfed` (§3.1), koń NIE odchodzi.
- `stable_night` (istniejąca usługa 3 gp, `migrations_admin.py:2092`) przy noclegu w osadzie pokrywa paszę tej nocy (nie naliczać podwójnie).

### 3.3 Ucieczka konno z encountera

Punkt wpięcia: przerwanie podróży encounterem — `out["encounter"]` / `encounter_hex` (`hex_travel_service.py:738-739`), przed startem walki.

- Warunek: aktywny wierzchowiec z `escape_enabled` i nie `underfed`.
- Gracz dostaje opcję **„Uciekaj konno"** obok normalnego wejścia w walkę (suggested action / przycisk w modalu encountera ŻAR).
- Test: `riding` (d20 + DEX_mod + ranga + proficiency) vs **DC = 10 + 2×tier wroga** (start, tuning).
- Sukces → walki nie ma, podróż trwa; encounter liczy się do cooldownu (`ENCOUNTER_DAY_COOLDOWN`, `:221`) — bez farmy „ucieczka i re-roll".
- Porażka → walka normalnie (koń czeka z boku, nie jest kombatantem).
- Nat 1 → wypadnięcie z siodła zgodnie z opisem skilla: obrażenia 1d4 + walka; narracyjna komplikacja.
- Intent tekstowy („uciekam konno", „spinam konia") — matcher przez `strip_pl_diacritics` (`app/core/text_utils`, konwencja #1420).

### 3.4 Pies — ostrzeganie przed zasadzką

`encounter_chance_mult` z pasywów aktywnego towarzysza przekazywany do `_roll_encounter(...)` (`hex_travel_service.py:267` — funkcja już przyjmuje `chance_mult`; komponować z `ROAD_ENCOUNTER_MULT :227`, `NIGHT_ENCOUNTER_MULT :206`, cap `TRIP_ENCOUNTER_CAP :220`).

### 3.5 Tropiciel — szybciej przez teren

`terrain_speed_mult` per `hex_type` mnoży `travel_hours` danego hexu w `step_cost` (`:173`) — tylko dla typów wymienionych w obiekcie.

### 3.6 Towarzysz bojowy w walce (najemnik / pies / tropiciel)

**Szablon: system summonów B15 (#821)** w `combat_service.py` — NIE budować od zera:

- Nowy `type: "companion"` w `combatants` JSON (obok `player`/`enemy`/`summon`). Kształt jak summon (`:5384-5400`): `{id, type:"companion", owner_id:"player", companion_key, name, hp_current, hp_max, defense, attack_bonus, damage_dice, conditions:[], zone, stats{}}` — bez `lifetime_remaining` (trwały).
- Wstrzyknięcie przy starcie walki: jeśli postać ma aktywnego towarzysza bojowego — jak `_resolve_summon_spell_in_combat` (`:5334`): dodać do `combatants` + `turn_order` zaraz po graczu (`:5403-5408`), persist wzorem `_b15_persist_with_turn_order` (`:5300`).
- AI tury: reuse `_b15_pick_summon_target` (`:5321`) + tor `resolve_summon_turn` — atak najsłabszego żywego wroga, preferencja własnej strefy. Zone start: pies/najemnik → engaged, tropiciel → ranged (analogia heurystyki `_default_zone_for_enemy`).
- Wrogowie MOGĄ atakować towarzysza (wchodzi do puli celów AI wroga — sprawdzić targeting `:5870-5877`).
- Po walce: sync `hp_current` → `character_companions.current_hp`. HP regeneruje przy długim odpoczynku (pełne, jak postać — start).
- **Śmierć = permanentna**: `state='dead'`, wpis w `system_events` + narracja. Bez wskrzeszania (decyzja #1192). Rekord zostaje (historia).
- Wierzchowce (`type='mount'` w katalogu) NIGDY nie wchodzą do `combatants`.

### 3.7 Grant narracyjny

`companion_service.grant_companion(character_id, companion_key, ownership='owned', source='gm')` — wywoływalne z:
- admin cheat (`routers/admin_cheat.py`) — nowy endpoint/akcja „przyznaj towarzysza",
- przyszłe hooki questowe/loot (fundament — sama funkcja + ledger w `system_events`).
Respektuje limity slotów (grant przy zajętym slocie → wymiana za zgodą / 409 w cheatcie).

---

## 4. Endpointy

### Gracz (`app/api/companions.py`, rejestracja w `main.py`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/api/characters/{id}/companions` | aktywni towarzysze (mount + bojowy) + stan |
| GET | `/api/locations/{loc_id}/companions` | dostępni w tej osadzie (filtr `region_tags`, typ wg lokacji: stajnia → mounty, karczma → hirelingi) |
| POST | `/api/characters/{id}/companions/hire` | `{companion_key}` — najem (slot check, 1. dzień płatny z góry) |
| POST | `/api/characters/{id}/companions/buy` | `{companion_key, custom_name?}` — kupno (tylko `buy_cost` NOT NULL) |
| POST | `/api/characters/{id}/companions/dismiss` | `{companion_id}` — zwolnienie/sprzedaż? (v1: zwolnienie bez zwrotu; odsprzedaż = v2) |

### Admin

- CRUD `game_config_companions` wzorem enemies (`routers/admin` lub nowy moduł).
- Smart Entry: rejestracja tabeli w `smart_entry.py:72` + schema-dict wzorem `game_config_enemies` (`:316-364`) — Kreator AI generuje towarzyszy.
- Cheat: grant/heal/kill towarzysza.
- Monitor kampanii: sekcja „Towarzysze" (kto, HP, stan) w zakładce Przegląd.

### Dostępność w osadzie

Reuse mechanizmu usług: `location_services.py` — stajnia wykrywana już przez `_STABLE_KEYWORDS` (`:29,45-46`), `stable_night` auto w noclegach (`:81-83`). Rekrutacja: suggested action `OPEN_COMPANIONS:{loc_key}` analogicznie do `OPEN_SERVICES` (`suggested_actions.py:283-290`) — emitowana gdy lokacja ma stajnię (mounty) lub karczmę/tawernę (hirelingi).

---

## 5. Frontend ŻAR (`frontend/front-v2/`)

Build na `.61` (`sudo npm run build`), dist gitignored. `frontend/front/` ZAMROŻONY — nie dotykać.

1. **Karta towarzyszy** w arkuszu postaci (`src/components/sheet/`): mount + bojowy, HP bar, stan (underfed/unpaid warning), przycisk zwolnij, imię.
2. **Chip w pasku inicjatywy** (`src/components/game/`): towarzysz bojowy jak inne combatanty, glyph 🐺/🗡 + strefa.
3. **Modal stajni/rekrutacji**: z suggested action `OPEN_COMPANIONS` — lista dostępnych, koszt najmu/kupna, przyciski. Wzór: istniejący modal usług.
4. **Encounter: przycisk „Uciekaj konno"** obok wejścia w walkę (widoczny tylko z aktywnym koniem). Wynik testu → popup kości (wzór `skill_test_pending` → `Dice3DOverlay`, #1299).
5. **Estymata podróży** pokazuje czas konny + info o rozszerzonym budżecie (GOTCHA: typ `TravelNotice` w `useGameData.ts`, #1405).
6. Suggested actions ulotne → dociągać GETem (konwencja front-v2).

Ledger: wpis F-NN w `frontend_design.md` §7.

---

## 6. Zadania wdrożeniowe TW1–TW11

**Statusy (2026-07-18):**
| Zadanie | Status | Uwagi |
|---|---|---|
| TW1 DB+seedy | ✅ WDROŻONE | `_ensure_companions_schema`, 5 seedów, migracja w live DB |
| TW2 serwis | ✅ WDROŻONE | `companion_service.py`, 26 pytest zielonych |
| TW3 upkeep | ✅ WDROŻONE | wpięte w day-tick `hex_travel_service` |
| TW4 endpointy | ✅ WDROŻONE | `api/companions.py`, live smoke buy/list/dismiss OK |
| TW5 podróż konna | ✅ WDROŻONE | mult+cap wpięte w `hex_travel_service` |
| TW6 pies encounter | ✅ WDROŻONE | `_companion_enc_mult` w `_step_mult` |
| TW7 ucieczka | 🟡 PRYMITYW | `resolve_mount_escape`/`can_escape_mounted` gotowe+testowane; brak wpięcia w flow encountera (turns.py) + przycisk ŻAR |
| TW8 walka | ✅ WDROŻONE | towarzysz wstrzykiwany na starcie walki; tura rozwiązywana SERWEROWO w `_advance_turn_impl` (auto-atak, current_turn nigdy nie zatrzyma się na `companion_*` → front się nie zawiesi); HP sync + śmierć permanentna na końcu walki; 3 testy flow + regresja summonów/advance zielona. Enemy-targets-companion (koń może zginąć od AoE) = follow-up |
| TW9 frontend ŻAR | ⬜ TODO | build+visual verify |
| TW10 admin | 🟡 CZĘŚĆ | Smart Entry schema ✅ (`smart_entry.py`); brak zakładki Świat→Towarzysze + monitor + cheat |
| TW11 Księga | ⬜ TODO | rozdział wg checklisty #868 |


Kolejność = zależności. Jedno zadanie = jedna sesja agenta (konwencja FAZA-U). Testy: TYLKO pliki zadania (nigdy pełna suita). TDD: docker cp → pytest w kontenerze (`ai-gm-dev-backend-1`, testy w `/app/tests/`).

### TW1 — DB + seedy + lint
**Cel:** tabele §2.1–2.2, seedy §2.4, rejestracja w seed-lincie i snapshot content-as-code.
**Dla agenta:** migracje w `migrations_admin.py` (`_ensure_game_config_companions` wzorem `_ensure_game_config_services :4297`); seedy `INSERT OR IGNORE`, `created_by='seed'`; sprawdzić `scripts/content_seed_lib.py` (GOTCHA #1382: nowa tabela/kolumna bez re-snapshotu = wyzerowana po deployu — dodać do snapshotu). GOTCHA #1377: boot-migracje nie mogą clobberować rekordów `created_by != 'seed'`.
**Weryfikacja:** pytest `test_tw1_companions_schema.py` (tabele, seedy, XOR attack_json dla mountów NULL); `lint_seeds.py` czysty.

### TW2 — `companion_service.py` (najem/kupno/zwolnienie/grant + sloty)
**Cel:** pełne API serwisowe: `hire`, `buy`, `dismiss`, `grant_companion`, `get_active_companions`, limity slotów (1 bojowy + 1 mount), płatności przez `economy_service.change_gold`.
**Weryfikacja:** pytest — najem, kupno, slot 409, grant, ledger złota.

### TW3 — utrzymanie dzienne (day-tick + odpoczynek)
**Cel:** §3.2 — potrącanie przy zmianie `march_day` i długim odpoczynku; `unpaid_days`→odejście; `underfed`.
**Dla agenta:** hook w reset dzienny `hex_travel_service.py:809-830` + `rest_service.py`; komunikaty `system_events`; integracja `stable_night`.
**Weryfikacja:** pytest — 2 dni bez złota → hired odchodzi; owned koń → underfed; stable_night nie dubluje paszy.

### TW4 — endpointy gracza + rekrutacja w lokacji
**Cel:** §4 endpointy + `OPEN_COMPANIONS` suggested action + filtr dostępności (stajnia→mount, karczma→hireling, `region_tags`).
**Weryfikacja:** pytest — lista w osadzie ze stajnią vs dziki hex; hire przez endpoint end-to-end.

### TW5 — podróż konna (mnożnik + budżet + estymata)
**Cel:** §3.1 — `RIDING_RANK_MULT`, cap +2h, underfed wyłącza bonusy; §3.5 tropiciel; estymata #1405 uwzględnia konia.
**Dla agenta:** punkty wpięcia `hex_travel_service.py:173/:966-992/:998/:2146/:2167`; komponować z mult pogody/eventów, NIE nadpisywać. Uwaga na split `cost` vs `budget_cost`.
**Weryfikacja:** pytest — czas trasy konno R0/R1/R3 vs pieszo; soft cap 10h konno; underfed → 1.0; tropiciel las.

### TW6 — pies: szansa encountera
**Cel:** §3.4 — `encounter_chance_mult` w `_roll_encounter`.
**Weryfikacja:** pytest — statystyczny/deterministyczny test mnożnika (seed RNG), komponowanie z road/night, cap 0.35 trzyma.

### TW7 — ucieczka konno
**Cel:** §3.3 — opcja ucieczki przy encounterze, test riding DC 10+2×tier, nat 1, cooldown bez re-rollu, intent tekstowy z diakrytykami.
**Weryfikacja:** pytest — sukces omija walkę, porażka startuje walkę, nat 1 zadaje 1d4, encounter liczy się do cooldownu.

### TW8 — towarzysz bojowy w walce
**Cel:** §3.6 — type `companion` na szablonie B15, wstrzyknięcie na starcie walki, AI tury, targeting wrogów, sync HP po walce, śmierć permanentna.
**Dla agenta:** `combat_service.py:5334/:5384-5400/:5321/:5300/:5403-5408`; NIE ruszać mechanik obrony #826; multiplayer-zgodność: strona = `type`, bez założeń „1 gracz".
**Weryfikacja:** pytest — towarzysz w turn_order po graczu, atakuje najsłabszego, ginie i `state='dead'`, HP sync, mount nie wchodzi do walki.

### TW9 — frontend ŻAR
**Cel:** §5 pkt 1–6.
**Dla agenta:** build na `.61`; weryfikacja wizualna na `https://aigm-dev.studio-colorbox.com/`; ledger `frontend_design.md`.
**Weryfikacja:** Playwright spec (rekrutacja w osadzie, karta towarzysza, chip inicjatywy) + screenshoty.

### TW10 — admin (katalog + Smart Entry + monitor + cheat)
**Cel:** zakładka Świat → Towarzysze; Smart Entry schema; monitor kampanii; cheat grant.
**Dla agenta:** wzór enemies; `smart_entry.py:72/:316-364`; ledger `manual.js` (zakładka 🧭 Instrukcja — nazwy przycisków 1:1).
**Weryfikacja:** Kreator AI generuje poprawnego towarzysza; CRUD działa; cheat grant widoczny u gracza.

### TW11 — Księga Zasad + smoke
**Cel:** rozdział „Towarzysze i wierzchowce" w `frontend/front/rules/index.html` (TOC, glossy, przykład testu riding — Księga OPISUJE, nie definiuje); smoke playtest (kupno konia → podróż konna → encounter → ucieczka → najem psa → walka → śmierć/przeżycie).
**Weryfikacja:** checklist Księgi (#868); smoke report na issue.

**Opcjonalnie TW12** (niski priorytet): Sandbox — dodanie towarzysza do setupu walki (`routers/sandbox.py`, `/admin2/`) do tuningu liczb.

---

## 7. Numbers Policy

WSZYSTKIE liczby w tym dokumencie (koszty, HP, mnożniki, DC, capy, progi unpaid/underfed) to **wartości startowe**. Tuning: Sandbox (TW12) + smoke. Stałe trzymać w jednym miejscu (`companion_service.py` na górze), nie rozsiane po kodzie.

## 8. Out of scope (v2+)

- Levelowanie/rozwój towarzysza, lojalność/relacje (#1192 out of scope).
- Więcej niż 1+1 slotów.
- Walka konna (mounted combat: szarże, walka z siodła).
- System udźwigu/encumbrance (carry_bonus_kg zostaje informacyjne).
- Odsprzedaż konia, kradzież konia przez wrogów.
- Towarzysze w multiplayerze (kod TW8 pisać multiplayer-zgodnie, ale MP-testy poza zakresem).

## 9. GOTCHA dla agenta wdrażającego (z pamięci projektu)

- Backend zapieczony w obrazie: `docker cp` do TDD, `--build` przy deployu.
- Testy edytować NA `.61` (sshfs staleness), git przez `ssh claude@.61 sudo -u piotrszmidt git ...`.
- `campaign_turns.user_text` NOT NULL.
- Restore/many potrafi clobberować `sheet_json` po grancie (#1368) — uważać przy zapisach arkusza.
- Matchery tekstu gracza ZAWSZE przez `strip_pl_diacritics` (#1420).
- Zagnieżdżony `_conn` w transakcji = database-is-locked (#1390) — commit przed grantem.
- Każde zadanie: issue implementacyjne wg szablonu #18, komentarz fix+SHA, label `needs-testing`.
