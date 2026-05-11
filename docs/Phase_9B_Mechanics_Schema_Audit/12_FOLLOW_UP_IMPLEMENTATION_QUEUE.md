# Kolejka następcza — Phase 9B (po T01–T21)







**Cel:** Jedna lista **ustaleń z audytu** (`[04_decisions_log.md](04_decisions_log.md)`, `[06_schema_gaps.md](06_schema_gaps.md)`, `[07_extended_design_spec.md](07_extended_design_spec.md)`, `[08_open_decisions_checklist.md](08_open_decisions_checklist.md)`), które **nie są** jeszcze domknięte w kodzie — z wyłączeniem rzeczy świadomie odłożonych (np. mapa taktyczna **[S19]**).

**Zasady (2026-05-04):**

1. **Nowy frontend gry (React / Figma / [S16]) — poza zakresem tej kolejki.** Pracujemy na **istniejącym** kliencie HTML/JS i panelu admin (`frontend/`).
2. **[S20] asystent LLM** wdrażamy na **legacy adminie** (zakładki Game design / katalog), zgodnie z dopiskiem w `[07_extended_design_spec.md](07_extended_design_spec.md)` §10–11 (*„chyba że zespół zdecyduje się podpiąć asystenta wcześniej pod legacy admin”*).
3. Po każdym ukończonym ID: odhacz `[x]` w tabeli poniżej, zaktualizuj `[06_schema_gaps.md](06_schema_gaps.md)` oraz **Notatki po implementacji** w `[11_MASTER_TASK_QUEUE_AND_PROMPTS.md](11_MASTER_TASK_QUEUE_AND_PROMPTS.md)` §17 (albo osobna podsekcja przy tym pliku).

**Zależności:** kolumna *Zależność* = minimalny numer ID gotowy wcześniej (lub `—`).

---

## 1. Kolejka realizacji (T22+)


| Lp  | ID      | Gotowe | Zadanie (skrót)                                                                                                                                                                                                                                                                                                                  | Zależność | Uchwały / ślad w dokach |
| --- | ------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ----------------------- |
| 22  | **T22** | [x]    | **[S12]** Migracja `game_config_weapons`: `targeting`, `aoe_radius_m`, `magic_school`; seed; admin CRUD; `import_catalog_snapshot`; walidacja aplikacyjna (`[07` §1](07_extended_design_spec.md))                                                                                                                                | —         | [S12], `06` broń/czary  |
| 23  | **T23** | [x]    | **[S14]** Kolumna `game_config_enemies.skills_json` + zapis/odczyt; użycie w konfrontacjach / przygotowanie pod **[S1b]** (`[07` §5](07_extended_design_spec.md))                                                                                                                                                                | —         | [S14], `06` wrogowie    |
| 24  | **T24** | [x]    | **[S6]** Runtime turowy: obsługa wybranych typów z `effect_json` — min. `periodic_save`, `block_action` w pętli walki / stanie postaci (obecnie częściowo tylko przy consumables)                                                                                                                                                | T17†      | [S6], `06` warunki      |
| 25  | **T25** | [x]    | **[S13] cleanup:** migracja treści z płaskich `effect_*` wyłącznie do `effect_json`; potem migracja schematu usuwająca legacy kolumny (etapami, z dry-run). Uruchomiono `scripts/migrate_effect_columns_to_effect_json.py --apply` na `.61`, poprawiono blocker `poisoned`, potwierdzono dry-run importu i po rebuildzie backendu usunięto legacy kolumny z `game_config_items`. | T17, T18  | `06` przedmioty         |
| 26  | **T26** | [x]    | **[S7a]** Backup bazy / artefaktu przed `import_catalog_snapshot` / `import_config` + polityka retencji kopii (`[04](04_decisions_log.md)`, `[00_brief.md](00_brief.md)`). Backend tworzy snapshot przed realnym importem, zapisuje go do `backups/imports/` i stosuje retencję: `30 dni`, minimum `3` starsze, max `10` plików. | T19       | import                  |
| 27  | **T27** | [x]    | **[S18]** Centralny resolver LLM: jedna ścieżka wyboru providera/modelu/klucza dla narracji, panelu admina i testów; hierarchia Default vs Custom; dokumentacja `env`. Dodano `user_llm_settings.mode`, resolver default/custom w backendzie, poprawkę UI gracza/admina i test `test_phase9b_t27_llm_resolver.py`. | —         | [S18], `07` §12         |
| 28  | **T28** | [ ]    | **[S20]** Asystent konwersacyjny **na legacy adminie**: API (draft rekordu / JSON z opisu) → walidacja → podgląd → zapis; integracja z `game_design.js` i kolejnymi zakładkami katalogu **[S15]**                                                                                                                                | T27, T17  | [S20], `07` §10         |
| 28.5| **T28.5**| [x]   | **Mobile-first alternative frontend** (Figma v18-20): nowy klient `/front/` z CSS Grid/Flexbox, slide-up panels, dark theme (#1a1a2e, accent #c9a54a), tab-based character sheet; działa równolegle do legacy frontu                                                                                                            | —         | Figma designs           |
| 29  | **T29** | [ ]    | **Frontend gracza (legacy):** UI do **wydawania XP na cechy** (endpointy **T21**) + wyświetlanie kosztów z `GET …/xp`                                                                                                                                                                                                            | T21       | —                       |
| 30  | **T30** | [ ]    | **[S1b]** Konfrontacje / taktyka NPC: konkretne formuły w kodzie + testy; korzystanie z `skills_json` wroga po **T23** (lub częściowy zakres wcześniej)                                                                                                                                                                          | T23†      | `08` §2, `06`           |
| 31  | **T31** | [ ]    | **AC / pancerze (MVP):** jawna reguła sumowania `ac_bonus` przy wielu źródłach (`[07` §4](07_extended_design_spec.md)) — implementacja + test                                                                                                                                                                                    | —         | [S2]                    |
| 32  | **T32** | [ ]    | **W2** Tabela `campaign_story_beats` + migracja — **tylko jeśli** W1 (`gm_plan_json`) przestaje wystarczać; najpierw ADR / kryterium wejścia (`[ADR_T14_W2_story_beats_deferred.md](ADR_T14_W2_story_beats_deferred.md)`)                                                                                                        | T06, T07  | [S11b]                  |


