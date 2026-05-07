# Luki i nadmiary w schemacie — przedmioty, umiejętności, czary

**Status:** **T11 (2026-05-04)** — wiersze poniżej **zsynchronizowane** z repozytorium (`migrations_admin.py` + wyszukiwanie w `backend/`). Nierozwiązane pozycje są **jawnie** oznaczone jako otwarte; plan domknięcia: [`12_FOLLOW_UP_IMPLEMENTATION_QUEUE.md`](12_FOLLOW_UP_IMPLEMENTATION_QUEUE.md) (**T22+**). Uchwały: [`04_decisions_log.md`](04_decisions_log.md) sekcja **[AUDIT]** (zamknięta). Źródła historyczne: [`01_schema_inventory.md`](01_schema_inventory.md), [`02_code_usage_matrix.md`](02_code_usage_matrix.md). **Projekt pod przegląd:** [`07_extended_design_spec.md`](07_extended_design_spec.md); **[S12]–[S20]**. **Zasada [S6] §2:** stany złożone w **parametrycznym JSON**; unikać kolumny SQL na każdy wariant.

## Cel

Wypisać:

- **Braki:** czego **nie da się** zapisać w bazie przy planowanych mechanikach.
- **Nadmiary:** które kolumny są **nieużywane** albo tylko „opis bez liczenia”.

## Tabela — stan po weryfikacji T11

Metoda: `grep` po `backend/` + definicje w [`migrations_admin.py`](../../backend/app/migrations_admin.py) (stan na **2026-05-04**).

