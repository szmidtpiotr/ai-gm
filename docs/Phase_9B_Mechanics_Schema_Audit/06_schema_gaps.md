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
| Broń / magia ([S1]) | Magia: cel vs **AOE**, szkoła / zasięg | **`targeting`**, **`aoe_radius_m`**, **`magic_school`** — **[S12]** w specyfikacji | Mapa/siatka — **[S19]** (poza MVP silnika) | **Otwarte:** brak tych kolumn w `game_config_weapons` w migracjach → **T16** |
| Umiejętności ([S1]) | **Dwuręczność** + modyfikatory | `game_config_skills` + arkusz | Klucze vs `dice` | **Częściowo:** skills w DB + rzuty — spójność kluczy do monitorowania przy rozwoju walki |
| Umiejętności (**[S4]** / **[S10]**–**[S10e]**) | XP, koszty, magazyn | meta `xp_skill_rank_costs`, granty, `xp_award` na wrogach | **`game_config_xp_rewards`** (**[S10e]** / **T12**) | **Zgodne:** tier fallback przy `xp_award=0`; grant MG z `reward_key`; seed + admin GET/PATCH |
| Kampania / LLM (**[S11]**…) | Plan, rollup, scena | `campaigns.gm_plan_json`; `campaign_ai_summaries` (+ `audience`); **POST** `…/gm-plan/advance-scene` w [`campaigns.py`](../../backend/app/api/campaigns.py) | SoT tur: `campaign_turns`; cooldown rollupu w meta | **Zgodne z kodem** (funkcje MVP wdrożone) |
| Przedmioty | Efekty JSON vs płaskie pola | `game_config_items`: **`effect_json`** + jednocześnie kolumny `effect_type` / `effect_*` (migracje 8H) | Docelowo jeden schemat **[S13]** | **Częściowo:** dane nadal dualne do migracji treści → **T17** |
| Przedmioty | AC z pancerza | `ac_bonus` w `game_config_items` | Hit locations — przyszłość | **Zgodne** (kolumna w migracji) |
| Czary | vs bronie | `weapon_type` (m.in. `spell`), bronie jako rekordy | Brak `targeting` / `magic_school` w DB | **Częściowo:** czar jako broń — tak; pola **[S12]** — nie → **T16** |
| Przedmioty | Klasy / magia | `allowed_classes`; magia — **[S2]** w JSON | — | **Zgodne** (kolumna + kierunek JSON) |
| Wrogowie (**[S14]**) | **`skills_json`**, sparse jak PC | W migracjach **`game_config_enemies`** — **bez** `skills_json` | `xp_award`, walka podstawowa | **Otwarte:** kolumna nie istnieje w repo → migracja + kod (iteracja) |
| Warunki ([**S6**](../04_decisions_log.md)) | Wspólny JSON z przedmiotami | `game_config_conditions.effect_json` NOT NULL | Schemat § **[S13]** / walidator | **Częściowo:** pole jest; walidator pełny → **T17** |
| Warunki — typy (**[S6]** §2) | `effects[]`, enum `type` | W dok / §7 spec | Implementacja iteracyjna | **Otwarte** (dopóki walidator nie egzekwuje pełnego zestawu) |
| Konsumable | Jedna ścieżka `item_key` | **`game_config_consumables`** nadal istnieje; dual z `game_config_items` + migracja seed z consumables | Loot FK `consumable_key` | **Otwarte:** ujednolicenie → **T18** |
| DC (**[S5]** / **[S9]**) | Klucz → liczba | [`dice.py`](../../backend/app/services/dice.py): `resolve_dc_for_roll`; `game_config_dc` | — | **Zgodne** |
| Umiejętności (**[S4b]**) | `linked_stat` z DB | `skill_linked_stat_for_test`, runtime config | Aliasy `melee_attack`↔`attack` | **Zgodne** |
| Umiejętności (**[S4]**) | `rank_ceiling` vs ranga | Kolumna w skills + logika awansu | — | **Do weryfikacji** przy API awansu (nieblokujące dla T11) |
| Broń / rzuty (**[S1]**) | `weapon_type` vs atak | `combat_service` / `dice` | Macierz **[S1]** | **Częściowo** — domknięcie taktyki → **T16** |
| Import (**[S7]**) | Pełny INSERT vs wąski | [`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py): `import_catalog_snapshot` (dynamiczny), `import_config` (węższy) | Ryzyko ucięcia pól przy złym torze | **Świadome:** dokumentacja ostrzega; operator używa snapshotu przy pełnym katalogu |

*(Nowe luki dopisywać osobnym wierszem z datą.)*

---

## Odnośniki

- Agenda: [Sesja 6b](03_discussion_agenda.md#sesja-6b--luki-w-kolumnach-przedmioty-umiejętności-czary).