† *Zależność miękka:* można rozpocząć prototyp równolegle, ale „DONE” dopiero po domknięciu wskazanego ID.

---

### T25 follow-up notes

- `scripts/migrate_effect_columns_to_effect_json.py` fills `game_config_items.effect_json` for heal/restore/condition effects by reusing `effect_*`. Na `.61` użyto hostowej ścieżki `data/ai_gm.db` (bind-mount do kontenera `/data/ai_gm.db`) przed rebuildem backendu.
- The migration flags rows it cannot convert (stat buffs or missing `condition_key`). W aktualnej DEV DB jedynym pominiętym rekordem był `leatherarmor`, który jako armor nie wymaga `effect_json`.
- `skills/project-memory/SKILL.md` now documents T25 with the new CLI + normalization workflow so future agents know which tools and files to touch.
### T25 status (2026-05-07)
- **Zrobiono**
- - Helper `backend/app/services/effect_json_migration.py`, CLI `scripts/migrate_effect_columns_to_effect_json.py` i test `backend/tests/test_phase9b_t25_effect_json_migration.py` pokrywają konwersję `heal_hp`, `restore_mana`, `apply/remove_condition` oraz zgodność admin/runtime po usunięciu flat columns.
- - `backend/app/services/admin_config.py`, `loot_service.py` i `combat_service.py` działają na `effect_json`, a warstwa API utrzymuje kompatybilność dla prostych legacy payloadów.
- - Na `.61` wykonano backup DB, `python3 scripts/migrate_effect_columns_to_effect_json.py --apply --db data/ai_gm.db`, poprawkę legacy warunku `poisoned` do schema v1, eksport snapshotu, `scripts/normalize_catalog_snapshot.py` oraz `admin_config_transfer.import_catalog_snapshot(..., dry_run=True)` bez błędów.
- - Po rebuildzie backendu DEV tabela `game_config_items` nie ma już kolumn `effect_type`, `effect_dice`, `effect_bonus`, `effect_target`; backend wrócił do stanu `healthy`.
- - Testy przez SSH na `.61`: `test_phase9b_t25_effect_json_migration.py`, `test_phase9b_t17_effect_json_validation.py`, `test_phase8c_loot_service.py` — zielone.
- **Otwarte drobiazgi / uwagi**
- - `test_phase9b_t18_consumables_item_key.py` nadal nie uruchamia się na hoście `.61`, bo lokalny interpreter nie ma zależności `starlette`; to problem środowiska testowego, nie samego T25.

