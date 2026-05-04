# Luki i nadmiary w schemacie — przedmioty, umiejętności, czary

**Status:** **T11 (2026-05-04)** — wiersze poniżej **zsynchronizowane** z repozytorium (`migrations_admin.py` + wyszukiwanie w `backend/`). Nierozwiązane pozycje są **jawnie** oznaczone jako otwarte / backlog (T12, T16–T19) zamiast „cichych” braków. Uchwały: [`04_decisions_log.md`](04_decisions_log.md) sekcja **[AUDIT]** (zamknięta). Źródła historyczne: [`01_schema_inventory.md`](01_schema_inventory.md), [`02_code_usage_matrix.md`](02_code_usage_matrix.md). **Projekt pod przegląd:** [`07_extended_design_spec.md`](07_extended_design_spec.md); **[S12]–[S20]**. **Zasada [S6] §2:** stany złożone w **parametrycznym JSON**; unikać kolumny SQL na każdy wariant.

## Cel

Wypisać:

- **Braki:** czego **nie da się** zapisać w bazie przy planowanych mechanikach.
- **Nadmiary:** które kolumny są **nieużywane** albo tylko „opis bez liczenia”.

## Tabela — stan po weryfikacji T11

Metoda: `grep` po `backend/` + definicje w [`migrations_admin.py`](../../backend/app/migrations_admin.py) (stan na **2026-05-04**).

| Obszar | Potrzeba mechaniczna | Czy jest kolumna / tabela? | Uwagi | **T11** |
|--------|----------------------|----------------------------|--------|---------|
| Broń / magia ([S1]) | Magia: cel vs **AOE**, szkoła / zasięg | **`targeting`**, **`aoe_radius_m`**, **`magic_school`** — **[S12]** w specyfikacji | Mapa/siatka — **[S19]** (poza MVP silnika) | **Otwarte:** brak tych kolumn w `game_config_weapons`; runtime T16 domknął `weapon_type ↔ attack`, ale schema **[S12]** nadal czeka na osobną migrację |
| Umiejętności ([S1]) | **Dwuręczność** + modyfikatory | `game_config_skills` + arkusz | Klucze vs `dice` | **Zgodne (T16):** seed `two_handed` + runtime bonus/kara przy broni 2H |
| Umiejętności (**[S4]** / **[S10]**–**[S10e]**) | XP, koszty, magazyn | meta `xp_skill_rank_costs`, granty, `xp_award` na wrogach | **`game_config_xp_rewards`** (**[S10e]** / **T12**) | **Zgodne:** tier fallback przy `xp_award=0`; grant MG z `reward_key`; seed + admin GET/PATCH |
| Kampania / LLM (**[S11]**…) | Plan, rollup, scena | `campaigns.gm_plan_json`; `campaign_ai_summaries` (+ `audience`); **POST** `…/gm-plan/advance-scene` w [`campaigns.py`](../../backend/app/api/campaigns.py) | SoT tur: `campaign_turns`; cooldown rollupu w meta | **Zgodne z kodem** (funkcje MVP wdrożone) |
| Kampania — **W2** (**[S11b]**) | Kolejka beatów (`planned` / `active` / …) | Brak tabeli **`campaign_story_beats`** | **T14 (2026-05-04):** W1 wystarcza MVP — [`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md) | **Świadomie odłożone** — bez migracji w tej iteracji |
| Przedmioty | Efekty JSON vs płaskie pola | `game_config_items`: **`effect_json`** + jednocześnie kolumny `effect_type` / `effect_*` (migracje 8H) | Docelowo jeden schemat **[S13]** | **Częściowo po T17:** admin create/update + import egzekwują już schemat `effect_json` v0; dual danych (`effect_*` + JSON) nadal istnieje do migracji treści / runtime |
| Przedmioty | AC z pancerza | `ac_bonus` w `game_config_items` | Hit locations — przyszłość | **Zgodne** (kolumna w migracji) |
| Czary | vs bronie | `weapon_type` (m.in. `spell`), bronie jako rekordy | Brak `targeting` / `magic_school` w DB | **Częściowo:** czar jako broń — tak; runtime ataku `spell_attack` spięty w **T16**; pola **[S12]** — nadal nie |
| Przedmioty | Klasy / magia | `allowed_classes`; magia — **[S2]** w JSON | — | **Zgodne** (kolumna + kierunek JSON) |
| Wrogowie (**[S14]**) | **`skills_json`**, sparse jak PC | W migracjach **`game_config_enemies`** — **bez** `skills_json` | `xp_award`, walka podstawowa | **Otwarte:** kolumna nie istnieje w repo → migracja + kod (iteracja) |
| Warunki ([**S6**](../04_decisions_log.md)) | Wspólny JSON z przedmiotami | `game_config_conditions.effect_json` NOT NULL | Schemat § **[S13]** / walidator | **Zgodne (T17):** create/update + import walidują `schema_version`, `effect_category` i `effects[]` wg wspólnego walidatora |
| Warunki — typy (**[S6]** §2) | `effects[]`, enum `type` | W dok / §7 spec | Implementacja iteracyjna | **Częściowo po T17:** egzekwowany startowy enum (`periodic_save`, `static_stat_modifier`, `heal_hp`, `apply_condition`, `remove_condition`, `block_action`, `narrative_only`); kolejne typy i runtime będą rozszerzane iteracyjnie |
| Konsumable | Jedna ścieżka `item_key` | **`game_config_consumables`** nadal istnieje; dual z `game_config_items` + migracja seed z consumables | Loot FK `consumable_key` | **Otwarte:** ujednolicenie → **T18** |
| DC (**[S5]** / **[S9]**) | Klucz → liczba | [`dice.py`](../../backend/app/services/dice.py): `resolve_dc_for_roll`; `game_config_dc` | — | **Zgodne** |
| Umiejętności (**[S4b]**) | `linked_stat` z DB | `skill_linked_stat_for_test`, runtime config | Aliasy `melee_attack`↔`attack` | **Zgodne** |
| Umiejętności (**[S4]**) | `rank_ceiling` vs ranga | Kolumna w skills + logika awansu | — | **Do weryfikacji** przy API awansu (nieblokujące dla T11) |
| Broń / rzuty (**[S1]**) | `weapon_type` vs atak | `combat_service` / `dice` | Macierz **[S1]** | **Zgodne (T16):** runtime wybiera `melee_attack` / `ranged_attack` / `spell_attack` z broni i respektuje finesse / 2H |
| Import (**[S7]**) | Pełny INSERT vs wąski | [`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py): `import_catalog_snapshot` (dynamiczny), `import_config` (węższy) | Ryzyko ucięcia pól przy złym torze | **Świadome:** dokumentacja ostrzega; operator używa snapshotu przy pełnym katalogu |

*(Nowe luki dopisywać osobnym wierszem z datą.)*

---

## Odnośniki

- Agenda: [Sesja 6b](03_discussion_agenda.md#sesja-6b--luki-w-kolumnach-przedmioty-umiejętności-czary).
