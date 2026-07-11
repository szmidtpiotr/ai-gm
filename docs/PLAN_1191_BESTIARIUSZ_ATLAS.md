# PLAN #1191 — Bestiariusz i Atlas Kresów (kolekcje odkryć)

> Issue: https://github.com/szmidtpiotr/ai-gm/issues/1191
> Status: plan zatwierdzony 2026-07-11, implementacja etapami E1–E6.
> Każdy etap = jedna sesja agenta: implementacja → testy → commit+push (develop) → komentarz na #1191 → STOP.

## Decyzje projektowe (Piotr, 2026-07-11)

1. **Wiedza łowcy — progresja dwuprogowa** (nie „jedna z dwóch"):
   - **5 zabójstw** danego typu → podgląd HP wroga w walce (informacyjny),
   - **15 zabójstw** → dodatkowo **+1 do trafienia** na ten typ (mechaniczny, wzór proficiency).
2. **Pełny zakres**: Bestiariusz + Atlas + **system plotek** (budowany od zera).
3. **UI**: panel karty postaci w ŻAR (`SHEET_TABS`), NIE zakładka poziomu gry. Jedna zakładka **„Kolekcje"** z wewnętrznym przełącznikiem Bestiariusz / Atlas (rail i mobilny tabbar są już ciasne — 7 zakładek).
4. **Portrety**: batch-gen brakujących w ramach zadania istniejącym `scripts/generate_portraits_batch.py` (FLUX na .170:8765 — wymaga włączonego desktopa Piotra).

## Numbers Policy (wartości startowe, tuning w Sandboxie)

| Parametr | Start | Uwagi |
|---|---|---|
| Próg wpisu podstawowego | 1 zabójstwo | nazwa + opis + portret |
| Próg podglądu HP (tier 2) | 5 zabójstw | |
| Próg +1 do trafienia (tier 3) | 15 zabójstw | wpis do Księgi Zasad |
| Wielkość bonusu | +1 | stała, nie skaluje się |
| Kredyt za zabójstwo w MP | **wszyscy uczestnicy walki** | decyzja Piotra 2026-07-11 (wspólne trofeum); helper `_credit_bestiary_kill` |
| DC plotki (quest_rumor) | 8 (istniejące) | bez zmian |

## Architektura — fakty z rekonesansu (nie odkrywaj ponownie)

- **Kill hook**: `combat_service.py` — dwa zduplikowane bloki śmierci wroga: `if dead:` @ ~6932 (single-target, `_resolve_player_attack_turn`) oraz @ ~2762 (AOE). Oba mają `enemy.get("enemy_key")` i id postaci. **MP i lochy idą przez te same bloki** (`multiplayer_round_service` deleguje do `combat_service.initiate_combat_mp`; dungeon też) — dwa hooki pokrywają wszystko.
- **Wzór bonusu do trafienia**: proficiency doliczane @ ~8424-8430 (opposed check) i w reakcjach @ ~1181, ~1284; import z `app.core.mechanics` @ linia 20.
- **Odkrycia heksów są PER-KAMPANIA**: `campaign_hex_data.discovered` (migrations_admin.py @ ~3627, UNIQUE campaign_id+hex_q+hex_r). Zapisy rozproszone w ~6 miejscach (`hex_travel_service` ×3, `combat_service` ×2, `map_reveal_service.reveal_hexes`). **Dlatego Atlas = agregacja on-read**, NIE nowa tabela write-through.
- **Wzorzec cross-campaign per bohater = Hero Chronicle (#1096)**: `character_campaign_history` (character_id, campaign_id, …) + `GET /api/characters/{id}/chronicle` w `api/characters.py` @ ~1200. Kampanie bohatera = `characters.campaign_id` (bieżąca) ∪ `character_campaign_history.campaign_id` (przeszłe).
- **Plotki dziś**: `social_encounter_service.py` @ 56 — `quest_rumor` (CHA/gossip/DC 8, kind soft, pula tavern). Czysto narracyjne, **zero persystencji**.
- **Portrety**: `game_config_enemies.image_url` już istnieje (`_ensure_portrait_columns` @ ~5026), pipeline `routers/admin_images.py` → FLUX .170:8765, batch: `scripts/generate_portraits_batch.py --entity enemy`.
- **Endpointy per-character**: `backend/app/api/characters.py`, rejestracja w main.py @ ~845 z prefiksem `/api`.
- **ŻAR** (`frontend/front-v2/`): zakładki karty = `src/components/sheet/tabs.ts` (`SHEET_TABS` @ 27) + union `GameTab` w `src/store/appStore.ts` @ 59 + dispatch w `CharacterSheet.tsx` @ 40. Rail (`GameRail.tsx:16`) i tabbar (`TabBar.tsx:25`) podłączają się automatycznie. Wzór panelu-kolekcji: `PanelInventory.tsx` (grid, modal szczegółów, `<img src={image_url}>` z fallbackiem). Hooki fetch: `hooks/useSheetData.ts` (wzór `useSpellCatalog` ze `staleTime`). Build: `sudo npm run build` w `frontend/front-v2` na .61, dist bind-mounted (bez restartu kontenera).

## Schemat DB (E1, E4)

```sql
-- E1: migrations_admin.py
CREATE TABLE IF NOT EXISTS character_bestiary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    enemy_key TEXT NOT NULL,
    kills INTEGER NOT NULL DEFAULT 0,
    first_kill_at TEXT,          -- ISO UTC
    last_kill_at TEXT,
    unlocked_tier INTEGER NOT NULL DEFAULT 0,  -- 0 none, 1 wpis, 2 HP, 3 +1
    UNIQUE(character_id, enemy_key)
);
CREATE INDEX IF NOT EXISTS idx_bestiary_char ON character_bestiary(character_id);

-- E1: kolumna lore (opcjonalna treść; fallback = description)
ALTER TABLE game_config_enemies ADD COLUMN lore_text TEXT;  -- idempotentnie, wzór _ensure_portrait_columns

-- E4: plotki
CREATE TABLE IF NOT EXISTS character_rumors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    rumor_text TEXT NOT NULL,
    target_type TEXT,            -- 'location' | 'hex' | 'enemy' | NULL (czysty klimat)
    target_key TEXT,             -- location_key / "q,r" / enemy_key
    status TEXT NOT NULL DEFAULT 'heard',   -- 'heard' | 'confirmed'
    heard_at TEXT NOT NULL,
    confirmed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_rumors_char ON character_rumors(character_id, status);
```

Progi tierów jako stałe modułowe w `bestiary_service.py` (`BESTIARY_TIER_KILLS = {1: 1, 2: 5, 3: 15}`) — Sandbox-tunable, jak `MARGIN_DAMAGE_STEP`.

---

## E1 — DB + bestiary_service + kill hooki + pytest

**Cel**: liczniki zabójstw per (bohater, typ wroga) rosną z każdej ścieżki walki; tier wyliczany automatycznie.

**Dla agenta**:
1. Migracja w `migrations_admin.py`: tabela `character_bestiary` + idempotentne `lore_text` na `game_config_enemies` (wzór `_ensure_portrait_columns`).
2. Nowy `backend/app/services/bestiary_service.py`:
   - `record_kill(character_id, enemy_key, conn=None)` — UPSERT, inkrement `kills`, przelicz `unlocked_tier`, ustaw `first_kill_at`/`last_kill_at`. Zwraca `{kills, unlocked_tier, tier_up: bool}`.
   - `get_entry_tier(character_id, enemy_key) -> int` — tani lookup pod walkę.
   - `get_bestiary(character_id)` — patrz E3.
   - Odporność: brak `enemy_key`/pusty → no-op (nie wywalaj tury walki); całość w try/except z logiem, licznik NIE może położyć resolve_attack.
3. Hooki w `combat_service.py`: w OBU blokach śmierci (`if dead:` single @ ~6932 i AOE @ ~2762) wywołaj `bestiary_service.record_kill(...)`. Id postaci = zabójca (w MP: postać, której atak zabił — jest w kontekście bloku). `tier_up` dorzuć do combat log/eventu (np. event `bestiary_tier_up`), żeby ŻAR mógł kiedyś pokazać toast — bez UI w tym etapie.
4. pytest `backend/tests/test_bestiary_service.py`: inkrement, UNIQUE-upsert, progi 1/5/15, tier_up flaga, no-op przy braku klucza, MP-kredyt dla zabójcy. Uruchamiaj przez docker cp + `pytest tests/test_bestiary_service.py -v` (NIE pełna suita).

**Weryfikacja**: pytest zielony; smoke — zabij wroga w kampanii Demo (user 1, [TEST] hero) i sprawdź wiersz w `character_bestiary` przez `docker exec … sqlite3`.

## E2 — Wiedza łowcy w walce + Księga Zasad

**Cel**: tier 2 → gracz widzi HP znanego wroga; tier 3 → +1 do trafienia na ten typ.

**Dla agenta**:
1. **Podgląd HP (tier ≥2)**: znajdź serializację stanu walki do gracza (payload z combatants; grep `hp_current` w odpowiedziach combat/turn). Dodaj per-combatant-wróg flagę `hp_visible: true` gdy `get_entry_tier(...) >= 2`. Gdy false — HP wroga jak dotąd (ukryte/opisowe). Tiery pobierz RAZ na serializację (jedno zapytanie na listę enemy_keys, nie per wróg).
2. **+1 do trafienia (tier ≥3)**: w ścieżce ataku gracza w `combat_service.py` dolicz `hunter_bonus = 1` do modyfikatora trafienia gdy tier celu ≥3 (wzór doliczania proficiency @ ~8424; sprawdź też reakcje @ ~1181/~1284 — bonus dotyczy ATAKU gracza, nie obrony; reakcji NIE dotykaj). Bonus widoczny w breakdownie rzutu (tam gdzie proficiency), żeby gracz widział skąd +1.
3. Cache tieru per walka (np. w combatants JSON przy starcie walki lub prosty lookup — decyzja agenta; uwaga: tier może wzrosnąć W TRAKCIE walki po zabiciu 5./15. sztuki — akceptowalne, że bonus zadziała od następnej walki LUB od następnego ataku, wybierz prostsze i zapisz w issue).
4. **Księga Zasad** (`frontend/front/rules/index.html`, `/rules/`): rozdział/sekcja „Wiedza łowcy" — progi 1/5/15, co dają, przykład; gloss tooltip + TOC + kotwica. To zmiana player-facing rules — obowiązkowe w tym samym PR.
5. pytest: atak na wroga tier 3 ma +1 w breakdownie; tier <3 nie ma; hp_visible poprawnie flagowane.

**Weryfikacja**: pytest zielony; Sandbox (`/admin2/` → ⚔ Sandbox) — ustaw klonowi licznik w DB na 15, sprawdź +1 w raporcie rzutu.

## E3 — Endpointy: bestiariusz + atlas (agregacja)

**Cel**: `GET /api/characters/{id}/bestiary` i `GET /api/characters/{id}/atlas`.

**Dla agenta**:
1. W `backend/app/api/characters.py` (wzór `/chronicle` @ ~1200, auth jak sąsiednie endpointy — właściciel postaci lub admin):
   - **`/bestiary`**: pełny katalog `game_config_enemies` × `character_bestiary` bohatera. Wpis odblokowany (kills ≥1): `{enemy_key, name, description, lore_text, image_url, kills, unlocked_tier, first_kill_at}` + przy tier ≥2 podstawowe staty (hp_max), tier 3 = pełny wpis. Wpis zamknięty: **tylko** `{enemy_key: null, locked: true}` — bez nazwy, bez klucza (frontend rysuje „???"; nie wyciekaj treści w JSON). Dodaj `summary: {unlocked, total, pct}`.
   - **`/atlas`**: agregacja on-read po kampaniach bohatera (`characters.campaign_id` ∪ `character_campaign_history.campaign_id`): liczba+lista odkrytych heksów (`campaign_hex_data.discovered=1`, dedup po q,r, tylko map_level=0), odkryte lokacje (analogiczna tabela lokacji per kampania — znajdź jak `/chronicle` liczy lokacje albo grep `locations` z campaign_id), plotki (E4: `character_rumors` heard/confirmed), rozbicie per `world_hexes.region` (FAZA RM). Zwróć `summary` z procentami względem całej mapy (COUNT world_hexes map_level=0).
2. Wydajność: pojedyncze zapytania z JOIN/IN, bez pętli po kampaniach.
3. pytest: locked-wpis nie wycieka nazwy; agregacja liczy heksy z dwóch kampanii tego samego bohatera raz (dedup q,r); postać bez historii → puste sumy, nie 500.

**Weryfikacja**: pytest zielony; `curl` oba endpointy na Demo bohaterze — sensowny JSON.

## E4 — System plotek (od zera)

**Cel**: udany `quest_rumor` zostawia trwały ślad; odkrycie celu potwierdza plotkę.

**Dla agenta**:
1. Migracja `character_rumors` (schemat wyżej).
2. Nowy `backend/app/services/rumor_service.py`:
   - `create_rumor(character_id, campaign_id)` — wołane przy SUKCESIE encountera `quest_rumor` (znajdź rozstrzygnięcie w `social_encounter_service.py` / `turn_pipeline.py`). **Target deterministycznie, nie z tagu LLM** (lekcja #1294): wylosuj z puli = nieodkryte `key_locations` planu GM ∪ nieodkryte heksy z lokacją w promieniu N od pozycji ∪ typy wrogów z `encounter_pool` bieżącego regionu. Tekst plotki = krótki szablon PL z nazwą celu (np. „W tawernie mówią, że w {label} grasuje {enemy}…"); tekst dołóż do kontekstu narratora tej tury, żeby narracja się zgadzała.
   - `confirm_rumors_for(character_id, target_type, target_key)` — hooki: przy odkryciu heksa/lokacji (najlepiej JEDNO miejsce: `map_reveal_service.reveal_hexes` + wejście do lokacji) i przy pierwszym zabójstwie typu (z `bestiary_service.record_kill`). Ustawia `status='confirmed'` + `confirmed_at`.
   - Dedup: nie twórz drugiej otwartej plotki na ten sam target dla tej postaci.
3. Dopięcie do `/atlas` (E3): sekcja `rumors: {heard, confirmed, entries:[…]}`.
4. pytest: sukces quest_rumor tworzy wiersz z targetem z puli; odkrycie targetu potwierdza; dedup; fail encountera nie tworzy nic.

**Weryfikacja**: pytest zielony; smoke turą w tawernie na Demo (realny LLM, nie stub) — plotka w DB, narracja ją wspomina.

## E5 — ŻAR: panel „Kolekcje"

**Cel**: zakładka Kolekcje w karcie postaci — Bestiariusz (grid kart, zamknięte jako „???") + Atlas (staty eksploracji).

**Dla agenta** (wszystko w `frontend/front-v2/`, stary front zamrożony):
1. `store/appStore.ts:59` — dodaj `"collections"` do union `GameTab`.
2. `components/sheet/tabs.ts:27` — wpis w `SHEET_TABS` (label „Kolekcje", ikona Phosphor np. `BookBookmark`). Rail + tabbar podłączą się same.
3. `components/sheet/CharacterSheet.tsx:40` — gałąź `collections` → nowy `PanelCollections.tsx` z wewnętrznym przełącznikiem (segmented control) **Bestiariusz | Atlas**.
4. `PanelBestiary` (w pliku PanelCollections lub osobno, wzór `PanelInventory.tsx`):
   - grid kart: portret (`<img src={image_url}>`, fallback ikona), nazwa, kills, pasek progresu do następnego progu (x/5, x/15), badge tieru (📖 / 👁 HP / ⚔ +1);
   - zamknięte: karta-sylwetka „???" (ciemna, bez treści);
   - klik → modal szczegółów (opis, lore_text, przy tier≥2 hp_max; wzór `ItemDetailModal`);
   - nagłówek: `unlocked/total` + %.
5. `PanelAtlas`: kafle statystyk (heksy odkryte x/y + %, lokacje, plotki heard/confirmed), rozbicie per region, lista potwierdzonych plotek. Bez mapy — same agregaty (mapa jest w zakładce Mapa).
6. Hooki w `hooks/useSheetData.ts`: `useBestiary(characterId)`, `useAtlas(characterId)` — wzór `useInventory`, `enabled` gdy panel aktywny, `staleTime` ~60s. Invalidacja `["bestiary"]` po zakończonej walce (znajdź gdzie invaliduje się inventory/sheet po walce i dołóż).
7. Styl: tokeny ŻAR (świat ciepły / mechanika stalowa — `frontend_design.md` §6). **Ledger**: nowy wpis `F-NN` w `frontend_design.md` (Sekcja 7).
8. Build na .61: `cd /home/piotrszmidt/ai-gm/frontend/front-v2 && sudo npm run build` (dist bind-mounted, bez restartu).

**Weryfikacja**: `https://aigm-dev.studio-colorbox.com/graj/` — zakładka widoczna desktop+mobile, „???" dla nieznanych, wpis odblokowany po walce, konsola czysta. Playwright spec w `ai_test_agent/playwright/` (bind-mounted, auto-listing): otwarcie zakładki + asercja kart.

## E6 — Portrety, lore, smoke, domknięcie

**Cel**: treść uzupełniona, całość zweryfikowana, issue udokumentowane.

**Dla agenta**:
1. **Portrety**: sprawdź ilu wrogom brakuje `image_url`; upewnij się z Piotrem, że FLUX na .170:8765 działa (desktop musi być włączony); `python3 scripts/generate_portraits_batch.py --entity enemy` na .61. Raportuj ile wygenerowano/pominięto.
2. **lore_text**: backfill skryptem przez content-LLM (profil `content_llm_profile` = gpt-5.4, NIE gemma) — 2-4 zdania klimatu per wróg, zapis do `game_config_enemies.lore_text`; wrogowie bez lore → frontend pokazuje `description` (fallback już w E5). Sprawdź, że Smart Entry schema (`GET /api/admin/smart-entry/schema?table=game_config_enemies`) widzi nową kolumnę.
3. **Smoke E2E**: `/game-test-player #1191` — kilka walk z tym samym typem wroga, sprawdź: licznik rośnie, wpis odblokowany w UI, (DB-cheat kills→5) HP widoczne, (kills→15) +1 w rzucie, plotka z tawerny → potwierdzenie po odkryciu.
4. **Issue #1191**: komentarz-raport wg szablonu implementation record (sekcje What/Files/Backend/Numbers/Acceptance), SHA wszystkich etapów, label `needs-testing` + `review` (feature player-facing → wizualna kolejka Piotra). NIE zamykaj — zamyka Piotr po weryfikacji wizualnej.

**Weryfikacja**: checklist acceptance z issue odhaczona; screenshot zakładki Kolekcje w komentarzu.

---

## Zależności między etapami

E1 → E2, E3; E3 → E4 (sekcja rumors w atlas), E5; E4 → E5 (panel Atlas pokazuje plotki — może wejść z pustą listą jeśli E4 później); E6 ostatni. Dopuszczalna kolejność: E1, E2, E3, E4, E5, E6.

## Ryzyka / pułapki

- **Backend baked into image** — zmiany Pythona wymagają `docker compose -f docker-compose.dev.yml up -d --build backend` na .61 (albo docker cp w pętli TDD). Nigdy pełna suita pytest.
- **Nie ruszać locked mechanics** poza zatwierdzonym +1 (decyzja Piotra 2026-07-11 w tym planie).
- **MP**: kredyt zabójstwa tylko dla zabójcy (Numbers Policy) — nie iterować po całej drużynie.
- **record_kill nie może położyć walki** — twardy try/except, log, jedziemy dalej.
- **Locked wpisy nie wyciekają w JSON** — „???" to brak danych po stronie API, nie CSS.
- **world_hexes (map_level=0) = własność Piotra** — Atlas tylko CZYTA, żadnych zapisów do world_hexes.
- **Plotki: target deterministyczny** z zamkniętej puli — nie parsować tagów LLM (#1294).
- **FLUX .170** dostępny tylko gdy desktop Piotra włączony — E6 pkt 1 wymaga potwierdzenia.
- **JS cache**: przy zmianie shared modułów ŻAR build i tak hashuje bundle; stary front nie jest dotykany.

## Prompt startowy (per sesja agenta)

```
Pracuj nad #1191 (Bestiariusz i Atlas Kresów) wg planu docs/PLAN_1191_BESTIARIUSZ_ATLAS.md.
Wykonaj DOKŁADNIE JEDEN etap: E<N> (pierwszy nieukończony wg komentarzy na issue #1191).
Zasady: sekcja „Dla agenta" etapu = zakres; „Ryzyka/pułapki" obowiązują; testy tylko targetowane
(nigdy pełna suita); commit+push na develop z referencją #1191; po zakończeniu komentarz na
#1191 (etap, SHA, wynik testów, co zweryfikowano) i STOP + raport po polsku prostym językiem.
Nie zaczynaj kolejnego etapu.
```