### T27 status (2026-05-07)
- **Zrobiono**
- - `backend/app/services/llm_service.py` zwraca już efektywny default LLM z jednego miejsca (`runtime` override albo `LLM_*` z env), a `GET /api/settings/llm` pokazuje ten sam resolved stan zamiast pustego runtime cache.
- - `backend/app/services/user_llm_settings.py` i migracja `user_llm_settings.mode` rozróżniają teraz `default` vs `custom`; przy `custom` wygrywa profil użytkownika, przy `default` backend bierze konfigurację serwera/admina.
- - Front gracza (`frontend/index.html`, `frontend/js/app.js`) nie pozwala już edytować provider / URL / API key; te ustawienia są tylko w adminie, a UI gracza korzysta z rozwiązanego configu backendu.
- - Adminowy panel kont (`frontend/admin_panel/sections/accounts.js`) ma teraz blok `Global LLM` nad listą kont: aktywny preset globalny, zapis / aktywację nowych presetów, powrót do `LLM_*` z env i kasowanie nieaktywnych presetów.
- - Per-user `mode=default` nadal zachowuje zapisane pola custom w `user_llm_settings`, więc można wrócić do wcześniejszej konfiguracji bez ręcznego przepisywania.
- - Testy / CI mają jeden punkt wejścia do defaultu (`LLM_*`), a `backend/tests/test_phase9b_t27_llm_resolver.py` sprawdza fallback env, `custom` override, zachowanie customów po przełączeniu na `default` oraz globalne presety admina.
- **Weryfikacja**
- - SSH `.61`: `python3 -m pytest backend/tests/test_phase9b_t27_llm_resolver.py -q` → `4 passed`.

### T28 status (2026-05-07)
- **MVP wdrożone**
- - Backend dostał endpointy `GET /api/admin/assistant/resources`, `POST /api/admin/assistant/draft` i `POST /api/admin/assistant/save`, które używają centralnego resolvera LLM z T27 i zwracają draft + wynik walidacji przed zapisem.
- - `frontend/admin_panel/sections/game_design.js` ma nowy panel rozmowy LLM nad zakładkami Game Design: historia rozmowy, wybór katalogu, preview walidowanego JSON oraz zapis draftu do istniejącego admin API.
- - Na start asystent obsługuje create-capable katalogi z legacy admina: `skills`, `weapons`, `enemies`, `conditions`, `items`, `consumables`, `loot-tables`.
- - Test API: `backend/tests/test_phase9b_t28_admin_assistant.py` pokrywa draft + save dla warunku oraz negatywny przypadek walidacji.
- **Pozostało przed pełnym DONE**
- - Jeśli uznamy T28 za „cały Game Design”, do objęcia pozostają zakładki bez prostego create-flow (`stats`, `dc`, `archetypes`, część `npcs` / `locations` / `prompts`) albo jawna decyzja, że zakres T28 dotyczy tylko katalogów z tworzeniem rekordów.

### T28.5 status (2026-05-08)
- **DONE**
- - Utworzono `frontend/front/` z mobile-first frontendem na podstawie Figma v18-20 (14 screenów w `frontend/front/img/`).
- - `frontend/front/index.html` — pełna struktura HTML: ekrany login, campaigns, new-campaign, character-wizard, game; panel karty postaci z tabami (stats/skills/inventory); panel ustawień.
- - `frontend/front/css/styles.css` (~800 linii) — design system z CSS variables; kolory dark theme (#1a1a2e, #252542, accent #c9a54a); komponenty: buttons, cards, form fields, chat bubbles (GM green, user blue), stat rows, skill rows; animacje paneli transform: translateY; breakpointy desktop 768px i 1024px.
- - `frontend/front/js/app.js` — logika aplikacji: nawigacja ekranów, login/logout, CRUD kampanii, wizard postaci, chat messaging, toggle panelu karty postaci, panel ustawień; import konfiguracji z `../../js/config.js`, `state.js`, `utils.js`.
- - `frontend/nginx.conf` — dodano location `/front/` z aliasem do `/usr/share/nginx/html/front/`.
- - Dostępne pod `https://aigm-dev.studio-colorbox.com/front/` po rebuildzie kontenerów.

## 2. Świadomie poza tą kolejką (nie „do domknięcia teraz”)


| Temat                                                      | Powód                                                                            |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **[S19]** Mapa bitwy / solver AOE / tokeny                 | MVP bez mapy — `[07` §1.1](07_extended_design_spec.md); osobna przyszła uchwała. |
| **Nowy klient gry React + Figma [S16]**                    | Odłożony — praca na starym froncie do domknięcia backendu i legacy admina.       |
| **Profil konta gracza + własny endpoint LLM w prod [S17]** | Backlog produktowy po epiku konta — nie blokuje powyższej kolejki backendowej.   |