| Obszar | Potrzeba mechaniczna | Czy jest kolumna / tabela? | Uwagi | **T11** |
|--------|----------------------|----------------------------|--------|---------|
| Broń / magia ([S1]) | Magia: cel vs **AOE**, szkoła / zasięg | **`targeting`**, **`aoe_radius_m`**, **`magic_school`** — **[S12]** w specyfikacji | Mapa/siatka — **[S19]** (poza MVP silnika) | **Częściowo (T22):** kolumny istnieją w `game_config_weapons` + admin CRUD/legacy UI; nadal bez solvera mapy (zgodnie z [S19]) |
| Umiejętności ([S1]) | **Dwuręczność** + modyfikatory | `game_config_skills` + arkusz | Klucze vs `dice` | **Zgodne (T16):** seed `two_handed` + runtime bonus/kara przy broni 2H |
| Umiejętności (**[S4]** / **[S10]**–**[S10e]**) | XP, koszty, magazyn | meta `xp_skill_rank_costs`, granty, `xp_award` na wrogach | **`game_config_xp_rewards`** (**[S10e]** / **T12**) | **Zgodne:** tier fallback przy `xp_award=0`; grant MG z `reward_key`; seed + admin GET/PATCH |
| Cechy bazowe (**[S10a]** / **[S3]**) | Podnoszenie statu za XP | meta **`xp_stat_point_costs`**, **`xp_stat_value_ceiling`**; `sheet_json.stats` | Klucz musi istnieć w **`game_config_stats`** | **Zgodne (T21):** `POST /api/characters/{id}/xp/spend-stat`; koszt = przejście **do** wartości N (JSON jak dla rang skill) |
| Kampania / LLM (**[S11]**…) | Plan, rollup, scena | `campaigns.gm_plan_json`; `campaign_ai_summaries` (+ `audience`); **POST** `…/gm-plan/advance-scene` w [`campaigns.py`](../../backend/app/api/campaigns.py) | SoT tur: `campaign_turns`; cooldown rollupu w meta | **Zgodne po T20:** W1 plan MG + rollup + advance scene są w runtime, a T20 dodał heurystykę dywergencji gracza i adminowy UI/endpointy do edycji `gm_plan_json` |
| Kampania — **W2** (**[S11b]**) | Kolejka beatów (`planned` / `active` / …) | Brak tabeli **`campaign_story_beats`** | **T14 (2026-05-04):** W1 wystarcza MVP — [`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md) | **Świadomie odłożone** — bez migracji w tej iteracji |
| Przedmioty | Efekty JSON vs płaskie pola | `game_config_items`: kanoniczne **`effect_json`**; legacy `effect_type` / `effect_*` usunięte z tabeli po T25 | Jeden schemat **[S13]** | **Zgodne po T25:** treść z legacy consumabli została przeniesiona do `effect_json`, snapshot/import dry-run przechodzi na `.61`, a runtime/admin API utrzymują tylko warstwę kompatybilności dla starszych klientów |
| Przedmioty | AC z pancerza | `ac_bonus` w `game_config_items` | Hit locations — przyszłość | **Zgodne** (kolumna w migracji) |
| Czary | vs bronie | `weapon_type` (m.in. `spell`), bronie jako rekordy | Brak `targeting` / `magic_school` w DB | **Częściowo:** czar jako broń — tak; runtime ataku `spell_attack` spięty w **T16**; pola **[S12]** — nadal nie |
| Przedmioty | Klasy / magia | `allowed_classes`; magia — **[S2]** w JSON | — | **Zgodne** (kolumna + kierunek JSON) |
| Wrogowie (**[S14]**) | **`skills_json`**, sparse jak PC | `game_config_enemies.skills_json` (nullable) + zapis/odczyt w admin CRUD | `xp_award`, walka podstawowa | **Częściowo (T23):** kolumna + API/UI + testy są; runtime walki zapisuje mapę skilli w stanie wroga jako przygotowanie pod pełne formuły konfrontacji z **T30** |
| Warunki ([**S6**](../04_decisions_log.md)) | Wspólny JSON z przedmiotami | `game_config_conditions.effect_json` NOT NULL | Schemat § **[S13]** / walidator | **Zgodne (T17):** create/update + import walidują `schema_version`, `effect_category` i `effects[]` wg wspólnego walidatora |
| Warunki — typy (**[S6]** §2) | `effects[]`, enum `type` | W dok / §7 spec | Implementacja iteracyjna | **Częściowo po T18:** runtime wspiera już `heal_hp`, legacy `restore_mana`, `apply_condition`, `remove_condition`, `narrative_only` przy użyciu consumabli; `periodic_save` / `block_action` nadal czekają na obsługę turową |
| Konsumable | Jedna ścieżka `item_key` | **`game_config_consumables`** nadal istnieje; dual z `game_config_items` + migracja seed z consumables | Loot FK `consumable_key` | **Częściowo po T18:** shop, loot grant i claim walki używają kanonicznie `item_key`; legacy `game_config_consumables` / `consumable_key` zostały jako fallback kompatybilności dla starszych danych |
| DC (**[S5]** / **[S9]**) | Klucz → liczba | [`dice.py`](../../backend/app/services/dice.py): `resolve_dc_for_roll`; `game_config_dc` | — | **Zgodne** |
| Umiejętności (**[S4b]**) | `linked_stat` z DB | `skill_linked_stat_for_test`, runtime config | Aliasy `melee_attack`↔`attack` | **Zgodne** |
| Umiejętności (**[S4]**) | `rank_ceiling` vs ranga | Kolumna w skills + logika awansu | — | **Do weryfikacji** przy API awansu (nieblokujące dla T11) |
| Broń / rzuty (**[S1]**) | `weapon_type` vs atak | `combat_service` / `dice` | Macierz **[S1]** | **Zgodne (T16):** runtime wybiera `melee_attack` / `ranged_attack` / `spell_attack` z broni i respektuje finesse / 2H |
| Import (**[S7]**) | Pełny INSERT vs wąski | [`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py): `import_catalog_snapshot` (dynamiczny), `import_config` (węższy) | Ryzyko ucięcia pól przy złym torze | **Zgodne po T26:** API/UI zwracają jawne ostrzeżenia przy `import_config`, panel Game Design robi dry-run snapshotu przed commitem, a realny import tworzy automatyczny backup DB z retencją (`30 dni`, min. `3` starsze, max `10`) |

*(Nowe luki dopisywać osobnym wierszem z datą.)*

---

## Odnośniki

- Agenda: [Sesja 6b](03_discussion_agenda.md#sesja-6b--luki-w-kolumnach-przedmioty-umiejętności-czary).