---

## 3. Backlog pomocniczy (po żądaniu — poza T22–T32)


| ID      | Opis                                                                                                                                                             |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **B03** | Dalsza konsolidacja `**game_config_consumables`** / FK `consumable_key` vs wyłącznie `game_config_items` — jeśli macie jeszcze stare środowiska z legacy danymi. |
| **B04** | Grant XP / mechanika MG dla użytkownika **nie będącego ownerem** kampanii (`campaign_members` / rola `gm`) — [`07` §8].                                          |
| **B05** | Widok „wszystkie rekordy bez filtra” w adminie — z **[S15]** wynika, że **nie** jest potrzebny; tylko jeśli zmienicie decyzję.                                   |


---

## 4. Mapowanie: ID → glówny dokument źródłowy


| ID  | Gdzie dyskusja / uzasadnienie                        |
| --- | ---------------------------------------------------- |
| T22 | `06` wiersz broń/czary; `07` §1; `08` [S12] accepted |
| T23 | `06` wrogowie; `07` §5; `08` [S14]                   |
| T24 | `06` warunki — typy efektów; `04` [S6]               |
| T25 | `06` przedmioty dual JSON; `04` [S13]                |
| T26 | `00_brief`, `04` [S7a]                               |
| T27 | `07` §12; `08` [S18]                                 |
| T28 | `07` §10–11; `08` [S20]; **legacy UI**               |
| T28.5 | Figma designs v18-20; mobile-first parallel frontend |
| T29 | Konsekwencja **T21** dla gracza (API już jest)       |
| T30 | `08` §2 [S1b]; `06`                                  |
| T31 | `07` §4                                              |
| T32 | `ADR_T14`; `06` W2                                   |


---

## 5. Sugerowana kolejność pracy (orientacyjna)

1. **T22** — odblokowuje spójny katalog czarów/AOE w DB i imporcie (reszta mechaniki nadal bez mapy — **[S19]**).
2. **T23** + **T30** — silnik konfrontacji zależy od skilli wroga.
3. **T24** — najbardziej „systemowe”; często po stablinym effekcie JSON.
4. **T25** — porządek danych przed długim utrzymaniem.
5. **T26** — bezpieczeństwo operacyjne przy importach na prod.
6. **T27** → **T28** — resolver przed asystentem admina wołającym LLM.
7. **T29** — UX gracza na istniejącym froncie.
8. **T31** — jeśli walka już liczy AC z kilku źródeł — wtedy pilne; inaczej można wcześniej.
9. **T32** — tylko po decyzji produktowej vs ADR.

---

## 6. Historia zmian tego pliku


| Data       | Zmiana                                                                                                                                                                                                                                                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-05-04 | Utworzenie kolejki T22–T32 + backlog B03–B05; zakres bez nowego frontu gry; [S20] na legacy adminie.                                                                                                                                                                                                                                       |
| 2026-05-05 | **T22 DONE** — dodane pola `targeting`, `aoe_radius_m`, `magic_school` w `game_config_weapons`; walidacja API/admin + legacy UI; testy `test_phase9b_t22_weapon_targeting.py`.                                                                                                                                                             |
| 2026-05-05 | **T24 DONE** — runtime warunków w walce obsługuje `periodic_save` i `block_action` na starcie tury; blokada omija LLM dla gracza i zatrzymuje atak wroga; testy `test_phase9b_t24_condition_runtime.py` + regresja `test_phase8_combat.py`; wymagany rebuild backendu DEV.                                                                 |
| 2026-05-05 | **T24 follow-up DONE** — domknięty osobny blocker baseline po T24: `game_engine.build_narrative_messages()` obsługuje testowe `conn=None` / `MagicMock()` bez wejścia w ścieżki DB, a `format_roll_result_message()` znów wspiera starsze payloady bez `modifier`; baseline i test `test_game_engine_death.py` wróciły do zielonego stanu. |
| 2026-05-08 | **T28.5 DONE** — Mobile-first alternative frontend (`frontend/front/`) based on Figma v18-20; HTML + CSS (~800 lines) + JS; nginx location `/front/`; dark theme, slide-up panels, tabbed character sheet.                                                                                                                                 |


